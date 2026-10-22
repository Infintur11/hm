import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "hospital.db"

class Settings:
    PROJECT_NAME: str = "City Hospital HMS"
    VERSION: str = "2.0.0"
    HOSPITAL_NAME: str = "City Hospital"
    HOSPITAL_ADDRESS: str = "42 Health Sciences Boulevard, Medical District"
    HOSPITAL_PHONE: str = "+91 98765 43210"
    HOSPITAL_EMAIL: str = "care@cityhospital.org"
    TIMEZONE: str = os.getenv("HMS_TIMEZONE", "Asia/Kolkata")
    
    # Database
    # Allows tests and local deployments to point at an isolated/persistent SQLite file.
    DATABASE_URL: str = os.getenv("HMS_DATABASE_URL", f"sqlite:///{DB_PATH.as_posix()}")
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "aegis-hms-super-production-secret-key-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 12  # 12 hours shift duration
    
    # Server
    HOST: str = os.getenv("HMS_HOST", "0.0.0.0")
    PORT: int = 8000
    RELOAD: bool = os.getenv("HMS_RELOAD", "false").lower() == "true"
    DEBUG: bool = True

settings = Settings()
