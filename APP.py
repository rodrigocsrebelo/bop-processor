import os
import re
import tempfile

import streamlit as st

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None

st.set_page_config(page_title="BOP Processor", page_icon="☁️", layout="centered")

# =========================
# CONFIG
# =========================
MAX_ROWS_PER_SHEET = 999_900  # limite do Excel: 1.048.576
MAX_CELL_CHARS = 32_767       # limite do Excel por célula
SOURCE_COL = "Source File"

ALL_COLUMNS = [
    "Level","Search Object (SO)","Description DC","Item Quantity DU","Direct Usage","Description DU",
    "Status DU (MMA/DOC)","Plant status DU (MMA)","Status DU (BOM)","System Desc. DU","Plant DU (BOM)",
    "Plant Name DU","Final Usage","Description FU","Status FU(MMA/DOC)","Plant status FU (MMA)",
    "Status FU (BOM)","System Description FU","Plant FU (BOM)","FU Charact. 1 Value","Subitem Number",
    "Install. Point","Sub Item Quantity","Valid from CMA DU","Valid from date DU","Valid to CMA DU",
    "Valid to date DU","Status Text","WU Status Code",
]
NUM_COLS = len(ALL_COLUMNS)
FU_IDX = ALL_COLUMNS.index("Final Usage")

GROUP_COLUMNS = [
    "Group","Part Number","Level","Description DC","Item Quantity DU","Direct Usage",
    "Final Usage","Description FU","Plant FU (BOM)","FU Charact. 1 Value",
]
GROUP_SRC_IDX = [
    ALL_COLUMNS.index(c) for c in
    ["Level","Description DC","Item Quantity DU","Direct Usage",
     "Final Usage","Description FU","Plant FU (BOM)","FU Charact. 1 Value"]
]

ILLEGAL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
SPLIT_SPACES = re.compile(r"(?<!\S)\s{2,}(?!\S)")

# =========================
# FUNCTIONS
# =========================
def identify_group(final_usage: str) -> str:
    fu = re.sub(r"\D", "", final_usage)
    if fu.startswith(("7612", "7609", "764", "750", "751", "752")):
        return "Group CP1"
    if fu.startswith("0263"):
        return "Group CP2"
    if fu.startswith(("7620", "7607")):
        return "Group CP1-PRO"
    if fu.startswith("8613600"):
        return "Group Bombardier"
    if fu.startswith("1270020"):
        return "Group E-bike"
    return ""


def parse_line(line: str):
    cols = line.split("\t")
    if len(cols) == 1:
        cols = SPLIT_SPACES.split(line)
    if len(cols) < NUM_COLS:
        cols += [""] * (NUM_COLS - len(cols))
    return cols[:NUM_COLS]


class SheetWriter:
    """Escreve linhas numa folha e cria automaticamente novas folhas quando o limite é atingido."""

    def __init__(self, workbook, base_name, headers, limit, header_fmt):
        self.wb, self.base, self.headers = workbook, base_name, headers
        self.limit, self.header_fmt = limit, header_fmt
        self.ws = None
        self.sheet_no = 0
        self.row = 0
        self.total = 0
        self._new_sheet()

    def _new_sheet(self):
        self.sheet_no += 1
        name = self.base if self.sheet_no == 1 else f"{self.base}_{self.sheet_no}"
        self.ws = self.wb.add_worksheet(name)
        for c, h in enumerate(self.headers):
            self.ws.write_string(0, c, h, self.header_fmt)
        self.ws.freeze_panes(1, 0)
        self.row = 1

    def add(self, values):
        if self.row > self.limit:
            self._new_sheet()
        ws, r = self.ws, self.row
        for c, v in enumerate(values):
            ws.write_string(r, c, v[:MAX_CELL_CHARS])
        self.row += 1
        self.total += 1


def process_to_excel(files, out_path, progress):
    total_bytes = sum(f.size for f in files) or 1
    done_bytes = 0

    wb = xlsxwriter.Workbook(
        out_path,
        {
            "constant_memory": True,
            "strings_to_numbers": False,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        },
    )
    header_fmt = wb.add_format({"bold": True, "bg_color": "#E8EEF7", "border": 1})
    complete = SheetWriter(wb, "Complete", [SOURCE_COL] + ALL_COLUMNS, MAX_ROWS_PER_SHEET, header_fmt)
    groups = SheetWriter(wb, "ByGroups", [SOURCE_COL] + GROUP_COLUMNS, MAX_ROWS_PER_SHEET, header_fmt)

    try:
        for f in files:
            f.seek(0)
            for n, raw in enumerate(f, 1):
                done_bytes += len(raw)
                line = raw.decode("utf-8", errors="ignore").lstrip("\ufeff")
                line = ILLEGAL_CHARS.sub("", line).strip()

                if line and not line.startswith("Level"):
                    cols = parse_line(line)
                    complete.add([f.name] + cols)

                    group_name = identify_group(cols[FU_IDX])
                    if group_name:
                        groups.add([f.name, group_name, cols[FU_IDX]] + [cols[i] for i in GROUP_SRC_IDX])

                if n % 2000 == 0:
                    progress.progress(
                        min(done_bytes / total_bytes, 0.99),
                        text=f"A processar **{f.name}** · {complete.total:,} linhas",
                    )

        progress.progress(0.99, text="A finalizar o ficheiro Excel...")
    finally:
        wb.close()

    progress.progress(1.0, text="Concluído")
    return complete.total, groups.total, complete.sheet_no


def cleanup_result():
    path = st.session_state.pop("xlsx_path", None)
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
    st.session_state.pop("stats", None)


# =========================
# UI
# =========================
st.title("☁︎ BOP Processor")
st.caption("Carrega um ou mais ficheiros TXT e gera um relatório Excel (Complete + ByGroups).")

if xlsxwriter is None:
    st.error("Falta o pacote `xlsxwriter`. Instala com: `pip install xlsxwriter`")
    st.stop()

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

with st.container(border=True):
    uploaded_files = st.file_uploader(
        "▣ Ficheiros TXT",
        type=["txt"],
        accept_multiple_files=True,
        key=f"txt_uploader_{st.session_state.uploader_key}",
    )

    if uploaded_files:
        total_mb = sum(f.size for f in uploaded_files) / 1_048_576
        c1, c2 = st.columns(2)
        c1.metric("Ficheiros", len(uploaded_files))
        c2.metric("Tamanho total", f"{total_mb:,.1f} MB")
        with st.expander("Ver ficheiros"):
            for f in uploaded_files:
                st.write(f"• {f.name} — {f.size / 1_048_576:,.1f} MB")

    b1, b2 = st.columns([3, 1])
    process_clicked = b1.button(
        "▶ Processar", type="primary", use_container_width=True, disabled=not uploaded_files
    )
    if b2.button("✕ Limpar", use_container_width=True):
        cleanup_result()
        st.session_state.uploader_key += 1
        st.rerun()

if process_clicked and uploaded_files:
    cleanup_result()
    fd, out_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)

    progress = st.progress(0.0, text="A iniciar...")
    try:
        n_complete, n_groups, n_sheets = process_to_excel(uploaded_files, out_path, progress)
        st.session_state.xlsx_path = out_path
        st.session_state.stats = (n_complete, n_groups, n_sheets)
    except Exception as e:
        progress.empty()
        if os.path.exists(out_path):
            os.remove(out_path)
        st.error(f"Erro durante o processamento: {type(e).__name__}: {e}")

if st.session_state.get("xlsx_path") and os.path.exists(st.session_state["xlsx_path"]):
    n_complete, n_groups, n_sheets = st.session_state["stats"]
    st.success("Processamento concluído!")

    with st.container(border=True):
        m1, m2, m3 = st.columns(3)
        m1.metric("Linhas processadas", f"{n_complete:,}")
        m2.metric("Linhas em grupos", f"{n_groups:,}")
        m3.metric("Folhas 'Complete'", n_sheets)

        with open(st.session_state["xlsx_path"], "rb") as fh:
            st.download_button(
                "↓ Descarregar Excel",
                data=fh,
                file_name="BOP_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                use_container_width=True,
            )
