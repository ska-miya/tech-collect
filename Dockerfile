FROM python:3.11-slim

WORKDIR /app

# 依存関係のインストール
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# アプリケーションコード
COPY . .

# データディレクトリ
RUN mkdir -p data

# デフォルトコマンド: 全パイプライン実行
CMD ["python", "-m", "src.main", "run"]
