"""LLMファクトリー: 環境変数に基づいてプロバイダーを切り替え"""

from src.config import LLMProvider, get_settings
from src.llm.base import BaseLLM


def create_llm() -> BaseLLM:
    """設定に基づいてLLMプロバイダーを生成

    LLM_PROVIDER 環境変数で切り替え:
        - ollama: ローカルLLM（無料・デフォルト）
        - openai: OpenAI API
        - claude: Anthropic Claude API
    """
    settings = get_settings()
    provider = settings.llm_provider

    if provider == LLMProvider.OLLAMA:
        from src.llm.ollama import OllamaLLM

        return OllamaLLM()

    elif provider == LLMProvider.OPENAI:
        from src.llm.openai_llm import OpenAILLM

        return OpenAILLM()

    elif provider == LLMProvider.CLAUDE:
        from src.llm.claude_llm import ClaudeLLM

        return ClaudeLLM()

    else:
        raise ValueError(f"未対応のLLMプロバイダー: {provider}")
