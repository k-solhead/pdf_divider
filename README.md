# PDFページ抽出ツール

Streamlit アプリ — PDF ファイルの任意のページを好きな順番で抽出・再構成してダウンロードできます。

## 機能

- **3つの入力方法** から選択可能
  1. **範囲指定** — 連続ページを開始〜終了で指定
  2. **ソート可能マルチセレクト** — ドラッグでページ順序を自由に変更
  3. **テキスト手入力** — カンマ・改行区切り、範囲指定（`5-8`）も対応
- **重複除去** — 同じページ番号が複数含まれていても自動で1つに
- **ダウンロード** — 抽出後の PDF をブラウザから直接ダウンロード

## クイックスタート

```bash
pip install -r requirements.txt
streamlit run main.py
```

ブラウザで http://localhost:8501 にアクセスして PDF をアップロードするだけです。

## 対応環境

- Python 3.13+ (slim Docker イメージでも動作)
- Docker 利用時は `docker build -t pdf-divider . && docker run -p 8500:8500 pdf-divider`

## 依存関係

- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) — PDF ページ操作
- [Streamlit](https://streamlit.io) — UI フレームワーク
- [streamlit-sortable-multiselect](https://github.com/annahowell/streamlit-sortable-multiselect) — ドラッグ順序変更 (オプション)
