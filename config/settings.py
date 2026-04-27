from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    hf_token: str
    notion_api_key: str
    jira_base_url: str
    jira_username: str
    jira_api_token: str
    langchain_tracing_v2: str = "true"
    langchain_api_key: str = ""
    langchain_project: str = "agent-crm-support"
    chroma_db_dir: str = "./chroma_db"
    chroma_api_key: str = ""
    chroma_tenant: str = ""
    chroma_database: str = "default"
    model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"
    embedding_model: str = "BAAI/bge-large-en-v1.5"
    max_retries: int = 2

    class Config:
        env_file = ".env"
        protected_namespaces = ('settings_',)

settings = Settings()
