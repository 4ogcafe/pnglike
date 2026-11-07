import os
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any, Optional
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)

DEFAULT_SMTP_CONFIG = {
    "smtp_enabled": "true",
    "smtp_host": "smtp.gmail.com",
    "smtp_port": "587",
    "smtp_user": "",
    "smtp_password": "",
    "smtp_from_name": "PngLike AI Studio - Powered by Div Sri",
    "smtp_from_email": "",
    "smtp_use_tls": "true",
}


def get_smtp_config(db_manager=None) -> Dict[str, Any]:
    """Retrieve SMTP / Gmail configuration from .env and MySQL site_settings."""
    # Ensure latest .env values are reloaded dynamically
    if ENV_PATH.exists():
        try:
            load_dotenv(ENV_PATH, override=True)
        except Exception:
            pass

    config = dict(DEFAULT_SMTP_CONFIG)

    # 1. Read from MySQL database site_settings if available
    if db_manager and hasattr(db_manager, "get_site_settings"):
        try:
            settings = db_manager.get_site_settings()
            for key in DEFAULT_SMTP_CONFIG:
                val = settings.get(key)
                if val is not None and str(val).strip() != "":
                    config[key] = str(val).strip()
        except Exception:
            pass

    # 2. .env environment variables (explicit .env entries take precedence)
    if os.getenv("SMTP_ENABLED") is not None:
        config["smtp_enabled"] = os.getenv("SMTP_ENABLED")
    if os.getenv("SMTP_HOST"):
        config["smtp_host"] = os.getenv("SMTP_HOST")
    if os.getenv("SMTP_PORT"):
        config["smtp_port"] = os.getenv("SMTP_PORT")
    if os.getenv("SMTP_USER") or os.getenv("GMAIL_USER"):
        config["smtp_user"] = os.getenv("SMTP_USER") or os.getenv("GMAIL_USER", "")
    if os.getenv("SMTP_PASSWORD") or os.getenv("GMAIL_PASSWORD") or os.getenv("GMAIL_APP_PASSWORD"):
        config["smtp_password"] = (
            os.getenv("SMTP_PASSWORD")
            or os.getenv("GMAIL_PASSWORD")
            or os.getenv("GMAIL_APP_PASSWORD", "")
        )
    if os.getenv("SMTP_FROM_NAME"):
        config["smtp_from_name"] = os.getenv("SMTP_FROM_NAME")
    if os.getenv("SMTP_FROM_EMAIL"):
        config["smtp_from_email"] = os.getenv("SMTP_FROM_EMAIL")
    if os.getenv("SMTP_USE_TLS") is not None:
        config["smtp_use_tls"] = os.getenv("SMTP_USE_TLS")

    return {
        "enabled": str(config.get("smtp_enabled", "true")).lower() in ("true", "1", "yes"),
        "host": config.get("smtp_host", "smtp.gmail.com"),
        "port": int(config.get("smtp_port", 587)),
        "user": config.get("smtp_user", "").strip(),
        "password": config.get("smtp_password", "").strip(),
        "from_name": config.get("smtp_from_name", "PngLike AI Studio"),
        "from_email": config.get("smtp_from_email", "").strip() or config.get("smtp_user", "").strip(),
        "use_tls": str(config.get("smtp_use_tls", "true")).lower() in ("true", "1", "yes"),
    }


def send_verification_email(
    to_email: str,
    username: str,
    verification_code: str,
    verification_token: str,
    base_url: str = "https://pnglike.com",
    db_manager=None,
) -> Dict[str, Any]:
    """
    Send an account verification email with a 6-digit code and 1-click verification link.
    If SMTP credentials are not yet configured or connection fails, returns dev fallback info.
    """
    cfg = get_smtp_config(db_manager)
    verify_url = f"{base_url.rstrip('/')}/dashboard?verify_token={verification_token}&email={to_email}"
    clean_username = username.strip() or "Creator"

    subject = f"{verification_code} is your PngLike verification code"

    text_body = f"""Hello {clean_username},

Welcome to PngLike AI Studio (Powered by Div Sri)!

Please verify your Gmail address to activate your account.

Your 6-Digit Verification Code is:
{verification_code}

Or click the link below to verify and activate your account directly:
{verify_url}

This verification code will expire in 24 hours.
If you did not register for PngLike, you can safely ignore this email.

Best regards,
PngLike Studio Team
"""

    html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Verify your PngLike account</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f8fafc; padding: 40px 15px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 540px; background-color: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0;">
          
          <!-- Header Bar -->
          <tr>
            <td style="background-color: #161B33; padding: 28px 36px; text-align: center;">
              <div style="display: inline-block;">
                <span style="font-size: 24px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;">PngLike</span>
                <span style="display: block; font-size: 11px; color: #FF4365; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px;">Powered by Div Sri</span>
              </div>
            </td>
          </tr>

          <!-- Content Body -->
          <tr>
            <td style="padding: 36px 36px 28px 36px;">
              <h1 style="margin: 0 0 12px 0; font-size: 20px; font-weight: 800; color: #0f172a;">Verify your Gmail address</h1>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #475569;">
                Hi <strong>{clean_username}</strong>, thanks for registering at <strong>PngLike</strong>. To activate your account and start using the 9-in-1 AI Image Studio, please confirm your email address.
              </p>

              <!-- 6-Digit Code Box -->
              <div style="background-color: #f1f5f9; border: 2px dashed #cbd5e1; border-radius: 16px; padding: 20px; text-align: center; margin: 24px 0;">
                <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; color: #64748b; display: block; margin-bottom: 8px;">Your 6-Digit Verification Code</span>
                <span style="font-family: 'SF Mono', Monaco, Menlo, Consolas, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #2563eb; display: inline-block; padding-left: 8px;">
                  {verification_code}
                </span>
                <span style="display: block; font-size: 11px; color: #94a3b8; margin-top: 6px;">Valid for 24 hours</span>
              </div>

              <!-- 1-Click Verification Button -->
              <div style="text-align: center; margin: 30px 0 20px 0;">
                <a href="{verify_url}" style="display: inline-block; background-color: #2563eb; color: #ffffff; font-size: 14px; font-weight: 700; text-decoration: none; padding: 14px 32px; border-radius: 14px; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);">
                  Activate My Account Instantly &rarr;
                </a>
              </div>

              <p style="margin: 24px 0 0 0; font-size: 12px; line-height: 1.5; color: #94a3b8; text-align: center;">
                If you have trouble with the button, copy and paste this URL into your browser:<br>
                <a href="{verify_url}" style="color: #2563eb; word-break: break-all;">{verify_url}</a>
              </p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; border-top: 1px solid #f1f5f9; padding: 20px 36px; text-align: center;">
              <p style="margin: 0; font-size: 11px; color: #94a3b8;">
                If you didn't create an account on PngLike, you can safely ignore this email.<br>
                &copy; PngLike AI Studio • Powered by Div Sri
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # If SMTP is not configured with user/pass, return simulation result cleanly
    if not cfg["enabled"] or not cfg["user"] or not cfg["password"]:
        return {
            "sent": False,
            "smtp_configured": False,
            "reason": "SMTP credentials not configured. Verification code available in response.",
            "verification_code": verification_code,
            "verify_url": verify_url,
        }

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>"
        msg["To"] = to_email

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if cfg["port"] == 465:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=10)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=10)
            if cfg["use_tls"]:
                server.starttls()

        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["from_email"], [to_email], msg.as_string())
        server.quit()

        return {
            "sent": True,
            "smtp_configured": True,
            "to": to_email,
            "verification_code": verification_code,
            "verify_url": verify_url,
        }
    except Exception as e:
        return {
            "sent": False,
            "smtp_configured": True,
            "error": str(e),
            "verification_code": verification_code,
            "verify_url": verify_url,
        }


def test_smtp_connection(
    host: str,
    port: int,
    user: str,
    password: str,
    use_tls: bool = True,
    to_email: Optional[str] = None,
) -> Dict[str, Any]:
    """Test connecting and authenticating to an SMTP/Gmail server."""
    try:
        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=8)
        else:
            server = smtplib.SMTP(host, port, timeout=8)
            if use_tls:
                server.starttls()

        server.login(user, password)

        if to_email:
            msg = MIMEText(
                "This is a test email from PngLike AI Studio to verify your Gmail SMTP credentials.",
                "plain",
                "utf-8",
            )
            msg["Subject"] = "PngLike SMTP Test Connection"
            msg["From"] = user
            msg["To"] = to_email
            server.sendmail(user, [to_email], msg.as_string())

        server.quit()
        return {"success": True, "message": "Successfully connected and authenticated with SMTP server!"}
    except Exception as e:
        return {"success": False, "error": str(e)}
