import os
import webbrowser
import pathlib


def open_interface_in_browser(interface_dir: str) -> None:
    """Opens interface/index.html in the browser."""
    index_html_path = os.path.join(interface_dir, "index.html")
    if not os.path.exists(index_html_path): print(f"❌ Error: Cannot open interface. File not found: {index_html_path}"); return
    try:
        uri = pathlib.Path(os.path.abspath(index_html_path)).as_uri(); print(f"-> Opening URI: {uri}")
        webbrowser.open(uri); print("✅ Opened interface in browser (attempted).")
    except Exception as e: print(f"❌❌ Error opening browser: {e}")