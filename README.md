# tech-collect

技術ブログ自動収集・RAG要約・Notion投稿システム

Qiita / Zenn の技術記事を毎日自動収集し、RAG（Retrieval-Augmented Generation）で要約・分類・類似記事検出を行い、Notion に構造化して蓄積します。

## 特徴

- **マルチソース収集**: Qiita API v2 + Zenn RSS から横断的に記事を収集
- **RAG要約**: ChromaDB（ベクトルDB）+ LLM で記事を要約・分類・類似記事検出
- **LLM切り替え**: Ollama（ローカル無料）/ OpenAI / Claude をワンライン切替
- **Notion二層出力**: ALLデータベース（蓄積・フィルタ）+ Dailyページ（日次レポート）
- **A2Aアーキテクチャ**: 3つのエージェントが協調動作する設計
- **GitHub Actions対応**: 毎日自動実行で技術トレンドを蓄積

## アーキテクチャ

```
┌──────────────────────────────────────────────────────────┐
│                 A2A Protocol (Agent-to-Agent)             │
│                                                          │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Collector  │ →  │  Summarizer  │ →  │  Publisher   │  │
│  │   Agent     │    │    Agent     │    │    Agent     │  │
│  └─────┬──────┘    └──────┬───────┘    └──────┬───────┘  │
│        │                  │                    │          │
│   Qiita API v2       ChromaDB              Notion API    │
│   Zenn RSS           + LLM                 ALL DB        │
│                   (Ollama/OpenAI/          Daily Page     │
│                    Claude)                               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SQLite: 重複排除 + メタデータ永続化               │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 3つのエージェント

| Agent | 役割 | 入力 | 出力 |
|-------|------|------|------|
| **Collector** | 記事収集・重複排除 | キーワード設定 | `CollectResult` |
| **Summarizer** | RAG要約・分類・類似検出 | `CollectResult` | `SummaryResult` |
| **Publisher** | Notion投稿（ALL + Daily） | `SummaryResult` | `PublishResult` |

### Notion出力構造

```
Tech Collect（親ページ）
├── Tech Collect - ALL（データベース）
│   └── 各記事ページ（12プロパティ + 詳細本文）
└── Daily レポート
    ├── 2026-04-07 技術記事レポート（65件）
    ├── 2026-04-08 技術記事レポート（XX件）
    └── ...
```

**ALLデータベースのプロパティ**:

| プロパティ | 型 | 用途 |
|-----------|------|------|
| タイトル | title | 記事タイトル |
| ソース | select | Qiita / Zenn |
| カテゴリ | select | AI/ML, Web開発, インフラ等 |
| キーワード | multi_select | LLM抽出キーワード |
| タグ | multi_select | 元記事タグ |
| URL | url | 元記事リンク |
| 要約 | rich_text | 3〜4行の要約 |
| 注目ポイント | rich_text | 差別化ポイント |
| 類似記事 | rich_text | 類似記事タイトル（リンク付き） |
| いいね数 | number | 人気順ソート |
| 関連度 | number(%) | キーワード関連度 |
| 収集日 | date | 日付フィルタ |
| お気に入り | checkbox | ブックマーク |

## 技術スタック

| カテゴリ | 技術 |
|---------|------|
| 言語 | Python 3.9+ |
| データモデル | Pydantic |
| CLI | Click + Rich |
| エージェント間通信 | A2A Protocol (python-a2a) |
| ベクトルDB | ChromaDB (all-MiniLM-L6-v2 embedding) |
| LLM | Ollama / OpenAI / Claude（切替可能） |
| API連携 | Notion API, Qiita API v2, Zenn RSS |
| 永続化 | SQLite（WALモード） |
| HTTP | httpx (async) |
| コンテナ | Docker / docker-compose |
| CI/CD | GitHub Actions（毎日定時実行） |

## セットアップ

### 1. 依存関係インストール

```bash
pip install -e .
```

### 2. 環境変数設定

```bash
cp .env.example .env
# .env を編集してAPIキーを設定
```

### 3. LLMセットアップ

**Ollama（ローカル・無料）**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama serve  # 別ターミナルで起動
```

**OpenAI / Claude（クラウド）**:
`.env` の `LLM_PROVIDER` を変更するだけ。

### 4. Notion準備

1. [Notion Integrations](https://www.notion.so/my-integrations) でインテグレーション作成
2. APIキーを `.env` に設定
3. Notionでページを作成 → インテグレーションに共有
4. 初回実行時にデータベースが自動作成されます

## 使い方

```bash
# 全パイプライン実行（収集 → 要約 → Notion投稿）
python -m src.main run

# 記事収集のみ
python -m src.main collect-only

# キーワード管理
python -m src.main keyword list
python -m src.main keyword add "Docker"
python -m src.main keyword add "コンテナ" --type keyword
python -m src.main keyword remove "Docker"

# ステータス確認
python -m src.main status
```

## LLM切り替え

`.env` の `LLM_PROVIDER` を変更するだけで切り替え可能:

| Provider | 値 | 特徴 | コスト |
|----------|------|------|--------|
| Ollama | `ollama` | ローカル実行。プライバシー重視 | 無料 |
| OpenAI | `openai` | 高品質。GitHub Actions推奨 | 65件 ≈ $0.02 |
| Claude | `claude` | 日本語に強い | 65件 ≈ $0.03 |

## GitHub Actions（毎日自動実行）

リポジトリの **Settings > Secrets and variables > Actions** に以下を設定:

| Secret名 | 必須 | 説明 |
|-----------|:---:|------|
| `LLM_PROVIDER` | ○ | `openai` 推奨 |
| `OPENAI_API_KEY` | ○ | OpenAI APIキー |
| `NOTION_API_KEY` | ○ | Notion APIキー |
| `NOTION_DATABASE_ID` | ○ | ALLデータベースID |
| `NOTION_DAILY_PAGE_ID` | ○ | Dailyページの親ページID |
| `QIITA_ACCESS_TOKEN` | - | レート制限緩和用 |

毎日 JST 7:00 に自動実行。手動実行も可能（Actions > Run workflow）。

## テスト

```bash
pip install -e ".[dev]"
pytest
```

## ライセンス

MIT

---

# tech-collect (English)

Automated Tech Blog Collector · RAG Summarizer · Notion Publisher

Automatically collects technical articles from Qiita and Zenn every day, summarizes and classifies them using RAG (Retrieval-Augmented Generation), detects similar articles, and stores them in Notion in a structured format.

## Features

- **Multi-source collection**: Cross-platform article collection via Qiita API v2 + Zenn RSS
- **RAG summarization**: Summarizes, classifies, and detects similar articles using ChromaDB (vector DB) + LLM
- **Switchable LLM**: Switch between Ollama (local, free) / OpenAI / Claude with a single line
- **Dual Notion output**: ALL database (archive & filter) + Daily page (daily report)
- **A2A architecture**: Three agents working cooperatively
- **GitHub Actions support**: Automatically runs daily to accumulate tech trends

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                 A2A Protocol (Agent-to-Agent)             │
│                                                          │
│  ┌────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Collector  │ →  │  Summarizer  │ →  │  Publisher   │  │
│  │   Agent     │    │    Agent     │    │    Agent     │  │
│  └─────┬──────┘    └──────┬───────┘    └──────┬───────┘  │
│        │                  │                    │          │
│   Qiita API v2       ChromaDB              Notion API    │
│   Zenn RSS           + LLM                 ALL DB        │
│                   (Ollama/OpenAI/          Daily Page     │
│                    Claude)                               │
│                                                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │  SQLite: deduplication + metadata persistence      │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### Three Agents

| Agent | Role | Input | Output |
|-------|------|-------|--------|
| **Collector** | Article collection & deduplication | Keyword config | `CollectResult` |
| **Summarizer** | RAG summarization, classification & similarity detection | `CollectResult` | `SummaryResult` |
| **Publisher** | Notion posting (ALL + Daily) | `SummaryResult` | `PublishResult` |

### Notion Output Structure

```
Tech Collect (parent page)
├── Tech Collect - ALL (database)
│   └── Article pages (12 properties + detailed body)
└── Daily Reports
    ├── 2026-04-07 Tech Article Report (65 articles)
    ├── 2026-04-08 Tech Article Report (XX articles)
    └── ...
```

**ALL Database Properties**:

| Property | Type | Purpose |
|----------|------|---------|
| Title | title | Article title |
| Source | select | Qiita / Zenn |
| Category | select | AI/ML, Web Dev, Infrastructure, etc. |
| Keywords | multi_select | LLM-extracted keywords |
| Tags | multi_select | Original article tags |
| URL | url | Link to original article |
| Summary | rich_text | 3–4 line summary |
| Highlights | rich_text | Differentiating points |
| Similar Articles | rich_text | Similar article titles (with links) |
| Likes | number | Sort by popularity |
| Relevance | number(%) | Keyword relevance score |
| Collected At | date | Date filter |
| Favorite | checkbox | Bookmark |

## Tech Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.9+ |
| Data model | Pydantic |
| CLI | Click + Rich |
| Agent communication | A2A Protocol (python-a2a) |
| Vector DB | ChromaDB (all-MiniLM-L6-v2 embedding) |
| LLM | Ollama / OpenAI / Claude (switchable) |
| API integration | Notion API, Qiita API v2, Zenn RSS |
| Persistence | SQLite (WAL mode) |
| HTTP | httpx (async) |
| Container | Docker / docker-compose |
| CI/CD | GitHub Actions (scheduled daily) |

## Setup

### 1. Install dependencies

```bash
pip install -e .
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env and set your API keys
```

### 3. Set up LLM

**Ollama (local, free)**:
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull gemma3:4b
ollama serve  # Run in a separate terminal
```

**OpenAI / Claude (cloud)**:
Just change `LLM_PROVIDER` in `.env`.

### 4. Set up Notion

1. Create an integration at [Notion Integrations](https://www.notion.so/my-integrations)
2. Set the API key in `.env`
3. Create a page in Notion and share it with your integration
4. The database will be created automatically on first run

## Usage

```bash
# Run full pipeline (collect → summarize → post to Notion)
python -m src.main run

# Collect articles only
python -m src.main collect-only

# Manage keywords
python -m src.main keyword list
python -m src.main keyword add "Docker"
python -m src.main keyword add "container" --type keyword
python -m src.main keyword remove "Docker"

# Check status
python -m src.main status
```

## Switching LLM

Change `LLM_PROVIDER` in `.env` to switch:

| Provider | Value | Feature | Cost |
|----------|-------|---------|------|
| Ollama | `ollama` | Local execution. Privacy-friendly | Free |
| OpenAI | `openai` | High quality. Recommended for GitHub Actions | 65 articles ≈ $0.02 |
| Claude | `claude` | Strong Japanese language support | 65 articles ≈ $0.03 |

## GitHub Actions (Daily Automation)

Set the following in **Settings > Secrets and variables > Actions**:

| Secret | Required | Description |
|--------|:--------:|-------------|
| `LLM_PROVIDER` | ✓ | `openai` recommended |
| `OPENAI_API_KEY` | ✓ | OpenAI API key |
| `NOTION_API_KEY` | ✓ | Notion API key |
| `NOTION_DATABASE_ID` | ✓ | ALL database ID |
| `NOTION_DAILY_PAGE_ID` | ✓ | Parent page ID for Daily reports |
| `QIITA_ACCESS_TOKEN` | - | Optional: relaxes rate limits |

Runs automatically at 7:00 AM JST every day. Manual execution is also available (Actions > Run workflow).

## Testing

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
