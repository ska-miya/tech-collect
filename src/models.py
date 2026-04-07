"""Pydanticモデル定義: データ構造の型安全な定義"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ArticleSource(str, Enum):
    """記事ソース"""

    QIITA = "qiita"
    ZENN = "zenn"


class Article(BaseModel):
    """収集した記事のデータモデル"""

    source: ArticleSource
    source_id: str = Field(description="ソース上のユニークID")
    title: str
    url: str
    body: str = Field(default="", description="記事本文（マークダウン）")
    tags: list[str] = Field(default_factory=list)
    likes_count: int = Field(default=0)
    author: str = Field(default="")
    published_at: datetime | None = None
    collected_at: datetime = Field(default_factory=datetime.now)


class ArticleSummary(BaseModel):
    """LLMによる要約結果"""

    article_source_id: str
    keywords: list[str] = Field(default_factory=list, description="記事のキーワード（3〜5個）")
    summary: str = Field(description="3〜4行の要約")
    highlight: str = Field(default="", description="注目ポイント（1〜2行）")
    target_audience: str = Field(default="", description="おすすめ対象 / 見る価値")
    conclusion: str = Field(default="", description="結論（1行）")
    category: str = Field(description="LLMによる分類カテゴリ")
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="キーワードとの関連度スコア"
    )
    similar_article_ids: list[str] = Field(
        default_factory=list, description="類似記事のsource_id一覧"
    )
    summarized_at: datetime = Field(default_factory=datetime.now)


class NotionPublishResult(BaseModel):
    """Notion投稿結果"""

    article_source_id: str
    notion_page_id: str
    notion_url: str
    published_at: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error_message: str = ""


class KeywordConfig(BaseModel):
    """キーワード設定"""

    tags: list[str] = Field(default_factory=list, description="タグ検索用キーワード")
    keywords: list[str] = Field(
        default_factory=list, description="本文フィルタ用キーワード"
    )
    sources: dict[str, dict] = Field(default_factory=dict)


class CollectResult(BaseModel):
    """収集Agent → 要約Agentへのデータ受け渡し"""

    articles: list[Article]
    collected_at: datetime = Field(default_factory=datetime.now)
    source_stats: dict[str, int] = Field(
        default_factory=dict, description="ソース別収集件数"
    )


class SummaryResult(BaseModel):
    """要約Agent → 投稿Agentへのデータ受け渡し"""

    summaries: list[ArticleSummary]
    articles: list[Article]
    processed_at: datetime = Field(default_factory=datetime.now)


class PublishResult(BaseModel):
    """投稿Agentの最終結果"""

    results: list[NotionPublishResult]
    total: int = 0
    success_count: int = 0
    error_count: int = 0
