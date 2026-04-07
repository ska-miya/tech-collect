"""Notion投稿Agentのテスト"""

from __future__ import annotations

from datetime import datetime

from src.agents.publisher import _build_properties
from src.models import Article, ArticleSource, ArticleSummary


class TestBuildProperties:
    """Notionプロパティ構築のテスト"""

    def test_build_basic_properties(self):
        """基本的なプロパティが正しく構築されること"""
        article = Article(
            source=ArticleSource.QIITA,
            source_id="test123",
            title="テスト記事タイトル",
            url="https://qiita.com/test/items/test123",
            tags=["Python", "AI"],
            likes_count=42,
        )
        summary = ArticleSummary(
            article_source_id="test123",
            summary="これはテスト要約です",
            category="AI/ML",
            relevance_score=0.9,
        )

        props = _build_properties(article, summary)

        assert props["タイトル"]["title"][0]["text"]["content"] == "テスト記事タイトル"
        assert props["要約"]["rich_text"][0]["text"]["content"] == "これはテスト要約です"
        assert props["カテゴリ"]["select"]["name"] == "AI/ML"
        assert props["ソース"]["select"]["name"] == "Qiita"
        assert props["URL"]["url"] == "https://qiita.com/test/items/test123"
        assert props["いいね数"]["number"] == 42

    def test_tags_property(self):
        """タグが正しくmulti_selectに変換されること"""
        article = Article(
            source=ArticleSource.ZENN,
            source_id="test",
            title="テスト",
            url="https://zenn.dev/test",
            tags=["Python", "LangChain", "RAG"],
        )
        summary = ArticleSummary(
            article_source_id="test",
            summary="要約",
            category="AI/ML",
        )

        props = _build_properties(article, summary)
        tag_names = [t["name"] for t in props["タグ"]["multi_select"]]
        assert "Python" in tag_names
        assert "LangChain" in tag_names

    def test_no_tags(self):
        """タグがない場合はタグプロパティが含まれないこと"""
        article = Article(
            source=ArticleSource.ZENN,
            source_id="test",
            title="テスト",
            url="https://zenn.dev/test",
            tags=[],
        )
        summary = ArticleSummary(
            article_source_id="test",
            summary="要約",
            category="その他",
        )

        props = _build_properties(article, summary)
        assert "タグ" not in props
