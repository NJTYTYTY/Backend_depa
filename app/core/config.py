"""
Configuration settings for Backend_PWA
"""

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Storage Configuration
    STORAGE_TYPE: str = "json"
    STORAGE_DIR: str = "data"
    
    # JWT Configuration
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://10.106.61.144:3000",
        "http://10.106.61.144:3001",
        "http://10.106.61.144:3000",
        "http://10.106.61.144:3001",
        "https://your-frontend.vercel.app"
    ]
    
    # Backend_Center Integration
    BACKEND_CENTER_WEBHOOK_SECRET: str = "your-webhook-secret"
    BACKEND_CENTER_BASE_URL: str = "https://backend-center.com"
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 100
    
    # Cache Configuration
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    
    class Config:
        env_file = "config.env"
        case_sensitive = False


# Create settings instance
settings = Settings()
