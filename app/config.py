from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application settings and configurations.
    """
    APP_NAME: str = "Multi-Source Candidate Data Transformer"
    DEBUG: bool = False
    
    # Source confidence scores
    CONFIDENCE_CSV: float = 0.8
    CONFIDENCE_RESUME: float = 0.6

    class Config:
        env_file = ".env"

settings = Settings()
