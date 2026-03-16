from pydantic_settings import BaseSettings
from pydantic import Extra
from typing import List

class Settings(BaseSettings):
    GOOGLE_API_KEY : str
    GROQ_API_KEY: str
    OPENROUTER_API_KEY: str
    LANGSMITH_TRACING:bool
    LANGSMITH_API_KEY:str
    LANGSMITH_PROJECT:str
    LANGFUSE_SECRET_KEY:str
    LANGFUSE_PUBLIC_KEY:str
    LANGFUSE_BASE_URL:str
    CARTESIA_API_KEY:str
    DEEPGRAM_API_KEY:str
    DAILY_API_KEY:str


    class Config:
        env_file = ".env"
        env_prefix = ""  # Add this line to remove any prefix for environment variables

def get_settings() -> Settings:
    return Settings()