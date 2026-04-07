"""SQLiteデータベース管理: 記事・要約・投稿結果を永続化"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from src.config import get_settings
from src.models import Article, ArticleSource, ArticleSummary, NotionPublishResult


def get_db_path() -> Path:
    """DB保存先パスを取得し、親ディレクトリを作成"""
    settings = get_settings()
    db_path = settings.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


@contextmanager
def get_connection():
    """SQLiteコネクションのコンテキストマネージャー"""
    conn = sqlite3.connect(str(get_db_path()))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """テーブルを作成（初回起動時に自動実行）"""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                body TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                likes_count INTEGER DEFAULT 0,
                author TEXT DEFAULT '',
                published_at TEXT,
                collected_at TEXT NOT NULL,
                UNIQUE(source, source_id)
            );

            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_source_id TEXT NOT NULL,
                keywords TEXT DEFAULT '[]',
                summary TEXT NOT NULL,
                highlight TEXT DEFAULT '',
                target_audience TEXT DEFAULT '',
                conclusion TEXT DEFAULT '',
                category TEXT NOT NULL,
                relevance_score REAL DEFAULT 0.0,
                similar_article_ids TEXT DEFAULT '[]',
                summarized_at TEXT NOT NULL,
                UNIQUE(article_source_id)
            );

            CREATE TABLE IF NOT EXISTS publish_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_source_id TEXT NOT NULL,
                notion_page_id TEXT NOT NULL,
                notion_url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                success INTEGER DEFAULT 1,
                error_message TEXT DEFAULT '',
                UNIQUE(article_source_id)
            );

            CREATE INDEX IF NOT EXISTS idx_articles_source
                ON articles(source);
            CREATE INDEX IF NOT EXISTS idx_articles_collected
                ON articles(collected_at);
        """)

        # マイグレーション: summariesテーブルに新カラムを追加（既存DB対応）
        _migrate_summaries_table(conn)


def _migrate_summaries_table(conn) -> None:
    """既存のsummariesテーブルに新カラムを追加（ALTER TABLE）"""
    # 既存カラムを取得
    cursor = conn.execute("PRAGMA table_info(summaries)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = {
        "keywords": "TEXT DEFAULT '[]'",
        "highlight": "TEXT DEFAULT ''",
        "target_audience": "TEXT DEFAULT ''",
        "conclusion": "TEXT DEFAULT ''",
    }

    for col_name, col_def in new_columns.items():
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE summaries ADD COLUMN {col_name} {col_def}")
            print(f"[DB] summariesテーブルに {col_name} カラムを追加しました")


def save_article(article: Article) -> bool:
    """記事を保存（重複時はスキップ）。保存成功ならTrue"""
    import json

    with get_connection() as conn:
        try:
            conn.execute(
                """INSERT OR IGNORE INTO articles
                   (source, source_id, title, url, body, tags, likes_count,
                    author, published_at, collected_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    article.source.value,
                    article.source_id,
                    article.title,
                    article.url,
                    article.body,
                    json.dumps(article.tags, ensure_ascii=False),
                    article.likes_count,
                    article.author,
                    article.published_at.isoformat() if article.published_at else None,
                    article.collected_at.isoformat(),
                ),
            )
            return conn.total_changes > 0
        except sqlite3.Error:
            return False


def save_summary(summary: ArticleSummary) -> bool:
    """要約結果を保存"""
    import json

    with get_connection() as conn:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO summaries
                   (article_source_id, keywords, summary, highlight,
                    target_audience, conclusion, category, relevance_score,
                    similar_article_ids, summarized_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    summary.article_source_id,
                    json.dumps(summary.keywords, ensure_ascii=False),
                    summary.summary,
                    summary.highlight,
                    summary.target_audience,
                    summary.conclusion,
                    summary.category,
                    summary.relevance_score,
                    json.dumps(summary.similar_article_ids),
                    summary.summarized_at.isoformat(),
                ),
            )
            return True
        except sqlite3.Error:
            return False


def save_publish_result(result: NotionPublishResult) -> bool:
    """Notion投稿結果を保存"""
    with get_connection() as conn:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO publish_results
                   (article_source_id, notion_page_id, notion_url,
                    published_at, success, error_message)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    result.article_source_id,
                    result.notion_page_id,
                    result.notion_url,
                    result.published_at.isoformat(),
                    1 if result.success else 0,
                    result.error_message,
                ),
            )
            return True
        except sqlite3.Error:
            return False


def is_article_exists(source: str, source_id: str) -> bool:
    """記事が既に収集済みか確認"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM articles WHERE source = ? AND source_id = ?",
            (source, source_id),
        ).fetchone()
        return row is not None


def get_recent_articles(days: int = 7, source: "str | None" = None) -> list[dict]:
    """最近N日間の記事を取得"""
    with get_connection() as conn:
        query = "SELECT * FROM articles WHERE collected_at >= date('now', ?)"
        params: list = [f"-{days} days"]
        if source:
            query += " AND source = ?"
            params.append(source)
        query += " ORDER BY collected_at DESC"
        return [dict(row) for row in conn.execute(query, params).fetchall()]
