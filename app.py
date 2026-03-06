import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
import os
import sys
from pathlib import Path
import pdf2image
from PIL import Image
import warnings
import traceback

#設定エリア
# APIキー
GEMINI_API_KEY = ""

# フォントファイル名
FONT_FILENAME = "ipaexg.ttf" 


# ページ設定
st.set_page_config(page_title="Ultimate Exam Builder", layout="wide")

# API設定
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"APIキーの設定に失敗しました: {e}")
    st.stop()

def get_robust_poppler_path():
   
    #Popplerのパスを徹底的に探す関数。
    
    base_dir = Path(__file__).parent if "__file__" in locals() else Path.cwd()
    
    # 探索パターンの定義
    search_patterns = [
        base_dir / "poppler" / "Library" / "bin",
        base_dir / "poppler" / "bin",
        base_dir / "bin",
        # バージョン名がついている場合も想定
        base_dir / "poppler-24.02.0" / "Library" / "bin",
        base_dir / "Release-24.02.0-0" / "poppler-24.02.0" / "Library" / "bin",
    ]
    
    # 見つかったら即リターン
    for path in search_patterns:
        if path.exists() and (path / "pdftoppm.exe").exists():
            return str(path)
            
    # ここまで来て見つからない場合、ユーザーに警告を出すがクラッシュはさせない
    return None

def get_best_available_model():
    
    try:
        all_models = genai.list_models()
        # 'gemini対応
        candidates = [m.name for m in all_models if 'generateContent' in m.supported_generation_methods and 'gemini' in m.name]
        
        if not candidates:
            # 最終手段
            return "models/gemini-1.5-flash"

        # 1.5-pro系を最優先
        pro_models = [m for m in candidates if '1.5-pro' in m]
        if pro_models:
            # 最新のものがあればそれを使う
            latest = [m for m in pro_models if 'latest' in m]
            return latest[0] if latest else pro_models[0]
            
        # ProがなければFlash
        flash_models = [m for m in candidates if '1.5-flash' in m]
        if flash_models:
            return flash_models[0]
            
        return candidates[0]
        
    except Exception as e:
        # ネット接続エラー
        st.warning(f"モデルリスト取得時に警告:  -> デフォルト設定を使用します")
        return "models/gemini-1.5-flash"

def sanitize_text_strict(text):
   
    #文字対策
    
    if not text: return ""
    
    # 置換マップ
    replacements = {
        "\u2212": "-",   
        "\u2013": "-",   
        "\u2014": "-",   
        "−": "-",        
        "〜": "~",      
        "〰": "~",
        "“": "\"", "”": "\"",  
        "‘": "'", "’": "'",
        "…": "...",
        "▲": "*", "△": "*", "▼": "*", "▽": "*", "■": "-", "□": "-",
        "※": "*",
        "≤": "<=", "≥": ">=", "≠": "!=",
    }
    
    # 1. 特定の記号を置換
    for k, v in replacements.items():
        text = text.replace(k, v)
    
    # 2. Shift-JIS (cp932) で表現できない文字が含まれていないか最終チェック
    safe_text = ""
    for char in text:
        try:
            char.encode('cp932')
            safe_text += char
        except UnicodeEncodeError:
            # エンコードできない文字は無視するか、近い文字があれば置換
            safe_text += "?" 
            
    return safe_text


#  PDFクラス定義
class RobustExamPDF(FPDF):
    def __init__(self, font_path):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=15)
        self.font_path = font_path
        self.font_loaded = False
        
        # フォント読み込み試行
        if os.path.exists(font_path):
            try:
                self.add_font("Japanese", "", font_path, uni=True)
                self.set_font("Japanese", size=11)
                self.font_loaded = True
            except Exception as e:
                st.error(f"フォント読み込みエラー: {e}")
        
    def header(self):
        if self.font_loaded:
            self.set_font("Japanese", size=9)
            self.cell(0, 10, "AI Generated Exam Result", ln=True, align="R")


#  メイン

st.title("類似問題作成ツール")

# 1. 環境チェック
POPPLER_PATH = get_robust_poppler_path()
MODEL_NAME = get_best_available_model()
FONT_EXISTS = os.path.exists(FONT_FILENAME)

# ステータス表示エリア
status_col1, status_col2, status_col3 = st.columns(3)
with status_col1:
    if POPPLER_PATH:
        st.success("Poppler: 準備完了")
    else:
        st.error("Poppler: 未検出")
with status_col2:
    st.info(f"AIモデル: {MODEL_NAME}")
with status_col3:
    if FONT_EXISTS:
        st.success("フォント: 準備完了")
    else:
        st.error(f"フォント: 未検出 ({FONT_FILENAME})")

# Popplerがない場合、致命的なのでここでストップするか、画像モードのみ案内する
if not POPPLER_PATH:
    st.warning(" Popplerが見つからないため、PDF読み込み機能は制限されます。`poppler`フォルダを配置してください。")

st.divider()

col_input, col_settings = st.columns([1, 1], gap="medium")

#  入力エリア
with col_input:
    st.subheader("資料のアップロード")
    input_mode = st.radio("入力モード", ["PDF (Poppler解析)", "画像 (スクリーンショット)"])
    
    uploaded_file = st.file_uploader("ファイルをアップロード", type=["pdf", "png", "jpg", "jpeg"])
    
    # 解析用データ保持リスト
    vision_inputs = []
    
    if uploaded_file:
        # 画像モード
        if input_mode == "画像 (スクリーンショット)" or uploaded_file.type in ["image/png", "image/jpeg", "image/jpg"]:
            try:
                img = Image.open(uploaded_file)
                st.image(img, caption="解析対象画像", use_container_width=True)
                vision_inputs = ["以下の画像を詳細に分析してください。", img]
            except Exception as e:
                st.error(f"画像読み込みエラー: {e}")

        # PDFモード
        elif input_mode == "PDF (Poppler解析)" and uploaded_file.type == "application/pdf":
            if not POPPLER_PATH:
                st.error("PopplerがないためPDFを解析できません。画像をアップロードしてください。")
            else:
                with st.spinner("Popplerを使用し、PDFを高解像度画像に変換中..."):
                    try:
                        # pdf2imageで画像化
                        images = pdf2image.convert_from_bytes(
                            uploaded_file.read(),
                            poppler_path=POPPLER_PATH
                        )
                        st.image(images[0], caption="1ページ目プレビュー", use_container_width=True)
                        
                        # AIに渡すデータを作成
                        vision_inputs = ["以下の試験問題画像（図表含む）を分析してください。", images[0]]
                        if len(images) > 1: vision_inputs.append(images[1])
                        if len(images) > 2: vision_inputs.append(images[2])
                        
                    except Exception as e:
                        st.error(f"PDF変換中にエラーが発生しました。\n詳細: {e}")
                        st.info("※PDFが暗号化されているか、破損している可能性があります。")

# 設定エリア
with col_settings:
    st.subheader("② 生成パラメータ")
    target_section = st.selectbox("模倣する問題形式", [
        "全体を解析して類似問題を作成",
        "第1問・第2問 (チラシ・Web・要約)",
        "第3問・第4問 (物語・ブログ・記事)",
        "第5問・第6問 (メール・図表・長文統合)"
    ])
    
    difficulty = st.select_slider("難易度設定", ["易しめ", "本番レベル", "難しめ"], value="本番レベル")
    
    st.markdown("---")
    
    # 生成ボタン
    generate_btn = st.button("プロ品質で問題を生成する", type="primary")

    if generate_btn:
        if not vision_inputs:
            st.error(" 解析するファイルがありません。左側でアップロードしてください。")
        else:
            # モデル初期化
            model = genai.GenerativeModel(MODEL_NAME)
            
            with st.spinner("AIが論理構造・図表・レイアウトを解析し、問題を設計中..."):
                try:
                    # プロンプト設計
                    prompt = f"""
                    あなたは最高レベルの試験作成プロフェッショナルです。
                    入力された画像の「{target_section}」の構造をピクセル単位で理解するレベルで模倣し、
                    トピックを刷新した【最高品質の類似問題】を作成してください。

                    【厳守事項: 図表の扱い】
                    画像内のグラフや図表は重要情報です。新しい問題でも必ず配置してください。
                    AIは画像生成ができないため、以下のような**「画像生成AIへの指示プロンプト」**を出力してください。
                    
                    [[Image Prompt]]: "A bar chart showing..."
                    
                    【厳守事項: 出力構成】
                    1. タイトル
                    2. 本文・資料 (English)
                    3. 設問 (English)
                    4. 解答・詳細な解説 (Japanese)
                    
                    難易度: {difficulty}
                    """
                    
                    # 生成実行
                    response = model.generate_content(vision_inputs + [prompt])
                    
                    # 結果をsession_stateに保存
                    st.session_state.exam_result = response.text
                    st.success("生成完了。")
                    
                except Exception as e:
                    st.error(f"予期せぬエラーが発生しました: {e}")
                    st.write(traceback.format_exc())

#結果出力エリア
if "exam_result" in st.session_state:
    st.markdown("---")
    st.subheader("生成結果")
    
    result_text = st.session_state.exam_result
    st.markdown(result_text)
    
    st.markdown("---")
    st.subheader("保存オプション")
    
    dl_col1, dl_col2 = st.columns(2)
    
    # オプション1: テキストファイル保存
    with dl_col1:
        st.download_button(
            label="テキスト形式で保存",
            data=result_text,
            file_name="exam_result.txt",
            mime="text/plain",
            help="PDF生成がうまくいかない場合はこちらを使ってください"
        )
        
    # オプション2: PDF保存
    with dl_col2:
        if st.button("PDF形式で保存"):
            if not FONT_EXISTS:
                st.error("フォントファイルがないためPDFを作成できません。")
            else:
                try:
                    pdf = RobustExamPDF(FONT_FILENAME)
                    pdf.add_page()
                    
                    # 文字浄化
                    safe_content = sanitize_text_strict(result_text)
                    
                    pdf.multi_cell(0, 7, safe_content)
                    
                    # バイナリデータとして出力
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    
                    st.download_button(
                        label="クリックしてPDFをダウンロード",
                        data=pdf_bytes,
                        file_name="exam_result.pdf",
                        mime="application/pdf"
                    )
                except Exception as e:
                    st.error(f"PDF作成中にエラーが発生しました: {e}")

                    st.warning("テキスト形式での保存をお試しください。")

