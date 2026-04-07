"""RAG要約Agent: 記事をベクトル化・要約・分類するA2Aエージェント"""

from __future__ import annotations

from pathlib import Path

from src.config import get_settings
from src.db import save_summary
from src.llm import create_llm
from src.models import Article, ArticleSummary, CollectResult, SummaryResult

# 要約プロンプトテンプレート
SUMMARIZE_PROMPT = """あなたは技術記事の要約・分類を行うAIアシスタントです。

以下の技術記事を分析して、JSON形式で回答してください。

## 記事情報
タイトル: {title}
著者: {author}
ソース: {source}
URL: {url}
タグ: {tags}

## 記事本文（先頭2000文字）
{body}

## 回答形式（JSONのみ返してください。各項目は日本語で書いてください）
{{
    "keywords": ["キーワード1", "キーワード2", "キーワード3"],
    "summary": "3〜4行の要約。記事の内容を具体的にまとめてください。",
    "highlight": "この記事の注目ポイント（他の記事と差別化できる点、新しい知見など）を1〜2行で書いてください。",
    "target_audience": "この記事をおすすめできる対象者と、読む価値を1行で書いてください。例: 「RAGを初めて導入するエンジニアに最適。実装手順が具体的で即実践可能」",
    "conclusion": "記事の結論を1行で書いてください。",
    "category": "以下から1つ選択: AI/ML, Web開発, インフラ, データ, セキュリティ, その他",
    "relevance_score": 0.0から1.0の関連度スコア（検索キーワード {search_keywords} との関連度。直接扱っている=0.8〜1.0、関連技術=0.5〜0.7、間接的=0.2〜0.4）
}}
"""


async def summarize_articles(collect_result: CollectResult) -> SummaryResult:
    """収集した記事をRAGで要約・分類

    1. 記事をベクトルDBに格納（将来の類似検索用）
    2. LLMで要約・分類
    3. 類似記事を検出
    4. 結果をDBに保存

    Args:
        collect_result: 収集Agentの出力

    Returns:
        要約結果
    """
    llm = create_llm()
    summaries: list[ArticleSummary] = []

    # ChromaDBにコレクションを準備
    chroma_collection = _get_or_create_collection(llm)

    # 検索キーワードをロード（関連度スコア用）
    from src.agents.collector import load_keywords
    kw_config = load_keywords()
    search_keywords = kw_config.tags + kw_config.keywords

    for article in collect_result.articles:
        try:
            print(f"[Summarizer] 要約中: {article.title[:50]}...")

            # 1. ベクトルDBに格納
            _add_to_vectordb(chroma_collection, article, llm)

            # 2. LLMで要約
            summary = await _summarize_single(llm, article, search_keywords)

            # 3. 類似記事検索
            similar_ids = _find_similar(
                chroma_collection, article, llm
            )
            summary.similar_article_ids = similar_ids

            # 4. DBに保存
            save_summary(summary)
            summaries.append(summary)

        except Exception as e:
            print(f"[Summarizer] 要約失敗: {article.title[:50]} - {e}")
            continue

    print(f"[Summarizer] {len(summaries)}件の記事を要約しました")

    return SummaryResult(
        summaries=summaries,
        articles=collect_result.articles,
    )


def _get_or_create_collection(llm):
    """ChromaDBコレクションを取得または作成"""
    import chromadb

    settings = get_settings()
    persist_dir = Path(settings.chroma_persist_dir)
    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(
        name="tech_articles",
        metadata={"hnsw:space": "cosine"},
    )
    return collection


def _add_to_vectordb(collection, article: Article, llm) -> None:
    """記事をベクトルDBに追加"""
    # 既存チェック
    existing = collection.get(ids=[article.source_id])
    if existing["ids"]:
        return

    text = f"{article.title}\n{article.body[:2000]}"

    collection.add(
        ids=[article.source_id],
        documents=[text],
        metadatas=[{
            "source": article.source.value,
            "title": article.title,
            "url": article.url,
        }],
    )


def _find_similar(collection, article: Article, llm, top_k: int = 3) -> list[str]:
    """ベクトルDBから類似記事を検索"""
    text = f"{article.title}\n{article.body[:500]}"

    try:
        results = collection.query(
            query_texts=[text],
            n_results=top_k + 1,  # 自分自身を含むため+1
        )
        # 自分自身を除外
        similar_ids = [
            id_ for id_ in results["ids"][0]
            if id_ != article.source_id
        ]
        return similar_ids[:top_k]
    except Exception:
        return []


async def _summarize_single(
    llm, article: Article, search_keywords: list[str] = None,
) -> ArticleSummary:
    """1記事をLLMで要約"""
    import json

    kw_str = ", ".join(search_keywords) if search_keywords else "AI, LLM"

    prompt = SUMMARIZE_PROMPT.format(
        title=article.title,
        author=article.author or "不明",
        source=article.source.value,
        url=article.url,
        tags=", ".join(article.tags),
        body=article.body[:2000],
        search_keywords=kw_str,
    )

    response = await llm.generate(prompt)

    # JSONパース（LLMの出力からJSON部分を抽出）
    try:
        # ```json ... ``` で囲まれている場合の対応
        json_str = response
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        data = json.loads(json_str.strip())

        # keywordsがリストでない場合の対応
        keywords = data.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [k.strip() for k in keywords.split(",")]

        return ArticleSummary(
            article_source_id=article.source_id,
            keywords=keywords[:5],
            summary=data.get("summary", "要約の取得に失敗しました"),
            highlight=data.get("highlight", ""),
            target_audience=data.get("target_audience", ""),
            conclusion=data.get("conclusion", ""),
            category=data.get("category", "その他"),
            relevance_score=float(data.get("relevance_score", 0.5)),
        )
    except (json.JSONDecodeError, IndexError, KeyError):
        # パース失敗時はレスポンスをそのまま要約として使用
        return ArticleSummary(
            article_source_id=article.source_id,
            summary=response[:500],
            category="その他",
            relevance_score=0.5,
        )
