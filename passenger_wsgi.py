"""
Passenger WSGI Entrypoint for PngLike Studio
Used by cPanel / CloudLinux / Hostinger "Setup Python App" (Phusion Passenger).
"""
import os
import sys

# Ensure local venv and project root are in the sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

VENV_SITE_PACKAGES = os.path.join(BASE_DIR, ".venv", "lib", "python3.12", "site-packages")
if os.path.isdir(VENV_SITE_PACKAGES):
    sys.path.insert(0, VENV_SITE_PACKAGES)

from app import app

# Adapt ASGI (FastAPI) to WSGI for Passenger
try:
    from a2wsgi import ASGIMiddleware
    application = ASGIMiddleware(app)
except ImportError:
    try:
        from asgiref.wsgi import WsgiToAsgi
        application = app
    except ImportError:
        application = app
