import os
import sys
import webbrowser
import threading
import time

def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:7860")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)

    # Set U2NET_HOME to local models directory
    models_dir = os.path.join(base_dir, "models")
    os.environ["U2NET_HOME"] = models_dir

    print("=" * 60)
    print("  RemBG Studio - AI Background Remover")
    print("=" * 60)
    print(f"Working Directory : {base_dir}")
    print(f"Models Directory  : {models_dir}")
    print("Starting Web Application at http://127.0.0.1:7860 ...")
    print("=" * 60)

    # Automatically launch browser in background thread
    threading.Thread(target=open_browser, daemon=True).start()

    import uvicorn
    from app import app

    uvicorn.run(app, host="127.0.0.1", port=7860, log_level="info")
