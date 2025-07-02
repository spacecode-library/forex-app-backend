from pydantic_settings import BaseSettings
from typing import Optional
from urllib.parse import quote_plus

class Settings(BaseSettings):
    # Database - Individual components
    DATABASE_HOST: str
    DATABASE_PORT: str
    DATABASE_USER: str
    DATABASE_PASSWORD: str
    DATABASE_NAME: str 

    ADMIN_SETUP_KEY: str = "setup_admin_2024_secure_key" 
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    
    # MT5
    MT5_LOGIN: int
    MT5_PASSWORD: str
    MT5_SERVER: str
    
    # Trading
    SYMBOLS: list = ["EURUSD", "USDJPY", "XAUUSD"]
    DEFAULT_LEVERAGE: int = 100
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    MAX_LOGIN_ATTEMPTS: int = 5
    PASSWORD_MIN_LENGTH: int = 6
    USERNAME_MIN_LENGTH: int = 3
    
    @property
    def DATABASE_URL(self) -> str:
        """Construct database URL from components, URL-encoding the password."""
        # URL-encode the password so special chars like '@' become safe (e.g., '%40')
        pwd = quote_plus(self.DATABASE_PASSWORD)
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{pwd}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    class Config:
        env_file = ".env"

settings = Settings()
