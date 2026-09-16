import os

API_ID = int(os.getenv("API_ID", "123456"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "relay")
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "1.0"))
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
