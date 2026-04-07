"""Qiita API v2 クライアント: タグ検索で記事を収集"""

from __future__ import annotations

from datetime import datetime

import httpx

from src.config import get_settings
from src.models import Article, ArticleSource

# Qiita API v2 ベースURL
BASE_URL = "https://qiita.com/api/v2"


async def fetch_articles_by_tag(
    tag: str,
    per_page: int = 20,
    page: int = 1,
) -> list[Article]:
    """指定タグの最新記事を取得

    Args:
        tag: 検索タグ（例: "Python", "LLM"）
        per_page: 1ページの取得件数（最大100）
        page: ページ番号

    Returns:
        記事リスト
    """
    settings = get_settings()
    headers = {}
    if settings.qiita_access_token:
        headers["Authorization"] = f"Bearer {settings.qiita_access_token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{BASE_URL}/items",
            headers=headers,
            params={
                "query": f"tag:{tag}",
                "per_page": min(per_page, 100),
                "page": page,
            },
        )
        response.raise_for_status()
        items = response.json()

    return [_parse_item(item) for item in items]


async def fetch_articles_by_tags(
    tags: list[str],
    per_page: int = 20,
) -> list[Article]:
    """複数タグで記事を取得し、重複を排除して返す

    Args:
        tags: 検索タグのリスト
        per_page: タグあたりの取得件数

    Returns:
        重複排除済みの記事リスト
    """
    seen_ids: set[str] = set()
    articles: list[Article] = []

    for tag in tags:
        try:
            tag_articles = await fetch_articles_by_tag(tag, per_page=per_page)
            for article in tag_articles:
                if article.source_id not in seen_ids:
                    seen_ids.add(article.source_id)
                    articles.append(article)
        except httpx.HTTPError as e:
            print(f"[Qiita] タグ '{tag}' の取得に失敗: {e}")
            continue

    return articles


def _parse_item(item: dict) -> Article:
    """Qiita APIレスポンスをArticleモデルに変換"""
    tags = [t["name"] for t in item.get("tags", [])]
    published_at = None
    if item.get("created_at"):
        try:
            published_at = datetime.fromisoformat(
                item["created_at"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            pass

    return Article(
        source=ArticleSource.QIITA,
        source_id=item["id"],
        title=item.get("title", ""),
        url=item.get("url", ""),
        body=item.get("body", ""),
        tags=tags,
        likes_count=item.get("likes_count", 0),
        author=item.get("user", {}).get("id", ""),
        published_at=published_at,
    )
