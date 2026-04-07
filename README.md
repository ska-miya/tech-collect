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
