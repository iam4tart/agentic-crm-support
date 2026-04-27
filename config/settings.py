from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    HF_TOKEN: str
    NOTION_API_KEY: str
    JIRA_BASE_URL: str
    JIRA_USERNAME: str
    JIRA_API_TOKEN: str
    JIRA_PROJECT_KEY: str = 'KAN'
    LANGCHAIN_TRACING_V2: str = 'true'
    LANGCHAIN_API_KEY: str = ''
    LANGCHAIN_PROJECT: str = 'agent-crm-support'
    CHROMA_DB_DIR: str = './chroma_db'
    CHROMA_API_KEY: str = ''
    CHROMA_TENANT: str = ''
    CHROMA_DATABASE: str = 'default'
    MODEL_NAME: str = 'Qwen/Qwen2.5-1.5B-Instruct:featherless-ai'
    EMBEDDING_MODEL: str = 'BAAI/bge-large-en-v1.5'
    MAX_RETRIES: int = 2


    class Config:
        env_file = '.env'
        protected_namespaces = 'settings_',


settings = Settings()
