import base64
import datetime
import html
import importlib
import hashlib
import json
import os
import tempfile

import fitz   # PyMuPDF
import streamlit as st
import streamlit.components.v1 as components


# ── アクセスログ・カウンター ──
LOG_FILE = os.path.join(tempfile.gettempdir(), "pdf_extractor_log.json")


def load_log() -> dict:
    """JSON からログデータを読み込む（なければ初期値を返す）"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"access_count": 0, "download_count": 0, "history": []}


def save_log(data: dict) -> None:
    """ログデータを JSON に書き込む"""
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def increment_access() -> dict:
    """アクセスカウントを +1 し、履歴に記録する"""
    data = load_log()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["access_count"] += 1
    data["history"].append({"type": "access", "time": now})
    save_log(data)
    return data


def increment_download() -> dict:
    """ダウンロードカウントを +1 し、履歴に記録する"""
    data = load_log()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data["download_count"] += 1
    data["history"].append({"type": "download", "time": now})
    save_log(data)
    return data


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


def get_pdf_cache_key(pdf_path: str) -> str:
    """PDF の内容に基づくキャッシュキーを返す。"""
    sha1 = hashlib.sha1()
    with open(pdf_path, "rb") as pdf_file:
        while chunk := pdf_file.read(1024 * 1024):
            sha1.update(chunk)
    return sha1.hexdigest()[:12]


def build_thumbnail_items(pdf_path: str, max_pages: int, file_name: str) -> list[dict[str, str | int]]:
    """PDF の各ページからサムネイル画像を生成して返す。"""
    safe_name = os.path.splitext(file_name)[0] or "uploaded_pdf"
    cache_key = get_pdf_cache_key(pdf_path)
    thumbnail_dir = os.path.join(
        tempfile.gettempdir(),
        f"{safe_name}_{cache_key}_thumbnails",
    )
    os.makedirs(thumbnail_dir, exist_ok=True)

    thumbnail_mat = fitz.Matrix(0.25, 0.25)
    preview_mat = fitz.Matrix(1.5, 1.5)
    items: list[dict[str, str | int]] = []

    with fitz.open(pdf_path) as doc:
        for index in range(min(max_pages, len(doc))):
            page_number = index + 1
            thumbnail_path = os.path.join(thumbnail_dir, f"thumbnail_page_{page_number}.png")
            temp_thumbnail_path = os.path.join(
                thumbnail_dir,
                f"thumbnail_page_{page_number}.tmp.png",
            )
            preview_path = os.path.join(thumbnail_dir, f"preview_page_{page_number}.png")
            temp_preview_path = os.path.join(
                thumbnail_dir,
                f"preview_page_{page_number}.tmp.png",
            )

            page = doc[index]

            if not os.path.exists(thumbnail_path):
                thumbnail_pix = page.get_pixmap(matrix=thumbnail_mat)
                thumbnail_pix.save(temp_thumbnail_path)
                os.replace(temp_thumbnail_path, thumbnail_path)

            if not os.path.exists(preview_path):
                preview_pix = page.get_pixmap(matrix=preview_mat)
                preview_pix.save(temp_preview_path)
                os.replace(temp_preview_path, preview_path)

            items.append(
                {
                    "label": str(page_number),
                    "value": page_number,
                    "icon_url": thumbnail_path,
                    "preview_url": preview_path,
                }
            )

    return items


@st.cache_data(show_spinner=False)
def image_file_to_data_url(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_clickable_thumbnail_grid(
    items: list[dict[str, str | int]],
    grid_columns: int,
) -> None:
    gallery_items: list[dict[str, str]] = []
    cards: list[str] = []
    for index, item in enumerate(items):
        label = html.escape(f"Page {item['label']}")
        image_url = image_file_to_data_url(str(item["icon_url"]))
        preview_url = image_file_to_data_url(str(item.get("preview_url", item["icon_url"])))
        gallery_items.append({"label": f"Page {item['label']}", "previewUrl": preview_url})
        cards.append(
            f"""
            <button class="thumb-card" type="button" onclick="openModal({index})">
              <img src="{image_url}" alt="{label}" />
              <span>{label}</span>
            </button>
            """
        )

    rows = max(1, (len(items) + grid_columns - 1) // grid_columns)
    frame_height = min(1200, max(420, rows * 220 + 140))
    gallery_items_json = json.dumps(gallery_items, ensure_ascii=False)
    gallery_html = f"""
        <style>
            body {{
                margin: 0;
                font-family: "Segoe UI", sans-serif;
                background: transparent;
            }}
            .thumb-grid {{
                display: grid;
                grid-template-columns: repeat({grid_columns}, minmax(0, 1fr));
                gap: 14px;
                align-items: start;
            }}
            .thumb-card {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                width: 100%;
                border: 1px solid #d0d7de;
                border-radius: 12px;
                background: #ffffff;
                padding: 10px;
                cursor: pointer;
                box-shadow: 0 1px 4px rgba(15, 23, 42, 0.08);
            }}
            .thumb-card:hover {{
                border-color: #2563eb;
                box-shadow: 0 6px 20px rgba(37, 99, 235, 0.18);
            }}
            .thumb-card img {{
                width: 100%;
                height: 180px;
                object-fit: contain;
                background: #f8fafc;
                border-radius: 8px;
            }}
            .thumb-card span {{
                font-size: 14px;
                color: #334155;
            }}
            .modal {{
                display: none;
                position: fixed;
                inset: 0;
                z-index: 999;
                background: rgba(15, 23, 42, 0.76);
                padding: 28px;
            }}
            .modal.open {{
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .modal-content {{
                position: relative;
                max-width: min(92vw, 1100px);
                max-height: 92vh;
                background: #ffffff;
                border-radius: 16px;
                padding: 18px 56px 12px;
                box-shadow: 0 18px 48px rgba(15, 23, 42, 0.35);
            }}
            .modal-content img {{
                display: block;
                max-width: 100%;
                max-height: 78vh;
                object-fit: contain;
                margin: 0 auto;
                background: #f8fafc;
                border-radius: 10px;
            }}
            .modal-caption {{
                margin-top: 10px;
                text-align: center;
                color: #334155;
                font-size: 15px;
            }}
            .close-button {{
                position: absolute;
                top: 8px;
                right: 10px;
                border: none;
                background: transparent;
                font-size: 28px;
                line-height: 1;
                cursor: pointer;
                color: #475569;
            }}
            .nav-button {{
                position: absolute;
                top: 50%;
                transform: translateY(-50%);
                width: 38px;
                height: 38px;
                border: none;
                border-radius: 999px;
                background: rgba(255, 255, 255, 0.92);
                color: #1e293b;
                font-size: 24px;
                line-height: 1;
                cursor: pointer;
                box-shadow: 0 4px 16px rgba(15, 23, 42, 0.18);
            }}
            .nav-button:hover {{
                background: #ffffff;
            }}
            .nav-button.prev {{
                left: 10px;
            }}
            .nav-button.next {{
                right: 10px;
            }}
        </style>
        <div class="thumb-grid">
            {''.join(cards)}
        </div>
        <div id="thumb-modal" class="modal" onclick="closeModal(event)">
            <div class="modal-content">
                <button class="nav-button prev" type="button" onclick="showPrevious(event)">&#8249;</button>
                <button class="close-button" type="button" onclick="closeModal(event)">&times;</button>
                <button class="nav-button next" type="button" onclick="showNext(event)">&#8250;</button>
                <img id="modal-image" src="" alt="Expanded preview" />
                <div id="modal-caption" class="modal-caption"></div>
            </div>
        </div>
        <script>
            const galleryItems = {gallery_items_json};
            const modal = document.getElementById('thumb-modal');
            const modalImage = document.getElementById('modal-image');
            const modalCaption = document.getElementById('modal-caption');
            let currentIndex = 0;

            function showImage(index) {{
                currentIndex = (index + galleryItems.length) % galleryItems.length;
                const item = galleryItems[currentIndex];
                modalImage.src = item.previewUrl;
                modalCaption.textContent = `${{item.label}} (${{currentIndex + 1}} / ${{galleryItems.length}})`;
            }}

            function openModal(index) {{
                showImage(index);
                modal.classList.add('open');
            }}

            function showPrevious(event) {{
                event.stopPropagation();
                showImage(currentIndex - 1);
            }}

            function showNext(event) {{
                event.stopPropagation();
                showImage(currentIndex + 1);
            }}

            function closeModal(event) {{
                if (!event || event.target === modal || event.target.classList.contains('close-button')) {{
                    modal.classList.remove('open');
                }}
            }}

            document.addEventListener('keydown', function(event) {{
                if (!modal.classList.contains('open')) {{
                    return;
                }}
                if (event.key === 'Escape') {{
                    modal.classList.remove('open');
                }}
                if (event.key === 'ArrowLeft') {{
                    showImage(currentIndex - 1);
                }}
                if (event.key === 'ArrowRight') {{
                    showImage(currentIndex + 1);
                }}
            }});
        </script>
        """
    components.html(gallery_html, height=frame_height, scrolling=True)


def get_selected_items(items: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    labels = [str(item["label"]) for item in items]
    items_by_label = {str(item["label"]): item for item in items}
    sortable_multiselect = get_sortable_multiselect()

    if sortable_multiselect is not None:
        selected_labels = sortable_multiselect(
            label="ページを選択して順序を入れ替え",
            options=labels,
            default=labels,
        )
    else:
        st.warning(
            "streamlit_sortable_multiselect が未導入のため、"
            "通常のマルチセレクトで代替します。"
        )
        selected_labels = st.multiselect(
            "ページを選択",
            labels,
            default=labels,
        )

    return [items_by_label[label] for label in selected_labels]


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


st.set_page_config(page_title="PDF Extractor v2", page_icon="pdf", layout="wide")

# ── アクセスログ（コンソールのみ） ──
log_data = increment_access()
print(f"[ACCESS] {log_data['history'][-1]['time']} | "
      f"total_access={log_data['access_count']} "
      f"total_download={log_data['download_count']}")

if "num_pages" not in st.session_state:
    st.session_state["num_pages"] = 0
if "file_name" not in st.session_state:
    st.session_state["file_name"] = ""

st.title("PDFページ抽出ツール v2")
st.caption("3つの入力方法から選べ、好きな順番でページを抽出できます。")

uploaded_file = st.file_uploader("PDFファイルをアップロード", type=["pdf"])

if uploaded_file is not None:
    temp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.read())
    try:
        with fitz.open(temp_path) as doc:
            n = len(doc)
        st.session_state["num_pages"] = n
        st.session_state["file_name"] = os.path.splitext(uploaded_file.name)[0]
        st.session_state["temp_path"] = temp_path
        st.session_state["thumbnail_items"] = build_thumbnail_items(
            temp_path,
            n,
            uploaded_file.name,
        )
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
        selector_col, preview_col = st.columns([0.9, 2.1], gap="large")

        with selector_col:
            st.subheader("ページ選択")
            st.info(
                "1. ページを選択\n"
                "2. ドラッグで順序を自在に変更\n"
                "3. 右側のプレビューへ即時反映されます"
            )

            thumbnail_items = st.session_state.get("thumbnail_items", [])
            selected_items = get_selected_items(thumbnail_items)

        final_pages = [int(item["value"]) for item in selected_items] if selected_items else []

        with preview_col:
            st.subheader("選択結果のグリッド表示")
            st.caption(f"{len(final_pages)} ページ選択中")

            if selected_items:
                grid_columns = 4 if len(selected_items) >= 8 else 3
                st.caption("サムネイルをクリックすると拡大表示します。")
                render_clickable_thumbnail_grid(selected_items, grid_columns)
            else:
                st.info("左側でページを選択してください。")

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
            output_pdf = os.path.join(tempfile.gettempdir(), extracted_name)

            try:
                extract_pages(st.session_state["temp_path"], output_pdf, deduped)
                with open(output_pdf, "rb") as dl:
                    st.session_state["download_pdf_data"] = dl.read()
                st.session_state["download_pdf_name"] = extracted_name
                # ── ダウンロードカウント ──
                dl_data = increment_download()
                print(f"[DOWNLOAD] {dl_data['history'][-1]['time']} | "
                      f"total_download={dl_data['download_count']} "
                      f"total_access={dl_data['access_count']}")
                st.success(f"PDFを作成しました ({len(deduped)}ページ)")
            except Exception as exc:
                st.error(f"エラーが発生しました:{exc}")

    if "download_pdf_data" in st.session_state:
        if st.download_button(
            label="PDFをダウンロード",
            data=st.session_state["download_pdf_data"],
            file_name=st.session_state["download_pdf_name"],
            mime="application/pdf",
            use_container_width=True,
            key="download_btn",
        ):
            dl_data = increment_download()
            print(f"[DOWNLOAD] {dl_data['history'][-1]['time']} | "
                  f"total_download={dl_data['download_count']} "
                  f"total_access={dl_data['access_count']}")

    # ── Sidebar │───────────────────────────
    with st.sidebar:
        st.info(
            "PDFページ抽出ツール v2\n\n"
            "1. 連続範囲\n"
            "2. ドラッグで順序変更\n"
            "3. テキスト手入力"
        )