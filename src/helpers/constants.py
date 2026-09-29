from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

LEARNING_PATHS = ROOT_DIR / "paths" / "ai_paths"

AI_PATH = LEARNING_PATHS / "ai_paths.json"
ML_PATH = LEARNING_PATHS / "ml_paths.json"
DL_PATH = LEARNING_PATHS / "dl_paths.json"