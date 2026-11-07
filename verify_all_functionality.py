import io
import os
import sys
import zipfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from PIL import Image
from fastapi.testclient import TestClient

# Ensure BASE_DIR is set
os.chdir(Path(__file__).resolve().parent)

from app import app
from database import db_manager, RemovalJob

client = TestClient(app)

SAMPLE_IMG_PATH = Path("static/samples/coffee_mug.jpg")
assert SAMPLE_IMG_PATH.exists(), f"Missing sample test image: {SAMPLE_IMG_PATH}"
SAMPLE_BYTES = SAMPLE_IMG_PATH.read_bytes()

results = []

def record(category: str, name: str, success: bool, detail: str = ""):
    status = "PASS" if success else "FAIL"
    results.append({"category": category, "name": name, "status": status, "detail": detail})
    print(f"[{status}] {category} -> {name}: {detail}")
    assert success, f"Assertion failed: {category} -> {name}: {detail}"

def test_public_pages_and_seo():
    cat = "1. Public & SEO Endpoints"
    pages = ["/", "/blog", "/dashboard", "/login", "/register", "/verify", "/admin", "/about", "/contact", "/privacy", "/terms", "/cookies", "/faq"]
    for page in pages:
        res = client.get(page)
        record(cat, f"Serve HTML {page}", res.status_code == 200, f"Status: {res.status_code}")

    # SEO Files
    r_robots = client.get("/robots.txt")
    record(cat, "GET /robots.txt", r_robots.status_code == 200 and "User-agent: *" in r_robots.text, "Robots rules delivered")

    r_sitemap = client.get("/sitemap.xml")
    record(cat, "GET /sitemap.xml", r_sitemap.status_code == 200 and "<urlset" in r_sitemap.text, "Sitemap XML valid")

    r_llms = client.get("/llms.txt")
    record(cat, "GET /llms.txt", r_llms.status_code == 200 and "PngLike" in r_llms.text, "AI Agent llms.txt delivered")

def test_public_api_configs():
    cat = "2. Public Configurations & Catalogs"
    r_cfg = client.get("/api/site-config")
    record(cat, "GET /api/site-config", r_cfg.status_code == 200 and "settings" in r_cfg.json(), f"Site title: {r_cfg.json().get('settings', {}).get('site_title')}")

    r_tools = client.get("/api/tools")
    data_tools = r_tools.json()
    tools_list = data_tools.get("tools", [])
    first_3_ids = [t["id"] for t in tools_list[:3]]
    is_default_bg = data_tools.get("default_tool") == "bg-remover"
    are_free_first = first_3_ids == ["bg-remover", "image-editor", "skin-enhancer"]
    all_free_flagged = all(t.get("is_free") is True for t in tools_list[:3])
    pro_flagged = all(t.get("is_free") is False for t in tools_list[3:])
    record(cat, "GET /api/tools (Catalog Count)", r_tools.status_code == 200 and len(tools_list) == 9, f"Tools count: {len(tools_list)}")
    record(cat, "Tool Ordering & Default (Free Tools First)", is_default_bg and are_free_first and all_free_flagged and pro_flagged, f"Default: {data_tools.get('default_tool')}, Free 3: {first_3_ids}")

    r_models = client.get("/api/models")
    data_models = r_models.json()
    record(cat, "GET /api/models", r_models.status_code == 200 and len(data_models.get("models", [])) >= 2, f"Models available: {len(data_models.get('models', []))}")

    r_samples = client.get("/api/samples")
    data_samples = r_samples.json()
    record(cat, "GET /api/samples", r_samples.status_code == 200 and len(data_samples.get("samples", [])) >= 1, f"Samples available: {len(data_samples.get('samples', []))}")

def test_admin_workflows():
    cat = "3. Admin Management System"
    # Login
    r_login = client.post("/api/admin/login", json={"username": "admin", "password": "admin123"})
    if r_login.status_code != 200:
        # Check if environment password was used or reset
        adm_pass = os.getenv("ADMIN_PASSWORD", "admin123")
        r_login = client.post("/api/admin/login", json={"username": "admin", "password": adm_pass})
    record(cat, "POST /api/admin/login", r_login.status_code == 200, f"Logged in as admin")
    token = r_login.json()["token"]
    headers = {"X-Admin-Token": token}

    r_me = client.get("/api/admin/me", headers=headers)
    record(cat, "GET /api/admin/me", r_me.status_code == 200 and r_me.json()["admin"]["username"] == "admin", "Token validated")

    r_ov = client.get("/api/admin/overview", headers=headers)
    record(cat, "GET /api/admin/overview", r_ov.status_code == 200 and "analytics" in r_ov.json(), "Metrics & status verified")

    r_set = client.get("/api/admin/settings", headers=headers)
    record(cat, "GET /api/admin/settings", r_set.status_code == 200, "CMS settings loaded")

    # Update CMS settings
    r_put = client.put("/api/admin/settings", headers=headers, json={"site_title": "RemBG Studio Pro"})
    record(cat, "PUT /api/admin/settings", r_put.status_code == 200 and r_put.json()["settings"]["site_title"] == "RemBG Studio Pro", "CMS updated")

    # Restore title
    client.put("/api/admin/settings", headers=headers, json={"site_title": "RemBG Studio"})

    # Admin jobs listing
    r_jobs = client.get("/api/admin/jobs", headers=headers)
    record(cat, "GET /api/admin/jobs", r_jobs.status_code == 200, f"Total jobs in DB: {r_jobs.json().get('total', 0)}")

    # Admin users listing
    r_users = client.get("/api/admin/users", headers=headers)
    record(cat, "GET /api/admin/users", r_users.status_code == 200, f"Total registered users: {r_users.json().get('total', 0)}")

    # IndexNow Status & Submission Verification
    r_idx_status = client.get("/api/admin/indexnow/status", headers=headers)
    record(cat, "GET /api/admin/indexnow/status", r_idx_status.status_code == 200 and r_idx_status.json().get("key_file_exists"), f"IndexNow key {r_idx_status.json().get('key')} verified")

    r_idx_submit = client.post("/api/admin/indexnow/submit", headers=headers, json={"target": "home"})
    record(cat, "POST /api/admin/indexnow/submit", r_idx_submit.status_code == 200 and r_idx_submit.json().get("urls_count") >= 1, "Submitted homepage to IndexNow")

    return headers

def test_blog_cms(admin_headers):
    cat = "4. Blog System & Admin CRUD"
    r_list = client.get("/api/blog")
    record(cat, "GET /api/blog", r_list.status_code == 200 and "posts" in r_list.json(), f"Articles published: {len(r_list.json().get('posts', []))}")

    # Create new article
    r_create = client.post(
        "/api/admin/blog",
        headers=admin_headers,
        json={
            "title": "Verifying AI Neural Masking 2026",
            "excerpt": "A deep dive into Salient Object Detection using nested U-Net architectures.",
            "content": "<p>Neural masking achieves sub-pixel edge transparency.</p>",
            "category": "AI Tutorials",
            "tags": "onnx,ai,verification",
            "author": "Div Sri",
            "is_published": True,
            "is_featured": False,
        },
    )
    record(cat, "POST /api/admin/blog", r_create.status_code == 200, f"Post created: ID {r_create.json().get('post', {}).get('id')}")
    post = r_create.json()["post"]
    post_id = post["id"]
    post_slug = post["slug"]

    # Read article by slug
    r_single = client.get(f"/api/blog/{post_slug}")
    record(cat, f"GET /api/blog/{post_slug}", r_single.status_code == 200 and r_single.json()["post"]["views_count"] >= 1, "Article fetched & view count incremented")

    # Update article
    r_update = client.put(f"/api/admin/blog/{post_id}", headers=admin_headers, json={"title": "Verifying AI Neural Masking 2026 (Updated)"})
    record(cat, f"PUT /api/admin/blog/{post_id}", r_update.status_code == 200 and "Updated" in r_update.json()["post"]["title"], "Article updated")

    # Delete article
    r_del = client.delete(f"/api/admin/blog/{post_id}", headers=admin_headers)
    record(cat, f"DELETE /api/admin/blog/{post_id}", r_del.status_code == 200, "Article deleted successfully")

def test_presets_crud(admin_headers):
    cat = "5. Presets Management"
    r_list = client.get("/api/presets")
    record(cat, "GET /api/presets", r_list.status_code == 200 and len(r_list.json().get("presets", [])) >= 3, f"Presets count: {len(r_list.json().get('presets', []))}")

    r_create = client.post(
        "/api/presets",
        headers=admin_headers,
        json={
            "name": "Verification Studio Preset",
            "model_used": "u2netp",
            "alpha_matting": True,
            "af_threshold": 240,
            "ab_threshold": 10,
            "ae_size": 10,
            "post_process_mask": True,
            "bg_mode": "solid",
            "bg_value": "#ffffff",
            "export_format": "png",
        },
    )
    record(cat, "POST /api/presets", r_create.status_code == 200, f"Preset created: ID {r_create.json().get('preset', {}).get('id')}")
    preset_id = r_create.json()["preset"]["id"]

    r_del = client.delete(f"/api/presets/{preset_id}", headers=admin_headers)
    record(cat, f"DELETE /api/presets/{preset_id}", r_del.status_code == 200, "Preset deleted successfully")

def test_user_lifecycle_and_security():
    cat = "6. User Registration, Profile & Dashboard"
    test_user_ident = "studio_creator_test"
    test_email = "creator.test@pnglike.com"
    test_pass = "CreatorSecretPass123!#"

    # Ensure clean state if previously registered
    existing = db_manager.authenticate_user(test_user_ident, test_pass)
    if existing:
        db_manager.delete_user_account(existing["id"], test_pass)

    # 1. Registration
    r_reg = client.post(
        "/api/auth/register",
        json={"username": test_user_ident, "email": test_email, "password": test_pass, "full_name": "Studio Creator"},
    )
    record(cat, "POST /api/auth/register", r_reg.status_code == 200 and r_reg.json().get("requires_verification") is True, "Registered, awaiting code")

    # Fetch verification code from DB
    with db_manager.get_session() as db:
        from database import AppUser
        user_row = db.query(AppUser).filter(AppUser.username == test_user_ident).first()
        assert user_row is not None
        v_code = user_row.verification_code

    # 2. Verify Email Code
    r_vcode = client.post("/api/auth/verify-code", json={"email": test_email, "code": v_code})
    record(cat, "POST /api/auth/verify-code", r_vcode.status_code == 200 and r_vcode.json().get("is_active") is True, "Account activated with 6-digit code")
    user_token = r_vcode.json()["token"]
    u_headers = {"X-User-Token": user_token}

    # 3. Authenticate User Profile
    r_me = client.get("/api/auth/me", headers=u_headers)
    record(cat, "GET /api/auth/me", r_me.status_code == 200 and r_me.json()["user"]["username"] == test_user_ident, "User session verified")

    # 4. Quota check
    r_quota = client.get("/api/user/quota", headers=u_headers)
    record(cat, "GET /api/user/quota", r_quota.status_code == 200 and r_quota.json().get("tier") == "registered", f"Daily limit: {r_quota.json().get('daily_limit')}")

    # 5. User Profile Update
    r_up = client.put(
        "/api/user/profile",
        headers=u_headers,
        json={"full_name": "Studio Creator Pro", "bio": "Master Designer", "country": "Japan"},
    )
    record(cat, "PUT /api/user/profile", r_up.status_code == 200 and r_up.json()["user"]["full_name"] == "Studio Creator Pro", "Profile updated")

    # 6. User Dashboard Data
    r_dash = client.get("/api/user/dashboard", headers=u_headers)
    record(cat, "GET /api/user/dashboard", r_dash.status_code == 200 and "stats" in r_dash.json(), "Dashboard data loaded")

    # 7. User Data Export
    r_export = client.get("/api/user/export", headers=u_headers)
    record(cat, "GET /api/user/export", r_export.status_code == 200 and r_export.json()["account"]["username"] == test_user_ident, "GDPR export verified")

    return u_headers, user_row.id, test_pass

def test_ai_bg_removal(u_headers):
    cat = "7. AI Background Removal Inference"
    # Transparent PNG
    files = {"file": ("coffee_mug.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
    r_rem = client.post("/api/remove", headers=u_headers, files=files, data={"model": "u2netp", "format": "png"})
    record(cat, "POST /api/remove (Transparent PNG)", r_rem.status_code == 200 and r_rem.headers.get("content-type") == "image/png", f"Time: {r_rem.headers.get('X-Process-Time-Ms')} ms, Dimensions: {r_rem.headers.get('X-Original-Width')}x{r_rem.headers.get('X-Original-Height')}")

    out_img = Image.open(io.BytesIO(r_rem.content))
    record(cat, "Output Mode Verification", out_img.mode == "RGBA", f"Image mode is RGBA with alpha channel")

    # Solid Color JPEG
    files_solid = {"file": ("coffee_mug.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
    r_solid = client.post("/api/remove", headers=u_headers, files=files_solid, data={"model": "u2netp", "format": "jpg", "bg_color": "#ffffff"})
    record(cat, "POST /api/remove (Solid White #FFFFFF JPEG)", r_solid.status_code == 200 and r_solid.headers.get("content-type") == "image/jpeg", "Solid backdrop JPEG generated")

    # WebP output
    files_webp = {"file": ("coffee_mug.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
    r_webp = client.post("/api/remove", headers=u_headers, files=files_webp, data={"model": "u2netp", "format": "webp"})
    record(cat, "POST /api/remove (WebP Export)", r_webp.status_code == 200 and r_webp.headers.get("content-type") == "image/webp", "WebP output delivered")

    # Mask Only
    files_mask = {"file": ("coffee_mug.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
    r_mask = client.post("/api/remove", headers=u_headers, files=files_mask, data={"model": "u2netp", "only_mask": "true", "format": "png"})
    record(cat, "POST /api/remove (Mask Only)", r_mask.status_code == 200, "Alpha segmentation mask generated")

def test_batch_removal(u_headers):
    cat = "8. Batch Background Removal"
    batch_files = [
        ("files", ("mug_1.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")),
        ("files", ("mug_2.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")),
    ]
    r_batch = client.post("/api/batch-remove", headers=u_headers, files=batch_files, data={"model": "u2netp", "format": "png"})
    record(cat, "POST /api/batch-remove", r_batch.status_code == 200 and r_batch.headers.get("content-type") == "application/zip", "ZIP archive delivered")

    with zipfile.ZipFile(io.BytesIO(r_batch.content), "r") as zf:
        namelist = zf.namelist()
        record(cat, "ZIP Archive Contents", len(namelist) == 2, f"Contained files: {namelist}")

def test_all_9_image_studio_tools(u_headers, uid):
    cat = "9. Image Studio Tools (Working Mode)"
    # First 4 tools (jobs 7, 8, 9, 10 for this test user):
    batch1_tools = [
        ("image-editor", {"brightness": "1.2", "contrast": "1.1", "saturation": "1.1", "rotate": "90"}),
        ("image-upscaler", {"scale": "2", "denoise": "0.3", "sharpen": "0.6"}),
        ("image-extender", {"target_ratio": "16:9", "expand_percent": "20", "extender_mode": "mirror_blur"}),
        ("variations", {"variation_style": "cyberpunk", "strength": "0.7"}),
    ]

    for tool_id, params in batch1_tools:
        data = {"tool_id": tool_id, "format": "png", **params}
        file_payload = {"file": ("sample.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
        res = client.post("/api/tools/process", headers=u_headers, files=file_payload, data=data)
        record(
            cat,
            f"Tool: {tool_id}",
            res.status_code == 200 and res.headers.get("X-Tool-Id") == tool_id,
            f"Processing time: {res.headers.get('X-Process-Time-Ms')} ms, Output: {res.headers.get('X-Output-Width')}x{res.headers.get('X-Output-Height')}",
        )

    # 10th image was reached with variations. Now test 11th image triggers 30-min rest cooldown (HTTP 429)
    blocked_data = {"tool_id": "cinematic-shot", "format": "png", "color_grade": "teal_orange", "letterbox": "true"}
    blocked_payload = {"file": ("sample.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
    res_cooldown = client.post("/api/tools/process", headers=u_headers, files=blocked_payload, data=blocked_data)
    record(
        cat,
        "10-Image Limit Enforcement (HTTP 429)",
        res_cooldown.status_code == 429 and "30-minute rest cooldown" in res_cooldown.json().get("detail", ""),
        "Blocked with 30-min rest cooldown message",
    )

    # Simulate 31 minutes passing (rest cooldown expires and resets quota)
    past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=31)
    with db_manager.get_session() as db:
        jobs = db.query(RemovalJob).filter(RemovalJob.user_id == uid).all()
        for j in jobs:
            j.created_at = past_time
        db.commit()

    # Verify quota has refreshed to 10 fresh uses
    r_q_reset = client.get("/api/user/quota", headers=u_headers)
    q_reset_data = r_q_reset.json()
    record(
        cat,
        "30-Minute Rest Reset (10 Fresh Uses)",
        q_reset_data.get("remaining_today") == 10 and q_reset_data.get("is_resting") is False,
        f"Remaining: {q_reset_data.get('remaining_today')}/10, is_resting: {q_reset_data.get('is_resting')}",
    )

    # Remaining 5 tools run cleanly in the fresh 10-image cycle:
    batch2_tools = [
        ("cinematic-shot", {"color_grade": "teal_orange", "letterbox": "true", "film_grain": "0.15"}),
        ("bg-remover", {"model": "u2netp", "alpha_matting": "false"}),
        ("skin-enhancer", {"smoothing": "0.6", "radiance": "0.4"}),
        ("relight", {"light_position": "top_left", "light_color": "#ff7b3a", "light_intensity": "0.8"}),
        ("change-camera", {"camera_angle": "wide_angle", "lens_type": "wide_24mm"}),
    ]

    for tool_id, params in batch2_tools:
        data = {"tool_id": tool_id, "format": "png", **params}
        file_payload = {"file": ("sample.jpg", io.BytesIO(SAMPLE_BYTES), "image/jpeg")}
        res = client.post("/api/tools/process", headers=u_headers, files=file_payload, data=data)
        record(
            cat,
            f"Tool: {tool_id}",
            res.status_code == 200 and res.headers.get("X-Tool-Id") == tool_id,
            f"Processing time: {res.headers.get('X-Process-Time-Ms')} ms, Output: {res.headers.get('X-Output-Width')}x{res.headers.get('X-Output-Height')}",
        )

def test_contact_and_cleanup(admin_headers, u_headers, user_id, user_pass):
    cat = "10. Contact Inquiries & Account Teardown"
    r_msg = client.post(
        "/api/contact",
        json={
            "name": "Jane Developer",
            "email": "jane@example.com",
            "subject": "Platform Verification Inquiry",
            "message": "We have completed comprehensive functional verification of RemBG Studio.",
        },
    )
    record(cat, "POST /api/contact", r_msg.status_code == 200 and r_msg.json().get("success") is True, f"Ticket #{r_msg.json().get('id')} recorded")

    r_c_list = client.get("/api/admin/contact", headers=admin_headers)
    record(cat, "GET /api/admin/contact", r_c_list.status_code == 200 and r_c_list.json().get("total") >= 1, f"Total tickets in admin: {r_c_list.json().get('total')}")

    # Clean up test user
    r_del_acc = client.post(
        "/api/user/delete-account",
        headers=u_headers,
        json={"confirm_phrase": "delete studio_creator_test", "password": user_pass},
    )
    record(cat, "POST /api/user/delete-account", r_del_acc.status_code == 200 and r_del_acc.json().get("deleted") is True, "Test account purged cleanly")

if __name__ == "__main__":
    print("=" * 70)
    print("  RemBG Studio & PngLike AI — Full Platform Functionality Audit")
    print("=" * 70)

    test_public_pages_and_seo()
    test_public_api_configs()
    admin_headers = test_admin_workflows()
    test_blog_cms(admin_headers)
    test_presets_crud(admin_headers)
    u_headers, uid, upass = test_user_lifecycle_and_security()
    test_ai_bg_removal(u_headers)
    test_batch_removal(u_headers)
    test_all_9_image_studio_tools(u_headers, uid)
    test_contact_and_cleanup(admin_headers, u_headers, uid, upass)

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    print("=" * 70)
    print(f"  AUDIT SUMMARY: {passed}/{total} Functionality Checks PASSED (100% OPERATIONAL)")
    print("=" * 70)
