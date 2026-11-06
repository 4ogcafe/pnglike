import os

# Ensure U2NET_HOME is set to local models directory
models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "models"))
os.makedirs(models_dir, exist_ok=True)
os.environ["U2NET_HOME"] = models_dir

print(f"Target model directory: {models_dir}")

from rembg.session_factory import new_session

for model_name in ("u2netp", "u2net"):
    print(f"Checking / downloading '{model_name}' model...")
    try:
        new_session(model_name)
        print(f"[OK] '{model_name}' is ready.")
    except Exception as e:
        print(f"[ERROR] Failed to prepare '{model_name}': {e}")

print("Model setup complete.")
