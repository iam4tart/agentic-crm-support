from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    HF_TOKEN: str
    MODEL_NAME: str = "Qwen/Qwen2.5-1.5B-Instruct:featherless-ai"
    EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"
    
    CHROMA_API_KEY: Optional[str] = None
    CHROMA_DB_DIR: str = "./data/chroma"
    CHROMA_TENANT: str = "default"
    CHROMA_DATABASE: str = "default"
    
    JIRA_BASE_URL: str
    JIRA_USERNAME: str
    JIRA_API_TOKEN: str
    JIRA_PROJECT_KEY: str = "KAN"
    
    LANGCHAIN_TRACING_V2: str = "false"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: str = "agentic-crm-support"
    
    MAX_RETRIES: int = 2

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
