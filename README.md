# みんなのまちAI風 🏙️

NTT西日本「みんなのまちAI®」の中核機能を**公表データのみ**で再現するオープンソースツール。

## 機能

| 画面 | 概要 |
|------|------|
| **Explore** | 地図上に人口・産業・交通・防災等のレイヤを重ね合わせ可視化 |
| **Scenario** | 施設・道路を地図上に描き、到達圏・人流指数の変化をシミュレーション |
| **Budget Draft** | プロンプトから根拠付き予算案（A/B/C案）を自動生成 |

## セットアップ

```bash
# 1. リポジトリをクローン
git clone https://github.com/<your-org>/machi-ai-style.git
cd machi-ai-style

# 2. 仮想環境を作成
python -m venv venv
venv\Scripts\activate  # Windows

# 3. 依存パッケージをインストール
pip install -r requirements.txt

# 4. 環境変数を設定
cp .env.example .env
# .env に GEMINI_API_KEY を設定
```

## 起動

```bash
# バックエンド（FastAPI）
uvicorn services.main:app --port 8000 --reload

# フロントエンド（Streamlit）— 別ターミナル
streamlit run app/app.py
```

ブラウザで <http://localhost:8501> にアクセス。

## 技術スタック

- **Frontend**: Streamlit + Folium + Plotly
- **Backend**: FastAPI
- **Data**: DuckDB + Parquet
- **Geo**: GeoPandas + OSMnx
- **LLM**: Google Gemini API
- **RAG**: LangChain + FAISS

## ライセンス

MIT License
