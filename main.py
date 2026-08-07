import importlib
import os

import fitz   # PyMuPDF
import streamlit as st


def get_sortable_multiselect():
    try:
        module = importlib.import_module("streamlit_sortable_multiselect")
    except ModuleNotFoundError:
        return None
    return getattr(module, "sortable_multiselect", None)


def extract_pages(input_path: str, output_path: str, pages: list[int]) -> None:
    """指定ページを抽出して保存 (1-indexed)"""
    doc = fitz.open(input_path)
    doc.select([p - 1 for p in pages])
    doc.save(output_path)
    doc.close()


def parse_text(text, max_pages):
    """テキスト入力をページリストに変換"""
    output = []
    errors = []
    for token in text.replace(",", "\n").strip().split("\n"):
        token = token.strip()
        if not token:
            continue
        if "-" in token and not token.startswith("-") and token.count("-") == 1:
            parts = token.split("-")
            try:
                s, e = int(parts[0]), int(parts[1])
                output.extend(range(s, min(e + 1, max_pages + 1)))
            except ValueError:
                errors.append(f"範囲指定が不正です: {token}")
        else:
            try:
                p = int(token)
                if not (1 <= p <= max_pages):
                    errors.append(f"ページ{p}は範囲外(1-{max_pages})")
                output.append(p)
            except ValueError:
                errors.append(f"無効な値: {token}")
    return output, errors


st.set_page_config(page_title="PDF Extractor v2", page_icon="pdf")

if "num_pages" not in st.session_state:
    st.session_state["num_pages"] = 0
if "file_name" not in st.session_state:
    st.session_state["file_name"] = ""

st.title("PDFページ抽出ツール")
st.caption("3つの入力方法から選べ、好きな順番でページを抽出できます。")

uploaded_file = st.file_uploader("PDFファイルをアップロード", type=["pdf"])

if uploaded_file is not None:
    temp_path = os.path.join("/tmp", uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())
    try:
        with fitz.open(temp_path) as doc:
            n = len(doc)
        st.session_state["num_pages"] = n
        st.session_state["file_name"] = os.path.splitext(uploaded_file.name)[0]
        st.session_state["temp_path"] = temp_path
        st.success(f"{n}ページ読み込み完了")
    except Exception as exc:
        st.error(f"PDFの読み込みに失敗しました: {exc}")

if st.session_state["num_pages"] > 0:
    page_types = [
        "① 範囲指定（連続ページ）",
        "② ソート可能マルチセレクト（ドラッグで順序変更）",
        "③ テキスト手入力（任意の順序）",
    ]

    selected_type = st.radio(
        "入力方法を選択してください:", page_types, key="input_method"
    )

    n_pages = st.session_state["num_pages"]
    final_pages: list[int] = []

    # ── Method 1: range │──────────────────────
    if selected_type == page_types[0]:
        col_s, col_e = st.columns(2)
        if "last_start" not in st.session_state:
            st.session_state["last_start"] = 1
        if "last_end" not in st.session_state:
            st.session_state["last_end"] = n_pages

        with col_s:
            start_page = st.number_input(
                "開始ページ",
                min_value=1,
                max_value=n_pages,
                value=st.session_state["last_start"],
                key="start_page",
            )
        with col_e:
            end_page = st.number_input(
                "終了ページ",
                min_value=start_page,
                max_value=n_pages,
                value=st.session_state["last_end"],
                key="end_page",
            )

        final_pages = list(range(start_page, end_page + 1))

    # ── Method 2: sortable multiselect │──────
    elif selected_type == page_types[1]:
        st.info(
            "1. ページを選択\n"
            "2. ドラッグで順序を自在に変更\n"
            "3. 選択順に抽出されます"
        )

        all_pages = list(range(1, n_pages + 1))
        page_options = [str(page) for page in all_pages]
        default_pages = st.session_state.get("final_page_list_from_sortable", all_pages)
        default_val = [str(page) for page in default_pages]

        sortable_multiselect = get_sortable_multiselect()
        if sortable_multiselect is None:
            st.warning(
                "streamlit_sortable_multiselect が未導入のため、"
                "通常のマルチセレクトで代替します。"
            )
            sortable_result = st.multiselect(
                "ページを選択",
                all_pages,
                default=default_val,
            )
        else:
            sortable_result = sortable_multiselect(
                label="ページを選択（ドラッグで順序変更）",
                options=page_options,
                default=default_val,
            )

        final_pages = [int(page) for page in sortable_result] if sortable_result else []

    # ── Method 3: text input │───────────────
    elif selected_type == page_types[2]:
        st.info(
            "ページ番号を任意の順で入力\n"
            "カンマ・スペース・改行区切り\n"
            "範囲指定も可（例: 5-8 → [5,6,7,8]）"
        )

        textarea = st.text_area(
            "ページ番号を入力",
            placeholder="例: 5,2,8,1 → 5番目→2番目→8番目→1番目の順で抽出",
            height=200,
            key="text_input_pages",
        )

        parsed, err_list = parse_text(textarea, n_pages)
        final_pages = parsed

    # ── Preview (methods 2 & 3 only) │───────
    if selected_type in (page_types[1], page_types[2]) and final_pages:
        with st.expander("スクロール順プレビュー"):
            for i, pg in enumerate(final_pages):
                _, col2 = st.columns([0.5, 3.5])
                col2.write(f"[{i + 1}] Page {pg}")

    # ── Execute button │────────────────────
    do_extract = False
    bad: list[int] = []
    deduped: list[int] = []

    with st.form("ex_form", clear_on_submit=True):
        pages_to_extract = final_pages

        if not pages_to_extract:
            st.warning("ページが選択されていません。")
        else:
            bad = [p for p in pages_to_extract if p < 1 or p > n_pages]
            if bad:
                st.error(f"有効なページ番号がありません:{bad}")

            seen = set()
            deduped: list[int] = []
            for p in pages_to_extract:
                if p not in seen:
                    seen.add(p)
                    deduped.append(p)

        do_extract = st.form_submit_button(
            "PDFを作成・ダウンロード", type="primary"
        )

        if do_extract and pages_to_extract and not bad:
            extracted_name = f"{st.session_state['file_name']}_processed.pdf"
            output_pdf = os.path.join("/tmp", extracted_name)

            try:
                extract_pages(st.session_state["temp_path"], output_pdf, deduped)
                with open(output_pdf, "rb") as dl:
                    st.session_state["download_pdf_data"] = dl.read()
                st.session_state["download_pdf_name"] = extracted_name
                st.success(f"PDFを作成しました ({len(deduped)}ページ)")
            except Exception as exc:
                st.error(f"エラーが発生しました:{exc}")

    if "download_pdf_data" in st.session_state:
        st.download_button(
            label="PDFをダウンロード",
            data=st.session_state["download_pdf_data"],
            file_name=st.session_state["download_pdf_name"],
            mime="application/pdf",
            use_container_width=True,
        )

    # ── Sidebar │───────────────────────────
    with st.sidebar:
        st.info(
            "PDFページ抽出ツール \n\n"
            "1. 連続範囲\n"
            "2. ドラッグで順序変更\n"
            "3. テキスト手入力"
        )
