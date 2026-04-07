"""Notion投稿Agent: 要約結果をNotionデータベース + Dailyページに投稿"""

from __future__ import annotations

from datetime import datetime

from src.config import get_settings
from src.db import save_publish_result
from src.models import (
    Article,
    ArticleSummary,
    NotionPublishResult,
    PublishResult,
    SummaryResult,
)

VALID_CATEGORIES = {"AI/ML", "Web開発", "インフラ", "データ", "セキュリティ", "その他"}


def _normalize_category(category: str) -> str:
    """カテゴリを正規化（LLMがカンマ区切り等で返した場合の対策）"""
    if not category:
        return "その他"
    for part in category.split(","):
        part = part.strip()
        if part in VALID_CATEGORIES:
            return part
    for valid in VALID_CATEGORIES:
        if valid in category:
            return valid
    return "その他"


async def publish_to_notion(summary_result: SummaryResult) -> PublishResult:
    """要約結果をNotionに投稿（ALL DB + Dailyページ）

    - ALL: データベースに全記事を蓄積（1記事=1ページ）
    - Daily: 日付タイトルのページに当日収集分をまとめて表示

    Args:
        summary_result: 要約Agentの出力

    Returns:
        投稿結果
    """
    from notion_client import Client

    settings = get_settings()

    if not settings.notion_api_key or not settings.notion_database_id:
        print("[Publisher] Notion APIキーまたはデータベースIDが未設定です")
        return PublishResult(results=[], total=0, success_count=0, error_count=0)

    notion = Client(auth=settings.notion_api_key)

    # 記事をsource_idで引けるようにマップ化
    article_map: dict[str, Article] = {
        a.source_id: a for a in summary_result.articles
    }

    # 類似記事のタイトル+URL解決用マップ
    article_info: dict[str, dict] = {
        a.source_id: {"title": a.title, "url": a.url}
        for a in summary_result.articles
    }
    # DBからも既存記事の情報を取得（過去記事への類似参照用）
    article_info.update(_load_article_info_from_db())

    results: list[NotionPublishResult] = []
    success_count = 0
    error_count = 0

    # 投稿成功した記事+要約をDailyページ用に収集
    daily_entries: list[tuple[Article, ArticleSummary]] = []

    # === ALL: データベースに1記事ずつページ作成 ===
    for summary in summary_result.summaries:
        article = article_map.get(summary.article_source_id)
        if not article:
            continue

        try:
            print(f"[Publisher] ALL DB投稿中: {article.title[:50]}...")

            page = notion.pages.create(
                parent={"database_id": settings.notion_database_id},
                properties=_build_properties(article, summary, article_info),
                children=_build_article_children(article, summary, article_info),
            )

            result = NotionPublishResult(
                article_source_id=article.source_id,
                notion_page_id=page["id"],
                notion_url=page["url"],
                success=True,
            )
            save_publish_result(result)
            results.append(result)
            success_count += 1
            daily_entries.append((article, summary))

        except Exception as e:
            error_msg = str(e)
            print(f"[Publisher] ALL投稿失敗: {article.title[:50]} - {error_msg}")
            result = NotionPublishResult(
                article_source_id=article.source_id,
                notion_page_id="",
                notion_url="",
                success=False,
                error_message=error_msg,
            )
            results.append(result)
            error_count += 1

    # === Daily: 日付ページに当日分をまとめて投稿 ===
    if daily_entries and settings.notion_daily_page_id:
        try:
            print(f"[Publisher] Dailyページ作成中（{len(daily_entries)}件）...")
            _create_daily_page(notion, settings.notion_daily_page_id, daily_entries, article_info)
            print("[Publisher] Dailyページ作成完了")
        except Exception as e:
            print(f"[Publisher] Dailyページ作成失敗: {e}")

    total = success_count + error_count
    print(
        f"[Publisher] 完了: {total}件中 {success_count}件成功, {error_count}件失敗"
    )

    return PublishResult(
        results=results,
        total=total,
        success_count=success_count,
        error_count=error_count,
    )


# =========================================================
# ALL データベース用（1記事 = 1ページ）
# =========================================================

def _resolve_similar_titles(
    similar_ids: list[str], article_info: dict[str, dict] = None,
) -> str:
    """類似記事IDリストをタイトル文字列に変換（プロパティ用・短縮版）"""
    if not similar_ids or not article_info:
        return ""
    titles = []
    for sid in similar_ids[:3]:
        info = article_info.get(sid)
        if info:
            titles.append(info["title"][:50])
    return " / ".join(titles) if titles else ""


def _build_similar_blocks(
    similar_ids: list[str], article_info: dict[str, dict] = None,
) -> list[dict]:
    """類似記事のNotionブロックを生成（タイトル=リンクテキスト + URL表示）"""
    if not similar_ids or not article_info:
        return []

    items = []
    for sid in similar_ids[:3]:
        info = article_info.get(sid)
        if info:
            items.append(info)

    if not items:
        return []

    blocks: list[dict] = []
    # 見出し
    blocks.append({
        "object": "block",
        "type": "heading_3",
        "heading_3": {
            "rich_text": [{"type": "text", "text": {"content": "🔗 類似記事"}}],
        },
    })
    # 各類似記事を箇条書き（タイトルがリンク）で表示
    for info in items:
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": info["title"],
                            "link": {"url": info["url"]},
                        },
                        "annotations": {"bold": True},
                    },
                ],
            },
        })

    return blocks


def _load_article_info_from_db() -> dict[str, dict]:
    """SQLiteから既存記事のsource_id→{title, url}マップを取得"""
    import sqlite3
    from src.config import get_settings
    settings = get_settings()
    try:
        conn = sqlite3.connect(str(settings.database_path))
        rows = conn.execute("SELECT source_id, title, url FROM articles").fetchall()
        conn.close()
        return {r[0]: {"title": r[1], "url": r[2]} for r in rows}
    except Exception:
        return {}


def _build_properties(article: Article, summary: ArticleSummary, article_info: dict[str, dict] = None) -> dict:
    """ALLデータベース: ページプロパティ（一覧で見える情報をフル設定）"""
    date_str = datetime.now().strftime("%Y-%m-%d")

    # multi_select用: キーワード（LLM抽出、最大5個）
    kw_options = [{"name": kw[:100]} for kw in (summary.keywords or [])[:5]]
    # multi_select用: タグ（記事の元タグ、最大10個）
    tag_options = [{"name": tag[:100]} for tag in (article.tags or [])[:10]]

    return {
        "Name": {
            "title": [{"text": {"content": article.title[:100]}}],
        },
        "ソース": {
            "select": {"name": article.source.value.capitalize()},
        },
        "カテゴリ": {
            "select": {"name": _normalize_category(summary.category)},
        },
        "キーワード": {
            "multi_select": kw_options,
        },
        "タグ": {
            "multi_select": tag_options,
        },
        "URL": {
            "url": article.url,
        },
        "要約": {
            "rich_text": [{"text": {"content": summary.summary[:2000]}}],
        },
        "注目ポイント": {
            "rich_text": [{"text": {"content": summary.highlight[:2000]}}] if summary.highlight else [],
        },
        "いいね数": {
            "number": article.likes_count,
        },
        "関連度": {
            "number": summary.relevance_score,
        },
        "収集日": {
            "date": {"start": date_str},
        },
        "お気に入り": {
            "checkbox": False,
        },
        "類似記事": {
            "rich_text": [{"text": {"content":
                _resolve_similar_titles(summary.similar_article_ids, article_info)
            }}] if summary.similar_article_ids else [],
        },
    }


def _build_article_children(
    article: Article, summary: ArticleSummary, article_info: dict[str, dict] = None,
) -> list:
    """ALLデータベース: 1記事の詳細ページ本文（プロパティで見えない詳細情報）"""
    blocks: list[dict] = []

    # 元記事リンク
    blocks.append({
        "object": "block",
        "type": "bookmark",
        "bookmark": {"url": article.url},
    })

    # おすすめ対象
    if summary.target_audience:
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🎯"},
                "rich_text": [{"type": "text", "text": {"content":
                    f"おすすめ対象: {summary.target_audience}"
                }}],
            },
        })

    # 結論
    if summary.conclusion:
        blocks.append({
            "object": "block",
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "💡"},
                "rich_text": [{"type": "text", "text": {"content":
                    f"結論: {summary.conclusion}"
                }}],
            },
        })

    # 類似記事（タイトル+URLリンク付き）
    blocks.extend(_build_similar_blocks(summary.similar_article_ids, article_info))

    return blocks


# =========================================================
# Daily ページ用（日付タイトル + 当日記事一覧）
# =========================================================

def _create_daily_page(
    notion,
    parent_page_id: str,
    entries: list[tuple[Article, ArticleSummary]],
    article_info: dict[str, dict] = None,
) -> dict:
    """Dailyページを作成（1日1ページ、記事を一覧表示）

    ページタイトル例: 「2026-04-06 技術記事レポート（12件）」
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    title = f"{date_str} 技術記事レポート（{len(entries)}件）"

    children = _build_daily_children(entries, article_info)

    # Notion API制限: 1回のcreateで100ブロックまで
    # 超える場合は分割して追加
    first_batch = children[:100]
    remaining = children[100:]

    page = notion.pages.create(
        parent={"page_id": parent_page_id},
        properties={
            "title": [{"type": "text", "text": {"content": title}}],
        },
        children=first_batch,
    )

    # 残りのブロックを追加
    while remaining:
        batch = remaining[:100]
        remaining = remaining[100:]
        notion.blocks.children.append(
            block_id=page["id"],
            children=batch,
        )

    print(f"[Publisher] Dailyページ作成: {title} ({page['url']})")
    return page


def _build_daily_children(
    entries: list[tuple[Article, ArticleSummary]],
    article_info: dict[str, dict] = None,
) -> list[dict]:
    """Dailyページの本文ブロックを構築"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    blocks: list[dict] = []

    # ヘッダー: サマリー情報
    # カテゴリ別集計
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    for article, summary in entries:
        cat = summary.category
        category_counts[cat] = category_counts.get(cat, 0) + 1
        src = article.source.value.capitalize()
        source_counts[src] = source_counts.get(src, 0) + 1

    cat_summary = " / ".join(f"{k}: {v}件" for k, v in category_counts.items())
    src_summary = " / ".join(f"{k}: {v}件" for k, v in source_counts.items())

    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "icon": {"type": "emoji", "emoji": "📅"},
            "rich_text": [{"type": "text", "text": {"content":
                f"収集日: {date_str}\n"
                f"記事数: {len(entries)}件\n"
                f"ソース: {src_summary}\n"
                f"カテゴリ: {cat_summary}"
            }}],
        },
    })

    blocks.append({
        "object": "block",
        "type": "divider",
        "divider": {},
    })

    # 各記事の要約カードを並べる
    for i, (article, summary) in enumerate(entries, 1):
        tags_str = ", ".join(article.tags[:5]) if article.tags else ""
        keywords_str = ", ".join(summary.keywords) if summary.keywords else ""

        # 記事見出し（番号 + タイトル）
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content":
                    f"{i}. {article.title[:80]}"
                }}],
            },
        })

        # メタ情報（ソース・カテゴリ・いいね数）
        meta_text = (
            f"📌 {article.source.value.capitalize()} | "
            f"{summary.category} | "
            f"❤️ {article.likes_count}"
        )
        if article.author:
            meta_text += f" | ✍️ {article.author}"
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": meta_text}}],
            },
        })

        # 元記事リンク
        blocks.append({
            "object": "block",
            "type": "bookmark",
            "bookmark": {"url": article.url},
        })

        # キーワード + タグ
        if keywords_str:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content":
                        f"🔑 {keywords_str}"
                    }}],
                },
            })

        # 要約
        blocks.append({
            "object": "block",
            "type": "quote",
            "quote": {
                "rich_text": [{"type": "text", "text": {"content":
                    summary.summary[:2000]
                }}],
            },
        })

        # 注目ポイント
        if summary.highlight:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "⭐ 注目: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": summary.highlight}},
                    ],
                },
            })

        # おすすめ対象
        if summary.target_audience:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "🎯 対象: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": summary.target_audience}},
                    ],
                },
            })

        # 結論
        if summary.conclusion:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": "💡 結論: "}, "annotations": {"bold": True}},
                        {"type": "text", "text": {"content": summary.conclusion}},
                    ],
                },
            })

        # 類似記事（タイトル=リンクテキスト）
        if summary.similar_article_ids and article_info:
            similar_items = []
            for sid in summary.similar_article_ids[:3]:
                info = article_info.get(sid)
                if info:
                    similar_items.append(info)
            if similar_items:
                # タイトルリンクを1行にまとめる
                rich_text_parts = [
                    {"type": "text", "text": {"content": "🔗 類似: "}, "annotations": {"bold": True}},
                ]
                for i, info in enumerate(similar_items):
                    if i > 0:
                        rich_text_parts.append({"type": "text", "text": {"content": " | "}})
                    rich_text_parts.append({
                        "type": "text",
                        "text": {"content": info["title"][:40], "link": {"url": info["url"]}},
                    })
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": rich_text_parts},
                })

        # 区切り線（最後の記事以外）
        if i < len(entries):
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {},
            })

    return blocks


async def create_notion_database(notion_api_key: str, parent_page_id: str) -> str:
    """Notionデータベースを新規作成（初回セットアップ用）

    Args:
        notion_api_key: Notion APIキー
        parent_page_id: 親ページID

    Returns:
        作成されたデータベースID
    """
    from notion_client import Client

    notion = Client(auth=notion_api_key)

    db = notion.databases.create(
        parent={"type": "page_id", "page_id": parent_page_id},
        title=[{"type": "text", "text": {"content": "Tech Collect - ALL"}}],
        properties={
            "タイトル": {"title": {}},
            "要約": {"rich_text": {}},
            "カテゴリ": {
                "select": {
                    "options": [
                        {"name": "AI/ML", "color": "blue"},
                        {"name": "Web開発", "color": "green"},
                        {"name": "インフラ", "color": "orange"},
                        {"name": "データ", "color": "purple"},
                        {"name": "セキュリティ", "color": "red"},
                        {"name": "その他", "color": "gray"},
                    ]
                }
            },
            "ソース": {
                "select": {
                    "options": [
                        {"name": "Qiita", "color": "green"},
                        {"name": "Zenn", "color": "blue"},
                    ]
                }
            },
            "タグ": {"multi_select": {}},
            "URL": {"url": {}},
            "いいね数": {"number": {}},
            "収集日": {"date": {}},
        },
    )

    print(f"[Publisher] Notionデータベース(ALL)を作成しました: {db['id']}")
    return db["id"]
