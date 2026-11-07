import io
import math
import os
import re
import json
import logging
import secrets
import time
import uuid
import zipfile
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger("app")

# Configure local models directory before importing rembg
BASE_DIR = Path(__file__).resolve().parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR = BASE_DIR / "static" / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
SAMPLES_DIR = BASE_DIR / "static" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
BLOG_IMAGES_DIR = BASE_DIR / "static" / "blog"
BLOG_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
AVATARS_DIR = BASE_DIR / "static" / "avatars"
AVATARS_DIR.mkdir(parents=True, exist_ok=True)
os.environ["U2NET_HOME"] = str(MODELS_DIR)

from PIL import Image, ImageColor

# Enforce image decompression ceiling to prevent decompression bomb DOS attacks
Image.MAX_IMAGE_PIXELS = 50_000_000
MAX_IMAGE_DIMENSION = 5000
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Header, Depends, Request
from fastapi.responses import Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
import rembg
from rembg import remove, new_session
from rembg.sessions.base import BaseSession

from database import db_manager
import image_tools
from email_service import send_verification_email, test_smtp_connection, get_smtp_config

app = FastAPI(
    title="PngLike - 9-in-1 AI Image Suite & Background Remover",
    description="High-performance 9-in-1 neural image suite & background removal platform powered by ONNX Runtime",
    version="3.0.0",
)

# --------------------------------------------------------
# PRODUCTION SECURITY: CORS, SECURITY HEADERS & UPLOAD LIMITS
# --------------------------------------------------------
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "https://pnglike.com").rstrip("/")
raw_allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in raw_allowed_origins.split(",")
    if origin.strip()
] or [
    SITE_BASE_URL,
    "http://127.0.0.1:7860",
    "http://localhost:7860",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_BYTES", 52_428_800))  # 50 MB default


@app.middleware("http")
async def security_and_limit_middleware(request: Request, call_next):
    """Enforce request body size limits and inject OWASP security headers."""
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_UPLOAD_SIZE:
                return Response(
                    content='{"detail": "Payload too large. Maximum upload size is 50 MB."}',
                    status_code=413,
                    media_type="application/json",
                )
        except ValueError:
            pass

    response = await call_next(request)

    # Security Headers (OWASP Level 2 Hardening)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), unload=*"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net https://unpkg.com https://cdn.tailwindcss.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net data:; "
        "img-src 'self' data: blob: https:; "
        "connect-src 'self' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net https://fonts.googleapis.com https://fonts.gstatic.com; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none';"
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# In-memory ONNX session cache for fast inference
_session_cache: Dict[str, BaseSession] = {}

# In-memory token stores (acting as fast L1 cache; backed by database sessions)
_admin_tokens: Dict[str, Dict[str, Any]] = {}
_user_tokens: Dict[str, int] = {}

# In-memory sliding-window IP rate limiters
_reg_ip_attempts: Dict[str, List[float]] = {}
_verify_ip_attempts: Dict[str, List[float]] = {}
_login_ip_attempts: Dict[str, List[float]] = {}
_admin_login_ip_attempts: Dict[str, List[float]] = {}
_contact_ip_attempts: Dict[str, List[float]] = {}


def check_rate_limit(attempts_dict: Dict[str, List[float]], client_ip: str, max_attempts: int, window_seconds: int) -> bool:
    """Sliding-window IP rate limiter."""
    now = time.time()
    if client_ip not in attempts_dict:
        attempts_dict[client_ip] = [now]
        return True
    attempts_dict[client_ip] = [t for t in attempts_dict[client_ip] if now - t < window_seconds]
    if len(attempts_dict[client_ip]) >= max_attempts:
        return False
    attempts_dict[client_ip].append(now)
    return True


# --------------------------------------------------------
# PYDANTIC SCHEMAS
# --------------------------------------------------------
class MySQLConfigPayload(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = ""
    database: str = "rembg_studio"


class PresetCreatePayload(BaseModel):
    name: str
    model_used: str = "u2net"
    alpha_matting: bool = False
    af_threshold: int = 240
    ab_threshold: int = 10
    ae_size: int = 10
    post_process_mask: bool = False
    bg_mode: str = "transparent"
    bg_value: Optional[str] = None
    export_format: str = "png"


class AdminLoginPayload(BaseModel):
    username: str
    password: str


class AdminCredentialsPayload(BaseModel):
    new_username: str
    new_password: Optional[str] = None
    current_password: Optional[str] = None


class AdminProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    designation: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    avatar_color: Optional[str] = None
    timezone_pref: Optional[str] = None
    email_notifications: Optional[bool] = None
    security_alerts: Optional[bool] = None


class AdminPasswordChangePayload(BaseModel):
    current_password: str
    new_password: str


class SiteSettingsPayload(BaseModel):
    site_title: Optional[str] = None
    site_tagline: Optional[str] = None
    site_badge: Optional[str] = None
    hero_title: Optional[str] = None
    hero_highlight: Optional[str] = None
    hero_subtitle: Optional[str] = None
    announcement_enabled: Optional[bool] = None
    announcement_text: Optional[str] = None
    footer_text: Optional[str] = None
    default_model: Optional[str] = None
    enabled_models: Optional[List[str]] = None
    default_tool: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    enable_batch_mode: Optional[bool] = None
    enable_history_tab: Optional[bool] = None
    enable_alpha_matting: Optional[bool] = None
    enable_custom_backdrop: Optional[bool] = None
    max_upload_mb: Optional[int] = None
    max_batch_files: Optional[int] = None
    maintenance_mode: Optional[bool] = None
    maintenance_message: Optional[str] = None


class SampleUpdatePayload(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None


class BlogPostCreatePayload(BaseModel):
    title: str
    slug: Optional[str] = None
    excerpt: str
    content: str
    category: str = "AI Tutorials"
    tags: str = ""
    cover_image: Optional[str] = None
    author: str = "Div Sri"
    read_time_minutes: Optional[int] = None
    is_published: bool = True
    is_featured: bool = False
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class BlogPostUpdatePayload(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    cover_image: Optional[str] = None
    author: Optional[str] = None
    read_time_minutes: Optional[int] = None
    is_published: Optional[bool] = None
    is_featured: Optional[bool] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None


class UserRegisterPayload(BaseModel):
    username: str
    email: str
    password: str
    full_name: str = ""
    website: Optional[str] = None  # Hidden anti-bot honeypot field


class UserLoginPayload(BaseModel):
    identifier: str
    password: str


class UserProfileUpdatePayload(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    avatar_color: Optional[str] = None
    new_password: Optional[str] = None
    current_password: Optional[str] = None
    bio: Optional[str] = None
    phone: Optional[str] = None
    country: Optional[str] = None
    preferred_format: Optional[str] = None
    dark_mode_pref: Optional[str] = None


class UserDeleteAccountPayload(BaseModel):
    password: str
    confirm_phrase: str


class UserVerifyCodePayload(BaseModel):
    email: str
    code: str


class UserVerifyTokenPayload(BaseModel):
    token: str


class UserResendVerificationPayload(BaseModel):
    email: str


class AdminUserUpdatePayload(BaseModel):
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None
    plan_tier: Optional[str] = None


class SmtpConfigPayload(BaseModel):
    smtp_enabled: bool = True
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: Optional[str] = None
    smtp_from_name: str = "PngLike AI Studio"
    smtp_from_email: str = ""
    smtp_use_tls: bool = True


class SmtpTestPayload(BaseModel):
    host: str = "smtp.gmail.com"
    port: int = 587
    user: str
    password: str
    use_tls: bool = True
    test_recipient: Optional[str] = None


class ContactMessagePayload(BaseModel):
    name: str
    email: str
    subject: str
    message: str
    website: Optional[str] = None  # Anti-bot honeypot field


raw_trusted_proxies = os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,localhost")
TRUSTED_PROXIES = {p.strip() for p in raw_trusted_proxies.split(",") if p.strip()}


def get_client_ip(request: Request) -> str:
    """Extract client IP address safely, only trusting X-Forwarded-For if client peer is a trusted proxy."""
    peer_ip = request.client.host if request.client else "127.0.0.1"
    if peer_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return peer_ip


# --------------------------------------------------------
# ADMIN & USER AUTH DEPENDENCIES
# --------------------------------------------------------
async def require_admin(x_admin_token: Optional[str] = Header(None)) -> Dict[str, Any]:
    """Validate the X-Admin-Token header for protected /api/admin/* endpoints."""
    if not x_admin_token or not x_admin_token.strip():
        raise HTTPException(status_code=401, detail="Unauthorized: Admin login required.")

    # 1. Check persistent database session
    admin = await run_in_threadpool(db_manager.get_admin_by_session_token, x_admin_token)
    if admin:
        return admin

    # 2. Check in-memory token fallback ONLY if database session engine is offline
    if not db_manager.is_mysql_connected and db_manager.active_dialect != "MySQL (Offline Fallback)":
        if x_admin_token in _admin_tokens:
            return _admin_tokens[x_admin_token]

    raise HTTPException(status_code=401, detail="Unauthorized: Admin login required or session expired.")


async def get_optional_user(
    x_user_token: Optional[str] = Header(None),
) -> Optional[Dict[str, Any]]:
    """Resolve optional logged-in user via X-User-Token session header."""
    if not x_user_token or not x_user_token.strip():
        return None

    # 1. Check persistent database session
    user = await run_in_threadpool(db_manager.get_user_by_session_token, x_user_token)
    if user:
        return user

    # 2. Check in-memory token fallback ONLY if database session engine is offline
    if not db_manager.is_mysql_connected and db_manager.active_dialect != "MySQL (Offline Fallback)":
        if x_user_token in _user_tokens:
            uid = _user_tokens[x_user_token]
            user = await run_in_threadpool(db_manager.get_user_by_id, uid)
            if user:
                return user
    return None


async def require_user(
    user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Require an authenticated user account for /api/user/* endpoints."""
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized: User login required.")
    return user


# --------------------------------------------------------
# CORE AI HELPERS
# --------------------------------------------------------
def get_session(model_name: str = "u2net") -> BaseSession:
    """Retrieve or initialize an ONNX inference session."""
    if model_name not in _session_cache:
        try:
            print(f"[AI] Initializing session for model: '{model_name}'...")
            _session_cache[model_name] = new_session(model_name)
            print(f"[AI] Model '{model_name}' loaded successfully.")
        except Exception as e:
            print(f"[AI Warning] Failed to load '{model_name}': {e}. Falling back to 'u2netp'...")
            if "u2netp" not in _session_cache:
                _session_cache["u2netp"] = new_session("u2netp")
            return _session_cache["u2netp"]
    return _session_cache[model_name]


def parse_color(color_str: Optional[str]) -> Optional[tuple]:
    """Parse hex, rgb, or css color string into RGBA tuple (0-255)."""
    if not color_str or color_str.strip().lower() in ("", "transparent", "none"):
        return None
    color_str = color_str.strip()
    try:
        if color_str.startswith("#"):
            rgb = ImageColor.getrgb(color_str)
            if len(rgb) == 3:
                return (rgb[0], rgb[1], rgb[2], 255)
            return rgb
        elif color_str.startswith("rgba"):
            parts = color_str.replace("rgba(", "").replace(")", "").split(",")
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            a = int(float(parts[3]) * 255)
            return (r, g, b, a)
        else:
            rgb = ImageColor.getrgb(color_str)
            return (rgb[0], rgb[1], rgb[2], 255) if len(rgb) == 3 else rgb
    except Exception:
        return None


def _process_single_image(
    image_bytes: bytes,
    model: str,
    alpha_matting: bool,
    af: int,
    ab: int,
    ae: int,
    only_mask: bool,
    post_process_mask: bool,
    bgcolor_tuple: Optional[tuple],
    out_format: str,
) -> tuple[bytes, str, int, int]:
    """Synchronous worker function for CPU-bound ONNX inference and image encoding."""
    input_image = Image.open(io.BytesIO(image_bytes))
    orig_w, orig_h = input_image.size
    if orig_w > MAX_IMAGE_DIMENSION or orig_h > MAX_IMAGE_DIMENSION:
        raise ValueError(
            f"Image dimensions ({orig_w}x{orig_h}) exceed maximum allowable size ({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION}px)."
        )

    session = get_session(model)

    kwargs = {
        "session": session,
        "alpha_matting": alpha_matting,
        "alpha_matting_foreground_threshold": af,
        "alpha_matting_background_threshold": ab,
        "alpha_matting_erode_size": ae,
        "only_mask": only_mask,
        "post_process_mask": post_process_mask,
    }
    if bgcolor_tuple:
        kwargs["bgcolor"] = bgcolor_tuple

    output_image: Image.Image = remove(input_image, **kwargs)

    buf = io.BytesIO()
    out_fmt = out_format.upper()
    if out_fmt == "JPG":
        out_fmt = "JPEG"

    if out_fmt == "JPEG":
        if output_image.mode == "RGBA":
            fill_rgb = bgcolor_tuple[:3] if bgcolor_tuple else (255, 255, 255)
            rgb_bg = Image.new("RGB", output_image.size, fill_rgb)
            rgb_bg.paste(output_image, mask=output_image.split()[3])
            output_image = rgb_bg
        elif output_image.mode != "RGB":
            output_image = output_image.convert("RGB")
        output_image.save(buf, format="JPEG", quality=95)
        media_type = "image/jpeg"
    elif out_fmt == "WEBP":
        output_image.save(buf, format="WEBP", quality=95)
        media_type = "image/webp"
    else:
        output_image.save(buf, format="PNG")
        media_type = "image/png"

    return buf.getvalue(), media_type, orig_w, orig_h


def _get_model_catalog() -> List[Dict[str, Any]]:
    available_files = {f.stem for f in MODELS_DIR.glob("*.onnx")} if MODELS_DIR.exists() else set()
    loaded_in_ram = set(_session_cache.keys())
    return [
        {
            "id": "u2net",
            "name": "U2-Net (High Quality)",
            "description": "Pre-trained deep learning model for general use cases. Best edge quality and boundary accuracy.",
            "is_downloaded": "u2net" in available_files,
            "is_loaded": "u2net" in loaded_in_ram,
            "recommended": True,
            "category": "General",
            "size": "~176 MB",
        },
        {
            "id": "u2netp",
            "name": "U2-Netp (Fast / Lightweight)",
            "description": "Lightweight variant of U2-Net. Ultra-fast inference with minimal memory usage.",
            "is_downloaded": "u2netp" in available_files,
            "is_loaded": "u2netp" in loaded_in_ram,
            "recommended": False,
            "category": "Speed",
            "size": "~4.6 MB",
        },
        {
            "id": "u2net_human_seg",
            "name": "U2-Net Human Segmentation",
            "description": "Specially trained for human portrait cutouts, clothes, and hair precision.",
            "is_downloaded": "u2net_human_seg" in available_files,
            "is_loaded": "u2net_human_seg" in loaded_in_ram,
            "recommended": False,
            "category": "Portrait",
            "size": "~176 MB",
        },
        {
            "id": "isnet-general-use",
            "name": "IS-Net General Use",
            "description": "High-accuracy salient object segmentation with sharp contours.",
            "is_downloaded": "isnet-general-use" in available_files,
            "is_loaded": "isnet-general-use" in loaded_in_ram,
            "recommended": False,
            "category": "General",
            "size": "~174 MB",
        },
        {
            "id": "isnet-anime",
            "name": "IS-Net Anime / Illustration",
            "description": "Optimized specifically for anime characters, illustrations, and 2D artwork.",
            "is_downloaded": "isnet-anime" in available_files,
            "is_loaded": "isnet-anime" in loaded_in_ram,
            "recommended": False,
            "category": "Anime",
            "size": "~174 MB",
        },
        {
            "id": "silueta",
            "name": "Silueta (Compact)",
            "description": "Compact footprint model for rapid object cutouts.",
            "is_downloaded": "silueta" in available_files,
            "is_loaded": "silueta" in loaded_in_ram,
            "recommended": False,
            "category": "Compact",
            "size": "~43 MB",
        },
    ]


def _get_tools_catalog() -> List[Dict[str, Any]]:
    """Return metadata for all 9 IMAGE tools with Free tools first and Background Remover as default."""
    return [
        {
            "id": "bg-remover",
            "name": "Background Remover",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Free • Default",
            "is_free": True,
            "description": "Instant AI background cutout with hair-level alpha refinement, mask preview, and studio backdrop replacement.",
        },
        {
            "id": "image-editor",
            "name": "Image Editor",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Free Studio",
            "is_free": True,
            "description": "Color grading, exposure, contrast, saturation, warmth, sharpness, rotation, flip, and aspect cropping.",
        },
        {
            "id": "skin-enhancer",
            "name": "Skin Enhancer",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Free Portrait",
            "is_free": True,
            "description": "YCrCb chrominance-guided skin detection with bilateral smoothing, studio radiance glow, and eye/hair crispness.",
        },
        {
            "id": "image-upscaler",
            "name": "Image Upscaler",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro Super-Res",
            "is_free": False,
            "description": "2x and 4x Lanczos-4 super-resolution upscaling with bilateral denoising and unsharp edge enhancement.",
        },
        {
            "id": "image-extender",
            "name": "Image Extender",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro Outpaint",
            "is_free": False,
            "description": "Expand canvas to 16:9, 9:16, 1:1, 4:3, or 21:9 using Telea Navier-Stokes outpainting and reflection.",
        },
        {
            "id": "variations",
            "name": "Variations",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro Restyle",
            "is_free": False,
            "description": "Generate artistic style variations: Cyberpunk, Watercolor, Oil Painting, Sketch, Pop Art, Anime, Noir, and Warm.",
        },
        {
            "id": "cinematic-shot",
            "name": "Cinematic Shot",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro Anamorphic",
            "is_free": False,
            "description": "AI depth-of-field bokeh, Teal & Orange / Bleach Bypass color grading, anamorphic lens flare, and 2.39:1 letterbox.",
        },
        {
            "id": "relight",
            "name": "Relight",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro 3D Light",
            "is_free": False,
            "description": "AI subject segmentation with surface-normal estimation, directional 3D point lighting, neon split, and rim glow.",
        },
        {
            "id": "change-camera",
            "name": "Change Camera",
            "category": "IMAGE",
            "requires_image": True,
            "badge": "Pro Perspective",
            "is_free": False,
            "description": "3D homography camera angle tilt/pan/dutch-roll and optical lens distortion (Wide, Telephoto, Fisheye, Dolly).",
        },
    ]


# --------------------------------------------------------
# PUBLIC FRONTEND ENDPOINTS
# --------------------------------------------------------
@app.get("/api/site-config")
async def get_public_site_config():
    """Return dynamic frontend configuration managed by the Admin Dashboard in MySQL."""
    settings = await run_in_threadpool(db_manager.get_site_settings)
    samples = await run_in_threadpool(db_manager.list_samples, True)
    presets = await run_in_threadpool(db_manager.list_presets)
    all_models = _get_model_catalog()
    enabled_ids = set(settings.get("enabled_models", []))
    enabled_models = [m for m in all_models if m["id"] in enabled_ids] or all_models

    all_tools = _get_tools_catalog()
    enabled_tool_ids = set(settings.get("enabled_tools", []))
    for t in all_tools:
        t["is_enabled"] = t["id"] in enabled_tool_ids if enabled_tool_ids else True
    enabled_tools = [t for t in all_tools if t["is_enabled"]] or all_tools

    return {
        "settings": settings,
        "samples": samples,
        "presets": presets,
        "models": enabled_models,
        "tools": enabled_tools,
        "all_tools": all_tools,
    }


@app.get("/api/tools")
async def list_image_tools():
    """Return all 10 IMAGE tools and their active status."""
    settings = await run_in_threadpool(db_manager.get_site_settings)
    all_tools = _get_tools_catalog()
    enabled_tool_ids = set(settings.get("enabled_tools", []))
    for t in all_tools:
        t["is_enabled"] = t["id"] in enabled_tool_ids if enabled_tool_ids else True
    return {
        "tools": [t for t in all_tools if t["is_enabled"]] or all_tools,
        "all_tools": all_tools,
        "default_tool": settings.get("default_tool", "bg-remover"),
    }


@app.get("/api/status")
async def get_status():
    """System health, MySQL database status, and available models."""
    available_models = [f.stem for f in MODELS_DIR.glob("*.onnx")] if MODELS_DIR.exists() else []
    analytics = await run_in_threadpool(db_manager.get_analytics)
    settings = await run_in_threadpool(db_manager.get_site_settings)

    db_status_text = "connected" if db_manager.is_mysql_connected else "offline_fallback"
    return {
        "status": "online",
        "rembg_version": rembg.__version__,
        "models_directory": str(MODELS_DIR),
        "cached_sessions": list(_session_cache.keys()),
        "downloaded_models": available_models,
        "default_model": settings.get("default_model", "u2net"),
        "settings": settings,
        "database": {
            "connected": db_manager.is_mysql_connected,
            "dialect": db_manager.active_dialect,
            "status": db_status_text,
            "total_jobs": analytics.get("total_jobs", 0),
        },
    }


@app.get("/api/admin/db/status")
@app.get("/api/db/status")
async def get_db_status(admin: Dict[str, Any] = Depends(require_admin)):
    """Detailed MySQL connection & analytics report (Protected)."""
    return await run_in_threadpool(db_manager.get_analytics)


@app.post("/api/admin/db/config")
@app.post("/api/db/config")
async def update_db_config(payload: MySQLConfigPayload, admin: Dict[str, Any] = Depends(require_admin)):
    """Update MySQL connection parameters at runtime, auto-create schema, and reconnect (Protected)."""
    return await run_in_threadpool(
        db_manager.configure_mysql,
        payload.host,
        payload.port,
        payload.user,
        payload.password,
        payload.database,
        True,
    )


@app.get("/api/history")
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    x_admin_token: Optional[str] = Header(None),
):
    """Fetch processed background removal jobs with user data isolation."""
    is_admin = False
    if x_admin_token:
        admin = await run_in_threadpool(db_manager.get_admin_by_session_token, x_admin_token)
        if admin or x_admin_token in _admin_tokens:
            is_admin = True

    if is_admin:
        return await run_in_threadpool(db_manager.list_jobs, limit, offset, search, model)

    if current_user:
        return await run_in_threadpool(
            db_manager.list_jobs_for_user,
            current_user["id"],
            limit,
            offset,
            search,
            model,
        )

    # Guest users without active session
    return {
        "jobs": [],
        "total": 0,
        "message": "Sign in to access your saved cloud gallery history.",
    }


@app.delete("/api/admin/jobs/{job_id}")
@app.delete("/api/history/{job_id}")
async def delete_history_item(
    job_id: int,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
    x_admin_token: Optional[str] = Header(None),
):
    """Delete a specific job from MySQL and remove its output image file (Protected)."""
    is_admin = False
    if x_admin_token:
        admin = await run_in_threadpool(db_manager.get_admin_by_session_token, x_admin_token)
        if admin or x_admin_token in _admin_tokens:
            is_admin = True

    if is_admin:
        deleted = await run_in_threadpool(db_manager.delete_job, job_id)
    elif current_user:
        deleted = await run_in_threadpool(db_manager.delete_user_job, current_user["id"], job_id)
    else:
        # Check if the job is unassigned/anonymous (user_id is None)
        with db_manager.get_session() as db:
            j = db.query(RemovalJob).filter(RemovalJob.id == job_id).first()
            if j and j.user_id is not None:
                raise HTTPException(status_code=401, detail="Authentication required to delete registered user records.")
            elif not j:
                raise HTTPException(status_code=404, detail="Job record not found.")
        deleted = await run_in_threadpool(db_manager.delete_job, job_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Job record not found or not owned by you.")

    out_file = OUTPUTS_DIR / deleted["output_filename"]
    if out_file.exists():
        try:
            out_file.unlink()
        except Exception:
            pass
    return {"deleted": True, "id": job_id}


@app.delete("/api/admin/jobs")
@app.delete("/api/history")
async def clear_all_history(admin: Dict[str, Any] = Depends(require_admin)):
    """Clear all job history from MySQL and remove stored output files (Admin Only)."""
    deleted_jobs = await run_in_threadpool(db_manager.clear_all_jobs)
    for job in deleted_jobs:
        out_file = OUTPUTS_DIR / job["output_filename"]
        if out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
    return {"cleared": True, "count": len(deleted_jobs)}


@app.get("/api/presets")
async def list_presets():
    """List saved Studio presets from the MySQL `preset_configs` table."""
    presets = await run_in_threadpool(db_manager.list_presets)
    return {"presets": presets}


@app.post("/api/presets")
async def save_preset(payload: PresetCreatePayload, admin: Dict[str, Any] = Depends(require_admin)):
    """Create or update a Studio preset in the MySQL `preset_configs` table (Admin Only)."""
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Preset name cannot be empty.")
    preset = await run_in_threadpool(
        db_manager.create_preset,
        name=payload.name.strip(),
        model_used=payload.model_used,
        alpha_matting=payload.alpha_matting,
        af_threshold=payload.af_threshold,
        ab_threshold=payload.ab_threshold,
        ae_size=payload.ae_size,
        post_process_mask=payload.post_process_mask,
        bg_mode=payload.bg_mode,
        bg_value=payload.bg_value,
        export_format=payload.export_format,
    )
    return {"preset": preset}


@app.delete("/api/presets/{preset_id}")
async def remove_preset(preset_id: int, admin: Dict[str, Any] = Depends(require_admin)):
    """Delete a Studio preset from MySQL (Admin Only)."""
    ok = await run_in_threadpool(db_manager.delete_preset, preset_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Preset not found.")
    return {"deleted": True, "id": preset_id}


@app.get("/api/models")
async def list_models():
    """List supported models filtered by Admin enabled models."""
    settings = await run_in_threadpool(db_manager.get_site_settings)
    enabled_ids = set(settings.get("enabled_models", []))
    catalog = _get_model_catalog()
    filtered = [m for m in catalog if m["id"] in enabled_ids] or catalog
    return {"models": filtered, "default_model": settings.get("default_model", "u2net")}


@app.get("/api/samples")
async def list_samples():
    """List active sample demo images managed in MySQL `sample_images`."""
    samples = await run_in_threadpool(db_manager.list_samples, True)
    return {"samples": samples}


@app.post("/api/remove")
async def remove_background(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form("u2net"),
    alpha_matting: bool = Form(False),
    af: int = Form(240),
    ab: int = Form(10),
    ae: int = Form(10),
    only_mask: bool = Form(False),
    post_process_mask: bool = Form(False),
    bg_color: Optional[str] = Form(None),
    format: str = Form("png"),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """
    Remove the background from an uploaded image, enforcing guest vs registered quotas,
    file size limits, and recording the job in the MySQL database.
    """
    start_time = time.perf_counter()
    settings = await run_in_threadpool(db_manager.get_site_settings)

    if settings.get("maintenance_mode"):
        raise HTTPException(status_code=503, detail=settings.get("maintenance_message", "Service under maintenance."))

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid image format.")

    try:
        image_bytes = await file.read()
        if not image_bytes:
            raise ValueError("Empty image file uploaded.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read uploaded file: {str(e)}")

    # Enforce Guest vs Registered User Quotas and Limits
    client_ip = get_client_ip(request)
    user_id = current_user["id"] if current_user else None
    try:
        quota_info = await run_in_threadpool(
            db_manager.check_user_access_quota,
            user_id,
            client_ip,
            "bg-remover",
            len(image_bytes),
        )
    except PermissionError as pe:
        status_code = 429 if "rest cooldown" in str(pe) or "limit reached" in str(pe) or "limitation reached" in str(pe) else 403
        raise HTTPException(status_code=status_code, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    bgcolor_tuple = parse_color(bg_color)
    clamped_af = max(0, min(255, af))
    clamped_ab = max(0, min(255, ab))
    clamped_ae = max(0, min(255, ae))

    try:
        out_bytes, media_type, orig_w, orig_h = await run_in_threadpool(
            _process_single_image,
            image_bytes,
            model,
            alpha_matting,
            clamped_af,
            clamped_ab,
            clamped_ae,
            only_mask,
            post_process_mask,
            bgcolor_tuple,
            format,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Background removal failed: {str(e)}")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    job_uuid = str(uuid.uuid4())
    ext = "jpg" if format.lower() in ("jpg", "jpeg") else ("webp" if format.lower() == "webp" else "png")
    orig_filename = file.filename or "uploaded_image.png"
    raw_stem = Path(orig_filename).stem
    safe_stem = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in raw_stem).strip("_") or "image"
    out_filename = f"{safe_stem}_{job_uuid[:8]}_nobg.{ext}"
    out_path = OUTPUTS_DIR / out_filename
    output_url = f"/static/outputs/{out_filename}"

    def _save_file_and_record() -> Dict[str, Any]:
        out_path.write_bytes(out_bytes)
        return db_manager.record_job(
            job_uuid=job_uuid,
            original_filename=orig_filename,
            output_filename=out_filename,
            output_url=output_url,
            model_used=model,
            alpha_matting=alpha_matting,
            af_threshold=clamped_af,
            ab_threshold=clamped_ab,
            ae_size=clamped_ae,
            only_mask=only_mask,
            post_process_mask=post_process_mask,
            bg_color=bg_color,
            output_format=ext,
            original_width=orig_w,
            original_height=orig_h,
            output_size_bytes=len(out_bytes),
            process_time_ms=elapsed_ms,
            batch_id=None,
            user_id=current_user["id"] if current_user else None,
            client_ip=client_ip,
            status="completed",
        )

    job_record = await run_in_threadpool(_save_file_and_record)

    headers = {
        "X-Process-Time-Ms": str(elapsed_ms),
        "X-Original-Width": str(orig_w),
        "X-Original-Height": str(orig_h),
        "X-Model-Used": model,
        "X-Job-Id": str(job_record["id"]),
        "X-Job-Uuid": job_uuid,
        "X-Output-Url": output_url,
        "X-User-Tier": quota_info["tier"],
        "X-RateLimit-Limit": str(quota_info["daily_limit"]),
        "X-RateLimit-Remaining": str(max(0, quota_info["remaining_today"] - 1)),
        "X-RateLimit-Reset-Timestamp": str(quota_info.get("reset_timestamp") or ""),
        "X-RateLimit-Reset-Utc": str(quota_info.get("reset_time_utc") or ""),
        "X-Server-Time-Utc": str(quota_info.get("server_time_utc") or ""),
        "Cache-Control": "no-cache",
    }
    return Response(content=out_bytes, media_type=media_type, headers=headers)


@app.post("/api/batch-remove")
async def batch_remove_background(
    request: Request,
    files: List[UploadFile] = File(...),
    model: str = Form("u2netp"),
    alpha_matting: bool = Form(False),
    post_process_mask: bool = Form(False),
    format: str = Form("png"),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """
    Process multiple images in batch, enforcing Admin settings, quota boundaries,
    and recording each job in the MySQL database.
    """
    settings = await run_in_threadpool(db_manager.get_site_settings)
    if settings.get("maintenance_mode"):
        raise HTTPException(status_code=503, detail=settings.get("maintenance_message", "Service under maintenance."))
    if not settings.get("enable_batch_mode", True):
        raise HTTPException(status_code=403, detail="Batch processing is currently disabled by the administrator.")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided for batch processing.")

    # Enforce Daily Quota check on Batch Processing
    client_ip = get_client_ip(request)
    user_id = current_user["id"] if current_user else None
    quota_info = await run_in_threadpool(
        db_manager.get_user_quota_summary,
        user_id,
        client_ip,
    )
    if quota_info.get("is_resting") or quota_info["remaining_today"] <= 0:
        mins = max(1, math.ceil(quota_info.get("seconds_until_reset", 1800) / 60))
        time_str = quota_info.get("time_remaining_formatted", f"{mins}m")
        reset_utc_display = f" (at {quota_info['reset_time_utc']} UTC)" if quota_info.get("reset_time_utc") else ""
        raise HTTPException(
            status_code=429,
            detail=f"Account limitation reached (10/10 images processed). A 30-minute rest cooldown is active to reset your uses. Global timer resets in {time_str}{reset_utc_display}.",
        )
    if quota_info["remaining_today"] < len(files):
        if quota_info.get("is_registered"):
            raise HTTPException(
                status_code=429,
                detail=f"Batch size ({len(files)} images) exceeds your remaining quota ({quota_info['remaining_today']} images remaining in current 10-image cycle).",
            )
        else:
            raise HTTPException(
                status_code=429,
                detail=f"Batch size ({len(files)} images) exceeds your remaining daily quota ({quota_info['remaining_today']} uses remaining).",
            )

    max_batch = int(settings.get("max_batch_files", 50))
    if len(files) > max_batch:
        raise HTTPException(status_code=400, detail=f"Batch exceeds maximum allowed limit of {max_batch} files.")

    file_payloads = []
    for idx, file in enumerate(files):
        content = await file.read()
        if content:
            file_payloads.append((file.filename or f"image_{idx}.png", content))

    batch_id = str(uuid.uuid4())

    def _build_batch_zip() -> bytes:
        zip_buffer = io.BytesIO()
        ext = "png" if format.lower() == "png" else ("webp" if format.lower() == "webp" else "jpg")
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for idx, (filename, content) in enumerate(file_payloads):
                try:
                    t0 = time.perf_counter()
                    out_bytes, _, orig_w, orig_h = _process_single_image(
                        content,
                        model=model,
                        alpha_matting=alpha_matting,
                        af=240,
                        ab=10,
                        ae=10,
                        only_mask=False,
                        post_process_mask=post_process_mask,
                        bgcolor_tuple=None,
                        out_format=ext,
                    )
                    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
                    raw_stem = Path(filename).stem
                    safe_stem = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in raw_stem).strip("_") or f"image_{idx}"
                    job_uuid = str(uuid.uuid4())
                    out_filename = f"{safe_stem}_{job_uuid[:8]}_nobg.{ext}"
                    out_path = OUTPUTS_DIR / out_filename
                    out_path.write_bytes(out_bytes)

                    db_manager.record_job(
                        job_uuid=job_uuid,
                        original_filename=filename,
                        output_filename=out_filename,
                        output_url=f"/static/outputs/{out_filename}",
                        model_used=model,
                        alpha_matting=alpha_matting,
                        af_threshold=240,
                        ab_threshold=10,
                        ae_size=10,
                        only_mask=False,
                        post_process_mask=post_process_mask,
                        bg_color=None,
                        output_format=ext,
                        original_width=orig_w,
                        original_height=orig_h,
                        output_size_bytes=len(out_bytes),
                        process_time_ms=elapsed_ms,
                        batch_id=batch_id,
                        user_id=current_user["id"] if current_user else None,
                        client_ip=client_ip,
                        status="completed",
                    )

                    zip_file.writestr(f"{safe_stem}_nobg.{ext}", out_bytes)
                except Exception as e:
                    print(f"[Batch Error] Failed processing '{filename}': {e}")
                    continue
        zip_buffer.seek(0)
        return zip_buffer.getvalue()

    zip_bytes = await run_in_threadpool(_build_batch_zip)
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="background_removed_images.zip"',
            "X-Batch-Id": batch_id,
        },
    )


def _encode_pil_image(img: Image.Image, out_format: str, bgcolor_tuple: Optional[tuple] = None) -> tuple[bytes, str]:
    """Encode a PIL Image into PNG, JPEG, or WebP bytes."""
    buf = io.BytesIO()
    out_fmt = out_format.upper()
    if out_fmt == "JPG":
        out_fmt = "JPEG"

    if out_fmt == "JPEG":
        if img.mode == "RGBA":
            fill_rgb = bgcolor_tuple[:3] if bgcolor_tuple else (255, 255, 255)
            rgb_bg = Image.new("RGB", img.size, fill_rgb)
            rgb_bg.paste(img, mask=img.split()[3])
            img = rgb_bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=95)
        media_type = "image/jpeg"
    elif out_fmt == "WEBP":
        img.save(buf, format="WEBP", quality=95)
        media_type = "image/webp"
    else:
        img.save(buf, format="PNG")
        media_type = "image/png"
    return buf.getvalue(), media_type


@app.post("/api/tools/process")
async def process_image_tool(
    request: Request,
    tool_id: str = Form(...),
    file: UploadFile = File(...),
    format: str = Form("png"),
    # 1. Image Editor params
    brightness: float = Form(1.0),
    contrast: float = Form(1.0),
    saturation: float = Form(1.0),
    sharpness: float = Form(1.0),
    warmth: float = Form(0.0),
    blur: float = Form(0.0),
    rotate: int = Form(0),
    flip_h: bool = Form(False),
    flip_v: bool = Form(False),
    filter_preset: str = Form("none"),
    crop_ratio: str = Form("original"),
    # 2. Image Upscaler params
    scale: int = Form(2),
    denoise: float = Form(0.35),
    sharpen: float = Form(0.65),
    # 3. Image Extender params
    target_ratio: str = Form("16:9"),
    expand_percent: int = Form(25),
    extender_mode: str = Form("ai_outpaint"),
    # 4. Variations params
    variation_style: str = Form("cyberpunk"),
    strength: float = Form(0.8),
    # 5. Cinematic Shot params
    color_grade: str = Form("teal_orange"),
    bokeh_blur: float = Form(0.65),
    letterbox: bool = Form(True),
    anamorphic_flare: bool = Form(True),
    film_grain: float = Form(0.18),
    # 6. Background Remover params
    model: str = Form("u2net"),
    alpha_matting: bool = Form(False),
    af: int = Form(240),
    ab: int = Form(10),
    ae: int = Form(10),
    only_mask: bool = Form(False),
    post_process_mask: bool = Form(False),
    bg_color: Optional[str] = Form(None),
    # 7. Skin Enhancer params
    smoothing: float = Form(0.65),
    radiance: float = Form(0.35),
    detail_crispness: float = Form(0.5),
    # 8. Relight params
    light_position: str = Form("top_left"),
    light_color: str = Form("#ff7b3a"),
    secondary_color: str = Form("#2563eb"),
    light_intensity: float = Form(0.75),
    ambient_dim: float = Form(0.45),
    # 9. Change Camera params
    camera_angle: str = Form("tilt_up"),
    lens_type: str = Form("wide_24mm"),
    camera_intensity: float = Form(0.6),
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """
    Unified endpoint executing any of the 9 IMAGE tools in working mode,
    enforcing guest vs registered user access restrictions and quotas,
    saving the output image and logging the job into MySQL `removal_jobs`.
    """
    start_time = time.perf_counter()
    settings = await run_in_threadpool(db_manager.get_site_settings)

    if settings.get("maintenance_mode"):
        raise HTTPException(status_code=503, detail=settings.get("maintenance_message", "Service under maintenance."))

    valid_tool_ids = {t["id"] for t in _get_tools_catalog()}
    if tool_id not in valid_tool_ids:
        raise HTTPException(status_code=400, detail=f"Unknown tool_id '{tool_id}'.")

    enabled_tool_ids = set(settings.get("enabled_tools", []))
    if enabled_tool_ids and tool_id not in enabled_tool_ids:
        raise HTTPException(status_code=403, detail=f"Tool '{tool_id}' is currently disabled by the administrator.")

    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be a valid image format.")
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image file uploaded.")

    # Enforce Guest vs Registered User Quotas and Tool Access Limitations
    client_ip = get_client_ip(request)
    user_id = current_user["id"] if current_user else None
    try:
        quota_info = await run_in_threadpool(
            db_manager.check_user_access_quota,
            user_id,
            client_ip,
            tool_id,
            len(image_bytes),
        )
    except PermissionError as pe:
        status_code = 429 if "rest cooldown" in str(pe) or "limit reached" in str(pe) or "limitation reached" in str(pe) else 403
        raise HTTPException(status_code=status_code, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    orig_filename = file.filename or "uploaded_image.png"

    bgcolor_tuple = parse_color(bg_color)

    def _run_tool_worker() -> tuple[bytes, str, int, int, int, int, str]:
        input_img = Image.open(io.BytesIO(image_bytes))
        orig_w, orig_h = input_img.size

        if tool_id == "bg-remover":
            clamped_af = max(0, min(255, af))
            clamped_ab = max(0, min(255, ab))
            clamped_ae = max(0, min(255, ae))
            out_b, m_type, orig_w, orig_h = _process_single_image(
                image_bytes,
                model,
                alpha_matting,
                clamped_af,
                clamped_ab,
                clamped_ae,
                only_mask,
                post_process_mask,
                bgcolor_tuple,
                format,
            )
            return out_b, m_type, orig_w, orig_h, orig_w, orig_h, model

        elif tool_id == "image-editor":
            out_img = image_tools.tool_image_editor(
                input_img,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
                sharpness=sharpness,
                warmth=warmth,
                blur=blur,
                rotate=rotate,
                flip_h=flip_h,
                flip_v=flip_v,
                filter_preset=filter_preset,
                crop_ratio=crop_ratio,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, "tool:image-editor"

        elif tool_id == "image-upscaler":
            out_img = image_tools.tool_image_upscaler(
                input_img,
                scale=scale,
                denoise=denoise,
                sharpen=sharpen,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:upscaler-{scale}x"

        elif tool_id == "image-extender":
            out_img = image_tools.tool_image_extender(
                input_img,
                target_ratio=target_ratio,
                expand_percent=expand_percent,
                mode=extender_mode,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:extender ({target_ratio})"

        elif tool_id == "variations":
            out_img = image_tools.tool_variations(
                input_img,
                variation_style=variation_style,
                strength=strength,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:variations ({variation_style})"

        elif tool_id == "cinematic-shot":
            sess = get_session("u2netp")
            out_img = image_tools.tool_cinematic_shot(
                input_img,
                session=sess,
                color_grade=color_grade,
                bokeh_blur=bokeh_blur,
                letterbox=letterbox,
                anamorphic_flare=anamorphic_flare,
                film_grain=film_grain,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:cinematic ({color_grade})"

        elif tool_id == "skin-enhancer":
            out_img = image_tools.tool_skin_enhancer(
                input_img,
                smoothing=smoothing,
                radiance=radiance,
                detail_crispness=detail_crispness,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, "tool:skin-enhancer"

        elif tool_id == "relight":
            sess = get_session("u2netp")
            out_img = image_tools.tool_relight(
                input_img,
                session=sess,
                light_position=light_position,
                light_color=light_color,
                secondary_color=secondary_color,
                light_intensity=light_intensity,
                ambient_dim=ambient_dim,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:relight ({light_position})"

        elif tool_id == "change-camera":
            sess = get_session("u2netp")
            out_img = image_tools.tool_change_camera(
                input_img,
                session=sess,
                camera_angle=camera_angle,
                lens_type=lens_type,
                intensity=camera_intensity,
            )
            out_w, out_h = out_img.size
            out_b, m_type = _encode_pil_image(out_img, format)
            return out_b, m_type, orig_w, orig_h, out_w, out_h, f"tool:camera ({lens_type})"

        raise ValueError(f"Unsupported tool: {tool_id}")

    try:
        out_bytes, media_type, orig_w, orig_h, out_w, out_h, model_label = await run_in_threadpool(_run_tool_worker)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Tool '{tool_id}' execution failed: {str(e)}")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    job_uuid = str(uuid.uuid4())
    ext = "jpg" if format.lower() in ("jpg", "jpeg") else ("webp" if format.lower() == "webp" else "png")
    safe_tool_tag = tool_id.replace("-", "_")
    raw_stem = Path(orig_filename).stem
    safe_stem = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in raw_stem).strip("_") or "image"
    out_filename = f"{safe_stem}_{job_uuid[:8]}_{safe_tool_tag}.{ext}"
    out_path = OUTPUTS_DIR / out_filename
    output_url = f"/static/outputs/{out_filename}"

    def _save_and_record() -> Dict[str, Any]:
        out_path.write_bytes(out_bytes)
        return db_manager.record_job(
            job_uuid=job_uuid,
            original_filename=orig_filename,
            output_filename=out_filename,
            output_url=output_url,
            model_used=model_label[:64],
            alpha_matting=alpha_matting if tool_id == "bg-remover" else False,
            af_threshold=af if tool_id == "bg-remover" else 240,
            ab_threshold=ab if tool_id == "bg-remover" else 10,
            ae_size=ae if tool_id == "bg-remover" else 10,
            only_mask=only_mask if tool_id == "bg-remover" else False,
            post_process_mask=post_process_mask if tool_id == "bg-remover" else False,
            bg_color=bg_color if tool_id == "bg-remover" else None,
            output_format=ext,
            original_width=out_w,
            original_height=out_h,
            output_size_bytes=len(out_bytes),
            process_time_ms=elapsed_ms,
            batch_id=None,
            user_id=current_user["id"] if current_user else None,
            client_ip=client_ip,
            status="completed",
        )

    job_record = await run_in_threadpool(_save_and_record)

    headers = {
        "X-Process-Time-Ms": str(elapsed_ms),
        "X-Original-Width": str(orig_w),
        "X-Original-Height": str(orig_h),
        "X-Output-Width": str(out_w),
        "X-Output-Height": str(out_h),
        "X-Tool-Id": tool_id,
        "X-Model-Used": model_label[:64],
        "X-Job-Id": str(job_record["id"]),
        "X-Job-Uuid": job_uuid,
        "X-Output-Url": output_url,
        "X-User-Tier": quota_info["tier"],
        "X-RateLimit-Limit": str(quota_info["daily_limit"]),
        "X-RateLimit-Remaining": str(max(0, quota_info["remaining_today"] - 1)),
        "X-RateLimit-Reset-Timestamp": str(quota_info.get("reset_timestamp") or ""),
        "X-RateLimit-Reset-Utc": str(quota_info.get("reset_time_utc") or ""),
        "X-Server-Time-Utc": str(quota_info.get("server_time_utc") or ""),
        "Cache-Control": "no-cache",
    }
    return Response(content=out_bytes, media_type=media_type, headers=headers)


# ========================================================
# ADMIN BACKEND SYSTEM ENDPOINTS (/api/admin/*)
# ========================================================
@app.post("/api/admin/login")
async def admin_login(payload: AdminLoginPayload, request: Request):
    """Authenticate an administrator against the MySQL `admin_users` table with brute-force protection."""
    client_ip = get_client_ip(request)
    is_local = client_ip in {"127.0.0.1", "::1", "localhost", "testclient"}
    max_att = 100 if is_local else 5
    if not check_rate_limit(_admin_login_ip_attempts, client_ip, max_attempts=max_att, window_seconds=600):
        raise HTTPException(
            status_code=429,
            detail="Too many admin login attempts from your IP address. Please wait 10 minutes before retrying."
        )

    user = await run_in_threadpool(db_manager.authenticate_admin, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid administrator username or password.")

    token = secrets.token_urlsafe(32)
    _admin_tokens[token] = user
    await run_in_threadpool(db_manager.create_admin_session, user["id"], token)
    return {"token": token, "admin": user}


@app.post("/api/admin/logout")
async def admin_logout(x_admin_token: Optional[str] = Header(None)):
    if x_admin_token:
        _admin_tokens.pop(x_admin_token, None)
        await run_in_threadpool(db_manager.delete_admin_session, x_admin_token)
    return {"logged_out": True}


@app.get("/api/admin/me")
async def admin_me(admin: Dict[str, Any] = Depends(require_admin)):
    return {"admin": admin}


@app.post("/api/admin/credentials")
async def admin_update_credentials(
    payload: AdminCredentialsPayload,
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Update administrator username and/or password in MySQL."""
    try:
        updated = await run_in_threadpool(
            db_manager.update_admin_credentials,
            admin["username"],
            payload.new_username,
            payload.new_password,
            payload.current_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if x_admin_token:
        _admin_tokens[x_admin_token] = updated
    return {"admin": updated}


# --------------------------------------------------------
# ADMIN PROFILE & SESSION MANAGEMENT
# --------------------------------------------------------
@app.get("/api/admin/profile")
async def admin_get_profile(admin: Dict[str, Any] = Depends(require_admin)):
    """Fetch current logged-in administrator's complete profile and system metrics."""
    profile = await run_in_threadpool(db_manager.get_admin_profile, admin["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="Admin profile not found.")
    return {"profile": profile}


@app.put("/api/admin/profile")
async def admin_update_profile(
    payload: AdminProfileUpdatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Update administrator profile fields (full name, email, bio, department, location, preferences)."""
    try:
        updated = await run_in_threadpool(
            db_manager.update_admin_profile,
            admin["id"],
            payload.model_dump(exclude_unset=True),
        )
        if x_admin_token and x_admin_token in _admin_tokens:
            _admin_tokens[x_admin_token].update(updated)
        return {"profile": updated, "message": "Admin profile updated successfully."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating admin profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update admin profile.")


@app.post("/api/admin/profile/avatar")
async def admin_upload_avatar(
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Upload and optimize a custom avatar photo for the administrator."""
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid image type. Supported formats: PNG, JPG, WEBP.")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Avatar image size cannot exceed 5 MB.")

    try:
        img = Image.open(io.BytesIO(content))
        img = img.convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)
        old_avatar = admin.get("avatar_url", "")
        if old_avatar and old_avatar.startswith("/static/avatars/"):
            old_file = BASE_DIR / old_avatar.lstrip("/")
            if old_file.exists() and old_file.is_file():
                try:
                    old_file.unlink()
                except Exception:
                    pass

        filename = f"admin_{admin['id']}_{secrets.token_hex(6)}.png"
        filepath = AVATARS_DIR / filename
        img.save(filepath, format="PNG", optimize=True)
        avatar_url = f"/static/avatars/{filename}"
        updated = await run_in_threadpool(db_manager.update_admin_avatar, admin["id"], avatar_url)
        if x_admin_token and x_admin_token in _admin_tokens:
            _admin_tokens[x_admin_token]["avatar_url"] = avatar_url
        return {"avatar_url": avatar_url, "profile": updated, "message": "Avatar uploaded successfully."}
    except Exception as e:
        logger.error(f"Failed to process admin avatar: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail="Invalid image file or corrupted data.")


@app.delete("/api/admin/profile/avatar")
async def admin_delete_avatar(
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Remove custom admin avatar and reset to default color badge."""
    old_avatar = admin.get("avatar_url", "")
    if old_avatar and old_avatar.startswith("/static/avatars/"):
        old_file = BASE_DIR / old_avatar.lstrip("/")
        if old_file.exists() and old_file.is_file():
            try:
                old_file.unlink()
            except Exception:
                pass

    updated = await run_in_threadpool(db_manager.update_admin_avatar, admin["id"], "")
    if x_admin_token and x_admin_token in _admin_tokens:
        _admin_tokens[x_admin_token]["avatar_url"] = ""
    return {"profile": updated, "message": "Avatar removed. Using default color badge."}


@app.post("/api/admin/profile/password")
async def admin_change_password(
    payload: AdminPasswordChangePayload,
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Securely change administrator password with current password verification."""
    try:
        updated = await run_in_threadpool(
            db_manager.change_admin_password,
            admin["id"],
            payload.current_password,
            payload.new_password,
            x_admin_token,
        )
        return {"profile": updated, "message": "Password changed successfully. All other sessions revoked."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/profile/sessions")
async def admin_get_sessions(
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """List active login sessions for the administrator."""
    sessions = await run_in_threadpool(db_manager.list_admin_sessions, admin["id"], x_admin_token)
    return {"sessions": sessions}


@app.post("/api/admin/profile/sessions/revoke-others")
async def admin_revoke_other_sessions(
    admin: Dict[str, Any] = Depends(require_admin),
    x_admin_token: Optional[str] = Header(None),
):
    """Revoke all active sessions for this admin except the current active session."""
    if not x_admin_token:
        raise HTTPException(status_code=400, detail="Missing active session token.")
    revoked_count = await run_in_threadpool(db_manager.revoke_other_admin_sessions, admin["id"], x_admin_token)
    return {"revoked_count": revoked_count, "message": f"Successfully revoked {revoked_count} other sessions."}


@app.delete("/api/admin/profile/sessions/{session_id}")
async def admin_revoke_session(
    session_id: int,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Revoke a specific admin session by ID."""
    success = await run_in_threadpool(db_manager.revoke_admin_session_by_id, admin["id"], session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found or already revoked.")
    return {"success": True, "message": "Session revoked."}


@app.get("/api/admin/overview")
async def admin_overview(admin: Dict[str, Any] = Depends(require_admin)):
    """Executive overview for the Admin Dashboard."""
    analytics = await run_in_threadpool(db_manager.get_analytics)
    settings = await run_in_threadpool(db_manager.get_site_settings)
    recent_jobs = await run_in_threadpool(db_manager.list_jobs, 8, 0)
    models = _get_model_catalog()
    tools = _get_tools_catalog()
    enabled_tool_ids = set(settings.get("enabled_tools", []))
    for t in tools:
        t["is_enabled"] = t["id"] in enabled_tool_ids if enabled_tool_ids else True

    return {
        "analytics": analytics,
        "settings": settings,
        "recent_jobs": recent_jobs["jobs"],
        "models": models,
        "tools": tools,
        "cached_sessions": list(_session_cache.keys()),
        "rembg_version": rembg.__version__,
    }


@app.get("/api/admin/settings")
async def admin_get_settings(admin: Dict[str, Any] = Depends(require_admin)):
    """Fetch all frontend CMS & feature-flag settings from MySQL."""
    settings = await run_in_threadpool(db_manager.get_site_settings)
    return {"settings": settings}


@app.put("/api/admin/settings")
async def admin_update_settings(
    payload: SiteSettingsPayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Update frontend CMS & feature-flag settings in MySQL."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = await run_in_threadpool(db_manager.update_site_settings, updates)
    return {"settings": updated}


@app.get("/api/admin/samples")
async def admin_list_samples(admin: Dict[str, Any] = Depends(require_admin)):
    """List all sample images (both active and inactive) from MySQL."""
    samples = await run_in_threadpool(db_manager.list_samples, False)
    return {"samples": samples}


@app.post("/api/admin/samples")
async def admin_upload_sample(
    file: UploadFile = File(...),
    title: str = Form("New Sample"),
    category: str = Form("Product"),
    is_active: bool = Form(True),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Upload a new sample image and add it to the MySQL `sample_images` table."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded sample must be an image.")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty sample image uploaded.")

    safe_stem = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in Path(file.filename or "sample").stem)
    out_filename = f"{safe_stem}_{uuid.uuid4().hex[:6]}.jpg"
    out_path = SAMPLES_DIR / out_filename

    def _save_sample() -> Dict[str, Any]:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_path, format="JPEG", quality=92)
        return db_manager.create_sample(
            title=title,
            category=category,
            filename=out_filename,
            url=f"/static/samples/{out_filename}",
            is_active=is_active,
        )

    created = await run_in_threadpool(_save_sample)
    return {"sample": created}


@app.patch("/api/admin/samples/{sample_id}")
async def admin_update_sample(
    sample_id: int,
    payload: SampleUpdatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Update sample image metadata or active visibility in MySQL."""
    updated = await run_in_threadpool(
        db_manager.update_sample,
        sample_id,
        payload.title,
        payload.category,
        payload.is_active,
        payload.sort_order,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Sample not found.")
    return {"sample": updated}


@app.delete("/api/admin/samples/{sample_id}")
async def admin_delete_sample(
    sample_id: int,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Delete a sample image record from MySQL."""
    deleted = await run_in_threadpool(db_manager.delete_sample, sample_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Sample not found.")
    return {"deleted": True, "id": sample_id}


@app.get("/api/admin/models")
async def admin_list_models(admin: Dict[str, Any] = Depends(require_admin)):
    """List all AI models with download, RAM cache, and enabled status."""
    settings = await run_in_threadpool(db_manager.get_site_settings)
    enabled_ids = set(settings.get("enabled_models", []))
    default_id = settings.get("default_model", "u2net")
    models = _get_model_catalog()
    for m in models:
        m["is_enabled"] = m["id"] in enabled_ids
        m["is_default"] = m["id"] == default_id
    return {"models": models, "default_model": default_id}


@app.post("/api/admin/models/{model_id}/load")
async def admin_load_model(model_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """Pre-load an ONNX model into memory."""
    await run_in_threadpool(get_session, model_id)
    return {"loaded": True, "model_id": model_id, "cached_sessions": list(_session_cache.keys())}


@app.post("/api/admin/models/{model_id}/unload")
async def admin_unload_model(model_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """Unload an ONNX model from RAM cache."""
    _session_cache.pop(model_id, None)
    return {"unloaded": True, "model_id": model_id, "cached_sessions": list(_session_cache.keys())}


@app.get("/api/admin/jobs")
async def admin_list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Search, filter, and paginate all background removal jobs in MySQL."""
    return await run_in_threadpool(db_manager.list_jobs, limit, offset, search, model)


# ========================================================
# BLOG ENDPOINTS (PUBLIC /api/blog & ADMIN /api/admin/blog)
# ========================================================
@app.get("/api/blog")
async def list_public_blog_posts(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    featured: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List published blog posts for the public /blog page."""
    result = await run_in_threadpool(
        db_manager.list_blog_posts,
        True,
        category,
        search,
        featured,
        limit,
        offset,
    )
    settings = await run_in_threadpool(db_manager.get_site_settings)
    result["settings"] = settings
    return result


@app.get("/api/blog/{slug}")
async def get_public_blog_post(slug: str):
    """Fetch a single published blog article by slug and increment its view count."""
    post = await run_in_threadpool(db_manager.get_blog_post_by_slug, slug, True, True)
    if not post:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    all_pub = await run_in_threadpool(db_manager.list_blog_posts, True, None, None, False, 6, 0)
    related = [p for p in all_pub.get("posts", []) if p["slug"] != post["slug"]][:3]
    return {"post": post, "related": related}


@app.get("/api/admin/blog")
async def admin_list_blog_posts(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """List all blog posts (published & drafts) with analytics for the Admin Dashboard."""
    result = await run_in_threadpool(
        db_manager.list_blog_posts,
        False,
        category,
        search,
        False,
        limit,
        offset,
    )
    if status == "published":
        result["posts"] = [p for p in result["posts"] if p["is_published"]]
    elif status == "draft":
        result["posts"] = [p for p in result["posts"] if not p["is_published"]]
    elif status == "featured":
        result["posts"] = [p for p in result["posts"] if p["is_featured"]]
    return result


@app.post("/api/admin/blog")
async def admin_create_blog_post(
    payload: BlogPostCreatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Create a new blog post in MySQL via the Admin Dashboard."""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Blog post title cannot be empty.")
    created = await run_in_threadpool(
        db_manager.create_blog_post,
        title=payload.title,
        slug=payload.slug,
        excerpt=payload.excerpt,
        content=payload.content,
        category=payload.category,
        tags=payload.tags,
        cover_image=payload.cover_image,
        author=payload.author,
        read_time_minutes=payload.read_time_minutes,
        is_published=payload.is_published,
        is_featured=payload.is_featured,
        meta_title=payload.meta_title,
        meta_description=payload.meta_description,
    )
    return {"post": created}


@app.put("/api/admin/blog/{post_id}")
async def admin_update_blog_post(
    post_id: int,
    payload: BlogPostUpdatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Update an existing blog post in MySQL via the Admin Dashboard."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updated = await run_in_threadpool(db_manager.update_blog_post, post_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return {"post": updated}


@app.delete("/api/admin/blog/{post_id}")
async def admin_delete_blog_post(
    post_id: int,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Delete a blog post from MySQL."""
    deleted = await run_in_threadpool(db_manager.delete_blog_post, post_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Blog post not found.")
    return {"deleted": True, "id": post_id}


@app.post("/api/admin/blog/upload-cover")
async def admin_upload_blog_cover(
    file: UploadFile = File(...),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Upload a custom cover image for a blog post and return its public static URL."""
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded cover must be an image file.")
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Empty image file uploaded.")

    safe_stem = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in Path(file.filename or "blog_cover").stem)
    out_filename = f"{safe_stem}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = BLOG_IMAGES_DIR / out_filename

    def _save_cover() -> str:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_path, format="JPEG", quality=92)
        return f"/static/blog/{out_filename}"

    url = await run_in_threadpool(_save_cover)
    return {"url": url, "filename": out_filename}


# ========================================================
# USER LOGIN, REGISTRATION & USER DASHBOARD ENDPOINTS
# ========================================================
@app.post("/api/auth/register")
async def register_user_account(payload: UserRegisterPayload, request: Request):
    """
    Register a new user account in MySQL `users`.
    Applies multi-layer security:
    - Rejects plus-addressing (e.g. name+1@domain.com) and temporary burner emails.
    - Rejects weak passwords & reserved usernames.
    - Enforces anti-bot honeypot and IP rate limiting.
    - Account starts as inactive until verified via Gmail/email code.
    """
    # 1. Anti-bot honeypot check
    if payload.website and payload.website.strip():
        raise HTTPException(status_code=400, detail="Invalid registration submission (bot activity detected).")

    # 2. IP rate limiting (max 10 registration attempts per 15 minutes per IP)
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_rate_limit(_reg_ip_attempts, client_ip, max_attempts=10, window_seconds=900):
        raise HTTPException(
            status_code=429,
            detail="Too many registration attempts from your IP address. Please wait a few minutes before trying again."
        )

    try:
        user = await run_in_threadpool(
            db_manager.register_user,
            payload.username,
            payload.email,
            payload.password,
            payload.full_name,
            auto_activate=False,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Send Gmail verification email with 6-digit code and 1-click activation link
    base_url = SITE_BASE_URL or str(request.base_url).rstrip("/")
    mail_res = await run_in_threadpool(
        send_verification_email,
        user["email"],
        user.get("full_name") or user["username"],
        user["verification_code"],
        user["verification_token"],
        base_url,
        db_manager,
    )

    response = {
        "success": True,
        "requires_verification": True,
        "is_active": False,
        "email": user["email"],
        "username": user["username"],
        "message": (
            f"Registration successful! We sent a 6-digit verification code to {user['email']}. "
            "Please verify your email address to activate your account."
        ),
        "email_sent": mail_res.get("sent", False),
    }
    # Provide dev fallback code only when explicitly configured in development mode
    is_dev = os.getenv("ENVIRONMENT", "production").lower() in ("dev", "development", "local")
    if is_dev and (not mail_res.get("smtp_configured") or not mail_res.get("sent")):
        response["dev_code"] = user["verification_code"]
        response["dev_token"] = user["verification_token"]
        response["dev_verify_url"] = mail_res.get("verify_url")

    return response


@app.post("/api/auth/verify-code")
async def verify_user_email_code(payload: UserVerifyCodePayload, request: Request):
    """Verify an unverified user account using the 6-digit code and activate it."""
    client_ip = get_client_ip(request)
    if not check_rate_limit(_verify_ip_attempts, client_ip, max_attempts=15, window_seconds=900):
        raise HTTPException(
            status_code=429,
            detail="Too many verification attempts from your IP address. Please wait a few minutes."
        )

    try:
        user = await run_in_threadpool(
            db_manager.verify_user_code,
            payload.email,
            payload.code,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    token = secrets.token_urlsafe(32)
    _user_tokens[token] = user["id"]
    await run_in_threadpool(db_manager.create_user_session, user["id"], token)
    return {
        "success": True,
        "verified": True,
        "is_active": True,
        "token": token,
        "user": user,
        "message": "Email verified successfully! Your account is now active.",
    }


@app.get("/api/auth/verify")
async def verify_user_email_token(token: str = Query(...)):
    """Verify an unverified user account using the 1-click token link and activate it."""
    try:
        user = await run_in_threadpool(
            db_manager.verify_user_token,
            token,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    session_token = secrets.token_urlsafe(32)
    _user_tokens[session_token] = user["id"]
    await run_in_threadpool(db_manager.create_user_session, user["id"], session_token)
    return {
        "success": True,
        "verified": True,
        "is_active": True,
        "token": session_token,
        "user": user,
        "message": "Account activated successfully!",
    }


@app.post("/api/auth/resend-verification")
async def resend_verification_email_code(payload: UserResendVerificationPayload, request: Request):
    """Resend a new 6-digit verification code and link to the user's Gmail."""
    try:
        user = await run_in_threadpool(
            db_manager.resend_verification_code,
            payload.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    base_url = SITE_BASE_URL or str(request.base_url).rstrip("/")
    mail_res = await run_in_threadpool(
        send_verification_email,
        user["email"],
        user.get("full_name") or user["username"],
        user["verification_code"],
        user["verification_token"],
        base_url,
        db_manager,
    )

    res = {
        "success": True,
        "email": user["email"],
        "message": f"A new 6-digit verification code has been sent to {user['email']}.",
        "email_sent": mail_res.get("sent", False),
    }
    is_dev = os.getenv("ENVIRONMENT", "production").lower() in ("dev", "development", "local")
    if is_dev and (not mail_res.get("smtp_configured") or not mail_res.get("sent")):
        res["dev_code"] = user["verification_code"]
        res["dev_token"] = user["verification_token"]
        res["dev_verify_url"] = mail_res.get("verify_url")
    return res


@app.post("/api/auth/login")
async def login_user_account(payload: UserLoginPayload, request: Request):
    """Authenticate a user by username or email against MySQL `users` with brute-force protection."""
    client_ip = get_client_ip(request)
    if not check_rate_limit(_login_ip_attempts, client_ip, max_attempts=10, window_seconds=600):
        raise HTTPException(
            status_code=429,
            detail="Too many failed login attempts from your IP. Please wait 10 minutes before retrying."
        )

    try:
        user = await run_in_threadpool(
            db_manager.authenticate_user,
            payload.identifier,
            payload.password,
        )
    except ValueError as e:
        err_msg = str(e)
        status_code = 403 if "not active" in err_msg.lower() or "suspended" in err_msg.lower() else 400
        raise HTTPException(status_code=status_code, detail=err_msg)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid username/email or password.")

    token = secrets.token_urlsafe(32)
    _user_tokens[token] = user["id"]
    await run_in_threadpool(db_manager.create_user_session, user["id"], token)
    return {"token": token, "user": user}


@app.post("/api/auth/logout")
async def logout_user_account(x_user_token: Optional[str] = Header(None)):
    """Sign out of the current user session and revoke token in database."""
    if x_user_token:
        _user_tokens.pop(x_user_token, None)
        await run_in_threadpool(db_manager.delete_user_session, x_user_token)
    return {"logged_out": True}


@app.get("/api/auth/me")
async def get_current_user_profile(user: Dict[str, Any] = Depends(require_user)):
    """Return the currently authenticated user profile."""
    return {"user": user}


@app.put("/api/user/profile")
async def update_current_user_profile(
    payload: UserProfileUpdatePayload,
    user: Dict[str, Any] = Depends(require_user),
):
    """Update the authenticated user's profile (name, email, avatar color, password, preferences, bio)."""
    try:
        updated = await run_in_threadpool(
            db_manager.update_user_profile,
            user["id"],
            full_name=payload.full_name,
            email=payload.email,
            avatar_color=payload.avatar_color,
            new_password=payload.new_password,
            current_password=payload.current_password,
            bio=payload.bio,
            phone=payload.phone,
            country=payload.country,
            preferred_format=payload.preferred_format,
            dark_mode_pref=payload.dark_mode_pref,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not updated:
        raise HTTPException(status_code=404, detail="User account not found.")
    return {"user": updated}


@app.get("/api/user/export")
async def export_current_user_data(user: Dict[str, Any] = Depends(require_user)):
    """Export the authenticated user's profile data, history, and telemetry as JSON."""
    data = await run_in_threadpool(db_manager.export_user_profile_data, user["id"])
    if not data:
        raise HTTPException(status_code=404, detail="User account data not found.")
    return data


@app.post("/api/user/delete-account")
async def delete_current_user_account(
    payload: UserDeleteAccountPayload,
    user: Dict[str, Any] = Depends(require_user),
):
    """Permanently delete the authenticated user's account and personal image history."""
    if payload.confirm_phrase != f"delete {user.get('username')}":
        raise HTTPException(status_code=400, detail=f"Please confirm by typing 'delete {user.get('username')}' exactly.")
    try:
        ok = await run_in_threadpool(db_manager.delete_user_account, user["id"], payload.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not ok:
        raise HTTPException(status_code=404, detail="User account could not be deleted.")
    return {"deleted": True, "message": "Account and all personal image processing history permanently deleted."}


@app.get("/api/user/quota")
async def get_current_user_quota(
    request: Request,
    current_user: Optional[Dict[str, Any]] = Depends(get_optional_user),
):
    """Return real-time access limitation and remaining daily quota for guest or registered user."""
    client_ip = get_client_ip(request)
    user_id = current_user["id"] if current_user else None
    quota = await run_in_threadpool(db_manager.get_user_quota_summary, user_id, client_ip)
    return quota


@app.post("/api/user/api-key/regenerate")
async def regenerate_current_user_api_key(user: Dict[str, Any] = Depends(require_user)):
    """Personal developer API key access is disabled."""
    raise HTTPException(status_code=403, detail="Personal developer API key access is disabled.")


@app.get("/api/user/dashboard")
async def get_user_dashboard(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    model: Optional[str] = Query(None),
    user: Dict[str, Any] = Depends(require_user),
):
    """Return comprehensive User Dashboard analytics, personal image history, and tools."""
    data = await run_in_threadpool(
        db_manager.get_user_dashboard_data,
        user["id"],
        limit,
        offset,
        search,
        model,
    )
    if not data:
        raise HTTPException(status_code=404, detail="User dashboard not found.")
    data["tools"] = _get_tools_catalog()
    return data


@app.delete("/api/user/jobs/{job_id}")
async def delete_user_job_item(
    job_id: int,
    user: Dict[str, Any] = Depends(require_user),
):
    """Delete a specific image processing job belonging to the logged-in user."""
    deleted = await run_in_threadpool(db_manager.delete_user_job, user["id"], job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found in your account.")
    out_file = OUTPUTS_DIR / deleted["output_filename"]
    if out_file.exists():
        try:
            out_file.unlink()
        except Exception:
            pass
    return {"deleted": True, "id": job_id}


@app.delete("/api/user/jobs")
async def clear_all_user_jobs(user: Dict[str, Any] = Depends(require_user)):
    """Clear all image processing jobs belonging to the logged-in user."""
    deleted_jobs = await run_in_threadpool(db_manager.clear_user_jobs, user["id"])
    for job in deleted_jobs:
        out_file = OUTPUTS_DIR / job["output_filename"]
        if out_file.exists():
            try:
                out_file.unlink()
            except Exception:
                pass
    return {"cleared": True, "count": len(deleted_jobs)}


# ========================================================
# ADMIN USER MANAGEMENT ENDPOINTS (/api/admin/users)
# ========================================================
@app.get("/api/admin/users")
async def admin_list_users_endpoint(
    search: Optional[str] = Query(None),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """List all registered users and account stats for the Admin Dashboard."""
    return await run_in_threadpool(db_manager.admin_list_users, search)


@app.patch("/api/admin/users/{user_id}")
async def admin_update_user_endpoint(
    user_id: int,
    payload: AdminUserUpdatePayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Update a user's active status, email verification, or plan tier from the Admin Dashboard."""
    updated = await run_in_threadpool(
        db_manager.admin_update_user,
        user_id,
        payload.is_active,
        payload.email_verified,
        payload.plan_tier,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": updated}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user_endpoint(
    user_id: int,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Delete a user account from MySQL."""
    deleted = await run_in_threadpool(db_manager.admin_delete_user, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"deleted": True, "id": user_id}


# ========================================================
# ADMIN GMAIL / SMTP SETTINGS ENDPOINTS (/api/admin/smtp)
# ========================================================
@app.get("/api/admin/smtp")
async def get_admin_smtp_endpoint(admin: Dict[str, Any] = Depends(require_admin)):
    """Retrieve current Gmail / SMTP configuration for email verification."""
    cfg = get_smtp_config(db_manager)
    # Mask password for security
    cfg_copy = dict(cfg)
    if cfg_copy.get("password"):
        cfg_copy["has_password"] = True
        cfg_copy["password"] = "••••••••••••••••"
    else:
        cfg_copy["has_password"] = False
    return {"smtp": cfg_copy}


@app.put("/api/admin/smtp")
async def update_admin_smtp_endpoint(
    payload: SmtpConfigPayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Save Gmail / SMTP settings in MySQL `site_settings` table."""
    updates = {
        "smtp_enabled": "true" if payload.smtp_enabled else "false",
        "smtp_host": payload.smtp_host.strip() or "smtp.gmail.com",
        "smtp_port": str(payload.smtp_port or 587),
        "smtp_user": payload.smtp_user.strip(),
        "smtp_from_name": payload.smtp_from_name.strip() or "PngLike AI Studio",
        "smtp_from_email": payload.smtp_from_email.strip() or payload.smtp_user.strip(),
        "smtp_use_tls": "true" if payload.smtp_use_tls else "false",
    }
    if payload.smtp_password and payload.smtp_password != "••••••••••••••••":
        updates["smtp_password"] = payload.smtp_password.strip()

    await run_in_threadpool(db_manager.update_site_settings, updates)

    # Keep .env file synchronized
    try:
        from dotenv import set_key
        env_file = BASE_DIR / ".env"
        if env_file.exists():
            set_key(str(env_file), "SMTP_ENABLED", updates["smtp_enabled"])
            set_key(str(env_file), "SMTP_HOST", updates["smtp_host"])
            set_key(str(env_file), "SMTP_PORT", updates["smtp_port"])
            set_key(str(env_file), "SMTP_USER", updates["smtp_user"])
            if "smtp_password" in updates:
                set_key(str(env_file), "SMTP_PASSWORD", updates["smtp_password"])
            set_key(str(env_file), "SMTP_FROM_NAME", updates["smtp_from_name"])
            set_key(str(env_file), "SMTP_FROM_EMAIL", updates["smtp_from_email"])
            set_key(str(env_file), "SMTP_USE_TLS", updates["smtp_use_tls"])
    except Exception:
        pass

    return {"success": True, "message": "Gmail SMTP configuration updated successfully in MySQL and .env!"}


@app.post("/api/admin/smtp/test")
async def test_admin_smtp_endpoint(
    payload: SmtpTestPayload,
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Test connecting and authenticating to Gmail SMTP server."""
    res = await run_in_threadpool(
        test_smtp_connection,
        payload.host,
        payload.port,
        payload.user,
        payload.password,
        payload.use_tls,
        payload.test_recipient,
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "SMTP test connection failed."))
    return res


# --------------------------------------------------------
# PUBLIC CONTACT & SUPPORT API
# --------------------------------------------------------
@app.post("/api/contact")
async def submit_contact_form(
    request: Request,
    payload: ContactMessagePayload,
):
    """Receive and record user contact/feedback inquiries with anti-bot validation."""
    if payload.website and payload.website.strip():
        raise HTTPException(status_code=400, detail="Automated submission blocked.")

    clean_name = payload.name.strip()
    clean_email = payload.email.strip().lower()
    clean_subject = payload.subject.strip()
    clean_msg = payload.message.strip()

    if len(clean_name) < 2:
        raise HTTPException(status_code=400, detail="Name must be at least 2 characters.")
    if "@" not in clean_email or "." not in clean_email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(clean_subject) < 3:
        raise HTTPException(status_code=400, detail="Subject must be at least 3 characters.")
    if len(clean_msg) < 10:
        raise HTTPException(status_code=400, detail="Message must be at least 10 characters.")

    client_ip = get_client_ip(request)
    if not check_rate_limit(_contact_ip_attempts, client_ip, max_attempts=5, window_seconds=900):
        raise HTTPException(
            status_code=429,
            detail="Too many contact submissions from your IP address. Please wait a few minutes before submitting again."
        )

    saved = await run_in_threadpool(
        db_manager.save_contact_message,
        clean_name,
        clean_email,
        clean_subject,
        clean_msg,
        client_ip,
    )
    return {
        "success": True,
        "message": "Thank you! Your message has been sent successfully. Our support team will review it within 24 hours.",
        "id": saved["id"],
    }


@app.get("/api/admin/contact")
async def admin_list_contact_messages(
    admin: Dict[str, Any] = Depends(require_admin),
    limit: int = 50,
    offset: int = 0,
):
    """List contact messages and feedback tickets for admin review."""
    return await run_in_threadpool(db_manager.list_contact_messages, limit, offset)


# --------------------------------------------------------
# SEO, SITEMAP & AI AGENT DISCOVERY ROUTES (/robots.txt, /sitemap.xml, /llms.txt, /{indexnow}.txt)
# --------------------------------------------------------
@app.get("/robots.txt")
async def serve_robots_txt(request: Request):
    robots_path = BASE_DIR / "robots.txt"
    if robots_path.exists():
        content = robots_path.read_text(encoding="utf-8")
        site_base = os.getenv("SITE_BASE_URL", "").rstrip("/")
        if site_base:
            content = re.sub(r"Sitemap:\s*https?://[^\s/]+/sitemap\.xml", f"Sitemap: {site_base}/sitemap.xml", content)
        return Response(content=content, media_type="text/plain; charset=utf-8")

    site_base = os.getenv("SITE_BASE_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    robots_content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Allow: /blog\n"
        "Allow: /about\n"
        "Allow: /faq\n"
        "Allow: /contact\n"
        "Allow: /privacy\n"
        "Allow: /terms\n"
        "Allow: /cookies\n"
        "Disallow: /admin\n"
        "Disallow: /dashboard\n\n"
        f"Sitemap: {site_base}/sitemap.xml\n"
    )
    return Response(content=robots_content, media_type="text/plain; charset=utf-8")


@app.get("/sitemap.xml")
async def serve_sitemap_xml(request: Request):
    sitemap_path = BASE_DIR / "sitemap.xml"
    if sitemap_path.exists():
        content = sitemap_path.read_text(encoding="utf-8")
        site_base = os.getenv("SITE_BASE_URL", "").rstrip("/")
        if site_base and site_base != "https://pnglike.com":
            content = content.replace("https://pnglike.com", site_base)
        return Response(content=content, media_type="application/xml; charset=utf-8")

    site_base = os.getenv("SITE_BASE_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    blog_data = await run_in_threadpool(db_manager.list_blog_posts, True, None, None, False, 100, 0)
    blog_urls_xml = ""
    for post in blog_data.get("posts", []):
        lastmod = (post.get("updated_at") or post.get("created_at") or "2026-11-07")[:10]
        blog_urls_xml += (
            f"  <url>\n"
            f"    <loc>{site_base}/blog/{post['slug']}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>weekly</changefreq>\n"
            f"    <priority>0.8</priority>\n"
            f"  </url>\n"
        )

    static_pages = [
        ("/", "daily", "1.0"),
        ("/blog", "daily", "0.9"),
        ("/about", "monthly", "0.8"),
        ("/faq", "weekly", "0.8"),
        ("/contact", "monthly", "0.7"),
        ("/privacy", "monthly", "0.5"),
        ("/terms", "monthly", "0.5"),
        ("/cookies", "monthly", "0.5"),
    ]
    pages_xml = ""
    for path, changefreq, priority in static_pages:
        pages_xml += (
            f"  <url>\n"
            f"    <loc>{site_base}{path}</loc>\n"
            f"    <lastmod>2026-11-07</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f'    <xhtml:link rel="alternate" hreflang="x-default" href="{site_base}{path}" />\n'
            f'    <xhtml:link rel="alternate" hreflang="en" href="{site_base}{path}" />\n'
            f"  </url>\n"
        )

    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
{pages_xml}{blog_urls_xml}</urlset>"""
    return Response(content=sitemap_xml, media_type="application/xml; charset=utf-8")


@app.get("/llms.txt")
async def serve_llms_txt():
    blog_data = await run_in_threadpool(db_manager.list_blog_posts, True, None, None, False, 20, 0)
    blog_lines = "\n".join(
        f"- [{p['title']}]({SITE_BASE_URL}/blog/{p['slug']}): {p['excerpt']}"
        for p in blog_data.get("posts", [])
    )
    llms_md = f"""# PngLike — 9-in-1 AI Image Suite & Neural Background Remover (Powered by Div Sri)

> Single-page AI image processing web application Powered by Div Sri, built on ONNX Runtime (U2-Net, IS-Net, Silueta), Pillow/NumPy computer vision pipelines, and a persistent MySQL telemetry & blog CMS backend.

## Core 9 Working IMAGE Tools
1. **Image Editor (`#image-editor`)**: Multi-parameter color grading (brightness, contrast, saturation, sharpness, warmth, blur), crop ratios (`1:1`, `16:9`, `9:16`, `4:3`), 90/180/270 rotation, and 1-click artistic filter presets.
2. **Image Upscaler (`#image-upscaler`)**: 2x and 4x Lanczos super-resolution upscaling with bilateral noise suppression and unsharp edge enhancement.
3. **Image Extender (`#image-extender`)**: Context-aware AI outpainting, seamless reflection mirror, and frosted glass canvas expansion (`16:9`, `9:16`, `1:1`, `4:3`, `21:9`).
4. **Variations (`#variations`)**: Multi-style visual restyling (Cyberpunk Neon, Synthwave Sunset, Vintage Film 70s, Anime Cel-Shaded, Sketch & Ink, Watercolor Art, Golden Hour, Pop Art).
5. **Cinematic Shot (`#cinematic-shot`)**: AI foreground subject segmentation + optical depth-of-field bokeh, Hollywood LUT color grading, anamorphic lens flare, film grain, and 2.39:1 letterbox bars.
6. **Background Remover (`#bg-remover`)**: High-precision U2-Net, U2-Netp, Human Seg, IS-Net General, and Anime ONNX segmentation with alpha matting and custom studio backdrops.
7. **Skin Enhancer (`#skin-enhancer`)**: Frequency-separated YCbCr skin-tone detection, bilateral blemish smoothing, high-pass pore & eye texture preservation, and warm portrait radiance.
8. **Relight (`#relight`)**: AI foreground isolation with dual-source 3D studio directional lighting (Left Key, Right Rim, Top Halo, Bottom Dramatic, Dual Neon Split) and ambient background dimming.
9. **Change Camera (`#change-camera`)**: 3D projective homography perspective warp (Tilt Up, Tilt Down, Pan Left, Pan Right, Dutch Roll) and optical lens distortion (24mm Wide, 16mm Fisheye, 85mm Telephoto).

## Official Blog & Tutorials (`/blog`)
{blog_lines}

## Company & Legal Resources
- [About Us]({SITE_BASE_URL}/about): Brand mission, creator spotlight (Div Sri), AI architecture, and local ONNX runtime pipeline.
- [FAQ & Knowledge Base]({SITE_BASE_URL}/faq): Answers to common questions regarding neural cutouts, guest vs registered quotas, and privacy.
- [Contact Support]({SITE_BASE_URL}/contact): Direct assistance, bug reporting, and feedback submissions.
- [Privacy Policy]({SITE_BASE_URL}/privacy): In-memory processing guarantees, zero data selling, GDPR & CCPA rights.
- [Terms of Service]({SITE_BASE_URL}/terms): Fair use policy, 100% intellectual property ownership of user creations, usage limits.
- [Cookie Policy]({SITE_BASE_URL}/cookies): Local storage keys, session tokens, and dark mode preferences.

## API Endpoints
- `GET /api/tools`: Lists the 9 active IMAGE tools and metadata.
- `POST /api/tools/process`: Executes any of the 9 IMAGE tools on an uploaded image file and logs telemetry to MySQL.
- `POST /api/remove`: Dedicated background removal endpoint supporting alpha matting and custom backdrops.
- `POST /api/contact`: Public support & inquiry submission endpoint.
- `GET /api/user/quota`: Real-time daily quota and tier limits for guests and registered users.
- `GET /api/blog`: Lists published blog articles, categories, and tutorials.
- `GET /api/site-config`: Public CMS configuration, enabled models, and sample gallery items.
"""
    return Response(content=llms_md, media_type="text/markdown; charset=utf-8")


@app.get("/{key_file}.txt")
async def serve_indexnow_key_txt(key_file: str):
    """Serve dynamic IndexNow host verification key file for Bing, Copilot, Naver, and Yandex."""
    indexnow_key = os.getenv("INDEXNOW_KEY", "").strip()
    if indexnow_key and key_file == indexnow_key:
        return Response(content=indexnow_key, media_type="text/plain; charset=utf-8")
    raise HTTPException(status_code=404, detail="File not found")


# --------------------------------------------------------
# STATIC & HTML ROUTES
# --------------------------------------------------------
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/blog")
@app.get("/blog.html")
@app.get("/blog/{slug}")
async def serve_blog_page(slug: Optional[str] = None):
    blog_file = BASE_DIR / "static" / "blog.html"
    if not blog_file.exists():
        raise HTTPException(status_code=404, detail="Blog UI file not found.")

    if slug and slug.strip():
        clean_slug = slug.strip()
        try:
            post = db_manager.get_blog_post_by_slug(clean_slug, increment_views=False, published_only=True)
            if post:
                html = blog_file.read_text(encoding="utf-8")
                raw_title = (post.get('meta_title') or post.get('title') or "AI Image Tutorial").strip()
                clean_base_title = re.sub(r'[\-—|]\s*PngLike Blog.*$', '', raw_title, flags=re.IGNORECASE).strip()
                post_title = f"{clean_base_title} — PngLike Blog | Powered by Div Sri"
                post_desc = post.get('meta_description') or post.get('excerpt') or "PngLike AI Studio deep-dive tutorial."
                post_url = f"https://pnglike.com/blog/{clean_slug}"
                raw_cover = post.get('cover_image') or "/static/brand/logo-dark-text.svg"
                cover_url = raw_cover if raw_cover.startswith("http") else f"https://pnglike.com{raw_cover}"
                author_name = post.get('author') or "Div Sri"
                pub_date = str(post.get('created_at') or "2026-11-06")
                mod_date = str(post.get('updated_at') or pub_date)

                # Replace Title & Canonical
                html = re.sub(r'<title id="pageMetaTitle">.*?</title>', lambda m: f'<title id="pageMetaTitle">{post_title}</title>', html, count=1)
                html = re.sub(r'<link id="pageCanonicalUrl" rel="canonical" href=".*?">', lambda m: f'<link id="pageCanonicalUrl" rel="canonical" href="{post_url}">', html, count=1)
                html = re.sub(r'<meta id="pageMetaDescription" name="description" content=".*?">', lambda m: f'<meta id="pageMetaDescription" name="description" content="{post_desc}">', html, count=1)

                # Replace OpenGraph
                html = re.sub(r'<meta id="ogTitle" property="og:title" content=".*?">', lambda m: f'<meta id="ogTitle" property="og:title" content="{post_title}">', html, count=1)
                html = re.sub(r'<meta id="ogDescription" property="og:description" content=".*?">', lambda m: f'<meta id="ogDescription" property="og:description" content="{post_desc}">', html, count=1)
                html = re.sub(r'<meta id="ogUrl" property="og:url" content=".*?">', lambda m: f'<meta id="ogUrl" property="og:url" content="{post_url}">', html, count=1)
                html = re.sub(r'<meta id="ogImage" property="og:image" content=".*?">', lambda m: f'<meta id="ogImage" property="og:image" content="{cover_url}">', html, count=1)

                # Replace Twitter Cards
                html = re.sub(r'<meta id="twitterTitle" name="twitter:title" content=".*?">', lambda m: f'<meta id="twitterTitle" name="twitter:title" content="{post_title}">', html, count=1)
                html = re.sub(r'<meta id="twitterDescription" name="twitter:description" content=".*?">', lambda m: f'<meta id="twitterDescription" name="twitter:description" content="{post_desc}">', html, count=1)
                html = re.sub(r'<meta id="twitterImage" name="twitter:image" content=".*?">', lambda m: f'<meta id="twitterImage" name="twitter:image" content="{cover_url}">', html, count=1)

                # Inject Rich BlogPosting Schema
                article_schema = {
                    "@context": "https://schema.org",
                    "@graph": [
                        {
                            "@type": "Organization",
                            "@id": "https://pnglike.com/#organization",
                            "name": "PngLike — Powered by Div Sri",
                            "url": "https://pnglike.com/",
                            "logo": {
                                "@type": "ImageObject",
                                "url": "https://pnglike.com/static/brand/logo-icon.svg"
                            }
                        },
                        {
                            "@type": "BlogPosting",
                            "@id": f"{post_url}#article",
                            "headline": post.get('title'),
                            "description": post_desc,
                            "image": cover_url,
                            "author": {
                                "@type": "Person",
                                "name": author_name
                            },
                            "publisher": {
                                "@id": "https://pnglike.com/#organization"
                            },
                            "datePublished": pub_date,
                            "dateModified": mod_date,
                            "mainEntityOfPage": {
                                "@type": "WebPage",
                                "@id": post_url
                            }
                        },
                        {
                            "@type": "BreadcrumbList",
                            "itemListElement": [
                                {
                                    "@type": "ListItem",
                                    "position": 1,
                                    "name": "Home",
                                    "item": "https://pnglike.com/"
                                },
                                {
                                    "@type": "ListItem",
                                    "position": 2,
                                    "name": "Blog",
                                    "item": "https://pnglike.com/blog"
                                },
                                {
                                    "@type": "ListItem",
                                    "position": 3,
                                    "name": post.get('title'),
                                    "item": post_url
                                }
                            ]
                        }
                    ]
                }
                schema_json = json.dumps(article_schema, indent=2)
                replacement_script = f'<script id="blogSchemaJsonLd" type="application/ld+json">\n{schema_json}\n  </script>'
                html = re.sub(
                    r'<script id="blogSchemaJsonLd" type="application/ld\+json">.*?</script>',
                    lambda m: replacement_script,
                    html,
                    flags=re.DOTALL,
                    count=1
                )
                return Response(content=html, media_type="text/html; charset=utf-8")
        except Exception as e:
            logger.warning(f"Error preparing dynamic blog SEO for slug '{clean_slug}': {e}")

    return FileResponse(blog_file)


@app.get("/dashboard")
@app.get("/dashboard.html")
@app.get("/login")
@app.get("/register")
@app.get("/verify")
async def serve_user_dashboard():
    dashboard_file = BASE_DIR / "static" / "dashboard.html"
    if dashboard_file.exists():
        return FileResponse(dashboard_file)
    raise HTTPException(status_code=404, detail="User Dashboard UI file not found.")


@app.get("/admin")
@app.get("/admin.html")
async def serve_admin_dashboard():
    admin_file = BASE_DIR / "static" / "admin.html"
    if admin_file.exists():
        return FileResponse(admin_file)
    raise HTTPException(status_code=404, detail="Admin UI file not found.")


@app.get("/privacy")
@app.get("/privacy.html")
async def serve_privacy_page():
    privacy_file = BASE_DIR / "static" / "privacy.html"
    if privacy_file.exists():
        return FileResponse(privacy_file)
    raise HTTPException(status_code=404, detail="Privacy Policy UI file not found.")


@app.get("/terms")
@app.get("/terms.html")
async def serve_terms_page():
    terms_file = BASE_DIR / "static" / "terms.html"
    if terms_file.exists():
        return FileResponse(terms_file)
    raise HTTPException(status_code=404, detail="Terms of Service UI file not found.")


@app.get("/cookies")
@app.get("/cookies.html")
async def serve_cookies_page():
    cookies_file = BASE_DIR / "static" / "cookies.html"
    if cookies_file.exists():
        return FileResponse(cookies_file)
    raise HTTPException(status_code=404, detail="Cookie Policy UI file not found.")


@app.get("/about")
@app.get("/about.html")
async def serve_about_page():
    about_file = BASE_DIR / "static" / "about.html"
    if about_file.exists():
        return FileResponse(about_file)
    raise HTTPException(status_code=404, detail="About UI file not found.")


@app.get("/contact")
@app.get("/contact.html")
async def serve_contact_page():
    contact_file = BASE_DIR / "static" / "contact.html"
    if contact_file.exists():
        return FileResponse(contact_file)
    raise HTTPException(status_code=404, detail="Contact UI file not found.")


@app.get("/faq")
@app.get("/faq.html")
async def serve_faq_page():
    faq_file = BASE_DIR / "static" / "faq.html"
    if faq_file.exists():
        return FileResponse(faq_file)
    raise HTTPException(status_code=404, detail="FAQ UI file not found.")


@app.get("/")
@app.get("/index.html")
async def serve_index():
    index_file = BASE_DIR / "static" / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "PngLike API is operational. Static UI not found."}


if __name__ == "__main__":
    import uvicorn

    print(f"Starting PngLike on http://127.0.0.1:7860 (Admin Portal: http://127.0.0.1:7860/admin)...")
    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="info")
