"""Anthropic Claude LLMプロバイダー"""

from __future__ import annotations

import httpx

from src.config import get_settings
from src.llm.base import BaseLLM


class ClaudeLLM(BaseLLM):
    """Anthropic Claudeプロバイダー"""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY が設定されていません")

    async def generate(self, prompt: str) -> str:
        """Claude Messages APIでテキスト生成"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]

    async def embed(self, text: str) -> list[float]:
        """Claude Embeddings (Voyageを使用)

        注: AnthropicにはEmbedding APIがないため、
        OllamaのEmbeddingにフォールバックするか、
        LangChainのHuggingFace Embeddingsを使用
        """
        # フォールバック: Ollamaのembeddingを使用
        from src.llm.ollama import OllamaLLM

        ollama = OllamaLLM()
        return await ollama.embed(text)

    def get_langchain_llm(self):
        """LangChain用ChatAnthropicを返す"""
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            api_key=self.api_key,
            model=self.model,
            temperature=0.3,
        )

    def get_langchain_embeddings(self):
        """LangChain用Embeddingsを返す (HuggingFaceフォールバック)"""
        # Claude自体にEmbedding APIがないため、Ollamaを使用
        from src.llm.ollama import OllamaLLM

        return OllamaLLM().get_langchain_embeddings()
