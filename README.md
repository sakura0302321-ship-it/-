類似問題作成ツール

概要
アップロードされた試験問題のPDFや画像をAI（Gemini 1.5 Pro/Flash）が解析し、その論理構造や図表配置を維持したまま、トピックを刷新した高品質な類似問題を作成するツールです。

特徴
マルチモーダル解析: 画像だけでなく、Popplerを使用したPDFの高解像度変換・解析に対応。
高精度なプロンプト設計: 試験作成プロフェッショナルの思考を模倣するシステムプロンプト。
マルチベンダー対応への布石: Google Gemini APIを基盤とし、柔軟なモデル選択ロジックを実装。
堅牢なPDF出力: 日本語フォントの埋め込みや特殊文字のサニタイズ処理を実装。

使用技術
Language: Python 3.x
Frontend: Streamlit
AI: Google Generative AI (Gemini API)
Library: fpdf2, pdf2image (Poppler)

セットアップ
pip install -r requirements.txt
poppler バイナリをプロジェクトルートに配置
streamlit run main.py で起動

依存ソフトウェア (Poppler)
PDF解析機能を利用するには、別途Popplerが必要です。
Releaseページ等からバイナリをダウンロードし、解凍したフォルダを poppler という名前でプロジェクトルートに配置してください。
（poppler/Library/bin/pdftoppm.exe が存在する状態にしてください）
