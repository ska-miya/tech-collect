"""メインエントリポイント: CLI + A2Aオーケストレーター"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from src.config import get_settings
from src.db import init_db

console = Console()


@click.group()
def cli():
    """tech-collect: 技術ブログ自動収集・RAG要約・Notion投稿システム"""
    pass


@cli.command()
def run():
    """全パイプラインを実行: 収集 → 要約 → Notion投稿"""
    asyncio.run(_run_pipeline())


async def _run_pipeline():
    """メインパイプライン"""
    from src.agents.collector import collect_articles
    from src.agents.publisher import publish_to_notion
    from src.agents.summarizer import summarize_articles

    settings = get_settings()
    console.print(f"\n[bold blue]🚀 tech-collect 開始[/bold blue]")
    console.print(f"  LLM: {settings.llm_provider.value}")
    console.print(f"  DB: {settings.db_path}\n")

    # DB初期化
    init_db()

    # STEP 1: 収集
    console.print("[bold green]📥 STEP 1: 記事収集[/bold green]")
    collect_result = await collect_articles()

    if not collect_result.articles:
        console.print("[yellow]新規記事はありませんでした[/yellow]")
        return

    # 統計表示
    table = Table(title="収集結果")
    table.add_column("ソース", style="cyan")
    table.add_column("件数", style="green", justify="right")
    for source, count in collect_result.source_stats.items():
        table.add_row(source, str(count))
    console.print(table)

    # STEP 2: 要約
    console.print("\n[bold green]🧠 STEP 2: RAG要約・分類[/bold green]")
    summary_result = await summarize_articles(collect_result)

    # STEP 3: Notion投稿
    console.print("\n[bold green]📤 STEP 3: Notion投稿[/bold green]")
    publish_result = await publish_to_notion(summary_result)

    # 最終結果
    console.print(f"\n[bold blue]✅ 完了[/bold blue]")
    console.print(f"  収集: {sum(collect_result.source_stats.values())}件")
    console.print(f"  要約: {len(summary_result.summaries)}件")
    console.print(
        f"  投稿: {publish_result.success_count}件成功"
        f" / {publish_result.error_count}件失敗"
    )


@cli.command()
def collect_only():
    """記事収集のみ実行（要約・投稿はスキップ）"""
    asyncio.run(_collect_only())


async def _collect_only():
    from src.agents.collector import collect_articles

    init_db()
    console.print("[bold green]📥 記事収集のみ実行[/bold green]")
    result = await collect_articles()
    console.print(f"  収集: {sum(result.source_stats.values())}件")


@cli.group()
def keyword():
    """キーワード管理"""
    pass


@keyword.command("list")
def keyword_list():
    """登録キーワード一覧"""
    from src.agents.collector import load_keywords

    kw = load_keywords()
    console.print("\n[bold]📋 登録キーワード[/bold]")

    table = Table()
    table.add_column("種別", style="cyan")
    table.add_column("キーワード", style="green")
    for tag in kw.tags:
        table.add_row("タグ", tag)
    for kw_text in kw.keywords:
        table.add_row("キーワード", kw_text)
    console.print(table)


@keyword.command("add")
@click.argument("word")
@click.option("--type", "kw_type", default="tag", help="tag or keyword")
def keyword_add(word: str, kw_type: str):
    """キーワードを追加"""
    from src.agents.collector import load_keywords, save_keywords

    kw = load_keywords()
    if kw_type == "tag":
        if word not in kw.tags:
            kw.tags.append(word)
            save_keywords(kw)
            console.print(f"[green]✅ タグ '{word}' を追加しました[/green]")
        else:
            console.print(f"[yellow]'{word}' は既に登録されています[/yellow]")
    else:
        if word not in kw.keywords:
            kw.keywords.append(word)
            save_keywords(kw)
            console.print(f"[green]✅ キーワード '{word}' を追加しました[/green]")
        else:
            console.print(f"[yellow]'{word}' は既に登録されています[/yellow]")


@keyword.command("remove")
@click.argument("word")
def keyword_remove(word: str):
    """キーワードを削除"""
    from src.agents.collector import load_keywords, save_keywords

    kw = load_keywords()
    removed = False
    if word in kw.tags:
        kw.tags.remove(word)
        removed = True
    if word in kw.keywords:
        kw.keywords.remove(word)
        removed = True

    if removed:
        save_keywords(kw)
        console.print(f"[green]✅ '{word}' を削除しました[/green]")
    else:
        console.print(f"[yellow]'{word}' は登録されていません[/yellow]")


@cli.command()
def status():
    """システムステータス表示"""
    from src.db import get_recent_articles

    settings = get_settings()
    init_db()

    console.print("\n[bold]📊 tech-collect ステータス[/bold]")
    console.print(f"  LLM: {settings.llm_provider.value}")
    console.print(f"  Notion: {'✅ 設定済み' if settings.notion_api_key else '❌ 未設定'}")
    console.print(f"  Qiita: {'✅ トークンあり' if settings.qiita_access_token else '⚠️ トークンなし（レート制限あり）'}")

    # 最近の記事数
    recent = get_recent_articles(days=7)
    console.print(f"\n  直近7日の収集記事: {len(recent)}件")


if __name__ == "__main__":
    cli()
