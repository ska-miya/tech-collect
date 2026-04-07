"""LLM抽象基底クラス: 全プロバイダー共通インターフェース"""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseLLM(ABC):
    """LLMプロバイダーの共通インターフェース"""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        """テキスト生成"""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """テキストをベクトルに変換（RAG用）"""
        ...

    @abstractmethod
    def get_langchain_llm(self):
        """LangChain互換のLLMオブジェクトを返す"""
        ...

    @abstractmethod
    def get_langchain_embeddings(self):
        """LangChain互換のEmbeddingsオブジェクトを返す"""
        ...
