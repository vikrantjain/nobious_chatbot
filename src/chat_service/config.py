from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ims_base_url: str = "http://localhost:5443"
    ims_auth_url: str = "http://localhost:5443"
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_provider: str = "bedrock_converse"
    github_repo_url: str = ""
    github_token: str = ""
    doc_index_path: str = "./doc_index"
    max_query_length: int = 200
    rate_limit_per_min: int = 3


config = Settings()
