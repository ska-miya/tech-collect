"""収集Agent: Qiita/Zennから記事を収集するA2Aエージェント"""

from __future__ import annotations

import json
from pathlib import Path

from src.config import get_settings
from src.db import is_article_exists, save_article
from src.models import Article, CollectResult, KeywordConfig
from src.sources import qiita, zenn


def load_keywords() -> KeywordConfig:
    """keywords.jsonからキーワード設定を読み込み"""
    settings = get_settings()
    path = Path(settings.keywords_path)
    if not path.exists():
        return KeywordConfig()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return KeywordConfig(**data)


def save_keywords(config: KeywordConfig) -> None:
    """キーワード設定をkeywords.jsonに保存"""
    settings = get_settings()
    path = Path(settings.keywords_path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)


async def collect_articles() -> CollectResult:
    """全ソースから記事を収集

    1. keywords.jsonからタグ/キーワードを読み込み
    2. Qiita APIでタグ検索
    3. Zenn RSSでトピック取得 + キーワードフィルタ
    4. 重複排除（DBチェック）
    5. 新規記事をDBに保存

    Returns:
        収集結果（記事リスト + 統計情報）
    """
    kw_config = load_keywords()
    all_articles: list[Article] = []
    stats: dict[str, int] = {"qiita": 0, "zenn": 0}

    # --- Qiita ---
    if kw_config.sources.get("qiita", {}).get("enabled", True):
        print(f"[Collector] Qiita: タグ {kw_config.tags} で検索中...")
        qiita_articles = await qiita.fetch_articles_by_tags(kw_config.tags, per_page=20)
        # 既存記事を除外
        new_qiita = [
            a for a in qiita_articles
            if not is_article_exists(a.source.value, a.source_id)
        ]
        for a in new_qiita:
            save_article(a)
        all_articles.extend(new_qiita)
        stats["qiita"] = len(new_qiita)
        print(f"[Collector] Qiita: {len(new_qiita)}件の新規記事を収集")

    # --- Zenn ---
    if kw_config.sources.get("zenn", {}).get("enabled", True):
        print(f"[Collector] Zenn: トピック {kw_config.tags} で検索中...")
        zenn_articles = await zenn.fetch_articles_by_topics(kw_config.tags)
        # キーワードフィルタ
        if kw_config.keywords:
            zenn_articles = zenn.filter_by_keywords(
                zenn_articles, kw_config.keywords
            )
        # 既存記事を除外
        new_zenn = [
            a for a in zenn_articles
            if not is_article_exists(a.source.value, a.source_id)
        ]
        for a in new_zenn:
            save_article(a)
        all_articles.extend(new_zenn)
        stats["zenn"] = len(new_zenn)
        print(f"[Collector] Zenn: {len(new_zenn)}件の新規記事を収集")

    total = sum(stats.values())
    print(f"[Collector] 合計 {total}件の新規記事を収集しました")

    return CollectResult(
        articles=all_articles,
        source_stats=stats,
    )
