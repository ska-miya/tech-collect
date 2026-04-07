"""OpenAI LLMプロバイダー"""

from __future__ import annotations

import httpx

from src.config import get_settings
from src.llm.base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAIプロバイダー"""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY が設定されていません")

    async def generate(self, prompt: str) -> str:
        """OpenAI Chat APIでテキスト生成"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def embed(self, text: str) -> list[float]:
        """OpenAI Embeddings APIでベクトル化"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": "text-embedding-3-small",
                    "input": text,
                },
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]

    def get_langchain_llm(self):
        """LangChain用ChatOpenAIを返す"""
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            api_key=self.api_key,
            model=self.model,
            temperature=0.3,
        )

    def get_langchain_embeddings(self):
        """LangChain用OpenAIEmbeddingsを返す"""
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            api_key=self.api_key,
            model="text-embedding-3-small",
        )
