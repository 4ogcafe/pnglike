import io
from pathlib import Path
from PIL import Image

import app as web_app
from database import db_manager


def test_core_and_database():
    print("1. Testing MySQL DSN builder & DatabaseManager initialization...")
    dsn = db_manager.build_mysql_url()
    assert dsn.startswith("mysql+pymysql://")
    assert "rembg_studio" in dsn
    print("   MySQL DSN:", dsn)
    print("   Active DB Engine:", db_manager.active_dialect)

    print("2. Testing MySQL PresetConfig CRUD (`preset_configs` table)...")
    presets = db_manager.list_presets()
    assert len(presets) >= 3
    print(f"   Default seeded presets count: {len(presets)}")
    custom = db_manager.create_preset(
        name="Test Studio Preset",
        model_used="u2netp",
        alpha_matting=True,
        af_threshold=230,
        ab_threshold=15,
        ae_size=8,
        post_process_mask=True,
        bg_mode="solid",
        bg_value="#ffffff",
        export_format="png",
    )
    assert custom["name"] == "Test Studio Preset"
    assert db_manager.delete_preset(custom["id"]) is True
    print("   Preset create & delete verified!")

    print("3. Testing AI inference + MySQL RemovalJob recording (`removal_jobs` table)...")
    sample_path = Path("static/samples/coffee_mug.jpg")
    raw_bytes = sample_path.read_bytes()

    out_png, mime_png, w, h = web_app._process_single_image(
        raw_bytes,
        model="u2netp",
        alpha_matting=False,
        af=240,
        ab=10,
        ae=10,
        only_mask=False,
        post_process_mask=True,
        bgcolor_tuple=None,
        out_format="png",
    )
    assert mime_png == "image/png"
    img_png = Image.open(io.BytesIO(out_png))
    assert img_png.mode == "RGBA"

    # Record job in database
    job = db_manager.record_job(
        original_filename="coffee_mug.jpg",
        output_filename="coffee_mug_test_nobg.png",
        output_url="/static/outputs/coffee_mug_test_nobg.png",
        model_used="u2netp",
        alpha_matting=False,
        af_threshold=240,
        ab_threshold=10,
        ae_size=10,
        only_mask=False,
        post_process_mask=True,
        bg_color=None,
        output_format="png",
        original_width=w,
        original_height=h,
        output_size_bytes=len(out_png),
        process_time_ms=145.5,
        batch_id=None,
        status="completed",
    )
    assert job["id"] is not None
    print(f"   Recorded job #{job['id']} ({job['job_uuid']}) in database!")

    # Query history and analytics
    history = db_manager.list_jobs(limit=10)
    assert history["total"] >= 1
    analytics = db_manager.get_analytics()
    assert analytics["total_jobs"] >= 1
    print(f"   Analytics verified: total_jobs={analytics['total_jobs']}, avg_ms={analytics['avg_process_time_ms']}")

    # Clean up test job record
    deleted = db_manager.delete_job(job["id"])
    assert deleted is not None
    print(f"   Cleaned up test job #{job['id']} successfully!")

    print("4. Testing BlogPost CRUD (`blog_posts` table) & FastAPI Blog Routes...")
    blog_data = db_manager.list_blog_posts(published_only=True)
    assert len(blog_data["posts"]) >= 3, f"Expected >= 3 seeded blog posts, got {len(blog_data['posts'])}"
    created_post = db_manager.create_blog_post(
        title="Admin Blog Test Post",
        excerpt="Testing blog creation and slug generation.",
        content="<h2>Test Heading</h2><p>Test body content.</p>",
        category="AI Tutorials",
        tags="test,blog",
        author="Div Sri",
        is_published=True,
        is_featured=True,
    )
    assert created_post["slug"] == "admin-blog-test-post"
    fetched_post = db_manager.get_blog_post_by_slug("admin-blog-test-post", increment_views=True)
    assert fetched_post is not None and fetched_post["views_count"] == 1
    updated_post = db_manager.update_blog_post(created_post["id"], {"title": "Updated Blog Title", "is_featured": False})
    assert updated_post is not None and updated_post["title"] == "Updated Blog Title" and updated_post["is_featured"] is False
    deleted_post = db_manager.delete_blog_post(created_post["id"])
    assert deleted_post is not None
    print(f"   Blog CRUD verified ({len(blog_data['posts'])} seeded articles active)!")

    print("5. Testing User Registration Security Levels (`users` table)...")
    demo_auth = db_manager.authenticate_user("demo", "user123")
    assert demo_auth is not None and demo_auth["username"] == "demo", "Default demo user failed authentication"

    # Security Test 1: Plus-addressing / aliases (name+1@domain.com) MUST be rejected
    try:
        db_manager.register_user("alias_user", "name+1@domain.com", "SecretPass123!#", "Alias User")
        assert False, "Should have rejected plus-addressing (name+1@domain.com)"
    except ValueError as e:
        assert "aliases or sub-addressing" in str(e), f"Unexpected error message: {e}"
        print(f"   [SECURITY PASS] Plus-addressing 'name+1@domain.com' rejected: {e}")

    # Security Test 2: Disposable / temporary burner emails MUST be rejected
    try:
        db_manager.register_user("temp_user", "attacker@tempmail.com", "SecretPass123!#", "Temp User")
        assert False, "Should have rejected disposable burner domain tempmail.com"
    except ValueError as e:
        assert "Disposable and temporary" in str(e), f"Unexpected error message: {e}"
        print(f"   [SECURITY PASS] Disposable domain 'attacker@tempmail.com' rejected: {e}")

    # Security Test 3: Weak / common passwords MUST be rejected
    try:
        db_manager.register_user("weak_pw_user", "clean.user@pnglike.studio", "12345678", "Weak User")
        assert False, "Should have rejected weak password"
    except ValueError as e:
        print(f"   [SECURITY PASS] Weak password rejected: {e}")

    # Security Test 4: Reserved system usernames MUST be rejected
    try:
        db_manager.register_user("admin", "admin.fake@pnglike.studio", "SecretPass123!#", "Admin Impersonator")
        assert False, "Should have rejected reserved username 'admin'"
    except ValueError as e:
        assert "reserved for system use" in str(e), f"Unexpected error message: {e}"
        print(f"   [SECURITY PASS] Reserved username 'admin' rejected: {e}")

    # Security Test 5: Valid registration with strong password & standard email
    try:
        test_user = db_manager.register_user("test_creator_99", "creator99@pnglike.studio", "SecretPass123!#", "Test Creator", auto_activate=True)
    except ValueError:
        test_user = db_manager.authenticate_user("test_creator_99", "SecretPass123!#")
    assert test_user is not None and test_user["username"] == "test_creator_99"
    print("   [SECURITY PASS] Valid registration accepted with high security standards!")

    user_job = db_manager.record_job(
        original_filename="user_dash_test.jpg",
        output_filename="user_dash_test_nobg.png",
        output_url="/static/outputs/user_dash_test_nobg.png",
        model_used="isnet-general-use",
        alpha_matting=True,
        af_threshold=240,
        ab_threshold=10,
        ae_size=10,
        post_process_mask=True,
        only_mask=False,
        bg_color=None,
        output_format="png",
        original_width=512,
        original_height=512,
        output_size_bytes=24500,
        process_time_ms=110.5,
        user_id=test_user["id"],
    )
    dash_data = db_manager.get_user_dashboard_data(test_user["id"])
    assert dash_data is not None and dash_data["stats"]["total_jobs"] >= 1
    assert "api_key" not in dash_data["user"], "Personal Developer API key should not be exposed in user dashboard"
    assert "presets" not in dash_data, "Studio Workflow Presets should not be exposed in user dashboard"
    assert db_manager.get_user_by_api_key("some_key") is None, "API key lookup must be disabled"

    # Profile Management Verification: Update bio, phone, country, format, avatar_color
    updated_prof = db_manager.update_user_profile(
        test_user["id"],
        full_name="Alex Master Creator",
        bio="Lead E-Commerce Studio Designer",
        phone="+1 555-0199",
        country="United Kingdom",
        preferred_format="webp",
        avatar_color="#10b981",
    )
    assert updated_prof is not None
    assert updated_prof["full_name"] == "Alex Master Creator"
    assert updated_prof["bio"] == "Lead E-Commerce Studio Designer"
    assert updated_prof["preferred_format"] == "webp"
    assert updated_prof["avatar_color"] == "#10b981"

    # Security Test: Password change MUST require current password verification
    try:
        db_manager.update_user_profile(test_user["id"], new_password="NewSecretPass999!#")
        assert False, "Should have rejected password change without current_password"
    except ValueError as ve:
        assert "Current password is required" in str(ve)
        print(f"   [SECURITY PASS] Unverified password change rejected: {ve}")

    try:
        db_manager.update_user_profile(test_user["id"], new_password="NewSecretPass999!#", current_password="wrong_password")
        assert False, "Should have rejected password change with incorrect current_password"
    except ValueError as ve:
        assert "Current password is incorrect" in str(ve)
        print(f"   [SECURITY PASS] Incorrect current password rejected: {ve}")

    # Security Test: Account deletion MUST require valid password verification
    try:
        db_manager.delete_user_account(test_user["id"], password="")
        assert False, "Should have rejected account deletion without password"
    except ValueError as ve:
        assert "Password confirmation failed" in str(ve)
        print(f"   [SECURITY PASS] Password-less account deletion rejected: {ve}")

    # Export User Data verification
    exported = db_manager.export_user_profile_data(test_user["id"])
    assert exported is not None and exported["account"]["username"] == "test_creator_99"
    assert exported["total_jobs"] >= 1

    # Cleanup with verified password
    db_manager.delete_user_job(test_user["id"], user_job["id"])
    assert db_manager.delete_user_account(test_user["id"], "SecretPass123!#") is True
    print("   User Auth, Profile Management Suite & Account Lifecycle verified!")

    # Security & Access Restrictions: Registered vs Unregistered Users Test
    guest_summary = db_manager.get_user_quota_summary(None, "198.51.100.22")
    assert guest_summary["tier"] == "guest"
    assert guest_summary["is_registered"] is False
    assert guest_summary["daily_limit"] == 3
    assert "image-upscaler" in guest_summary["restricted_tools"]

    # Test 1: Guest blocked from Pro generative tools
    try:
        db_manager.check_user_access_quota(None, "198.51.100.22", tool_id="image-upscaler", file_size_bytes=2048)
        assert False, "Should have blocked guest from image-upscaler"
    except PermissionError as pe:
        assert "requires a free registered account" in str(pe)

    # Test 2: Guest blocked from files > 10MB
    try:
        db_manager.check_user_access_quota(None, "198.51.100.22", tool_id="bg-remover", file_size_bytes=15 * 1024 * 1024)
        assert False, "Should have blocked guest for > 10MB file"
    except ValueError as ve:
        assert "Guest upload size is limited to 10 MB" in str(ve)

    # Test 3: Guest allowed for standard bg-remover under 10MB
    allowed_guest = db_manager.check_user_access_quota(None, "198.51.100.22", tool_id="bg-remover", file_size_bytes=1024)
    assert allowed_guest["is_registered"] is False
    print("   Registered vs Unregistered (Guest) Access Limitation Policies verified!")

    # Test Contact Messages CRUD
    contact_test = db_manager.save_contact_message(
        name="Alex River",
        email="alex@studio-art.com",
        subject="Commercial API Licensing",
        message="Hello PngLike team, we would love to integrate your background removal pipeline.",
        client_ip="198.51.100.22",
    )
    assert contact_test["id"] is not None
    assert contact_test["name"] == "Alex River"
    contact_list = db_manager.list_contact_messages(limit=10)
    assert contact_list["total"] >= 1
    print("   Contact / Support Inquiries Database Manager verified!")

    print("6. Verifying project files...")
    for path_str in (
        "database.py",
        "schema.sql",
        ".env",
        "app.py",
        "static/index.html",
        "static/app.js",
        "static/blog.html",
        "static/blog.js",
        "static/dashboard.html",
        "static/dashboard.js",
        "static/admin.html",
        "static/admin.js",
        "static/privacy.html",
        "static/terms.html",
        "static/cookies.html",
        "static/about.html",
        "static/contact.html",
        "static/faq.html",
    ):
        assert Path(path_str).exists(), f"Missing {path_str}"
    print("   All files verified!")

    print("\nALL MYSQL, BLOG, USER DASHBOARD & AI BACKEND TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    test_core_and_database()
