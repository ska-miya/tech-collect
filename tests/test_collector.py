"""収集Agentのテスト"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.collector import load_keywords, save_keywords
from src.models import Article, ArticleSource, KeywordConfig


class TestKeywordManagement:
    """キーワード管理のテスト"""

    def test_load_keywords_default(self, tmp_path):
        """keywords.jsonが存在しない場合はデフォルト値"""
        with patch("src.agents.collector.get_settings") as mock:
            mock.return_value.keywords_path = str(tmp_path / "not_exist.json")
            kw = load_keywords()
            assert kw.tags == []
            assert kw.keywords == []

    def test_load_keywords_from_file(self, tmp_path):
        """keywords.jsonから正しく読み込めること"""
        kw_file = tmp_path / "keywords.json"
        kw_file.write_text(json.dumps({
            "tags": ["Python", "LLM"],
            "keywords": ["生成AI"],
            "sources": {"qiita": {"enabled": True}}
        }))

        with patch("src.agents.collector.get_settings") as mock:
            mock.return_value.keywords_path = str(kw_file)
            kw = load_keywords()
            assert "Python" in kw.tags
            assert "LLM" in kw.tags
            assert "生成AI" in kw.keywords

    def test_save_keywords(self, tmp_path):
        """キーワード設定を正しく保存できること"""
        kw_file = tmp_path / "keywords.json"

        with patch("src.agents.collector.get_settings") as mock:
            mock.return_value.keywords_path = str(kw_file)
            config = KeywordConfig(tags=["Docker"], keywords=["コンテナ"])
            save_keywords(config)

        data = json.loads(kw_file.read_text())
        assert "Docker" in data["tags"]
        assert "コンテナ" in data["keywords"]


class TestQiitaSource:
    """Qiita APIクライアントのテスト"""

    @pytest.mark.asyncio
    async def test_parse_qiita_item(self):
        """Qiita APIレスポンスのパースが正しいこと"""
        from src.sources.qiita import _parse_item

        item = {
            "id": "test123",
            "title": "Pythonでテスト",
            "url": "https://qiita.com/test/items/test123",
            "body": "テスト本文",
            "tags": [{"name": "Python"}, {"name": "テスト"}],
            "likes_count": 10,
            "user": {"id": "testuser"},
            "created_at": "2024-01-01T00:00:00+09:00",
        }

        article = _parse_item(item)
        assert article.source == ArticleSource.QIITA
        assert article.source_id == "test123"
        assert article.title == "Pythonでテスト"
        assert "Python" in article.tags
        assert article.likes_count == 10


class TestZennSource:
    """Zenn RSSパーサーのテスト"""

    def test_filter_by_keywords(self):
        """キーワードフィルタが正しく動作すること"""
        from src.sources.zenn import filter_by_keywords

        articles = [
            Article(
                source=ArticleSource.ZENN,
                source_id="a1",
                title="Pythonで生成AIを使う",
                url="https://zenn.dev/test/a1",
            ),
            Article(
                source=ArticleSource.ZENN,
                source_id="a2",
                title="Rustの入門",
                url="https://zenn.dev/test/a2",
            ),
        ]

        filtered = filter_by_keywords(articles, ["生成AI"])
        assert len(filtered) == 1
        assert filtered[0].source_id == "a1"

    def test_filter_empty_keywords(self):
        """キーワードが空の場合は全記事を返すこと"""
        from src.sources.zenn import filter_by_keywords

        articles = [
            Article(
                source=ArticleSource.ZENN,
                source_id="a1",
                title="テスト",
                url="https://zenn.dev/test/a1",
            ),
        ]

        filtered = filter_by_keywords(articles, [])
        assert len(filtered) == 1
