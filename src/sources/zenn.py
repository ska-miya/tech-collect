"""Zenn RSSパーサー: トピック別RSSフィードから記事を収集"""

from __future__ import annotations

from datetime import datetime

import feedparser
import httpx

from src.models import Article, ArticleSource

# Zenn RSSフィードのベースURL
RSS_BASE_URL = "https://zenn.dev/topics/{topic}/feed"


async def fetch_articles_by_topic(topic: str) -> list[Article]:
    """指定トピックのRSSフィードから記事を取得

    Args:
        topic: Zennトピック名（例: "python", "llm"）
              ※小文字で指定

    Returns:
        記事リスト
    """
    url = RSS_BASE_URL.format(topic=topic.lower())

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()

    feed = feedparser.parse(response.text)
    return [_parse_entry(entry) for entry in feed.entries]


async def fetch_articles_by_topics(topics: list[str]) -> list[Article]:
    """複数トピックで記事を取得し、重複を排除して返す

    Args:
        topics: トピック名のリスト

    Returns:
        重複排除済みの記事リスト
    """
    seen_urls: set[str] = set()
    articles: list[Article] = []

    for topic in topics:
        try:
            topic_articles = await fetch_articles_by_topic(topic)
            for article in topic_articles:
                if article.url not in seen_urls:
                    seen_urls.add(article.url)
                    articles.append(article)
        except (httpx.HTTPError, Exception) as e:
            print(f"[Zenn] トピック '{topic}' の取得に失敗: {e}")
            continue

    return articles


def filter_by_keywords(
    articles: list[Article], keywords: list[str]
) -> list[Article]:
    """記事をキーワードでフィルタリング

    タイトルまたは本文にキーワードが含まれる記事のみ返す

    Args:
        articles: フィルタ対象の記事リスト
        keywords: フィルタキーワード（OR条件）

    Returns:
        キーワードに一致する記事リスト
    """
    if not keywords:
        return articles

    filtered = []
    for article in articles:
        text = f"{article.title} {article.body}".lower()
        if any(kw.lower() in text for kw in keywords):
            filtered.append(article)
    return filtered


def _parse_entry(entry: dict) -> Article:
    """RSSエントリをArticleモデルに変換"""
    published_at = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            published_at = datetime(*entry.published_parsed[:6])
        except (TypeError, ValueError):
            pass

    # Zenn RSSではソースIDとしてURLのslug部分を使う
    url = entry.get("link", "")
    source_id = url.split("/")[-1] if url else entry.get("id", "")

    # RSSフィードには本文の要約（summary）のみ含まれる
    body = entry.get("summary", "")

    return Article(
        source=ArticleSource.ZENN,
        source_id=source_id,
        title=entry.get("title", ""),
        url=url,
        body=body,
        tags=[],  # RSSにはタグ情報なし
        likes_count=0,
        author=entry.get("author", ""),
        published_at=published_at,
    )
