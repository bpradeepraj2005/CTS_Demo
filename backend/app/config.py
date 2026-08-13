import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR/'priorauth.db'}")
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-please")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "720"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MODELS_DIR = BASE_DIR / "ml" / "models"

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

# Decision thresholds for the medical-necessity engine. Tunable without code
# changes via env so a payer can calibrate to their own policy posture.
AUTO_APPROVE_MIN_POLICY_FIT = float(os.getenv("AUTO_APPROVE_MIN_POLICY_FIT", "0.62"))
AUTO_DENY_MAX_POLICY_FIT = float(os.getenv("AUTO_DENY_MAX_POLICY_FIT", "0.38"))
MIN_DOCUMENTATION_SCORE = float(os.getenv("MIN_DOCUMENTATION_SCORE", "0.75"))