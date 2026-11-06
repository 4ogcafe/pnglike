import io
import math
import random
from typing import Optional, Dict, Any, Tuple
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageColor
from rembg import remove

Image.MAX_IMAGE_PIXELS = 50_000_000


def _ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (20, 24, 36))
        bg.paste(img, mask=img.split()[3])
        return bg
    elif img.mode != "RGB":
        return img.convert("RGB")
    return img


def _get_subject_mask(img: Image.Image, session: Any) -> np.ndarray:
    """Return a float32 mask (0.0 to 1.0) of the foreground subject using rembg."""
    mask_img = remove(img, session=session, only_mask=True, post_process_mask=True)
    if mask_img.mode != "L":
        mask_img = mask_img.convert("L")
    if mask_img.size != img.size:
        mask_img = mask_img.resize(img.size, Image.Resampling.LANCZOS)
    return np.asarray(mask_img, dtype=np.float32) / 255.0


# ============================================================
# 1. IMAGE EDITOR
# ============================================================
def tool_image_editor(
    img: Image.Image,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    sharpness: float = 1.0,
    warmth: float = 0.0,
    blur: float = 0.0,
    rotate: int = 0,
    flip_h: bool = False,
    flip_v: bool = False,
    filter_preset: str = "none",
    crop_ratio: str = "original",
) -> Image.Image:
    """Full photo editor with color adjustments, transforms, crop ratios, and filters."""
    has_alpha = img.mode == "RGBA"
    alpha = img.split()[3] if has_alpha else None
    work = img.convert("RGB")

    # 1. Transforms (Rotate & Flip)
    if rotate in (90, 180, 270):
        work = work.rotate(-rotate, expand=True)
        if alpha:
            alpha = alpha.rotate(-rotate, expand=True)
    if flip_h:
        work = ImageOps.mirror(work)
        if alpha:
            alpha = ImageOps.mirror(alpha)
    if flip_v:
        work = ImageOps.flip(work)
        if alpha:
            alpha = ImageOps.flip(alpha)

    # 2. Aspect Ratio Center Crop
    ratio_map = {
        "1:1": 1.0,
        "16:9": 16.0 / 9.0,
        "9:16": 9.0 / 16.0,
        "4:3": 4.0 / 3.0,
    }
    if crop_ratio in ratio_map:
        target_r = ratio_map[crop_ratio]
        cw, ch = work.size
        curr_r = cw / ch
        if curr_r > target_r:
            new_w = int(ch * target_r)
            left = (cw - new_w) // 2
            box = (left, 0, left + new_w, ch)
        else:
            new_h = int(cw / target_r)
            top = (ch - new_h) // 2
            box = (0, top, cw, top + new_h)
        work = work.crop(box)
        if alpha:
            alpha = alpha.crop(box)

    # 3. Enhancements
    if abs(brightness - 1.0) > 0.01:
        work = ImageEnhance.Brightness(work).enhance(max(0.1, min(3.0, brightness)))
    if abs(contrast - 1.0) > 0.01:
        work = ImageEnhance.Contrast(work).enhance(max(0.1, min(3.0, contrast)))
    if abs(saturation - 1.0) > 0.01:
        work = ImageEnhance.Color(work).enhance(max(0.0, min(3.0, saturation)))
    if abs(sharpness - 1.0) > 0.01:
        work = ImageEnhance.Sharpness(work).enhance(max(0.0, min(4.0, sharpness)))
    if blur > 0.1:
        work = work.filter(ImageFilter.GaussianBlur(radius=min(25.0, blur)))

    # 4. Warmth & Filter Presets
    arr = np.asarray(work, dtype=np.float32)
    if abs(warmth) > 0.5:
        arr[..., 0] = np.clip(arr[..., 0] + warmth * 1.2, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] - warmth * 1.2, 0, 255)

    fp = filter_preset.lower()
    if fp == "vintage":
        # Sepia / warm faded curve
        r = arr[..., 0] * 0.393 + arr[..., 1] * 0.769 + arr[..., 2] * 0.189
        g = arr[..., 0] * 0.349 + arr[..., 1] * 0.686 + arr[..., 2] * 0.168
        b = arr[..., 0] * 0.272 + arr[..., 1] * 0.534 + arr[..., 2] * 0.131
        sepia = np.stack([r, g, b], axis=-1)
        arr = np.clip(arr * 0.35 + sepia * 0.65 + 10, 0, 255)
    elif fp == "noir":
        gray = arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114
        gray = np.clip((gray - 128) * 1.35 + 128, 0, 255)
        arr = np.stack([gray, gray, gray], axis=-1)
    elif fp == "vivid":
        hsv = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        hsv[..., 1] = np.clip(hsv[..., 1] * 1.4, 0, 255)
        hsv[..., 2] = np.clip(hsv[..., 2] * 1.08, 0, 255)
        arr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)
    elif fp == "cool_matte":
        arr = np.clip(arr * 0.88 + 22, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] + 18, 0, 255)

    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGB")
    if alpha:
        out.putalpha(alpha)
    return out


# ============================================================
# 3. IMAGE UPSCALER
# ============================================================
def tool_image_upscaler(
    img: Image.Image,
    scale: int = 2,
    denoise: float = 0.35,
    sharpen: float = 0.65,
) -> Image.Image:
    """
    Super-Resolution & Detail Enhancer using Lanczos-4 interpolation,
    edge-preserving bilateral denoising, CLAHE micro-contrast, and unsharp masking.
    """
    scale = 4 if scale >= 4 else 2
    orig_w, orig_h = img.size
    # Cap maximum dimension at 3840px (4K) so memory remains bounded
    max_dim = 3840
    if max(orig_w * scale, orig_h * scale) > max_dim:
        eff_scale = max_dim / max(orig_w, orig_h)
        new_w, new_h = max(1, int(orig_w * eff_scale)), max(1, int(orig_h * eff_scale))
    else:
        new_w, new_h = orig_w * scale, orig_h * scale

    has_alpha = img.mode == "RGBA"
    alpha = img.split()[3].resize((new_w, new_h), Image.Resampling.LANCZOS) if has_alpha else None
    rgb = img.convert("RGB")

    # Step 1: High-order Lanczos resize
    upscaled = rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
    arr = np.asarray(upscaled, dtype=np.uint8)

    # Step 2: Edge-preserving bilateral filter to remove compression artifacts
    if denoise > 0.05:
        d_sigma = int(15 + denoise * 45)
        arr = cv2.bilateralFilter(arr, d=5, sigmaColor=d_sigma, sigmaSpace=d_sigma)

    # Step 3: Subtle CLAHE local contrast enhancement on L channel
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=1.4, tileGridSize=(8, 8))
    l_enhanced = clahe.apply(l_chan)
    l_blended = cv2.addWeighted(l_chan, 0.65, l_enhanced, 0.35, 0)
    arr = cv2.cvtColor(cv2.merge([l_blended, a_chan, b_chan]), cv2.COLOR_LAB2RGB)

    # Step 4: Unsharp Masking for crisp high-frequency edge restoration
    if sharpen > 0.05:
        gaussian = cv2.GaussianBlur(arr, (0, 0), sigmaX=1.5)
        amount = float(sharpen * 1.35)
        arr = cv2.addWeighted(arr, 1.0 + amount, gaussian, -amount, 0)

    out = Image.fromarray(arr, mode="RGB")
    if alpha:
        out.putalpha(alpha)
    return out


# ============================================================
# 4. IMAGE EXTENDER (OUTPAINTING / UNCROP)
# ============================================================
def tool_image_extender(
    img: Image.Image,
    target_ratio: str = "16:9",
    expand_percent: int = 25,
    mode: str = "inpaint",
) -> Image.Image:
    """
    Outpaint / extend image borders using OpenCV Telea inpainting + reflected
    context feathering to seamlessly fill expanded aspect ratios or margins.
    """
    rgb = _ensure_rgb(img)
    arr = np.asarray(rgb, dtype=np.uint8)
    h, w, _ = arr.shape

    ratio_map = {
        "16:9": 16.0 / 9.0,
        "9:16": 9.0 / 16.0,
        "1:1": 1.0,
        "4:3": 4.0 / 3.0,
    }

    if target_ratio in ratio_map:
        tr = ratio_map[target_ratio]
        curr_r = w / h
        if abs(curr_r - tr) < 0.05:
            pad_x = int(w * (expand_percent / 200.0))
            pad_y = int(h * (expand_percent / 200.0))
            top, bottom, left, right = pad_y, pad_y, pad_x, pad_x
        elif curr_r < tr:
            new_w = int(h * tr)
            total_pad = max(20, new_w - w)
            left = total_pad // 2
            right = total_pad - left
            top, bottom = 0, 0
        else:
            new_h = int(w / tr)
            total_pad = max(20, new_h - h)
            top = total_pad // 2
            bottom = total_pad - top
            left, right = 0, 0
    else:
        pad_x = max(16, int(w * (expand_percent / 200.0)))
        pad_y = max(16, int(h * (expand_percent / 200.0)))
        top, bottom, left, right = pad_y, pad_y, pad_x, pad_x

    # Mirror-reflect base border for natural texture continuation
    reflected = cv2.copyMakeBorder(arr, top, bottom, left, right, cv2.BORDER_REFLECT_101)
    nh, nw, _ = reflected.shape

    # Create mask of extended region
    mask = np.ones((nh, nw), dtype=np.uint8) * 255
    mask[top : top + h, left : left + w] = 0

    if mode == "blur_ambient":
        blurred = cv2.GaussianBlur(reflected, (0, 0), sigmaX=24)
        feathered_mask = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), sigmaX=12)[..., None]
        out_arr = (reflected * (1.0 - feathered_mask) + blurred * feathered_mask).astype(np.uint8)
    else:
        # Downscale for fast Navier-Stokes/Telea inpainting, then blend with high-freq reflection
        scale_f = min(1.0, 480.0 / max(nh, nw))
        sw, sh = max(32, int(nw * scale_f)), max(32, int(nh * scale_f))
        small_img = cv2.resize(reflected, (sw, sh), interpolation=cv2.INTER_AREA)
        small_mask = cv2.resize(mask, (sw, sh), interpolation=cv2.INTER_NEAREST)

        # Inpaint the boundary seam and outer region
        inpainted_small = cv2.inpaint(small_img, small_mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
        inpainted_full = cv2.resize(inpainted_small, (nw, nh), interpolation=cv2.INTER_CUBIC)

        # Blend reflected texture (30% softly blurred) with inpainted colour structure (70%)
        soft_ref = cv2.GaussianBlur(reflected, (0, 0), sigmaX=9)
        ext_blend = cv2.addWeighted(inpainted_full, 0.65, soft_ref, 0.35, 0)

        feather = cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), sigmaX=10)[..., None]
        out_arr = np.clip(reflected * (1.0 - feather) + ext_blend * feather, 0, 255).astype(np.uint8)

    return Image.fromarray(out_arr, mode="RGB")


# ============================================================
# 5. VARIATIONS
# ============================================================
def tool_variations(
    img: Image.Image,
    variation_style: str = "grid_all",
    strength: float = 0.75,
) -> Image.Image:
    """
    Generate creative color/lighting/mood variations of an image.
    Supports a 2x2 quad showcase grid ('grid_all') or single style variations.
    """
    rgb = _ensure_rgb(img)
    arr = np.asarray(rgb, dtype=np.float32)

    def _make_variant(vtype: str) -> Image.Image:
        a = arr.copy()
        if vtype == "cyber_neon":
            # Cyberpunk magenta-cyan split tone
            lum = (a[..., 0] * 0.299 + a[..., 1] * 0.587 + a[..., 2] * 0.114) / 255.0
            shadows = (1.0 - lum)[..., None] * np.array([35, 10, 95], dtype=np.float32)
            highlights = lum[..., None] * np.array([255, 65, 200], dtype=np.float32)
            styled = np.clip(a * 0.45 + (shadows + highlights) * 0.75, 0, 255)
        elif vtype == "golden_hour":
            # Warm golden sunlight glow
            styled = a.copy()
            styled[..., 0] = np.clip(styled[..., 0] * 1.18 + 18, 0, 255)
            styled[..., 1] = np.clip(styled[..., 1] * 1.04 + 6, 0, 255)
            styled[..., 2] = np.clip(styled[..., 2] * 0.82, 0, 255)
        elif vtype == "emerald_cinema":
            # Moody emerald & gold
            styled = a.copy()
            styled[..., 0] = np.clip(styled[..., 0] * 0.92, 0, 255)
            styled[..., 1] = np.clip(styled[..., 1] * 1.12 + 10, 0, 255)
            styled[..., 2] = np.clip(styled[..., 2] * 0.95 + 8, 0, 255)
        else:
            # High-contrast pop art / dreamy bloom
            blur = cv2.GaussianBlur(a.astype(np.uint8), (0, 0), sigmaX=12).astype(np.float32)
            styled = np.clip(a * 0.75 + blur * 0.38, 0, 255)
            styled[..., 2] = np.clip(styled[..., 2] * 1.15, 0, 255)

        blended = np.clip(arr * (1.0 - strength) + styled * strength, 0, 255).astype(np.uint8)
        return Image.fromarray(blended, mode="RGB")

    if variation_style != "grid_all":
        return _make_variant(variation_style)

    # Create a 2x2 variation sheet at full resolution
    w, h = rgb.size
    hw, hh = max(120, w // 2), max(120, h // 2)
    v1 = _make_variant("golden_hour").resize((hw, hh), Image.Resampling.LANCZOS)
    v2 = _make_variant("cyber_neon").resize((hw, hh), Image.Resampling.LANCZOS)
    v3 = _make_variant("emerald_cinema").resize((hw, hh), Image.Resampling.LANCZOS)
    v4 = _make_variant("dreamy_bloom").resize((hw, hh), Image.Resampling.LANCZOS)

    gap = 6
    sheet = Image.new("RGB", (hw * 2 + gap, hh * 2 + gap), (15, 23, 42))
    sheet.paste(v1, (0, 0))
    sheet.paste(v2, (hw + gap, 0))
    sheet.paste(v3, (0, hh + gap))
    sheet.paste(v4, (hw + gap, hh + gap))

    draw = ImageDraw.Draw(sheet, "RGBA")
    labels = [
        (10, 10, "V1 • Golden Hour"),
        (hw + gap + 10, 10, "V2 • Cyber Neon"),
        (10, hh + gap + 10, "V3 • Emerald Cinema"),
        (hw + gap + 10, hh + gap + 10, "V4 • Dreamy Bloom"),
    ]
    for lx, ly, text in labels:
        draw.rounded_rectangle([lx, ly, lx + len(text) * 6 + 16, ly + 22], radius=5, fill=(15, 23, 42, 185))
        draw.text((lx + 8, ly + 4), text, fill=(255, 255, 255, 240))

    return sheet


# ============================================================
# 6. CINEMATIC SHOT
# ============================================================
def tool_cinematic_shot(
    img: Image.Image,
    session: Any,
    color_grade: str = "teal_orange",
    bokeh_blur: float = 10.0,
    letterbox: bool = True,
    anamorphic_flare: bool = True,
    film_grain: float = 0.18,
) -> Image.Image:
    """
    Transform an image into a Hollywood movie frame:
    1. AI subject segmentation (`rembg`) keeps foreground subject sharp while
       applying shallow depth-of-field bokeh to the background.
    2. Split-tone color grading (Teal & Orange, Bleach Bypass, Cyberpunk, Noir).
    3. Anamorphic horizontal cyan lens flare, vignette, film grain & 2.39:1 letterbox.
    """
    rgb = _ensure_rgb(img)
    w, h = rgb.size
    arr = np.asarray(rgb, dtype=np.float32)

    # 1. Subject-aware shallow depth-of-field bokeh
    if bokeh_blur > 0.5 and session is not None:
        mask = _get_subject_mask(rgb, session)[..., None]
        bg_blurred = cv2.GaussianBlur(arr.astype(np.uint8), (0, 0), sigmaX=min(30.0, bokeh_blur)).astype(np.float32)
        arr = arr * mask + bg_blurred * (1.0 - mask)

    # 2. Cinematic Split-Toning Color Grade
    lum = (arr[..., 0] * 0.299 + arr[..., 1] * 0.587 + arr[..., 2] * 0.114) / 255.0
    cg = color_grade.lower()
    if cg == "teal_orange":
        # Push shadows toward deep teal, highlights/midtones toward warm amber
        shadow_w = (1.0 - lum)[..., None]
        high_w = lum[..., None]
        arr[..., 0] = np.clip(arr[..., 0] + high_w[..., 0] * 24 - shadow_w[..., 0] * 18, 0, 255)
        arr[..., 1] = np.clip(arr[..., 1] + high_w[..., 0] * 6 + shadow_w[..., 0] * 4, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] - high_w[..., 0] * 20 + shadow_w[..., 0] * 26, 0, 255)
    elif cg == "bleach_bypass":
        gray = (lum * 255.0)[..., None]
        arr = arr * 0.45 + gray * 0.55
        arr = np.clip((arr - 128) * 1.28 + 128, 0, 255)
    elif cg == "matrix_green":
        arr[..., 1] = np.clip(arr[..., 1] * 1.18 + 12, 0, 255)
        arr[..., 0] = np.clip(arr[..., 0] * 0.85, 0, 255)

    # S-curve contrast boost
    norm = arr / 255.0
    curved = np.clip(0.5 + np.sin((norm - 0.5) * math.pi * 0.88) * 0.52, 0, 1)
    arr = curved * 255.0

    # 3. Anamorphic horizontal streak flare
    if anamorphic_flare:
        yy = np.linspace(0, 1, h)[:, None]
        xx = np.linspace(0, 1, w)[None, :]
        streak = np.exp(-((yy - 0.38) ** 2) / 0.0025) * np.exp(-((xx - 0.5) ** 2) / 0.18)
        arr[..., 0] = np.clip(arr[..., 0] + streak * 35, 0, 255)
        arr[..., 1] = np.clip(arr[..., 1] + streak * 165, 0, 255)
        arr[..., 2] = np.clip(arr[..., 2] + streak * 255, 0, 255)

    # 4. Optical Vignette
    yy = np.linspace(-1, 1, h)[:, None]
    xx = np.linspace(-1, 1, w)[None, :]
    rad = np.sqrt(xx**2 + yy**2)
    vig = np.clip(1.0 - np.maximum(0, rad - 0.55) * 0.65, 0.35, 1.0)[..., None]
    arr = arr * vig

    # 5. Subtle 35mm Film Grain
    if film_grain > 0.01:
        rng = np.random.default_rng(42)
        noise = rng.normal(0, film_grain * 28.0, size=arr.shape).astype(np.float32)
        arr = np.clip(arr + noise, 0, 255)

    # 6. CinemaScope 2.39:1 Letterbox Bars
    if letterbox:
        bar_h = max(18, int(h * 0.10))
        arr[:bar_h, :, :] = 8
        arr[h - bar_h :, :, :] = 8

    return Image.fromarray(arr.astype(np.uint8), mode="RGB")


# ============================================================
# 7. SKIN ENHANCER
# ============================================================
def tool_skin_enhancer(
    img: Image.Image,
    smoothing: float = 0.65,
    radiance: float = 0.25,
    detail_crispness: float = 0.5,
) -> Image.Image:
    """
    Portrait Skin Retouching & Frequency-Selective Smoothing:
    Detects skin regions in YCrCb space and blends edge-preserving bilateral
    smoothing while keeping eyes, hair, and structural details tack-sharp.
    """
    has_alpha = img.mode == "RGBA"
    alpha = img.split()[3] if has_alpha else None
    rgb = _ensure_rgb(img)
    arr = np.asarray(rgb, dtype=np.uint8)

    # 1. Detect skin-tone mask in YCrCb color space
    ycrcb = cv2.cvtColor(arr, cv2.COLOR_RGB2YCrCb)
    skin_mask = cv2.inRange(ycrcb, np.array([35, 130, 75]), np.array([255, 180, 135]))
    skin_float = cv2.GaussianBlur(skin_mask.astype(np.float32) / 255.0, (0, 0), sigmaX=9)[..., None]
    # Ensure general smoothing still applies gently even on non-typical lighting
    blend_mask = np.clip(skin_float * 0.75 + 0.25, 0.0, 1.0) * min(1.0, max(0.0, smoothing))

    # 2. Multi-pass edge-preserving bilateral filter
    sigma_c = int(25 + smoothing * 55)
    sigma_s = int(15 + smoothing * 35)
    smooth_arr = cv2.bilateralFilter(arr, d=9, sigmaColor=sigma_c, sigmaSpace=sigma_s)
    smooth_arr = cv2.bilateralFilter(smooth_arr, d=7, sigmaColor=sigma_c // 2, sigmaSpace=sigma_s // 2)

    # 3. Blend smoothed skin with original
    f_orig = arr.astype(np.float32)
    f_smooth = smooth_arr.astype(np.float32)
    retouched = f_orig * (1.0 - blend_mask) + f_smooth * blend_mask

    # 4. Soft skin radiance / glow boost
    if radiance > 0.02:
        bloom = cv2.GaussianBlur(retouched.astype(np.uint8), (0, 0), sigmaX=16).astype(np.float32)
        retouched = np.clip(retouched + bloom * (radiance * 0.28) * blend_mask, 0, 255)

    # 5. High-frequency detail restoration for eyes, lashes & lips
    if detail_crispness > 0.05:
        high_pass = f_orig - cv2.GaussianBlur(f_orig, (0, 0), sigmaX=1.2)
        non_skin = 1.0 - (skin_float * 0.65)
        retouched = np.clip(retouched + high_pass * detail_crispness * non_skin, 0, 255)

    out = Image.fromarray(retouched.astype(np.uint8), mode="RGB")
    if alpha:
        out.putalpha(alpha)
    return out


# ============================================================
# 8. RELIGHT (AI SUBJECT-AWARE 3D STUDIO RELIGHTING)
# ============================================================
def tool_relight(
    img: Image.Image,
    session: Any,
    light_position: str = "left",
    light_color: str = "#3b82f6",
    secondary_color: str = "#ec4899",
    light_intensity: float = 0.75,
    ambient_dim: float = 0.65,
) -> Image.Image:
    """
    AI Subject-Aware Studio Relighting:
    1. Segments the foreground subject via `rembg`.
    2. Estimates 3D surface normals from subject luminance & contour gradients.
    3. Projects directional key light + rim light onto the subject while dimming
       the background ambient light.
    """
    rgb = _ensure_rgb(img)
    w, h = rgb.size
    arr = np.asarray(rgb, dtype=np.float32)

    mask = _get_subject_mask(rgb, session) if session is not None else np.ones((h, w), dtype=np.float32)
    mask3 = mask[..., None]

    # Parse primary and secondary light RGB
    try:
        l_rgb = np.array(ImageColor.getrgb(light_color)[:3], dtype=np.float32)
    except Exception:
        l_rgb = np.array([59, 130, 246], dtype=np.float32)

    try:
        s_rgb = np.array(ImageColor.getrgb(secondary_color)[:3], dtype=np.float32)
    except Exception:
        s_rgb = np.array([236, 72, 153], dtype=np.float32)

    # Compute pseudo-normals from smoothed luminance + silhouette distance transform
    gray = cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    smooth_gray = cv2.GaussianBlur(gray, (0, 0), sigmaX=6)
    gx = cv2.Sobel(smooth_gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(smooth_gray, cv2.CV_32F, 0, 1, ksize=3)

    yy = np.linspace(-1, 1, h)[:, None]
    xx = np.linspace(-1, 1, w)[None, :]

    pos_map = {
        "left": (-0.85, -0.15),
        "right": (0.85, -0.15),
        "top_left": (-0.75, -0.75),
        "top_right": (0.75, -0.75),
        "center_rim": (0.0, -0.85),
        "dual_neon": (-0.9, 0.0),
    }
    lx, ly = pos_map.get(light_position.lower(), (-0.85, -0.15))

    # Directional spatial falloff + surface normal dot product
    spatial_falloff = np.clip(1.15 - np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) * 0.55, 0.0, 1.0)
    normal_term = np.clip(0.65 - (gx * lx + gy * ly) * 1.4, 0.2, 1.5)
    key_light = (spatial_falloff * normal_term)[..., None]

    # Rim highlight along subject contour edge
    edge_grad = cv2.Laplacian(mask, cv2.CV_32F, ksize=3)
    rim = cv2.GaussianBlur(np.abs(edge_grad), (0, 0), sigmaX=4)[..., None]

    # Dim background and unlit side of subject
    bg_factor = max(0.08, 1.0 - ambient_dim * 0.85)
    subj_ambient = max(0.25, 1.0 - ambient_dim * 0.55)

    lit_subject = (
        arr * subj_ambient
        + (arr / 255.0) * l_rgb * key_light * (light_intensity * 1.45)
        + l_rgb * rim * (light_intensity * 1.1)
    )

    if light_position.lower() == "dual_neon":
        # Opposite side secondary neon light
        opp_falloff = np.clip(1.15 - np.sqrt((xx - 0.9) ** 2 + yy ** 2) * 0.55, 0.0, 1.0)[..., None]
        lit_subject += (arr / 255.0) * s_rgb * opp_falloff * (light_intensity * 1.25)

    lit_bg = arr * bg_factor + l_rgb * 0.08 * spatial_falloff[..., None]
    final_arr = np.clip(lit_subject * mask3 + lit_bg * (1.0 - mask3), 0, 255).astype(np.uint8)
    return Image.fromarray(final_arr, mode="RGB")


# ============================================================
# 9. CHANGE CAMERA (3D PERSPECTIVE & LENS OPTICS)
# ============================================================
def tool_change_camera(
    img: Image.Image,
    session: Any,
    camera_angle: str = "low_angle",
    lens_type: str = "standard",
    intensity: float = 0.6,
) -> Image.Image:
    """
    Simulate 3D camera viewpoint changes (Low Angle Hero, High Overhead,
    Left/Right 3D Orbit, Dutch Tilt) and optical lenses (16mm Wide Barrel,
    85mm f/1.4 Telephoto Portrait Bokeh, Fisheye).
    """
    rgb = _ensure_rgb(img)
    w, h = rgb.size
    arr = np.asarray(rgb, dtype=np.uint8)

    # 1. Optional 85mm Telephoto Portrait Bokeh (before perspective warp)
    lt = lens_type.lower()
    if lt == "telephoto_85mm" and session is not None:
        mask = _get_subject_mask(rgb, session)[..., None]
        blurred_bg = cv2.GaussianBlur(arr, (0, 0), sigmaX=8 + intensity * 14)
        arr = np.clip(arr * mask + blurred_bg * (1.0 - mask), 0, 255).astype(np.uint8)

    # 2. 3D Perspective Homography Transform
    strength = max(0.05, min(1.0, intensity)) * 0.16
    src_pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dx = w * strength
    dy = h * strength

    angle = camera_angle.lower()
    if angle == "low_angle":
        # Camera tilts up: top narrows inward, bottom expands outward
        dst_pts = np.float32([[dx, dy * 0.4], [w - dx, dy * 0.4], [w + dx * 0.3, h], [-dx * 0.3, h]])
    elif angle == "high_angle":
        # Camera looks down: top expands, bottom narrows inward
        dst_pts = np.float32([[-dx * 0.3, 0], [w + dx * 0.3, 0], [w - dx, h - dy * 0.4], [dx, h - dy * 0.4]])
    elif angle == "orbit_left":
        # 3D yaw orbit from left
        dst_pts = np.float32([[0, dy * 0.5], [w - dx * 0.4, 0], [w - dx * 0.4, h], [0, h - dy * 0.5]])
    elif angle == "orbit_right":
        # 3D yaw orbit from right
        dst_pts = np.float32([[dx * 0.4, 0], [w, dy * 0.5], [w, h - dy * 0.5], [dx * 0.4, h]])
    elif angle == "dutch_tilt":
        # Cinema Dutch roll + slight zoom so corners stay filled
        M_rot = cv2.getRotationMatrix2D((w / 2, h / 2), 12.0 * (intensity + 0.3), 1.18)
        arr = cv2.warpAffine(arr, M_rot, (w, h), borderMode=cv2.BORDER_REFLECT_101)
        dst_pts = src_pts
    else:
        dst_pts = src_pts

    if not np.allclose(src_pts, dst_pts):
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        arr = cv2.warpPerspective(arr, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)

    # 3. Optical Lens Distortion (16mm Wide Barrel / Fisheye / 85mm Zoom Crop)
    if lt in ("wide_16mm", "fisheye"):
        k = 0.22 * intensity if lt == "wide_16mm" else 0.52 * intensity
        yy, xx = np.indices((h, w), dtype=np.float32)
        nx = (xx - w / 2.0) / (w / 2.0)
        ny = (yy - h / 2.0) / (h / 2.0)
        r2 = nx * nx + ny * ny
        factor = (1.0 + k * r2) / (1.0 + k * 0.65)
        map_x = (nx * factor) * (w / 2.0) + (w / 2.0)
        map_y = (ny * factor) * (h / 2.0) + (h / 2.0)
        arr = cv2.remap(arr, map_x, map_y, interpolation=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
    elif lt == "telephoto_85mm":
        # Slight optical compression zoom
        zx = int(w * 0.08 * intensity)
        zy = int(h * 0.08 * intensity)
        if zx > 2 and zy > 2:
            cropped = arr[zy : h - zy, zx : w - zx]
            arr = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LANCZOS4)

    return Image.fromarray(arr, mode="RGB")
