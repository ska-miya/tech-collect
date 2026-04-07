"""RAG要約Agentのテスト"""

from __future__ import annotations

import pytest

from src.models import Article, ArticleSource, ArticleSummary


class TestArticleSummaryModel:
    """ArticleSummaryモデルのテスト"""

    def test_create_summary(self):
        """要約モデルの生成が正しいこと"""
        summary = ArticleSummary(
            article_source_id="test123",
            summary="テスト要約テキスト",
            category="AI/ML",
            relevance_score=0.85,
        )
        assert summary.article_source_id == "test123"
        assert summary.category == "AI/ML"
        assert 0.0 <= summary.relevance_score <= 1.0

    def test_relevance_score_bounds(self):
        """関連度スコアの範囲チェック"""
        with pytest.raises(Exception):
            ArticleSummary(
                article_source_id="test",
                summary="test",
                category="test",
                relevance_score=1.5,  # 範囲外
            )


class TestSummarizerPrompt:
    """要約プロンプトのテスト"""

    def test_prompt_template_format(self):
        """プロンプトテンプレートが正しくフォーマットされること"""
        from src.agents.summarizer import SUMMARIZE_PROMPT

        article = Article(
            source=ArticleSource.QIITA,
            source_id="test123",
            title="テスト記事",
            url="https://example.com",
            body="テスト本文" * 100,
            tags=["Python", "AI"],
        )

        prompt = SUMMARIZE_PROMPT.format(
            title=article.title,
            source=article.source.value,
            tags=", ".join(article.tags),
            body=article.body[:2000],
        )

        assert "テスト記事" in prompt
        assert "qiita" in prompt
        assert "Python, AI" in prompt
