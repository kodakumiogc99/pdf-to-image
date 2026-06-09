import json
from pathlib import Path

SETTINGS_FILE = Path("user_settings.json")

DEFAULT_SETTINGS = {
    "last_upload_path": "",
    "output_path": str(Path("outputs").resolve()),
    "output_format": "jpg"
}

def load_settings() -> dict:
    """讀取使用者的歷史設定，若無則回傳預設值。"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                # 合併預設值與檔案中的設定
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: dict):
    """儲存使用者的設定到本地端。"""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"無法儲存設定檔: {e}")