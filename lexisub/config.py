from pathlib import Path
from platformdirs import user_data_dir

APP_NAME = "Lexisub"
APP_DATA_DIR = Path(user_data_dir(APP_NAME, appauthor=False))
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = APP_DATA_DIR / "lexisub.sqlite3"
MODELS_DIR = APP_DATA_DIR / "models"
LOG_DIR = APP_DATA_DIR / "logs"
TEMP_DIR = APP_DATA_DIR / "tmp"
for _d in (MODELS_DIR, LOG_DIR, TEMP_DIR):
    _d.mkdir(parents=True, exist_ok=True)

STT_MODEL_ID = "mlx-community/whisper-large-v3-turbo"
LLM_MODEL_ID = "mlx-community/gemma-3-4b-it-4bit"

TRANSLATION_CHUNK_LINES = 25
TRANSLATION_CONTEXT_LINES = 3
TRANSLATION_MAX_LENGTH_RATIO = 1.5

SUBTITLE_FONT = "Pretendard"
SUBTITLE_FONT_FALLBACK = "Apple SD Gothic Neo"
