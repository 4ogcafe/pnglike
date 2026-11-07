import hashlib
import math
import os
import re
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import quote_plus

import pymysql
from dotenv import load_dotenv, set_key
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Boolean,
    Float,
    DateTime,
    Text,
    func,
    desc,
    or_,
    text,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

Base = declarative_base()

DEFAULT_SITE_SETTINGS: Dict[str, str] = {
    "site_title": "PngLike",
    "site_tagline": "9-in-1 AI Image Suite & Background Remover",
    "site_badge": "AI Powered",
    "hero_title": "Remove Image Backgrounds",
    "hero_highlight": "Instantly with AI",
    "hero_subtitle": "High precision neural network cutout for portraits, products, animals, and graphics. 100% offline and private on your machine.",
    "announcement_enabled": "false",
    "announcement_text": "New U2-Net High-Precision Model & MySQL Backend Active!",
    "footer_text": "Powered by Div Sri • All AI processing is done locally on your device.",
    "default_model": "u2net",
    "enabled_models": "u2net,u2netp,u2net_human_seg,isnet-general-use,isnet-anime,silueta",
    "default_tool": "bg-remover",
    "enabled_tools": "bg-remover,image-editor,skin-enhancer,image-upscaler,image-extender,variations,cinematic-shot,relight,change-camera",
    "enable_batch_mode": "true",
    "enable_history_tab": "true",
    "enable_alpha_matting": "true",
    "enable_custom_backdrop": "true",
    "max_upload_mb": "25",
    "max_batch_files": "50",
    "guest_daily_limit": "3",
    "registered_daily_limit": "10",
    "registered_cycle_limit": "10",
    "registered_reset_minutes": "30",
    "guest_max_mb": "10",
    "registered_max_mb": "50",
    "guest_restricted_tools": "image-upscaler,image-extender,variations,cinematic-shot,relight,change-camera",
    "maintenance_mode": "false",
    "maintenance_message": "PngLike is currently undergoing scheduled maintenance. Please check back shortly.",
    "smtp_enabled": "true",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from_name": "PngLike AI Studio",
    "smtp_from_email": "",
    "smtp_use_tls": "true",
    "indexnow_enabled": "true",
    "indexnow_key": "950cf4f1e8b64e1f90b053abbfd50843",
    "indexnow_host": "pnglike.com",
    "indexnow_key_location": "https://pnglike.com/950cf4f1e8b64e1f90b053abbfd50843.txt",
    "indexnow_auto_submit_blog": "true",
    "indexnow_auto_submit_cms": "true",
}


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt$hash string."""
    if "$" not in stored_hash:
        return False
    salt, _ = stored_hash.split("$", 1)
    return secrets.compare_digest(hash_password(password, salt), stored_hash)


# --------------------------------------------------------
# ADVANCED REGISTRATION SECURITY & VALIDATION RULES
# --------------------------------------------------------
DISPOSABLE_EMAIL_DOMAINS = {
    "tempmail.com", "10minutemail.com", "mailinator.com", "guerrillamail.com",
    "guerrillamailblock.com", "yopmail.com", "trashmail.com", "sharklasers.com",
    "getairmail.com", "throwawaymail.com", "dispostable.com", "temp-mail.org",
    "fakemailgenerator.com", "crazymailing.com", "maildrop.cc", "nada.ltd",
    "inboxkitten.com", "mohmal.com", "emailondeck.com", "generator.email",
    "mytemp.email", "burnermail.io", "tempail.com", "disposablemail.com",
    "trashmail.net", "dropmail.me", "fakemail.net", "harakirimail.com",
    "spam4.me", "grr.la", "guerrillamail.biz", "guerrillamail.org",
    "mailcatch.com", "mytempemail.com", "trashmail.io", "getnada.com",
    "temporarymail.com", "throwaway.email", "mohmal.im", "armyspy.com",
    "cuvox.de", "dayrep.com", "fleckens.hu", "gustr.com", "jourrapide.com",
    "rhyta.com", "superrito.com", "teleworm.us", "tinemail.com",
}

RESERVED_USERNAMES = {
    "admin", "administrator", "root", "api", "system", "support", "help",
    "security", "staff", "moderator", "pnglike", "null", "undefined",
    "login", "register", "dashboard", "blog", "status", "webhook",
    "superuser", "user", "auth", "official", "owner", "master",
    "postmaster", "webmaster", "operator", "billing", "service",
    "guest", "anonymous", "demo", "tester", "test", "account",
}

COMMON_WEAK_PASSWORDS = {
    "password", "12345678", "123456789", "qwertyui", "admin123",
    "welcome1", "letmein1", "password123", "iloveyou", "pass1234",
    "user1234", "12345678a", "abcdefgh", "changeme",
}


def validate_registration_email(email: str) -> str:
    """
    Strict email integrity verification:
    1. Rejects sub-addressing / plus-addressing (e.g. name+1@domain.com, tag+test@gmail.com).
    2. Rejects disposable / temporary / burner domains.
    3. Rejects dot tricks (leading/trailing dots, consecutive dots).
    4. Validates RFC 5322 structure, valid public TLD, and max length.
    """
    clean = (email or "").strip().lower()
    if not clean:
        raise ValueError("Email address cannot be empty.")

    if len(clean) > 254:
        raise ValueError("Email address exceeds maximum length of 254 characters.")

    if "@" not in clean:
        raise ValueError("Invalid email format: missing '@' symbol.")

    parts = clean.split("@")
    if len(parts) != 2:
        raise ValueError("Invalid email format: email must contain exactly one '@' symbol.")

    local_part, domain_part = parts[0], parts[1]

    if not local_part or not domain_part:
        raise ValueError("Invalid email format: username or domain part is missing.")

    if len(local_part) > 64:
        raise ValueError("Email username part exceeds maximum length of 64 characters.")

    # 1. Reject plus-addressing / email aliases / sub-addressing (e.g. name+1@domain.com)
    if "+" in local_part or "%2b" in local_part:
        raise ValueError(
            "Email aliases or sub-addressing (e.g. name+tag@domain.com) are prohibited for security and account integrity. "
            "Please register using your primary standard email address."
        )

    # 2. Reject dot tricks & malformed local parts
    if local_part.startswith(".") or local_part.endswith("."):
        raise ValueError("Email address username cannot start or end with a period.")
    if ".." in clean:
        raise ValueError("Email address cannot contain consecutive periods ('..').")

    # Local-part allowed characters: alphanumeric, dots, underscores, hyphens
    if not re.match(r"^[a-zA-Z0-9_.-]+$", local_part):
        raise ValueError("Email username contains invalid characters.")

    # 3. Reject disposable & temporary burner email domains
    if domain_part in DISPOSABLE_EMAIL_DOMAINS:
        raise ValueError(
            f"Disposable and temporary email addresses ('@{domain_part}') are not permitted. "
            "Please register using a permanent email address (e.g. Gmail, Outlook, Yahoo, or your custom domain)."
        )

    # 4. Domain & TLD structure
    if "." not in domain_part:
        raise ValueError("Email domain must contain a valid top-level domain (e.g. .com, .org).")

    domain_labels = domain_part.split(".")
    for label in domain_labels:
        if not label:
            raise ValueError("Email domain contains empty segment.")
        if not re.match(r"^[a-z0-9-]+$", label):
            raise ValueError(f"Email domain segment '{label}' contains invalid characters.")
        if label.startswith("-") or label.endswith("-"):
            raise ValueError("Email domain segments cannot start or end with a hyphen.")

    tld = domain_labels[-1]
    if len(tld) < 2 or not tld.isalpha():
        raise ValueError("Email top-level domain is invalid.")

    invalid_tlds = {"local", "test", "localhost", "invalid", "example", "onion", "lan", "internal"}
    if tld in invalid_tlds:
        raise ValueError(f"Domain extension '.{tld}' is not allowed for public registration.")

    return clean


def validate_registration_username(username: str) -> str:
    """
    Validate username security rules:
    1. Length between 3 and 30 characters.
    2. Alphanumeric, underscores, hyphens, and dots.
    3. Must start and end with an alphanumeric character.
    4. Prohibits consecutive symbols.
    5. Rejects reserved system and administrative usernames.
    """
    clean = (username or "").strip()
    if not clean:
        raise ValueError("Username cannot be empty.")

    if len(clean) < 3 or len(clean) > 30:
        raise ValueError("Username must be between 3 and 30 characters in length.")

    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{1,28}[a-zA-Z0-9]$", clean):
        raise ValueError(
            "Username must start and end with a letter or digit and contain only letters, numbers, underscores, hyphens, or dots."
        )

    if ".." in clean or "__" in clean or "--" in clean:
        raise ValueError("Username cannot contain consecutive punctuation symbols ('..', '__', '--').")

    lower = clean.lower()
    if lower in RESERVED_USERNAMES:
        raise ValueError(f"The username '{clean}' is reserved for system use and cannot be registered.")

    return lower


def validate_registration_password(password: str, username: str = "", email: str = "") -> None:
    """
    Validate strong password requirements:
    1. Minimum 8 characters, max 128 characters.
    2. Must include uppercase, lowercase, number, and special character.
    3. Rejects common easily-guessed dictionary passwords.
    4. Prohibits containing the username or email local-part.
    """
    if not password:
        raise ValueError("Password cannot be empty.")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters in length.")

    if len(password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")

    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter (A-Z).")

    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter (a-z).")

    if not re.search(r"[0-9]", password):
        raise ValueError("Password must contain at least one numerical digit (0-9).")

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>\-_+=\[\]\\/`~;']", password):
        raise ValueError("Password must contain at least one special character (!@#$%^&*()_+-=[]{}...).")

    if password.lower() in COMMON_WEAK_PASSWORDS:
        raise ValueError("The provided password is too common. Please choose a stronger, unique password.")

    if username and len(username) >= 3 and username.lower() in password.lower():
        raise ValueError("Password cannot contain your username.")

    if email and "@" in email:
        local_email = email.split("@")[0].lower()
        if len(local_email) >= 3 and local_email in password.lower():
            raise ValueError("Password cannot contain your email username.")


class RemovalJob(Base):
    """SQLAlchemy ORM model for the MySQL `removal_jobs` table."""

    __tablename__ = "removal_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_uuid = Column(String(36), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    original_filename = Column(String(255), nullable=False)
    output_filename = Column(String(255), nullable=False)
    output_url = Column(String(512), nullable=False)
    model_used = Column(String(64), nullable=False, default="u2net", index=True)
    alpha_matting = Column(Boolean, nullable=False, default=False)
    af_threshold = Column(Integer, nullable=False, default=240)
    ab_threshold = Column(Integer, nullable=False, default=10)
    ae_size = Column(Integer, nullable=False, default=10)
    only_mask = Column(Boolean, nullable=False, default=False)
    post_process_mask = Column(Boolean, nullable=False, default=False)
    bg_color = Column(String(32), nullable=True)
    output_format = Column(String(16), nullable=False, default="png")
    original_width = Column(Integer, nullable=False, default=0)
    original_height = Column(Integer, nullable=False, default=0)
    output_size_bytes = Column(Integer, nullable=False, default=0)
    process_time_ms = Column(Float, nullable=False, default=0.0)
    batch_id = Column(String(36), nullable=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    client_ip = Column(String(64), nullable=True, index=True)
    status = Column(String(32), nullable=False, default="completed")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "job_uuid": self.job_uuid,
            "original_filename": self.original_filename,
            "output_filename": self.output_filename,
            "output_url": self.output_url,
            "model_used": self.model_used,
            "alpha_matting": self.alpha_matting,
            "af_threshold": self.af_threshold,
            "ab_threshold": self.ab_threshold,
            "ae_size": self.ae_size,
            "only_mask": self.only_mask,
            "post_process_mask": self.post_process_mask,
            "bg_color": self.bg_color,
            "output_format": self.output_format,
            "original_width": self.original_width,
            "original_height": self.original_height,
            "output_size_bytes": self.output_size_bytes,
            "process_time_ms": round(self.process_time_ms, 2),
            "batch_id": self.batch_id,
            "user_id": self.user_id,
            "client_ip": self.client_ip,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class PresetConfig(Base):
    """SQLAlchemy ORM model for the MySQL `preset_configs` table."""

    __tablename__ = "preset_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False)
    model_used = Column(String(64), nullable=False, default="u2net")
    alpha_matting = Column(Boolean, nullable=False, default=False)
    af_threshold = Column(Integer, nullable=False, default=240)
    ab_threshold = Column(Integer, nullable=False, default=10)
    ae_size = Column(Integer, nullable=False, default=10)
    post_process_mask = Column(Boolean, nullable=False, default=False)
    bg_mode = Column(String(32), nullable=False, default="transparent")
    bg_value = Column(String(255), nullable=True)
    export_format = Column(String(16), nullable=False, default="png")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "model_used": self.model_used,
            "alpha_matting": self.alpha_matting,
            "af_threshold": self.af_threshold,
            "ab_threshold": self.ab_threshold,
            "ae_size": self.ae_size,
            "post_process_mask": self.post_process_mask,
            "bg_mode": self.bg_mode,
            "bg_value": self.bg_value,
            "export_format": self.export_format,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class SiteSetting(Base):
    """SQLAlchemy ORM model for the MySQL `site_settings` table (Frontend CMS & feature flags)."""

    __tablename__ = "site_settings"

    setting_key = Column(String(128), primary_key=True)
    setting_value = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class SampleImage(Base):
    """SQLAlchemy ORM model for the MySQL `sample_images` table."""

    __tablename__ = "sample_images"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False, default="Product")
    filename = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.title,
            "title": self.title,
            "category": self.category,
            "filename": self.filename,
            "url": self.url,
            "is_active": self.is_active,
            "sort_order": self.sort_order,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class AdminUser(Base):
    """SQLAlchemy ORM model for the MySQL `admin_users` table."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False)
    full_name = Column(String(128), nullable=False, default="System Administrator")
    email = Column(String(128), nullable=False, default="")
    avatar_url = Column(String(512), nullable=True, default="")
    avatar_color = Column(String(32), nullable=False, default="#4f46e5")
    phone = Column(String(32), nullable=False, default="")
    designation = Column(String(128), nullable=False, default="Lead AI Systems Architect")
    department = Column(String(128), nullable=False, default="DevOps & AI Infrastructure")
    location = Column(String(128), nullable=False, default="Tokyo, Japan")
    bio = Column(Text, nullable=False, default="")
    timezone_pref = Column(String(64), nullable=False, default="Asia/Tokyo (UTC+9)")
    email_notifications = Column(Boolean, nullable=False, default=True)
    security_alerts = Column(Boolean, nullable=False, default=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(32), nullable=False, default="superadmin")
    last_login = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name or self.username,
            "email": self.email or "",
            "avatar_url": self.avatar_url or "",
            "avatar_color": self.avatar_color or "#4f46e5",
            "phone": self.phone or "",
            "designation": self.designation or "Lead AI Systems Architect",
            "department": self.department or "DevOps & AI Infrastructure",
            "location": self.location or "Tokyo, Japan",
            "bio": self.bio or "",
            "timezone_pref": self.timezone_pref or "Asia/Tokyo (UTC+9)",
            "email_notifications": bool(self.email_notifications),
            "security_alerts": bool(self.security_alerts),
            "role": self.role or "superadmin",
            "last_login": self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None,
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


def slugify_text(text: str) -> str:
    """Convert a blog post title or slug into a clean URL-safe slug."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", (text or "").strip().lower())
    slug = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    return slug or f"post-{uuid.uuid4().hex[:8]}"


def estimate_read_time(content: str) -> int:
    """Estimate reading time in minutes based on ~200 words per minute."""
    plain = re.sub(r"<[^>]+>", " ", content or "")
    words = len(plain.split())
    return max(1, round(words / 180))


class BlogPost(Base):
    """SQLAlchemy ORM model for the MySQL `blog_posts` table."""

    __tablename__ = "blog_posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    excerpt = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(64), nullable=False, default="AI Tutorials", index=True)
    tags = Column(String(255), nullable=False, default="")
    cover_image = Column(String(512), nullable=True)
    author = Column(String(128), nullable=False, default="Div Sri")
    read_time_minutes = Column(Integer, nullable=False, default=4)
    is_published = Column(Boolean, nullable=False, default=True, index=True)
    is_featured = Column(Boolean, nullable=False, default=False)
    views_count = Column(Integer, nullable=False, default=0)
    meta_title = Column(String(255), nullable=True)
    meta_description = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def to_dict(self, include_content: bool = True) -> Dict[str, Any]:
        tag_list = [t.strip() for t in (self.tags or "").split(",") if t.strip()]
        data = {
            "id": self.id,
            "title": self.title,
            "slug": self.slug,
            "excerpt": self.excerpt,
            "category": self.category,
            "tags": self.tags or "",
            "tag_list": tag_list,
            "cover_image": self.cover_image or "/static/samples/portrait_person.jpg",
            "author": self.author or "Div Sri",
            "read_time_minutes": self.read_time_minutes or 4,
            "is_published": bool(self.is_published),
            "is_featured": bool(self.is_featured),
            "views_count": int(self.views_count or 0),
            "meta_title": self.meta_title or self.title,
            "meta_description": self.meta_description or self.excerpt,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
            "published_date": self.created_at.strftime("%b %d, %Y") if self.created_at else "Nov 06, 2026",
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S") if self.updated_at else None,
        }
        if include_content:
            data["content"] = self.content
        return data


class AppUser(Base):
    """SQLAlchemy ORM model for the MySQL `users` table (User Login & User Dashboard)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False, default="")
    password_hash = Column(String(255), nullable=False)
    avatar_color = Column(String(32), nullable=False, default="#3b82f6")
    plan_tier = Column(String(32), nullable=False, default="Pro Studio")
    bio = Column(String(255), nullable=False, default="")
    phone = Column(String(32), nullable=True, default="")
    country = Column(String(64), nullable=True, default="")
    preferred_format = Column(String(16), nullable=False, default="png")
    dark_mode_pref = Column(String(16), nullable=False, default="system")
    api_key = Column(String(64), unique=True, nullable=False, index=True, default=lambda: f"pnglike_{secrets.token_hex(20)}")
    is_active = Column(Boolean, nullable=False, default=False)
    email_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(128), nullable=True, index=True)
    verification_code = Column(String(16), nullable=True, index=True)
    verification_expires_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    jobs_count = Column(Integer, nullable=False, default=0)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self, include_api_key: bool = False, include_verification: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name or self.username,
            "avatar_color": self.avatar_color or "#3b82f6",
            "plan_tier": self.plan_tier or "Pro Studio",
            "bio": self.bio or "",
            "phone": self.phone or "",
            "country": self.country or "",
            "preferred_format": self.preferred_format or "png",
            "dark_mode_pref": self.dark_mode_pref or "system",
            "is_active": bool(self.is_active),
            "email_verified": bool(self.email_verified),
            "verified_at": self.verified_at.strftime("%Y-%m-%d %H:%M:%S") if self.verified_at else None,
            "jobs_count": int(self.jobs_count or 0),
            "last_login": self.last_login.strftime("%Y-%m-%d %H:%M:%S") if self.last_login else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }
        if include_api_key:
            data["api_key"] = self.api_key
        if include_verification:
            data["verification_code"] = self.verification_code
            data["verification_token"] = self.verification_token
        return data


class ContactMessage(Base):
    """SQLAlchemy ORM model for user support tickets, feedback, and inquiries."""

    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, index=True)
    subject = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    client_ip = Column(String(64), nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "subject": self.subject,
            "message": self.message,
            "client_ip": self.client_ip,
            "is_read": bool(self.is_read),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class UserSession(Base):
    """Persistent user session store (replaces volatile in-memory dictionary)."""

    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "user_id": self.user_id,
            "expires_at": self.expires_at.strftime("%Y-%m-%d %H:%M:%S") if self.expires_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class AdminSession(Base):
    """Persistent admin session store (replaces volatile in-memory dictionary)."""

    __tablename__ = "admin_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(128), unique=True, nullable=False, index=True)
    admin_id = Column(Integer, ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "token": self.token,
            "admin_id": self.admin_id,
            "expires_at": self.expires_at.strftime("%Y-%m-%d %H:%M:%S") if self.expires_at else None,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else None,
        }


class IndexNowSubmission(Base):
    """Persistent telemetry log of IndexNow real-time search engine submissions."""

    __tablename__ = "indexnow_submissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    submitted_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), index=True)
    host = Column(String(255), default="pnglike.com", nullable=False)
    key = Column(String(255), nullable=False)
    urls_count = Column(Integer, default=1, nullable=False)
    urls_json = Column(Text, nullable=False)
    endpoint = Column(String(255), default="https://api.indexnow.org/indexnow", nullable=False)
    status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    status = Column(String(50), default="success", nullable=False)
    triggered_by = Column(String(100), default="manual", nullable=False)

    def to_dict(self) -> Dict[str, Any]:
        import json
        urls = []
        try:
            urls = json.loads(self.urls_json) if self.urls_json else []
        except Exception:
            urls = [self.urls_json] if self.urls_json else []

        return {
            "id": self.id,
            "submitted_at": self.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if self.submitted_at else None,
            "host": self.host,
            "key": self.key,
            "urls_count": self.urls_count,
            "urls": urls,
            "endpoint": self.endpoint,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "status": self.status,
            "triggered_by": self.triggered_by,
        }


class DatabaseManager:
    """Manages the MySQL database connection, auto-provisioning, and ORM operations."""

    def __init__(self):
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "rembg_studio")

        self.engine = None
        self.SessionLocal = None
        self.is_mysql_connected = False
        self.active_dialect = "mysql"
        self.last_error: Optional[str] = None

        self.initialize_connection()

    def build_mysql_url(self) -> str:
        encoded_user = quote_plus(self.user)
        encoded_pass = quote_plus(self.password)
        return (
            f"mysql+pymysql://{encoded_user}:{encoded_pass}"
            f"@{self.host}:{self.port}/{self.database}?charset=utf8mb4"
        )

    def _ensure_mysql_database_exists(self) -> None:
        if not re.match(r"^[a-zA-Z0-9_]{1,64}$", self.database):
            raise ValueError("Invalid database name: must be alphanumeric with underscores, max 64 characters.")
        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            charset="utf8mb4",
            connect_timeout=3,
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{self.database}` "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                )
            conn.commit()
        finally:
            conn.close()

    def _migrate_schema_columns(self) -> None:
        """Ensure newly added columns exist on legacy tables."""
        if not self.engine:
            return
        # 1. Migrate removal_jobs.user_id and client_ip
        for col_name, col_type in [("user_id", "INT NULL"), ("client_ip", "VARCHAR(64) NULL")]:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(f"SELECT {col_name} FROM removal_jobs LIMIT 1"))
            except Exception:
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE removal_jobs ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass

        # 2. Migrate users table verification columns
        user_cols = [
            ("email_verified", "BOOLEAN NOT NULL DEFAULT FALSE"),
            ("verification_token", "VARCHAR(128) NULL"),
            ("verification_code", "VARCHAR(16) NULL"),
            ("verification_expires_at", "DATETIME NULL"),
            ("verified_at", "DATETIME NULL"),
            ("bio", "VARCHAR(255) NOT NULL DEFAULT ''"),
            ("phone", "VARCHAR(32) NULL DEFAULT ''"),
            ("country", "VARCHAR(64) NULL DEFAULT ''"),
            ("preferred_format", "VARCHAR(16) NOT NULL DEFAULT 'png'"),
            ("dark_mode_pref", "VARCHAR(16) NOT NULL DEFAULT 'system'"),
        ]
        for col_name, col_type in user_cols:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(f"SELECT {col_name} FROM users LIMIT 1"))
            except Exception:
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass

        # 3. Migrate admin_users profile columns
        admin_cols = [
            ("full_name", "VARCHAR(128) NOT NULL DEFAULT 'System Administrator'"),
            ("email", "VARCHAR(128) NOT NULL DEFAULT ''"),
            ("avatar_url", "VARCHAR(512) NULL DEFAULT ''"),
            ("avatar_color", "VARCHAR(32) NOT NULL DEFAULT '#4f46e5'"),
            ("phone", "VARCHAR(32) NOT NULL DEFAULT ''"),
            ("designation", "VARCHAR(128) NOT NULL DEFAULT 'Lead AI Systems Architect'"),
            ("department", "VARCHAR(128) NOT NULL DEFAULT 'DevOps & AI Infrastructure'"),
            ("location", "VARCHAR(128) NOT NULL DEFAULT 'Tokyo, Japan'"),
            ("bio", "TEXT NULL"),
            ("timezone_pref", "VARCHAR(64) NOT NULL DEFAULT 'Asia/Tokyo (UTC+9)'"),
            ("email_notifications", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("security_alerts", "BOOLEAN NOT NULL DEFAULT TRUE"),
            ("updated_at", "DATETIME NULL"),
        ]
        for col_name, col_type in admin_cols:
            try:
                with self.engine.connect() as conn:
                    conn.execute(text(f"SELECT {col_name} FROM admin_users LIMIT 1"))
            except Exception:
                try:
                    with self.engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE admin_users ADD COLUMN {col_name} {col_type}"))
                except Exception:
                    pass

    def initialize_connection(self) -> bool:
        try:
            self._ensure_mysql_database_exists()
            db_url = self.build_mysql_url()
            self.engine = create_engine(
                db_url,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10,
            )
            Base.metadata.create_all(bind=self.engine)
            self._migrate_schema_columns()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.is_mysql_connected = True
            self.active_dialect = "MySQL"
            self.last_error = None
            self._seed_defaults()
            print(f"[DB] Connected to MySQL database '{self.database}' at {self.host}:{self.port}")
            return True
        except Exception as e:
            self.is_mysql_connected = False
            self.last_error = str(e)
            print(f"[DB Warning] MySQL connection to {self.host}:{self.port} failed ({e}).")
            print("[DB] Using local fallback database until MySQL server is available/configured.")
            fallback_path = BASE_DIR / "rembg_studio_fallback.db"
            self.engine = create_engine(
                f"sqlite:///{fallback_path}",
                connect_args={"check_same_thread": False},
            )
            Base.metadata.create_all(bind=self.engine)
            self._migrate_schema_columns()
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self.active_dialect = "MySQL (Offline Fallback)"
            self._seed_defaults()
            return False

    def configure_mysql(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        persist_env: bool = True,
    ) -> Dict[str, Any]:
        self.host = host.strip() or "127.0.0.1"
        self.port = int(port or 3306)
        self.user = user.strip() or "root"
        self.password = password
        clean_db = database.strip() or "rembg_studio"
        if not re.match(r"^[a-zA-Z0-9_]{1,64}$", clean_db):
            raise ValueError("Invalid database name: must be alphanumeric with underscores, max 64 characters.")
        self.database = clean_db

        if persist_env:
            if not ENV_PATH.exists():
                ENV_PATH.write_text("", encoding="utf-8")
            set_key(str(ENV_PATH), "MYSQL_HOST", self.host)
            set_key(str(ENV_PATH), "MYSQL_PORT", str(self.port))
            set_key(str(ENV_PATH), "MYSQL_USER", self.user)
            set_key(str(ENV_PATH), "MYSQL_PASSWORD", self.password)
            set_key(str(ENV_PATH), "MYSQL_DATABASE", self.database)

        success = self.initialize_connection()
        return {
            "connected": success,
            "dialect": self.active_dialect,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "error": self.last_error,
        }

    def get_session(self) -> Session:
        return self.SessionLocal()

    def _seed_defaults(self) -> None:
        """Seed presets, frontend site settings, sample images, and default admin user."""
        try:
            with self.get_session() as db:
                # 1. Seed default workflow presets
                if db.query(PresetConfig).count() == 0:
                    db.add_all(
                        [
                            PresetConfig(
                                name="High Precision Portrait",
                                model_used="u2net",
                                alpha_matting=True,
                                af_threshold=240,
                                ab_threshold=10,
                                ae_size=10,
                                post_process_mask=True,
                                bg_mode="transparent",
                                bg_value=None,
                                export_format="png",
                            ),
                            PresetConfig(
                                name="E-Commerce White Studio",
                                model_used="u2net",
                                alpha_matting=False,
                                af_threshold=240,
                                ab_threshold=10,
                                ae_size=10,
                                post_process_mask=True,
                                bg_mode="solid",
                                bg_value="#ffffff",
                                export_format="jpg",
                            ),
                            PresetConfig(
                                name="Ultra-Fast Batch Cutout",
                                model_used="u2netp",
                                alpha_matting=False,
                                af_threshold=240,
                                ab_threshold=10,
                                ae_size=10,
                                post_process_mask=False,
                                bg_mode="transparent",
                                bg_value=None,
                                export_format="png",
                            ),
                        ]
                    )

                # 2. Seed default site settings
                existing_keys = {row.setting_key for row in db.query(SiteSetting.setting_key).all()}
                for k, v in DEFAULT_SITE_SETTINGS.items():
                    if k not in existing_keys:
                        db.add(SiteSetting(setting_key=k, setting_value=v))

                # 3. Seed built-in sample images from static/samples/
                if db.query(SampleImage).count() == 0:
                    samples_dir = BASE_DIR / "static" / "samples"
                    if samples_dir.exists():
                        for idx, file in enumerate(sorted(samples_dir.glob("*.jpg"))):
                            category = (
                                "Product"
                                if "product" in file.name
                                else ("Portrait" if "portrait" in file.name else "Object")
                            )
                            title = file.stem.replace("_", " ").title()
                            db.add(
                                SampleImage(
                                    title=title,
                                    category=category,
                                    filename=file.name,
                                    url=f"/static/samples/{file.name}",
                                    is_active=True,
                                    sort_order=idx + 1,
                                )
                            )

                # 4. Seed default admin user (secure generation if unset)
                if db.query(AdminUser).count() == 0:
                    default_admin_user = os.getenv("ADMIN_USERNAME", "admin")
                    default_admin_pass = os.getenv("ADMIN_PASSWORD")
                    if not default_admin_pass or not default_admin_pass.strip():
                        default_admin_pass = secrets.token_urlsafe(16)
                        print(f"[SECURITY ALERT] No ADMIN_PASSWORD configured in environment. Generated initial secure admin password: {default_admin_pass}")
                    db.add(
                        AdminUser(
                            username=default_admin_user,
                            full_name=os.getenv("ADMIN_NAME", "System Administrator"),
                            email=os.getenv("ADMIN_EMAIL", "admin@pnglike.com"),
                            designation="Lead AI Systems Architect",
                            department="DevOps & AI Infrastructure",
                            location="Tokyo, Japan",
                            bio="Managing PngLike AI image suite engine, ONNX models, and infrastructure.",
                            avatar_color="#4f46e5",
                            timezone_pref="Asia/Tokyo (UTC+9)",
                            email_notifications=True,
                            security_alerts=True,
                            password_hash=hash_password(default_admin_pass),
                            role="superadmin",
                        )
                    )

                # 5. Seed default blog posts if none exist
                if db.query(BlogPost).count() == 0:
                    db.add_all(
                        [
                            BlogPost(
                                title="Mastering Hair-Level AI Background Removal with U2-Net & Alpha Matting",
                                slug="mastering-ai-background-removal-u2net-alpha-matting",
                                excerpt="Learn how to combine U2-Net deep salient object detection with foreground/background alpha matting thresholds for studio-grade hair, fur, and semi-transparent cutouts.",
                                category="AI Tutorials",
                                tags="u2net,alpha-matting,background-remover,onnx,portrait",
                                cover_image="/static/samples/portrait_person.jpg",
                                author="Div Sri",
                                read_time_minutes=5,
                                is_published=True,
                                is_featured=True,
                                views_count=142,
                                meta_title="Mastering Hair-Level AI Background Removal with U2-Net — PngLike Blog",
                                meta_description="Step-by-step guide to achieving razor-sharp hair and fur cutouts using U2-Net ONNX neural segmentation and alpha matting in PngLike Studio.",
                                content=(
                                    "<h2>Why Standard Cutouts Struggle with Hair and Fine Edges</h2>"
                                    "<p>Traditional binary segmentation masks classify every pixel as either 100% foreground or 100% background. While that works well for hard-edged boxes or shoes, human hair, pet fur, and glass edges contain mixed transparency (alpha values between <code>0.05</code> and <code>0.95</code>).</p>"
                                    "<h3>1. Choosing the Right ONNX Neural Model</h3>"
                                    "<ul>"
                                    "<li><strong>U2-Net (High Quality)</strong>: Our flagship 176 MB two-level nested U-structure architecture. Ideal for general studio photography and complex silhouettes.</li>"
                                    "<li><strong>U2-Net Human Segmentation</strong>: Specifically fine-tuned on human portraits, clothing textures, and flyaway hair strands.</li>"
                                    "<li><strong>IS-Net Anime</strong>: Engineered for 2D illustrations, cel-shaded artwork, and vector linework.</li>"
                                    "</ul>"
                                    "<h3>2. Fine-Tuning Alpha Matting Thresholds</h3>"
                                    "<p>When you enable <strong>Alpha Matting</strong> in PngLike's Background Remover panel, the trimap refinement solver uses three key parameters:</p>"
                                    "<ul>"
                                    "<li><strong>Foreground Threshold (default 240)</strong>: Pixels with probability above this value are locked as pure opaque subject. Lowering to <code>225</code> preserves more wisps of hair.</li>"
                                    "<li><strong>Background Threshold (default 10)</strong>: Pixels below this probability are cleared to 0% alpha. Raising to <code>20</code> eliminates color spill from studio backdrops.</li>"
                                    "<li><strong>Erode Size (default 10)</strong>: Controls the width of the unknown trimap boundary zone where closed-form alpha matting computes sub-pixel transparency.</li>"
                                    "</ul>"
                                    "<blockquote>Pro Tip: Enable <strong>Post-Process Mask</strong> alongside Alpha Matting to automatically smooth morphological jagged edges before compositing onto a solid or gradient backdrop.</blockquote>"
                                ),
                            ),
                            BlogPost(
                                title="E-Commerce Product Photography: Creating Pure White Studio Catalogs in Seconds",
                                slug="ecommerce-product-photography-pure-white-studio-catalogs",
                                excerpt="How online sellers and brand designers use PngLike's Batch Studio, 4x Super-Resolution Upscaler, and Pure White (#FFFFFF) presets to meet Amazon and Shopify marketplace specs.",
                                category="Product Photography",
                                tags="ecommerce,batch-processing,product-photos,upscaler,presets",
                                cover_image="/static/samples/product_sneaker.jpg",
                                author="Div Sri",
                                read_time_minutes=4,
                                is_published=True,
                                is_featured=True,
                                views_count=98,
                                meta_title="E-Commerce Product Photography Guide — Pure White Studio Cutouts",
                                meta_description="Automate Amazon and Shopify product photography with PngLike Batch Studio, pure #FFFFFF backdrops, and 4x Lanczos super-resolution upscaling.",
                                content=(
                                    "<h2>Marketplace Compliance Made Effortless</h2>"
                                    "<p>Major e-commerce marketplaces require primary product listings to feature a pure white (<code>RGB 255, 255, 255</code> / <code>#FFFFFF</code>) background with crisp object edges and high resolution (at least 1600px on the longest side).</p>"
                                    "<h3>Step 1: One-Click 'E-Commerce White Studio' Preset</h3>"
                                    "<p>Inside the PngLike AI Image Studio, select the <strong>E-Commerce White Studio</strong> preset from the top preset selector. This automatically configures:</p>"
                                    "<ul>"
                                    "<li>Model: <code>u2net</code> with morphological mask post-processing enabled</li>"
                                    "<li>Background Mode: Solid <code>#ffffff</code> pure studio white</li>"
                                    "<li>Export Format: High-quality 95% JPEG or lossless PNG</li>"
                                    "</ul>"
                                    "<h3>Step 2: Upscaling Low-Resolution Vendor Photos</h3>"
                                    "<p>Switch directly to the <strong>Image Upscaler</strong> tool in the 9-in-1 Dock to boost supplier images by <strong>2x or 4x</strong> using Lanczos-4 interpolation paired with bilateral noise reduction and unsharp edge enhancement.</p>"
                                    "<h3>Step 3: Multi-Image ZIP Batch Processing</h3>"
                                    "<p>Have 50 product SKUs to shoot? Open the <strong>Batch Studio</strong> tab, drag and drop your entire folder, and download a single ready-to-publish ZIP archive in seconds.</p>"
                                ),
                            ),
                            BlogPost(
                                title="Inside PngLike 9-in-1 AI Image Suite: 3D Relighting, Cinematic Bokeh & Camera Warp",
                                slug="inside-pnglike-9-in-1-ai-image-suite-3d-relight-cinematic",
                                excerpt="Explore the computer vision pipelines behind PngLike's 9 working IMAGE tools—from surface-normal 3D studio relighting to anamorphic bokeh and projective homography camera shifts.",
                                category="Computer Vision",
                                tags="relight,cinematic-shot,change-camera,skin-enhancer,computer-vision",
                                cover_image="/static/samples/coffee_mug.jpg",
                                author="Div Sri",
                                read_time_minutes=6,
                                is_published=True,
                                is_featured=False,
                                views_count=76,
                                meta_title="Inside PngLike 9-in-1 AI Image Suite: Relight, Cinematic & Camera Tools",
                                meta_description="Deep dive into the 9 neural and computer vision tools powering PngLike Studio: 3D Relight, Cinematic Shot, Skin Enhancer, Image Extender, and Change Camera.",
                                content=(
                                    "<h2>One Unified Workspace, Nine Specialized Vision Engines</h2>"
                                    "<p>PngLike (Powered by Div Sri) combines ONNX Runtime neural segmentation with real-time NumPy/Pillow signal processing so every tool runs locally on your machine with zero cloud latency or privacy risks.</p>"
                                    "<h3>Highlights from the 9-Tool Dock</h3>"
                                    "<ul>"
                                    "<li><strong>Relight (3D Light)</strong>: Isolates the foreground subject via U2-Net, estimates a 3D hemisphere surface normal map from luminance gradients, and casts dual directional key and rim lights (including Neon Split).</li>"
                                    "<li><strong>Cinematic Shot (Anamorphic)</strong>: Separates foreground and background planes to apply optical depth-of-field bokeh blur, Teal & Orange Hollywood LUT grading, horizontal anamorphic lens flares, and 2.39:1 widescreen letterbox bars.</li>"
                                    "<li><strong>Skin Enhancer (Portrait)</strong>: Uses YCbCr chrominance skin-tone masking and frequency separation to smooth blemishes while preserving sharp eye, eyelash, and pore detail.</li>"
                                    "<li><strong>Change Camera (Perspective)</strong>: Applies 3D projective homography matrices (Tilt Up, Tilt Down, Pan Left/Right, Dutch Roll) and radial Barrel/Pincushion lens profiles (24mm Wide, 16mm Fisheye, 85mm Telephoto).</li>"
                                    "</ul>"
                                ),
                            ),
                        ]
                    )

                # 6. Seed default demo user account (demo / user123)
                demo_user = db.query(AppUser).filter(AppUser.username == "demo").first()
                if not demo_user:
                    db.add(
                        AppUser(
                            username="demo",
                            email="demo@pnglike.com",
                            full_name="Demo Creator",
                            password_hash=hash_password("user123"),
                            avatar_color="#3b82f6",
                            plan_tier="Pro Studio",
                            api_key=f"pnglike_{secrets.token_hex(20)}",
                            is_active=True,
                            email_verified=True,
                            jobs_count=0,
                        )
                    )
                else:
                    if not demo_user.email_verified or not demo_user.is_active:
                        demo_user.email_verified = True
                        demo_user.is_active = True

                db.commit()
        except Exception as e:
            print(f"[DB Warning] Error seeding default data: {e}")

    # --------------------------------------------------------
    # SITE SETTINGS (FRONTEND CMS & FEATURE FLAGS)
    # --------------------------------------------------------
    def get_site_settings(self) -> Dict[str, Any]:
        """Return all frontend settings merged with defaults and typed booleans/numbers."""
        raw = dict(DEFAULT_SITE_SETTINGS)
        with self.get_session() as db:
            rows = db.query(SiteSetting).all()
            for r in rows:
                raw[r.setting_key] = r.setting_value

        return {
            "site_title": raw.get("site_title", "PngLike"),
            "site_tagline": raw.get("site_tagline", "Deep Learning Background Removal"),
            "site_badge": raw.get("site_badge", "AI Powered"),
            "hero_title": raw.get("hero_title", "Remove Image Backgrounds"),
            "hero_highlight": raw.get("hero_highlight", "Instantly with AI"),
            "hero_subtitle": raw.get("hero_subtitle", ""),
            "announcement_enabled": raw.get("announcement_enabled", "false").lower() == "true",
            "announcement_text": raw.get("announcement_text", ""),
            "footer_text": raw.get("footer_text", ""),
            "default_model": raw.get("default_model", "u2net"),
            "enabled_models": [m.strip() for m in raw.get("enabled_models", "u2net,u2netp").split(",") if m.strip()],
            "default_tool": "bg-remover" if raw.get("default_tool") in (None, "", "ai-generator") else raw.get("default_tool", "bg-remover"),
            "enabled_tools": [
                t.strip()
                for t in raw.get(
                    "enabled_tools",
                    "image-editor,image-upscaler,image-extender,variations,cinematic-shot,bg-remover,skin-enhancer,relight,change-camera",
                ).split(",")
                if t.strip() and t.strip() != "ai-generator"
            ],
            "enable_batch_mode": raw.get("enable_batch_mode", "true").lower() == "true",
            "enable_history_tab": raw.get("enable_history_tab", "true").lower() == "true",
            "enable_alpha_matting": raw.get("enable_alpha_matting", "true").lower() == "true",
            "enable_custom_backdrop": raw.get("enable_custom_backdrop", "true").lower() == "true",
            "max_upload_mb": int(raw.get("max_upload_mb", "25") or 25),
            "max_batch_files": int(raw.get("max_batch_files", "50") or 50),
            "guest_daily_limit": int(raw.get("guest_daily_limit", "3") or 3),
            "registered_daily_limit": int(raw.get("registered_daily_limit", "10") or 10),
            "registered_cycle_limit": int(raw.get("registered_cycle_limit", "10") or 10),
            "registered_reset_minutes": int(raw.get("registered_reset_minutes", "30") or 30),
            "guest_max_mb": int(raw.get("guest_max_mb", "10") or 10),
            "registered_max_mb": int(raw.get("registered_max_mb", "50") or 50),
            "guest_restricted_tools": [
                t.strip()
                for t in raw.get(
                    "guest_restricted_tools",
                    "image-upscaler,image-extender,variations,cinematic-shot,relight,change-camera",
                ).split(",")
                if t.strip()
            ],
            "maintenance_mode": raw.get("maintenance_mode", "false").lower() == "true",
            "maintenance_message": raw.get("maintenance_message", ""),
            "indexnow_enabled": raw.get("indexnow_enabled", "true").lower() == "true",
            "indexnow_key": raw.get("indexnow_key", "950cf4f1e8b64e1f90b053abbfd50843"),
            "indexnow_host": raw.get("indexnow_host", "pnglike.com"),
            "indexnow_key_location": raw.get("indexnow_key_location", "https://pnglike.com/950cf4f1e8b64e1f90b053abbfd50843.txt"),
            "indexnow_auto_submit_blog": raw.get("indexnow_auto_submit_blog", "true").lower() == "true",
            "indexnow_auto_submit_cms": raw.get("indexnow_auto_submit_cms", "true").lower() == "true",
        }

    def update_site_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Persist updated frontend settings into the MySQL `site_settings` table."""
        with self.get_session() as db:
            for k, v in updates.items():
                if k not in DEFAULT_SITE_SETTINGS:
                    continue
                if isinstance(v, list):
                    val_str = ",".join(str(x).strip() for x in v if str(x).strip())
                elif isinstance(v, bool):
                    val_str = "true" if v else "false"
                else:
                    val_str = str(v)

                existing = db.query(SiteSetting).filter(SiteSetting.setting_key == k).first()
                if existing:
                    existing.setting_value = val_str
                    existing.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                else:
                    db.add(SiteSetting(setting_key=k, setting_value=val_str))
            db.commit()
        return self.get_site_settings()

    # --------------------------------------------------------
    # ADMIN AUTHENTICATION & USER MANAGEMENT
    # --------------------------------------------------------
    def authenticate_admin(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.username == username.strip()).first()
            if not user or not verify_password(password, user.password_hash):
                return None
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(user)
            return user.to_dict()

    def update_admin_credentials(
        self,
        current_username: str,
        new_username: str,
        new_password: Optional[str] = None,
        current_password: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.username == current_username).first()
            if not user:
                user = db.query(AdminUser).first()
            if not user:
                raise ValueError("Admin account not found.")
            if new_password and new_password.strip():
                if not current_password or not verify_password(current_password.strip(), user.password_hash):
                    raise ValueError("Current admin password is required and must be correct to set a new password.")
                validate_registration_password(new_password.strip(), username=user.username)
                user.password_hash = hash_password(new_password.strip())
                db.query(AdminSession).filter(AdminSession.admin_id == user.id).delete()
            if new_username and new_username.strip():
                user.username = new_username.strip()
            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(user)
            return user.to_dict()

    def get_admin_profile(self, admin_id: int) -> Optional[Dict[str, Any]]:
        """Fetch admin profile with aggregate system statistics."""
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
            if not user:
                user = db.query(AdminUser).first()
            if not user:
                return None
            profile = user.to_dict()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            profile["stats"] = {
                "total_jobs": db.query(RemovalJob).count(),
                "total_users": db.query(AppUser).count(),
                "total_blog_posts": db.query(BlogPost).count(),
                "active_sessions": db.query(AdminSession).filter(
                    AdminSession.admin_id == user.id,
                    AdminSession.expires_at > now
                ).count(),
            }
            return profile

    def update_admin_profile(self, admin_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update admin user profile metadata, contact info, bio, and preferences."""
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
            if not user:
                user = db.query(AdminUser).first()
            if not user:
                raise ValueError("Admin account not found.")

            if "full_name" in data and data["full_name"] is not None:
                clean_name = data["full_name"].strip()
                if clean_name:
                    user.full_name = clean_name[:128]

            if "email" in data and data["email"] is not None:
                clean_email = data["email"].strip().lower()
                if clean_email:
                    validate_registration_email(clean_email)
                    user.email = clean_email[:128]
                else:
                    user.email = ""

            if "phone" in data and data["phone"] is not None:
                user.phone = data["phone"].strip()[:32]

            if "designation" in data and data["designation"] is not None:
                user.designation = data["designation"].strip()[:128]

            if "department" in data and data["department"] is not None:
                user.department = data["department"].strip()[:128]

            if "location" in data and data["location"] is not None:
                user.location = data["location"].strip()[:128]

            if "bio" in data and data["bio"] is not None:
                user.bio = data["bio"].strip()

            if "avatar_color" in data and data["avatar_color"] is not None:
                color = data["avatar_color"].strip()
                if re.match(r"^#[0-9a-fA-F]{6}$", color):
                    user.avatar_color = color

            if "timezone_pref" in data and data["timezone_pref"] is not None:
                user.timezone_pref = data["timezone_pref"].strip()[:64]

            if "email_notifications" in data and data["email_notifications"] is not None:
                user.email_notifications = bool(data["email_notifications"])

            if "security_alerts" in data and data["security_alerts"] is not None:
                user.security_alerts = bool(data["security_alerts"])

            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(user)
            return user.to_dict()

    def update_admin_avatar(self, admin_id: int, avatar_url: Optional[str]) -> Dict[str, Any]:
        """Update or remove the custom avatar URL for an administrator."""
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
            if not user:
                user = db.query(AdminUser).first()
            if not user:
                raise ValueError("Admin account not found.")

            user.avatar_url = (avatar_url or "").strip()[:512]
            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(user)
            return user.to_dict()

    def change_admin_password(
        self,
        admin_id: int,
        current_password: str,
        new_password: str,
        current_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Securely change admin password, with credential verification and session invalidation."""
        with self.get_session() as db:
            user = db.query(AdminUser).filter(AdminUser.id == admin_id).first()
            if not user:
                user = db.query(AdminUser).first()
            if not user:
                raise ValueError("Admin account not found.")

            if not current_password or not verify_password(current_password.strip(), user.password_hash):
                raise ValueError("Current password is incorrect. Verification failed.")

            validate_registration_password(new_password.strip(), username=user.username, email=user.email or "")
            user.password_hash = hash_password(new_password.strip())
            user.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

            # Invalidate all OTHER admin sessions to prevent stolen session reuse
            sess_q = db.query(AdminSession).filter(AdminSession.admin_id == user.id)
            if current_token:
                sess_q = sess_q.filter(AdminSession.token != current_token.strip())
            sess_q.delete(synchronize_session=False)

            db.commit()
            db.refresh(user)
            return user.to_dict()

    def list_admin_sessions(self, admin_id: int, current_token: Optional[str] = None) -> List[Dict[str, Any]]:
        """List active sessions for this administrator."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.get_session() as db:
            sessions = (
                db.query(AdminSession)
                .filter(AdminSession.admin_id == admin_id, AdminSession.expires_at > now)
                .order_by(AdminSession.created_at.desc())
                .all()
            )
            result = []
            for s in sessions:
                d = s.to_dict()
                d["is_current"] = (current_token is not None and s.token == current_token.strip())
                # Mask token for security
                d["token_preview"] = s.token[:6] + "..." + s.token[-4:] if len(s.token) > 10 else "******"
                result.append(d)
            return result

    def revoke_other_admin_sessions(self, admin_id: int, current_token: str) -> int:
        """Revoke all active sessions for this admin except the current one."""
        with self.get_session() as db:
            count = (
                db.query(AdminSession)
                .filter(AdminSession.admin_id == admin_id, AdminSession.token != current_token.strip())
                .delete(synchronize_session=False)
            )
            db.commit()
            return count

    def revoke_admin_session_by_id(self, admin_id: int, session_id: int) -> bool:
        """Revoke a specific admin session by ID."""
        with self.get_session() as db:
            deleted = (
                db.query(AdminSession)
                .filter(AdminSession.admin_id == admin_id, AdminSession.id == session_id)
                .delete(synchronize_session=False)
            )
            db.commit()
            return bool(deleted)

    # --------------------------------------------------------
    # SAMPLE IMAGES MANAGEMENT
    # --------------------------------------------------------
    def list_samples(self, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.get_session() as db:
            q = db.query(SampleImage)
            if active_only:
                q = q.filter(SampleImage.is_active == True)  # noqa: E712
            rows = q.order_by(SampleImage.sort_order.asc(), SampleImage.id.asc()).all()
            return [r.to_dict() for r in rows]

    def create_sample(self, title: str, category: str, filename: str, url: str, is_active: bool = True) -> Dict[str, Any]:
        with self.get_session() as db:
            count = db.query(func.count(SampleImage.id)).scalar() or 0
            sample = SampleImage(
                title=title.strip() or "Sample Image",
                category=category.strip() or "Product",
                filename=filename,
                url=url,
                is_active=is_active,
                sort_order=count + 1,
            )
            db.add(sample)
            db.commit()
            db.refresh(sample)
            return sample.to_dict()

    def update_sample(
        self,
        sample_id: int,
        title: Optional[str] = None,
        category: Optional[str] = None,
        is_active: Optional[bool] = None,
        sort_order: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            sample = db.query(SampleImage).filter(SampleImage.id == sample_id).first()
            if not sample:
                return None
            if title is not None:
                sample.title = title.strip()
            if category is not None:
                sample.category = category.strip()
            if is_active is not None:
                sample.is_active = bool(is_active)
            if sort_order is not None:
                sample.sort_order = int(sort_order)
            db.commit()
            db.refresh(sample)
            return sample.to_dict()

    def delete_sample(self, sample_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            sample = db.query(SampleImage).filter(SampleImage.id == sample_id).first()
            if not sample:
                return None
            data = sample.to_dict()
            db.delete(sample)
            db.commit()
            return data

    # --------------------------------------------------------
    # JOBS, ANALYTICS & ACCESS RESTRICTIONS
    # --------------------------------------------------------
    def get_user_quota_summary(
        self,
        user_id: Optional[int],
        client_ip: str,
    ) -> Dict[str, Any]:
        """Compute current quota usage, limits, and tool restrictions for registered vs guest user."""
        settings = self.get_site_settings()
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
        client_clean = (client_ip or "127.0.0.1").split(",")[0].strip()

        with self.get_session() as db:
            if user_id is not None:
                user = db.query(AppUser).filter(AppUser.id == int(user_id)).first()
                if user and user.is_active:
                    cycle_limit = int(settings.get("registered_cycle_limit", 10))
                    rest_minutes = int(settings.get("registered_reset_minutes", 30))
                    rest_delta = timedelta(minutes=rest_minutes)
                    now_utc = datetime.now(timezone.utc)
                    now = now_utc.replace(tzinfo=None)
                    server_timestamp = int(now_utc.timestamp())
                    server_time_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

                    # Query recent jobs for this user in chronological order (within 4x rest window)
                    cutoff = now - timedelta(minutes=rest_minutes * 4)
                    recent_jobs = (
                        db.query(RemovalJob)
                        .filter(RemovalJob.user_id == user.id, RemovalJob.created_at >= cutoff)
                        .order_by(RemovalJob.created_at.asc(), RemovalJob.id.asc())
                        .all()
                    )

                    cycle_jobs = []
                    cycle_completed_at = None

                    for job in recent_jobs:
                        job_time = job.created_at
                        if cycle_completed_at is not None:
                            # Previous cycle reached cycle_limit. Did 30-min rest period finish before this job?
                            if job_time >= cycle_completed_at + rest_delta:
                                cycle_jobs = [job]
                                cycle_completed_at = None
                            else:
                                cycle_jobs.append(job)
                        else:
                            # If an uncompleted cycle had inactivity > rest_minutes, it naturally resets
                            if cycle_jobs and (job_time - cycle_jobs[0].created_at) > rest_delta:
                                cycle_jobs = [job]
                            else:
                                cycle_jobs.append(job)

                            if len(cycle_jobs) >= cycle_limit:
                                cycle_completed_at = job_time

                    if cycle_completed_at is not None:
                        reset_at = cycle_completed_at + rest_delta
                        reset_at_utc = reset_at.replace(tzinfo=timezone.utc)
                        if now < reset_at:
                            is_resting = True
                            seconds_until_reset = max(1, int((reset_at - now).total_seconds()))
                            used_in_cycle = cycle_limit
                            remaining_in_cycle = 0
                            reset_timestamp = int(reset_at_utc.timestamp())
                            reset_time_utc = reset_at_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
                        else:
                            is_resting = False
                            seconds_until_reset = 0
                            used_in_cycle = 0
                            remaining_in_cycle = cycle_limit
                            reset_timestamp = None
                            reset_time_utc = None
                    else:
                        reset_timestamp = None
                        reset_time_utc = None
                        if cycle_jobs:
                            if (now - cycle_jobs[0].created_at) > rest_delta:
                                is_resting = False
                                seconds_until_reset = 0
                                used_in_cycle = 0
                                remaining_in_cycle = cycle_limit
                            else:
                                is_resting = False
                                seconds_until_reset = 0
                                used_in_cycle = len(cycle_jobs)
                                remaining_in_cycle = max(0, cycle_limit - used_in_cycle)
                        else:
                            is_resting = False
                            seconds_until_reset = 0
                            used_in_cycle = 0
                            remaining_in_cycle = cycle_limit

                    # Global MM:SS formatting
                    m_rem = seconds_until_reset // 60
                    s_rem = seconds_until_reset % 60
                    time_remaining_formatted = f"{m_rem:02d}:{s_rem:02d}"

                    return {
                        "is_registered": True,
                        "tier": "registered",
                        "username": user.username,
                        "full_name": user.full_name or user.username,
                        "plan_tier": user.plan_tier or "Pro Studio",
                        "daily_limit": cycle_limit,
                        "cycle_limit": cycle_limit,
                        "used_today": used_in_cycle,
                        "used_in_cycle": used_in_cycle,
                        "remaining_today": remaining_in_cycle,
                        "remaining_in_cycle": remaining_in_cycle,
                        "rest_minutes": rest_minutes,
                        "is_resting": is_resting,
                        "seconds_until_reset": seconds_until_reset,
                        "time_remaining_formatted": time_remaining_formatted,
                        "server_time_utc": server_time_utc,
                        "server_timestamp": server_timestamp,
                        "reset_time_utc": reset_time_utc,
                        "reset_timestamp": reset_timestamp,
                        "max_upload_mb": int(settings.get("registered_max_mb", 50)),
                        "restricted_tools": [],
                    }

            # Unregistered Guest User
            guest_limit = int(settings.get("guest_daily_limit", 3))
            used_today = (
                db.query(func.count(RemovalJob.id))
                .filter(
                    RemovalJob.client_ip == client_clean,
                    RemovalJob.user_id == None,
                    RemovalJob.created_at >= today_start,
                )
                .scalar()
                or 0
            )
            now_guest_utc = datetime.now(timezone.utc)
            return {
                "is_registered": False,
                "tier": "guest",
                "client_ip": client_clean,
                "daily_limit": guest_limit,
                "used_today": int(used_today),
                "remaining_today": max(0, guest_limit - int(used_today)),
                "is_resting": False,
                "seconds_until_reset": 0,
                "time_remaining_formatted": "00:00",
                "server_time_utc": now_guest_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "server_timestamp": int(now_guest_utc.timestamp()),
                "reset_time_utc": None,
                "reset_timestamp": None,
                "max_upload_mb": int(settings.get("guest_max_mb", 10)),
                "restricted_tools": settings.get("guest_restricted_tools", []),
            }

    def check_user_access_quota(
        self,
        user_id: Optional[int],
        client_ip: str,
        tool_id: Optional[str] = None,
        file_size_bytes: int = 0,
    ) -> Dict[str, Any]:
        """Validate access permissions, upload size boundaries, and daily usage limits."""
        quota = self.get_user_quota_summary(user_id, client_ip)
        max_bytes = quota["max_upload_mb"] * 1024 * 1024

        if file_size_bytes > max_bytes:
            if quota["is_registered"]:
                raise ValueError(
                    f"Uploaded image exceeds the registered account limit of {quota['max_upload_mb']} MB."
                )
            else:
                raise ValueError(
                    f"Guest upload size is limited to {quota['max_upload_mb']} MB. Please sign in or register for free to upload files up to 50 MB."
                )

        if not quota["is_registered"]:
            if tool_id and tool_id in quota["restricted_tools"]:
                tool_label = tool_id.replace("-", " ").title()
                raise PermissionError(
                    f"The '{tool_label}' tool requires a free registered account. Sign in or register in 30 seconds to unlock all 9 AI image studio tools!"
                )
            if quota["remaining_today"] <= 0:
                raise PermissionError(
                    f"Daily free guest limit reached ({quota['used_today']}/{quota['daily_limit']} uses). Create a free account or sign in to continue with unlimited cutouts and all 9 AI tools!"
                )
        else:
            if quota.get("is_resting") or quota["remaining_today"] <= 0:
                mins = max(1, math.ceil(quota.get("seconds_until_reset", 1800) / 60))
                time_str = quota.get("time_remaining_formatted", f"{mins}m")
                reset_utc_display = f" (at {quota['reset_time_utc']} UTC)" if quota.get("reset_time_utc") else ""
                raise PermissionError(
                    f"Account limitation reached ({quota['used_today']}/{quota['daily_limit']} images processed). "
                    f"A 30-minute rest cooldown is active to reset your uses. "
                    f"Global timer resets in {time_str}{reset_utc_display}."
                )

        return quota

    def record_job(self, **kwargs) -> Dict[str, Any]:
        with self.get_session() as db:
            job = RemovalJob(**kwargs)
            db.add(job)
            user_id = kwargs.get("user_id")
            if user_id is not None:
                user = db.query(AppUser).filter(AppUser.id == int(user_id)).first()
                if user:
                    user.jobs_count = int(user.jobs_count or 0) + 1
            db.commit()
            db.refresh(job)
            return job.to_dict()

    def list_jobs(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        model_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.get_session() as db:
            q = db.query(RemovalJob)
            if search and search.strip():
                term = f"%{search.strip()}%"
                q = q.filter(
                    or_(
                        RemovalJob.original_filename.ilike(term),
                        RemovalJob.output_filename.ilike(term),
                        RemovalJob.job_uuid.ilike(term),
                    )
                )
            if model_filter and model_filter.strip():
                q = q.filter(RemovalJob.model_used == model_filter.strip())

            total = q.count()
            jobs = q.order_by(desc(RemovalJob.created_at), desc(RemovalJob.id)).offset(offset).limit(limit).all()
            return {
                "total": total,
                "jobs": [j.to_dict() for j in jobs],
            }

    def delete_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            job = db.query(RemovalJob).filter(RemovalJob.id == job_id).first()
            if not job:
                return None
            data = job.to_dict()
            db.delete(job)
            db.commit()
            return data

    def clear_all_jobs(self) -> List[Dict[str, Any]]:
        with self.get_session() as db:
            jobs = db.query(RemovalJob).all()
            data = [j.to_dict() for j in jobs]
            db.query(RemovalJob).delete()
            db.commit()
            return data

    def get_analytics(self) -> Dict[str, Any]:
        with self.get_session() as db:
            total_jobs = db.query(func.count(RemovalJob.id)).scalar() or 0
            avg_time = db.query(func.avg(RemovalJob.process_time_ms)).scalar() or 0.0
            total_bytes = db.query(func.sum(RemovalJob.output_size_bytes)).scalar() or 0

            model_rows = (
                db.query(RemovalJob.model_used, func.count(RemovalJob.id))
                .group_by(RemovalJob.model_used)
                .all()
            )
            models_breakdown = {row[0]: row[1] for row in model_rows}
            top_model = max(models_breakdown, key=models_breakdown.get) if models_breakdown else "u2net"

            format_rows = (
                db.query(RemovalJob.output_format, func.count(RemovalJob.id))
                .group_by(RemovalJob.output_format)
                .all()
            )
            formats_breakdown = {row[0]: row[1] for row in format_rows}

            total_presets = db.query(func.count(PresetConfig.id)).scalar() or 0
            total_samples = db.query(func.count(SampleImage.id)).scalar() or 0
            total_blog_posts = db.query(func.count(BlogPost.id)).scalar() or 0
            published_blog_posts = (
                db.query(func.count(BlogPost.id)).filter(BlogPost.is_published == True).scalar() or 0  # noqa: E712
            )
            total_blog_views = db.query(func.sum(BlogPost.views_count)).scalar() or 0
            total_users = db.query(func.count(AppUser.id)).scalar() or 0

            return {
                "total_jobs": total_jobs,
                "avg_process_time_ms": round(float(avg_time), 2),
                "total_output_bytes": int(total_bytes),
                "top_model": top_model,
                "models_breakdown": models_breakdown,
                "formats_breakdown": formats_breakdown,
                "total_presets": total_presets,
                "total_samples": total_samples,
                "total_blog_posts": total_blog_posts,
                "published_blog_posts": published_blog_posts,
                "total_blog_views": int(total_blog_views),
                "total_users": total_users,
                "db_connected": self.is_mysql_connected,
                "db_dialect": self.active_dialect,
                "db_host": f"{self.host}:{self.port}",
                "db_name": self.database,
                "db_user": self.user,
                "db_error": self.last_error,
            }

    # --------------------------------------------------------
    # PRESETS CRUD
    # --------------------------------------------------------
    def list_presets(self) -> List[Dict[str, Any]]:
        with self.get_session() as db:
            presets = db.query(PresetConfig).order_by(PresetConfig.id).all()
            return [p.to_dict() for p in presets]

    def create_preset(self, **kwargs) -> Dict[str, Any]:
        with self.get_session() as db:
            existing = db.query(PresetConfig).filter(PresetConfig.name == kwargs.get("name")).first()
            if existing:
                for k, v in kwargs.items():
                    setattr(existing, k, v)
                db.commit()
                db.refresh(existing)
                return existing.to_dict()
            preset = PresetConfig(**kwargs)
            db.add(preset)
            db.commit()
            db.refresh(preset)
            return preset.to_dict()

    def delete_preset(self, preset_id: int) -> bool:
        with self.get_session() as db:
            preset = db.query(PresetConfig).filter(PresetConfig.id == preset_id).first()
            if not preset:
                return False
            db.delete(preset)
            db.commit()
            return True

    # --------------------------------------------------------
    # BLOG POSTS CRUD (PUBLIC & ADMIN CMS)
    # --------------------------------------------------------
    def _ensure_unique_slug(self, db: Session, desired_slug: str, exclude_id: Optional[int] = None) -> str:
        base_slug = slugify_text(desired_slug)
        candidate = base_slug
        counter = 2
        while True:
            q = db.query(BlogPost).filter(BlogPost.slug == candidate)
            if exclude_id is not None:
                q = q.filter(BlogPost.id != exclude_id)
            if not q.first():
                return candidate
            candidate = f"{base_slug}-{counter}"
            counter += 1

    def list_blog_posts(
        self,
        published_only: bool = True,
        category: Optional[str] = None,
        search: Optional[str] = None,
        featured_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        with self.get_session() as db:
            q = db.query(BlogPost)
            if published_only:
                q = q.filter(BlogPost.is_published == True)  # noqa: E712
            if featured_only:
                q = q.filter(BlogPost.is_featured == True)  # noqa: E712
            if category and category.strip() and category.strip().lower() != "all":
                q = q.filter(BlogPost.category == category.strip())
            if search and search.strip():
                term = f"%{search.strip()}%"
                q = q.filter(
                    or_(
                        BlogPost.title.ilike(term),
                        BlogPost.excerpt.ilike(term),
                        BlogPost.tags.ilike(term),
                        BlogPost.category.ilike(term),
                    )
                )

            total = q.count()
            posts = (
                q.order_by(desc(BlogPost.is_featured), desc(BlogPost.created_at), desc(BlogPost.id))
                .offset(offset)
                .limit(limit)
                .all()
            )

            # Collect distinct categories
            cat_q = db.query(BlogPost.category)
            if published_only:
                cat_q = cat_q.filter(BlogPost.is_published == True)  # noqa: E712
            categories = sorted({row[0] for row in cat_q.distinct().all() if row[0]})

            # Collect blog stats
            total_all = db.query(func.count(BlogPost.id)).scalar() or 0
            published_count = (
                db.query(func.count(BlogPost.id)).filter(BlogPost.is_published == True).scalar() or 0  # noqa: E712
            )
            draft_count = max(0, total_all - published_count)
            featured_count = (
                db.query(func.count(BlogPost.id)).filter(BlogPost.is_featured == True).scalar() or 0  # noqa: E712
            )
            total_views = db.query(func.sum(BlogPost.views_count)).scalar() or 0

            return {
                "total": total,
                "posts": [p.to_dict(include_content=True) for p in posts],
                "categories": categories,
                "stats": {
                    "total_posts": total_all,
                    "published_posts": published_count,
                    "draft_posts": draft_count,
                    "featured_posts": featured_count,
                    "total_views": int(total_views),
                },
            }

    def get_blog_post_by_slug(self, slug: str, increment_views: bool = True, published_only: bool = True) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            q = db.query(BlogPost).filter(BlogPost.slug == slug.strip())
            if published_only:
                q = q.filter(BlogPost.is_published == True)  # noqa: E712
            post = q.first()
            if not post:
                return None
            if increment_views:
                post.views_count = int(post.views_count or 0) + 1
                db.commit()
                db.refresh(post)
            return post.to_dict(include_content=True)

    def get_blog_post_by_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
            return post.to_dict(include_content=True) if post else None

    def create_blog_post(
        self,
        title: str,
        excerpt: str,
        content: str,
        slug: Optional[str] = None,
        category: str = "AI Tutorials",
        tags: str = "",
        cover_image: Optional[str] = None,
        author: str = "Div Sri",
        read_time_minutes: Optional[int] = None,
        is_published: bool = True,
        is_featured: bool = False,
        meta_title: Optional[str] = None,
        meta_description: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self.get_session() as db:
            clean_title = (title or "").strip() or "Untitled Blog Post"
            unique_slug = self._ensure_unique_slug(db, slug if slug and slug.strip() else clean_title)
            clean_content = (content or "").strip() or f"<p>{excerpt}</p>"
            clean_excerpt = (excerpt or "").strip() or re.sub(r"<[^>]+>", "", clean_content)[:200]
            calc_read_time = int(read_time_minutes) if read_time_minutes and int(read_time_minutes) > 0 else estimate_read_time(clean_content)

            post = BlogPost(
                title=clean_title,
                slug=unique_slug,
                excerpt=clean_excerpt,
                content=clean_content,
                category=(category or "AI Tutorials").strip() or "AI Tutorials",
                tags=(tags or "").strip(),
                cover_image=(cover_image or "/static/samples/portrait_person.jpg").strip(),
                author=(author or "Div Sri").strip() or "Div Sri",
                read_time_minutes=calc_read_time,
                is_published=bool(is_published),
                is_featured=bool(is_featured),
                meta_title=(meta_title or "").strip() or clean_title,
                meta_description=(meta_description or "").strip() or clean_excerpt[:300],
            )
            db.add(post)
            db.commit()
            db.refresh(post)
            return post.to_dict(include_content=True)

    def update_blog_post(self, post_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
            if not post:
                return None

            if "title" in updates and updates["title"] is not None:
                post.title = updates["title"].strip() or post.title
            if "slug" in updates and updates["slug"] is not None and updates["slug"].strip():
                post.slug = self._ensure_unique_slug(db, updates["slug"].strip(), exclude_id=post.id)
            if "excerpt" in updates and updates["excerpt"] is not None:
                post.excerpt = updates["excerpt"].strip()
            if "content" in updates and updates["content"] is not None:
                post.content = updates["content"].strip()
            if "category" in updates and updates["category"] is not None:
                post.category = updates["category"].strip() or "AI Tutorials"
            if "tags" in updates and updates["tags"] is not None:
                post.tags = updates["tags"].strip()
            if "cover_image" in updates and updates["cover_image"] is not None:
                post.cover_image = updates["cover_image"].strip() or "/static/samples/portrait_person.jpg"
            if "author" in updates and updates["author"] is not None:
                post.author = updates["author"].strip() or "Div Sri"
            if "read_time_minutes" in updates and updates["read_time_minutes"] is not None:
                post.read_time_minutes = max(1, int(updates["read_time_minutes"]))
            elif "content" in updates and updates["content"] is not None:
                post.read_time_minutes = estimate_read_time(post.content)
            if "is_published" in updates and updates["is_published"] is not None:
                post.is_published = bool(updates["is_published"])
            if "is_featured" in updates and updates["is_featured"] is not None:
                post.is_featured = bool(updates["is_featured"])
            if "meta_title" in updates and updates["meta_title"] is not None:
                post.meta_title = updates["meta_title"].strip() or post.title
            if "meta_description" in updates and updates["meta_description"] is not None:
                post.meta_description = updates["meta_description"].strip() or post.excerpt[:300]

            post.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(post)
            return post.to_dict(include_content=True)

    def delete_blog_post(self, post_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            post = db.query(BlogPost).filter(BlogPost.id == post_id).first()
            if not post:
                return None
            data = post.to_dict(include_content=False)
            db.delete(post)
            db.commit()
            return data

    # --------------------------------------------------------
    # USER AUTHENTICATION, USER DASHBOARD & ADMIN USER MANAGER
    # --------------------------------------------------------
    def register_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: str = "",
        auto_activate: bool = False,
    ) -> Dict[str, Any]:
        # Strict security validation for username, email, and password
        clean_username = validate_registration_username(username)
        clean_email = validate_registration_email(email)
        validate_registration_password(password, username=clean_username, email=clean_email)

        with self.get_session() as db:
            if db.query(AppUser).filter(AppUser.username == clean_username).first():
                raise ValueError(f"Username '{clean_username}' is already taken.")
            if db.query(AppUser).filter(AppUser.email == clean_email).first():
                raise ValueError(f"Email '{clean_email}' is already registered.")

            palette = ["#3b82f6", "#6366f1", "#10b981", "#f43f5e", "#f59e0b", "#8b5cf6"]
            color = palette[secrets.randbelow(len(palette))]
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Generate 6-digit OTP code and secure verification token
            v_code = f"{secrets.randbelow(900000) + 100000}"
            v_token = secrets.token_urlsafe(32)
            expires = now + timedelta(hours=24)

            user = AppUser(
                username=clean_username,
                email=clean_email,
                full_name=(full_name or "").strip() or clean_username.title(),
                password_hash=hash_password(password),
                avatar_color=color,
                plan_tier="Pro Studio",
                api_key=f"pnglike_{secrets.token_hex(20)}",
                is_active=auto_activate,
                email_verified=auto_activate,
                verification_code=None if auto_activate else v_code,
                verification_token=None if auto_activate else v_token,
                verification_expires_at=None if auto_activate else expires,
                verified_at=now if auto_activate else None,
                jobs_count=0,
                last_login=now if auto_activate else None,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            res = user.to_dict(include_api_key=True)
            res["verification_code"] = v_code
            res["verification_token"] = v_token
            return res

    def verify_user_code(self, email_or_identifier: str, code: str) -> Dict[str, Any]:
        """Verify user account with a 6-digit code and activate it."""
        ident = (email_or_identifier or "").strip().lower()
        clean_code = (code or "").strip()
        if not ident:
            raise ValueError("Email address or username is required.")
        if not clean_code:
            raise ValueError("Please enter the 6-digit verification code.")

        with self.get_session() as db:
            user = (
                db.query(AppUser)
                .filter(or_(AppUser.email == ident, AppUser.username == ident))
                .first()
            )
            if not user:
                raise ValueError("No account found with this email or username.")

            if user.is_active and user.email_verified:
                return user.to_dict(include_api_key=True)

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if user.verification_expires_at and user.verification_expires_at < now:
                raise ValueError("Verification code has expired. Please request a new verification code.")

            if not user.verification_code or user.verification_code.strip() != clean_code:
                raise ValueError("Invalid verification code. Please check your Gmail and try again.")

            # Activate user account
            user.is_active = True
            user.email_verified = True
            user.verified_at = now
            user.verification_code = None
            user.verification_token = None
            user.verification_expires_at = None
            user.last_login = now
            db.commit()
            db.refresh(user)
            return user.to_dict(include_api_key=True)

    def verify_user_token(self, token: str) -> Dict[str, Any]:
        """Verify user account via 1-click token link and activate it."""
        clean_token = (token or "").strip()
        if not clean_token:
            raise ValueError("Verification token is required.")

        with self.get_session() as db:
            user = (
                db.query(AppUser)
                .filter(AppUser.verification_token == clean_token)
                .first()
            )
            if not user:
                raise ValueError("Invalid or expired verification link.")

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if user.verification_expires_at and user.verification_expires_at < now:
                raise ValueError("Verification link has expired. Please request a new verification link.")

            # Activate user account
            user.is_active = True
            user.email_verified = True
            user.verified_at = now
            user.verification_code = None
            user.verification_token = None
            user.verification_expires_at = None
            user.last_login = now
            db.commit()
            db.refresh(user)
            return user.to_dict(include_api_key=True)

    def resend_verification_code(self, email_or_identifier: str) -> Dict[str, Any]:
        """Generate a new 6-digit code and token for an unverified user account."""
        ident = (email_or_identifier or "").strip().lower()
        if not ident:
            raise ValueError("Email address or username is required.")

        with self.get_session() as db:
            user = (
                db.query(AppUser)
                .filter(or_(AppUser.email == ident, AppUser.username == ident))
                .first()
            )
            if not user:
                raise ValueError("No account found with this email or username.")

            if user.is_active and user.email_verified:
                raise ValueError("Your account is already verified and active! You can sign in directly.")

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            v_code = f"{secrets.randbelow(900000) + 100000}"
            v_token = secrets.token_urlsafe(32)
            user.verification_code = v_code
            user.verification_token = v_token
            user.verification_expires_at = now + timedelta(hours=24)
            db.commit()
            db.refresh(user)
            res = user.to_dict(include_api_key=True)
            res["verification_code"] = v_code
            res["verification_token"] = v_token
            return res

    def authenticate_user(self, identifier: str, password: str) -> Optional[Dict[str, Any]]:
        ident = (identifier or "").strip().lower()
        if not ident or not password:
            return None
        with self.get_session() as db:
            user = (
                db.query(AppUser)
                .filter(or_(AppUser.username == ident, AppUser.email == ident))
                .first()
            )
            if not user or not verify_password(password, user.password_hash):
                return None
            if not user.email_verified or not user.is_active:
                raise ValueError(
                    f"Account not active. Please check your Gmail ({user.email}) "
                    f"and enter your 6-digit verification code to activate your account."
                )
            user.last_login = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()
            db.refresh(user)
            return user.to_dict(include_api_key=False)

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user or not user.is_active:
                return None
            return user.to_dict(include_api_key=False)

    def get_user_by_api_key(self, api_key: str) -> Optional[Dict[str, Any]]:
        # Personal developer API keys access disabled per security policy
        return None

    def update_user_profile(
        self,
        user_id: int,
        full_name: Optional[str] = None,
        email: Optional[str] = None,
        avatar_color: Optional[str] = None,
        new_password: Optional[str] = None,
        current_password: Optional[str] = None,
        bio: Optional[str] = None,
        phone: Optional[str] = None,
        country: Optional[str] = None,
        preferred_format: Optional[str] = None,
        dark_mode_pref: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return None
            if full_name is not None and full_name.strip():
                user.full_name = full_name.strip()
            if email is not None and email.strip():
                clean_email = validate_registration_email(email)
                conflict = (
                    db.query(AppUser)
                    .filter(AppUser.email == clean_email, AppUser.id != user.id)
                    .first()
                )
                if conflict:
                    raise ValueError(f"Email '{clean_email}' is already in use.")
                user.email = clean_email
            if avatar_color is not None and avatar_color.strip():
                user.avatar_color = avatar_color.strip()
            if bio is not None:
                user.bio = bio.strip()[:255]
            if phone is not None:
                user.phone = phone.strip()[:32]
            if country is not None:
                user.country = country.strip()[:64]
            if preferred_format is not None and preferred_format.strip().lower() in ("png", "webp", "jpeg"):
                user.preferred_format = preferred_format.strip().lower()
            if dark_mode_pref is not None and dark_mode_pref.strip().lower() in ("system", "dark", "light"):
                user.dark_mode_pref = dark_mode_pref.strip().lower()
            if new_password is not None and new_password.strip():
                if not current_password or not current_password.strip():
                    raise ValueError("Current password is required to change your password.")
                if not verify_password(current_password.strip(), user.password_hash):
                    raise ValueError("Current password is incorrect.")
                validate_registration_password(new_password.strip(), username=user.username, email=user.email)
                user.password_hash = hash_password(new_password.strip())
                db.query(UserSession).filter(UserSession.user_id == user_id).delete()

            db.commit()
            db.refresh(user)
            return user.to_dict(include_api_key=False)

    def export_user_profile_data(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return None
            jobs = (
                db.query(RemovalJob)
                .filter(RemovalJob.user_id == user_id)
                .order_by(desc(RemovalJob.created_at))
                .all()
            )
            return {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "service": "PngLike 9-in-1 AI Image Studio",
                "account": user.to_dict(include_api_key=False),
                "total_jobs": len(jobs),
                "jobs": [j.to_dict() for j in jobs],
            }

    def delete_user_account(self, user_id: int, password: str) -> bool:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return False
            if not password or not password.strip() or not verify_password(password.strip(), user.password_hash):
                raise ValueError("Password confirmation failed. Incorrect password.")
            db.query(UserSession).filter(UserSession.user_id == user_id).delete()
            db.query(RemovalJob).filter(RemovalJob.user_id == user_id).delete()
            db.delete(user)
            db.commit()
            return True

    def regenerate_user_api_key(self, user_id: int) -> Optional[Dict[str, Any]]:
        # Personal developer API keys access disabled per security policy
        return None

    def get_user_dashboard_data(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        model_filter: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return None

            base_q = db.query(RemovalJob).filter(RemovalJob.user_id == user_id)
            total_user_jobs = base_q.count()
            avg_time = (
                db.query(func.avg(RemovalJob.process_time_ms))
                .filter(RemovalJob.user_id == user_id)
                .scalar()
                or 0.0
            )
            total_bytes = (
                db.query(func.sum(RemovalJob.output_size_bytes))
                .filter(RemovalJob.user_id == user_id)
                .scalar()
                or 0
            )
            model_rows = (
                db.query(RemovalJob.model_used, func.count(RemovalJob.id))
                .filter(RemovalJob.user_id == user_id)
                .group_by(RemovalJob.model_used)
                .all()
            )
            models_breakdown = {row[0]: row[1] for row in model_rows}
            top_model = max(models_breakdown, key=models_breakdown.get) if models_breakdown else "u2net"

            q = base_q
            if search and search.strip():
                term = f"%{search.strip()}%"
                q = q.filter(
                    or_(
                        RemovalJob.original_filename.ilike(term),
                        RemovalJob.output_filename.ilike(term),
                        RemovalJob.model_used.ilike(term),
                    )
                )
            if model_filter and model_filter.strip():
                q = q.filter(RemovalJob.model_used == model_filter.strip())

            filtered_total = q.count()
            jobs = (
                q.order_by(desc(RemovalJob.created_at), desc(RemovalJob.id))
                .offset(offset)
                .limit(limit)
                .all()
            )
            stats_obj = {
                "total_jobs": total_user_jobs,
                "avg_process_time_ms": round(float(avg_time), 2),
                "total_output_bytes": int(total_bytes),
                "total_storage_mb": round(float(total_bytes) / (1024 * 1024), 2),
                "top_model": top_model,
                "favorite_model": top_model,
                "models_breakdown": models_breakdown,
                "model_breakdown": models_breakdown,
            }
            return {
                "user": user.to_dict(include_api_key=False),
                "kpis": stats_obj,
                "stats": stats_obj,
                "jobs": [j.to_dict() for j in jobs],
                "filtered_total": filtered_total,
            }

    def delete_user_job(self, user_id: int, job_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            job = (
                db.query(RemovalJob)
                .filter(RemovalJob.id == job_id, RemovalJob.user_id == user_id)
                .first()
            )
            if not job:
                return None
            data = job.to_dict()
            db.delete(job)
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if user and (user.jobs_count or 0) > 0:
                user.jobs_count = max(0, int(user.jobs_count) - 1)
            db.commit()
            return data

    def clear_user_jobs(self, user_id: int) -> List[Dict[str, Any]]:
        with self.get_session() as db:
            jobs = db.query(RemovalJob).filter(RemovalJob.user_id == user_id).all()
            data = [j.to_dict() for j in jobs]
            db.query(RemovalJob).filter(RemovalJob.user_id == user_id).delete()
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if user:
                user.jobs_count = 0
            db.commit()
            return data

    def admin_list_users(self, search: Optional[str] = None) -> Dict[str, Any]:
        with self.get_session() as db:
            q = db.query(AppUser)
            if search and search.strip():
                term = f"%{search.strip()}%"
                q = q.filter(
                    or_(
                        AppUser.username.ilike(term),
                        AppUser.email.ilike(term),
                        AppUser.full_name.ilike(term),
                    )
                )
            users = q.order_by(desc(AppUser.created_at), desc(AppUser.id)).all()
            total_all = db.query(func.count(AppUser.id)).scalar() or 0
            active_count = (
                db.query(func.count(AppUser.id)).filter(AppUser.is_active == True).scalar() or 0  # noqa: E712
            )
            return {
                "total": len(users),
                "users": [u.to_dict(include_api_key=True) for u in users],
                "stats": {
                    "total_users": total_all,
                    "active_users": active_count,
                    "suspended_users": max(0, total_all - active_count),
                },
            }

    def admin_update_user(
        self,
        user_id: int,
        is_active: Optional[bool] = None,
        email_verified: Optional[bool] = None,
        plan_tier: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return None
            if is_active is not None:
                user.is_active = bool(is_active)
            if email_verified is not None:
                user.email_verified = bool(email_verified)
                if user.email_verified:
                    user.is_active = True
                    user.verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    user.verification_code = None
                    user.verification_token = None
            if plan_tier is not None and plan_tier.strip():
                user.plan_tier = plan_tier.strip()
            db.commit()
            db.refresh(user)
            return user.to_dict(include_api_key=True)

    def admin_delete_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        with self.get_session() as db:
            user = db.query(AppUser).filter(AppUser.id == user_id).first()
            if not user:
                return None
            data = user.to_dict(include_api_key=False)
            db.delete(user)
            db.commit()
            return data

    def save_contact_message(
        self,
        name: str,
        email: str,
        subject: str,
        message: str,
        client_ip: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Save a new contact/feedback message."""
        with self.get_session() as db:
            msg = ContactMessage(
                name=name.strip(),
                email=email.strip().lower(),
                subject=subject.strip(),
                message=message.strip(),
                client_ip=client_ip,
                is_read=False,
            )
            db.add(msg)
            db.commit()
            db.refresh(msg)
            return msg.to_dict()

    def list_contact_messages(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List received contact inquiries."""
        with self.get_session() as db:
            q = db.query(ContactMessage)
            total = q.count()
            messages = q.order_by(desc(ContactMessage.created_at), desc(ContactMessage.id)).offset(offset).limit(limit).all()
            return {
                "total": total,
                "messages": [m.to_dict() for m in messages],
            }

    # --------------------------------------------------------
    # PERSISTENT SESSION MANAGEMENT (Multi-worker & Restart resilient)
    # --------------------------------------------------------
    def create_user_session(self, user_id: int, token: str, days: int = 30) -> None:
        """Store persistent user session token."""
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
        with self.get_session() as db:
            sess = UserSession(token=token.strip(), user_id=user_id, expires_at=expires)
            db.add(sess)
            db.commit()

    def get_user_by_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate session token and return active user profile."""
        if not token or not token.strip():
            return None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.get_session() as db:
            sess = (
                db.query(UserSession)
                .filter(UserSession.token == token.strip(), UserSession.expires_at > now)
                .first()
            )
            if not sess:
                return None
            user = db.query(AppUser).filter(AppUser.id == sess.user_id).first()
            if not user or not user.is_active:
                return None
            return user.to_dict()

    def delete_user_session(self, token: str) -> None:
        """Revoke a user session token upon logout."""
        if not token or not token.strip():
            return
        with self.get_session() as db:
            db.query(UserSession).filter(UserSession.token == token.strip()).delete()
            db.commit()

    def create_admin_session(self, admin_id: int, token: str, days: int = 7) -> None:
        """Store persistent admin session token."""
        expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=days)
        with self.get_session() as db:
            sess = AdminSession(token=token.strip(), admin_id=admin_id, expires_at=expires)
            db.add(sess)
            db.commit()

    def get_admin_by_session_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate admin session token and return admin profile."""
        if not token or not token.strip():
            return None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.get_session() as db:
            sess = (
                db.query(AdminSession)
                .filter(AdminSession.token == token.strip(), AdminSession.expires_at > now)
                .first()
            )
            if not sess:
                return None
            admin = db.query(AdminUser).filter(AdminUser.id == sess.admin_id).first()
            if not admin:
                return None
            return admin.to_dict()

    def delete_admin_session(self, token: str) -> None:
        """Revoke an admin session token upon logout."""
        if not token or not token.strip():
            return
        with self.get_session() as db:
            db.query(AdminSession).filter(AdminSession.token == token.strip()).delete()
            db.commit()

    def record_indexnow_submission(
        self,
        host: str,
        key: str,
        urls: List[str],
        endpoint: str,
        status_code: Optional[int],
        response_body: Optional[str],
        status: str,
        triggered_by: str = "manual",
    ) -> Dict[str, Any]:
        """Record an IndexNow real-time search engine submission."""
        import json
        with self.get_session() as db:
            sub = IndexNowSubmission(
                host=host,
                key=key,
                urls_count=len(urls),
                urls_json=json.dumps(urls),
                endpoint=endpoint,
                status_code=status_code,
                response_body=(response_body or "")[:2000],
                status=status,
                triggered_by=triggered_by,
            )
            db.add(sub)
            db.commit()
            db.refresh(sub)
            return sub.to_dict()

    def list_indexnow_submissions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent IndexNow submissions."""
        with self.get_session() as db:
            subs = (
                db.query(IndexNowSubmission)
                .order_by(desc(IndexNowSubmission.id))
                .limit(limit)
                .all()
            )
            return [s.to_dict() for s in subs]

    def clear_indexnow_submissions(self) -> int:
        """Clear the IndexNow submission history log."""
        with self.get_session() as db:
            count = db.query(IndexNowSubmission).delete()
            db.commit()
            return count


# Global database manager instance
db_manager = DatabaseManager()
