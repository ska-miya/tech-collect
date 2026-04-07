"""設定管理: 環境変数から全設定を読み込む"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic_settings import BaseSettings


class LLMProvider(str, Enum):
    """LLMプロバイダー選択"""

    OLLAMA = "ollama"
    OPENAI = "openai"
    CLAUDE = "claude"


class Settings(BaseSettings):
    """アプリケーション設定（.envから自動読み込み）"""

    # --- LLM ---
    llm_provider: LLMProvider = LLMProvider.OLLAMA

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # Anthropic Claude
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # --- Notion ---
    notion_api_key: str = ""
    notion_database_id: str = ""  # ALLデータベースID
    notion_daily_page_id: str = ""  # Dailyページの親ページID

    # --- Qiita ---
    qiita_access_token: str = ""

    # --- ChromaDB ---
    chroma_persist_dir: str = "./data/chroma"

    # --- Paths ---
    keywords_path: str = "./keywords.json"
    db_path: str = "./data/tech_collect.db"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def chroma_dir(self) -> Path:
        return Path(self.chroma_persist_dir)

    @property
    def database_path(self) -> Path:
        return Path(self.db_path)


# シングルトン（アプリ全体で1つの設定を共有）
from typing import Optional
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """設定を取得（初回呼び出し時にロード）"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
