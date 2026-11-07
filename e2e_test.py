import io
import time
import zipfile
import requests
from PIL import Image

import os
BASE_URL = os.getenv("TEST_SERVER_URL", "http://127.0.0.1:7860")


def wait_for_server(timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE_URL}/api/status", timeout=2)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(0.5)
    return False


def run_e2e_tests():
    print("=" * 68)
    print("  RemBG Studio & Admin Portal - Live HTTP End-to-End Test Suite")
    print("=" * 68)

    assert wait_for_server(), "Server did not become ready on http://127.0.0.1:7860"
    print("[PASS] 1. Server is online at", BASE_URL)

    # 1. Test Public Frontend & Admin Portal HTML pages + PngLike SVG Logos & "Powered by Div Sri"
    r_ui = requests.get(f"{BASE_URL}/")
    assert r_ui.status_code == 200 and "PngLike" in r_ui.text and "Powered by Div Sri" in r_ui.text
    assert "/static/brand/favicon.svg" in r_ui.text and ".png" not in r_ui.text.split("</header>")[0]
    r_adm_ui = requests.get(f"{BASE_URL}/admin")
    assert r_adm_ui.status_code == 200 and "PngLike" in r_adm_ui.text and "Powered by Div Sri" in r_adm_ui.text
    for asset_name in ["favicon.svg", "logo-icon.svg", "logo-dark-text.svg", "logo-white-text.svg"]:
        r_asset = requests.get(f"{BASE_URL}/static/brand/{asset_name}")
        assert r_asset.status_code == 200 and "<svg" in r_asset.text, f"Brand SVG logo {asset_name} failed to load"
    print("[PASS] 2. Public Frontend (GET /), Admin Dashboard (GET /admin), PngLike SVG Logos & 'Powered by Div Sri' verified")

    # 2. Test Public Dynamic Site Config API
    r_cfg = requests.get(f"{BASE_URL}/api/site-config").json()
    assert "settings" in r_cfg and "models" in r_cfg and "samples" in r_cfg
    print(f"[PASS] 3. Dynamic Site Config (GET /api/site-config): title='{r_cfg['settings']['site_title']}', models={len(r_cfg['models'])}")

    # 3. Test Admin Login & Session Token
    r_login = requests.post(
        f"{BASE_URL}/api/admin/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    login_data = r_login.json()
    token = login_data["token"]
    adm_headers = {"X-Admin-Token": token}
    r_me = requests.get(f"{BASE_URL}/api/admin/me", headers=adm_headers)
    assert r_me.status_code == 200 and r_me.json()["admin"]["username"] == "admin"
    print("[PASS] 4. Admin Authentication (POST /api/admin/login & GET /api/admin/me)")

    # 4. Test Admin CMS Settings Update -> Verify Reflected on Public Frontend Config
    r_put = requests.put(
        f"{BASE_URL}/api/admin/settings",
        headers=adm_headers,
        json={
            "announcement_enabled": False,
            "announcement_text": "PngLike 9-in-1 AI Image Suite — Powered by Div Sri",
            "site_tagline": "Professional AI Image Studio",
            "hero_subtitle": "Professional 9-in-1 AI image studio for instant cutouts, 4x upscaling, outpainting, portrait retouching, and 3D relighting.",
            "footer_text": "Powered by Div Sri • Professional 9-in-1 AI Image Studio.",
            "max_upload_mb": 30,
        },
    )
    assert r_put.status_code == 200
    r_cfg_after = requests.get(f"{BASE_URL}/api/site-config").json()
    assert r_cfg_after["settings"]["announcement_enabled"] is False
    assert r_cfg_after["settings"]["max_upload_mb"] == 30
    print("[PASS] 5. Admin CMS Update (PUT /api/admin/settings) persisted to MySQL & reflected on Frontend")

    # 5. Test Admin AI Models & Sample Gallery Endpoints
    r_models = requests.get(f"{BASE_URL}/api/admin/models", headers=adm_headers).json()
    assert len(r_models["models"]) >= 2
    r_samples = requests.get(f"{BASE_URL}/api/admin/samples", headers=adm_headers).json()
    assert len(r_samples["samples"]) >= 3
    print(f"[PASS] 6. Admin Models & Sample Gallery Manager: {len(r_models['models'])} models, {len(r_samples['samples'])} samples")

    # 6. Test Single Image Background Removal (POST /api/remove)
    guest_run_headers = {"X-Forwarded-For": f"198.51.100.{int(time.time()) % 150 + 10}"}
    with open("static/samples/product_sneaker.jpg", "rb") as f:
        r_rem = requests.post(
            f"{BASE_URL}/api/remove",
            headers=guest_run_headers,
            files={"file": ("product_sneaker.jpg", f, "image/jpeg")},
            data={"model": "u2netp", "post_process_mask": "true", "format": "png"},
        )
    assert r_rem.status_code == 200, f"Remove failed: {r_rem.text}"
    out_img = Image.open(io.BytesIO(r_rem.content))
    assert out_img.mode == "RGBA" and out_img.size == (800, 600)
    print(f"[PASS] 7. Single Image Removal (POST /api/remove): Job #{r_rem.headers.get('X-Job-Id')} ({r_rem.headers.get('X-Process-Time-Ms')} ms)")

    # 7. Test All 9 IMAGE Tools in Working Mode (GET /api/tools & POST /api/tools/process)
    r_tools = requests.get(f"{BASE_URL}/api/tools").json()
    tool_ids = [t["id"] for t in r_tools["all_tools"]]
    expected_tools = [
        "image-editor",
        "image-upscaler",
        "image-extender",
        "variations",
        "cinematic-shot",
        "bg-remover",
        "skin-enhancer",
        "relight",
        "change-camera",
    ]
    assert tool_ids == expected_tools, f"Expected {expected_tools}, got {tool_ids}"
    print(f"[PASS] 8. All 9 IMAGE Tools Catalog verified in exact order: {tool_ids}")

    # 8. Test All 9 Tools with sample portrait image (as registered user to access all tools)
    r_demo_login_init = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"identifier": "demo", "password": "user123"},
    )
    assert r_demo_login_init.status_code == 200, f"Demo login failed: {r_demo_login_init.text}"
    u_headers = {"X-User-Token": r_demo_login_init.json()["token"]}

    with open("static/samples/portrait_person.jpg", "rb") as f:
        sample_bytes = f.read()

    tool_test_cases = [
        ("image-editor", {"filter_preset": "vivid", "brightness": "1.1", "contrast": "1.1"}),
        ("image-upscaler", {"scale": "2", "denoise": "0.3", "sharpen": "0.6"}),
        ("image-extender", {"target_ratio": "16:9", "extender_mode": "ai_outpaint"}),
        ("variations", {"variation_style": "cyberpunk", "strength": "0.8"}),
        ("cinematic-shot", {"color_grade": "teal_orange", "bokeh_blur": "0.6", "letterbox": "true"}),
        ("bg-remover", {"model": "u2netp", "post_process_mask": "true"}),
        ("skin-enhancer", {"smoothing": "0.7", "radiance": "0.4", "detail_crispness": "0.5"}),
        ("relight", {"light_position": "neon_split", "light_color": "#ff5500", "secondary_color": "#00ccff"}),
        ("change-camera", {"camera_angle": "tilt_up", "lens_type": "wide_24mm", "camera_intensity": "0.65"}),
    ]

    for idx, (t_id, params) in enumerate(tool_test_cases, start=1):
        payload_data = {"tool_id": t_id, "format": "png"}
        payload_data.update(params)
        r_t = requests.post(
            f"{BASE_URL}/api/tools/process",
            headers=u_headers,
            files={"file": ("portrait_person.jpg", sample_bytes, "image/jpeg")},
            data=payload_data,
        )
        assert r_t.status_code == 200, f"Tool {t_id} failed: {r_t.text}"
        t_img = Image.open(io.BytesIO(r_t.content))
        assert t_img.width > 0 and t_img.height > 0
        print(
            f"[PASS] {idx + 8}. Tool [{idx}/9] {t_id}: output={t_img.size}, "
            f"job=#{r_t.headers.get('X-Job-Id')} ({r_t.headers.get('X-Process-Time-Ms')} ms)"
        )

    # 9. Test Admin Overview & Jobs Moderation Search
    r_ov = requests.get(f"{BASE_URL}/api/admin/overview", headers=adm_headers).json()
    assert r_ov["analytics"]["total_jobs"] >= 9
    r_jobs = requests.get(f"{BASE_URL}/api/admin/jobs?search=portrait", headers=adm_headers).json()
    assert r_jobs["total"] >= 1
    print(f"[PASS] 18. Admin Overview & Jobs Moderation: {r_ov['analytics']['total_jobs']} total jobs logged in MySQL")

    # 10. Test Single-Page Web App SEO, Schema.org JSON-LD, Sitemap, Robots & LLMs.txt
    assert "application/ld+json" in r_ui.text and "spaToolsRibbon" in r_ui.text and "all9ToolsShowcaseGrid" in r_ui.text
    assert r_ui.text.count("<h1") == 1, f"Expected exactly 1 <h1> tag, found {r_ui.text.count('<h1')}"
    r_robots = requests.get(f"{BASE_URL}/robots.txt")
    assert r_robots.status_code == 200 and "Sitemap:" in r_robots.text
    r_sitemap = requests.get(f"{BASE_URL}/sitemap.xml")
    assert r_sitemap.status_code == 200 and "<urlset" in r_sitemap.text and "/blog" in r_sitemap.text
    r_llms = requests.get(f"{BASE_URL}/llms.txt")
    assert r_llms.status_code == 200 and "Core 9 Working IMAGE Tools" in r_llms.text and "Official Blog" in r_llms.text
    print("[PASS] 19. Single-Page App SEO, Schema.org JSON-LD @graph, /robots.txt, /sitemap.xml & /llms.txt verified")

    # 11. Test Public Blog Page (/blog) & Admin Blog Manager CRUD (/api/admin/blog)
    r_blog_html = requests.get(f"{BASE_URL}/blog")
    assert r_blog_html.status_code == 200 and "PngLike" in r_blog_html.text and "Powered by Div Sri" in r_blog_html.text
    r_blog_list = requests.get(f"{BASE_URL}/api/blog").json()
    assert len(r_blog_list["posts"]) >= 3, f"Expected >=3 seeded blog posts, got {len(r_blog_list['posts'])}"

    # Create a new blog post via Admin API
    r_create_blog = requests.post(
        f"{BASE_URL}/api/admin/blog",
        headers=adm_headers,
        json={
            "title": "New AI Portrait Relighting Workflow in PngLike",
            "excerpt": "How to combine U2-Net subject isolation with dual-source 3D neon split lighting.",
            "content": "<h2>3D Relighting Guide</h2><p>Use the Relight tool for instant studio key and rim lights.</p>",
            "category": "AI Tutorials",
            "tags": "relight,portrait,3d-light",
            "author": "Div Sri",
            "read_time_minutes": 3,
            "is_published": True,
            "is_featured": True,
        },
    )
    assert r_create_blog.status_code == 200, f"Create blog failed: {r_create_blog.text}"
    created_post = r_create_blog.json()["post"]
    post_id = created_post["id"]
    post_slug = created_post["slug"]

    # Fetch single article via public API and verify view counter increments
    r_single_blog = requests.get(f"{BASE_URL}/api/blog/{post_slug}").json()
    assert r_single_blog["post"]["id"] == post_id and r_single_blog["post"]["views_count"] >= 1

    # Update the blog post via Admin API
    r_update_blog = requests.put(
        f"{BASE_URL}/api/admin/blog/{post_id}",
        headers=adm_headers,
        json={"title": "Updated: AI Portrait Relighting Workflow", "is_featured": False},
    )
    assert r_update_blog.status_code == 200 and r_update_blog.json()["post"]["is_featured"] is False

    # Delete the test blog post via Admin API
    r_del_blog = requests.delete(f"{BASE_URL}/api/admin/blog/{post_id}", headers=adm_headers)
    assert r_del_blog.status_code == 200 and r_del_blog.json()["deleted"] is True
    print(f"[PASS] 20. Public Blog (/blog) & Admin Blog CMS CRUD (Create/Read/Update/Delete) verified ({len(r_blog_list['posts'])} active articles)")

    # 12. Test User Login System, User Dashboard (/dashboard) & Admin User Manager (/api/admin/users)
    r_dash_html = requests.get(f"{BASE_URL}/dashboard")
    assert r_dash_html.status_code == 200 and "PngLike" in r_dash_html.text and "Powered by Div Sri" in r_dash_html.text

    # Login with seeded demo user
    r_demo_login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"identifier": "demo", "password": "user123"},
    )
    assert r_demo_login.status_code == 200, f"Demo user login failed: {r_demo_login.text}"
    user_token = r_demo_login.json()["token"]
    u_headers = {"X-User-Token": user_token}

    # Process an image as the logged-in user and verify it appears in /api/user/dashboard
    r_user_proc = requests.post(
        f"{BASE_URL}/api/tools/process",
        headers=u_headers,
        files={"file": ("user_test.jpg", sample_bytes, "image/jpeg")},
        data={"tool_id": "image-upscaler", "scale": "2", "format": "png"},
    )
    assert r_user_proc.status_code == 200

    r_user_dash = requests.get(f"{BASE_URL}/api/user/dashboard", headers=u_headers).json()
    assert r_user_dash["user"]["username"] == "demo"
    assert "api_key" not in r_user_dash["user"]
    assert "presets" not in r_user_dash
    assert r_user_dash["stats"]["total_jobs"] >= 1
    assert len(r_user_dash["jobs"]) >= 1

    # Personal developer API key regeneration must return 403 Forbidden
    r_regen_apikey = requests.post(f"{BASE_URL}/api/user/api-key/regenerate", headers=u_headers)
    assert r_regen_apikey.status_code == 403, f"Expected 403 on API key regenerate, got {r_regen_apikey.status_code}"

    # Verify Workflow Presets tab removed from user dashboard HTML
    assert "tab-presets" not in r_dash_html.text
    assert "id=\"presetSelect\"" not in r_ui.text

    # Complete User Profile Management Endpoints Test (PUT /api/user/profile & GET /api/user/export)
    r_update_prof = requests.put(
        f"{BASE_URL}/api/user/profile",
        headers=u_headers,
        json={
            "full_name": "Demo Pro Designer",
            "bio": "Senior E-Commerce Retoucher & Brand Creator",
            "country": "Germany",
            "phone": "+49 30 123456",
            "preferred_format": "png",
            "dark_mode_pref": "dark",
            "avatar_color": "#0ea5e9",
        },
    )
    assert r_update_prof.status_code == 200, f"Profile update failed: {r_update_prof.text}"
    prof_data = r_update_prof.json()["user"]
    assert prof_data["full_name"] == "Demo Pro Designer"
    assert prof_data["bio"] == "Senior E-Commerce Retoucher & Brand Creator"
    assert prof_data["country"] == "Germany"
    assert prof_data["avatar_color"] == "#0ea5e9"

    # Export User Profile Data
    r_export = requests.get(f"{BASE_URL}/api/user/export", headers=u_headers)
    assert r_export.status_code == 200
    export_json = r_export.json()
    assert export_json["account"]["username"] == "demo"
    assert "jobs" in export_json and len(export_json["jobs"]) >= 1

    # Admin Users Manager check
    r_adm_users = requests.get(f"{BASE_URL}/api/admin/users", headers=adm_headers).json()
    assert r_adm_users["total"] >= 1
    print(f"[PASS] 21. User Login System, User Dashboard (/dashboard) & Admin Users Manager verified ({r_adm_users['total']} users)")

    # 13. Test Registration Security Controls (Plus-addressing, Disposable domains, Weak Passwords, Honeypot)
    r_plus_rej = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "username": "alias_tester",
            "email": "name+1@domain.com",
            "password": "SecurePassword123!#",
            "full_name": "Alias Test",
        },
    )
    assert r_plus_rej.status_code == 400 and "aliases or sub-addressing" in r_plus_rej.text, f"Expected plus-addressing rejection: {r_plus_rej.text}"

    r_disp_rej = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "username": "burner_tester",
            "email": "burner@tempmail.com",
            "password": "SecurePassword123!#",
            "full_name": "Burner Test",
        },
    )
    assert r_disp_rej.status_code == 400 and "Disposable and temporary" in r_disp_rej.text, f"Expected disposable domain rejection: {r_disp_rej.text}"

    r_honeypot_rej = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "username": "bot_tester",
            "email": "clean.tester@pnglike.com",
            "password": "SecurePassword123!#",
            "full_name": "Bot Test",
            "website": "http://spambot.xyz",
        },
    )
    assert r_honeypot_rej.status_code == 400 and "bot activity detected" in r_honeypot_rej.text, f"Expected bot honeypot rejection: {r_honeypot_rej.text}"
    print("[PASS] 22. Registration Security: plus-addressing ('name+1@domain.com'), disposable emails, & honeypot bot trap verified rejected")

    # 14. Test Access Restrictions & Limitations for Registered vs Unregistered (Guest) Users
    fresh_guest_headers = {"X-Forwarded-For": f"198.51.100.{int(time.time()) % 200 + 10}"}

    # (a) Guest Quota Summary (GET /api/user/quota without login token)
    r_gquota = requests.get(f"{BASE_URL}/api/user/quota", headers=fresh_guest_headers).json()
    assert r_gquota["tier"] == "guest", f"Expected tier guest, got {r_gquota['tier']}"
    assert r_gquota["daily_limit"] == 3
    assert r_gquota["remaining_today"] == 3
    assert r_gquota["max_upload_mb"] == 10
    assert "image-upscaler" in r_gquota["restricted_tools"]
    assert "image-extender" in r_gquota["restricted_tools"]
    assert "variations" in r_gquota["restricted_tools"]

    # (b) Registered Quota Summary (GET /api/user/quota with X-User-Token)
    r_uquota = requests.get(f"{BASE_URL}/api/user/quota", headers=u_headers).json()
    assert r_uquota["tier"] == "registered"
    assert r_uquota["daily_limit"] == 100
    assert r_uquota["max_upload_mb"] == 50
    assert len(r_uquota["restricted_tools"]) == 0

    # (c) Guest attempting restricted tool (image-upscaler) must return 403 Forbidden
    r_guest_pro = requests.post(
        f"{BASE_URL}/api/tools/process",
        headers=fresh_guest_headers,
        files={"file": ("guest_test.jpg", sample_bytes, "image/jpeg")},
        data={"tool_id": "image-upscaler", "scale": "2", "format": "png"},
    )
    assert r_guest_pro.status_code == 403, f"Expected 403 for guest on image-upscaler, got {r_guest_pro.status_code}"
    assert "requires a free registered account" in r_guest_pro.text

    # (d) Guest using allowed tool (image-editor) succeeds and returns tier headers
    r_guest_allowed = requests.post(
        f"{BASE_URL}/api/tools/process",
        headers=fresh_guest_headers,
        files={"file": ("guest_test.jpg", sample_bytes, "image/jpeg")},
        data={"tool_id": "image-editor", "filter_preset": "vivid", "format": "png"},
    )
    assert r_guest_allowed.status_code == 200
    assert r_guest_allowed.headers.get("X-User-Tier") == "guest"
    assert "X-RateLimit-Remaining" in r_guest_allowed.headers

    # (e) Guest attempting file > 10MB rejected
    big_fake_file = b"0" * (11 * 1024 * 1024)
    r_guest_big = requests.post(
        f"{BASE_URL}/api/remove",
        headers=fresh_guest_headers,
        files={"file": ("big_fake.jpg", big_fake_file, "image/jpeg")},
        data={"model": "u2netp", "format": "png"},
    )
    assert r_guest_big.status_code in [400, 413], f"Expected 400/413, got {r_guest_big.status_code}"
    assert "Guest upload size is limited to 10 MB" in r_guest_big.text, f"Unexpected error message: {r_guest_big.text}"
    print("[PASS] 23. Access Restrictions & Limitations for Registered vs Unregistered (Guest) Users verified")

    # 15. Test Required Pages (/privacy, /terms, /cookies, /about, /contact, /faq) & Contact API
    pages_to_verify = [
        ("/privacy", ["Privacy Policy", "PngLike", "Powered by Div Sri", "GDPR", "CCPA"]),
        ("/terms", ["Terms of Service", "PngLike", "Powered by Div Sri", "Commercial Ownership Guarantee"]),
        ("/cookies", ["Cookie Policy", "pnglike_user_token", "pnglike_theme"]),
        ("/about", ["About PngLike", "Powered by Div Sri", "9-in-1 AI Tool Suite"]),
        ("/contact", ["Contact & Support", "support@pnglike.com"]),
        ("/faq", ["Frequently Asked Questions", "Is PngLike completely free to use?"]),
    ]
    for page_path, expected_snippets in pages_to_verify:
        r_page = requests.get(f"{BASE_URL}{page_path}")
        assert r_page.status_code == 200, f"Page {page_path} failed: {r_page.status_code}"
        for snippet in expected_snippets:
            assert snippet in r_page.text, f"Missing '{snippet}' in {page_path}"

    # Test Contact API Honeypot rejection
    r_bot_contact = requests.post(
        f"{BASE_URL}/api/contact",
        json={
            "name": "Bot Spammer",
            "email": "bot@spammer.xyz",
            "subject": "Spam Offer",
            "message": "Buy cheap backlinks now!",
            "website": "http://spammer.xyz",
        },
    )
    assert r_bot_contact.status_code == 400 and "Automated submission blocked" in r_bot_contact.text

    # Test Legitimate Contact API submission
    r_legit_contact = requests.post(
        f"{BASE_URL}/api/contact",
        json={
            "name": "Elena Rostova",
            "email": "elena@fashionbrand.com",
            "subject": "E-Commerce Catalog Retouching",
            "message": "We would love to use PngLike for our 2026 apparel catalog cutouts.",
        },
    )
    assert r_legit_contact.status_code == 200
    contact_resp = r_legit_contact.json()
    assert contact_resp["success"] is True and "within 24 hours" in contact_resp["message"]

    # Verify contact message stored in Admin Inquiries endpoint
    r_adm_contact = requests.get(f"{BASE_URL}/api/admin/contact", headers=adm_headers).json()
    assert r_adm_contact["total"] >= 1
    found_elena = any(m["email"] == "elena@fashionbrand.com" for m in r_adm_contact["messages"])
    assert found_elena is True, "Submitted contact message not found in admin inquiry list"

    # Verify updated robots.txt has required pages allowed
    r_robots_updated = requests.get(f"{BASE_URL}/robots.txt")
    for req_route in ["Allow: /about", "Allow: /faq", "Allow: /contact", "Allow: /privacy", "Allow: /terms", "Allow: /cookies"]:
        assert req_route in r_robots_updated.text, f"Missing {req_route} in robots.txt"

    # Verify updated sitemap.xml contains all required URLs
    r_sitemap_updated = requests.get(f"{BASE_URL}/sitemap.xml")
    for sitemap_url in ["/privacy", "/terms", "/cookies", "/about", "/contact", "/faq"]:
        assert f"<loc>{BASE_URL}{sitemap_url}</loc>" in r_sitemap_updated.text or f"{sitemap_url}</loc>" in r_sitemap_updated.text

    # Verify updated llms.txt has new resources
    r_llms_updated = requests.get(f"{BASE_URL}/llms.txt")
    assert "/about" in r_llms_updated.text and "/privacy" in r_llms_updated.text and "/faq" in r_llms_updated.text
    print("[PASS] 24. Required Pages (/privacy, /terms, /cookies, /about, /contact, /faq), Contact API & Updated SEO Sitemaps verified")

    print("=" * 68)
    print("  ALL 24 LIVE ADMIN, BLOG, USER DASHBOARD, SECURITY, PAGES & 9-TOOL E2E TESTS PASSED!")
    print("=" * 68)


if __name__ == "__main__":
    run_e2e_tests()
