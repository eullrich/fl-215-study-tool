import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# On Render, use the persistent disk mount; locally, use ./data
DATA_DIR = Path(os.environ.get("DATA_DIR", str(BASE_DIR / "data")))

DB_PATH = DATA_DIR / "study.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
LEGACY_DIR = BASE_DIR / "legacy"
