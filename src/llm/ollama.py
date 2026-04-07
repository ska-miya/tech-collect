"""Ollama LLMプロバイダー: ローカルで無料実行"""

from __future__ import annotations

import httpx

from src.config import get_settings
from src.llm.base import BaseLLM


class OllamaLLM(BaseLLM):
    """Ollamaプロバイダー（ローカルLLM）"""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

    async def generate(self, prompt: str) -> str:
        """Ollama APIでテキスト生成"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json()["response"]

    async def embed(self, text: str) -> list[float]:
        """Ollama APIでベクトル化"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": text,
                },
            )
            response.raise_for_status()
            return response.json()["embeddings"][0]

    def get_langchain_llm(self):
        """LangChain用OllamaLLMを返す"""
        from langchain_community.llms import Ollama

        return Ollama(
            base_url=self.base_url,
            model=self.model,
        )

    def get_langchain_embeddings(self):
        """LangChain用OllamaEmbeddingsを返す"""
        from langchain_community.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(
            base_url=self.base_url,
            model=self.model,
        )
