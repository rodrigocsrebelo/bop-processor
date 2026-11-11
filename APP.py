import streamlit as st
import pandas as pd
import re
from io import BytesIO, TextIOWrapper

st.set_page_config(page_title="BOP Processor", layout="centered")
st.title("☁︎ BOP Processor")

# =========================
# CONFIG
# =========================
MAX_ROWS_PER_SHEET = 999900  # limite do Excel ~1.048.576

ALL_COLUMNS = [
    "Level","Search Object (SO)","Description DC","Item Quantity DU","Direct Usage","Description DU",
    "Status DU (MMA/DOC)","Plant status DU (MMA)","Status DU (BOM)","System Desc. DU","Plant DU (BOM)",
    "Plant Name DU","Final Usage","Description FU","Status FU(MMA/DOC)","Plant status FU (MMA)",
    "Status FU (BOM)","System Description FU","Plant FU (BOM)","FU Charact. 1 Value","Subitem Number",
    "Install. Point","Sub Item Quantity","Valid from CMA DU","Valid from date DU","Valid to CMA DU",
    "Valid to date DU","Status Text","WU Status Code"
]
NUM_COLS = len(ALL_COLUMNS)
FU_IDX = ALL_COLUMNS.index("Final Usage")

GROUP_COLUMNS = [
    "Group","Part Number","Level","Description DC","Item Quantity DU","Direct Usage",
    "Final Usage","Description FU","Plant FU (BOM)","FU Charact. 1 Value"
]
GROUP_SRC_IDX = [ALL_COLUMNS.index(c) for c in
                 ["Level","Description DC","Item Quantity DU","Direct Usage",
                  "Final Usage","Description FU","Plant FU (BOM)","FU Charact. 1 Value"]]

# Colunas de origem para cada ficheiro (útil com vários uploads)
SOURCE_COL = "Source File"

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
    line = ILLEGAL_CHARS.sub("", line.strip())
    cols = line.split("\t")
    if len(cols) == 1:
        cols = SPLIT_SPACES.split(line)
    if len(cols) < NUM_COLS:
        cols += [""] * (NUM_COLS - len(cols))
    return cols[:NUM_COLS]

def process_files(files):
    rows_complete, rows_group = [], []
    total_bytes = sum(f.size for f in files) or 1
    done_bytes = 0
    progress = st.progress(0.0, text="A processar...")

    for f in files:
        f.seek(0)
        reader = TextIOWrapper(f, encoding="utf-8", errors="ignore", newline=None)
        for n, line in enumerate(reader, 1):
            done_bytes += len(line.encode("utf-8", errors="ignore"))
            if not line.strip() or line.startswith("Level"):
                continue

            cols = parse_line(line)
            rows_complete.append([f.name] + cols)

            group_name = identify_group(cols[FU_IDX])
            if group_name:
                rows_group.append(
                    [f.name, group_name, cols[FU_IDX]] + [cols[i] for i in GROUP_SRC_IDX]
                )

            if n % 5000 == 0:
                progress.progress(min(done_bytes / total_bytes, 1.0),
                                  text=f"A processar {f.name}...")
        reader.detach()  # não fechar o ficheiro do uploader

    progress.progress(1.0, text="Concluído")

    df_complete = pd.DataFrame(rows_complete, columns=[SOURCE_COL] + ALL_COLUMNS, dtype=str)
    df_group = pd.DataFrame(rows_group, columns=[SOURCE_COL] + GROUP_COLUMNS, dtype=str)
    return df_complete, df_group

def build_excel(df_complete, df_group) -> bytes:
    buffer = BytesIO()
    try:
        import xlsxwriter  # noqa: F401
        engine, kwargs = "xlsxwriter", {"engine_kwargs": {"options": {"constant_memory": False}}}
    except ImportError:
        engine, kwargs = "openpyxl", {}

    def write_chunks(writer, df, base_name):
        if len(df) <= MAX_ROWS_PER_SHEET:
            df.to_excel(writer, sheet_name=base_name, index=False)
            return
        for part, start in enumerate(range(0, len(df), MAX_ROWS_PER_SHEET), 1):
            df.iloc[start:start + MAX_ROWS_PER_SHEET].to_excel(
                writer, sheet_name=f"{base_name}_{part}", index=False
            )

    with pd.ExcelWriter(buffer, engine=engine, **kwargs) as writer:
        write_chunks(writer, df_complete, "Complete")
        write_chunks(writer, df_group, "ByGroups")
    return buffer.getvalue()

# =========================
# UI - FILE UPLOAD
# =========================
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

uploaded_files = st.file_uploader(
    "▣ TXT File Upload",
    type=["txt"],
    accept_multiple_files=True,
    key=f"txt_uploader_{st.session_state.uploader_key}",
)

col1, col2 = st.columns([3, 1])
with col2:
    if st.button("✕ Remove Files", use_container_width=True):
        for k in ("df_complete", "df_group", "csv_bytes", "xlsx_bytes"):
            st.session_state.pop(k, None)
        st.session_state.uploader_key += 1
        st.rerun()

if uploaded_files:
    st.success(f"{len(uploaded_files)} ficheiro(s) carregado(s)!")
    st.caption(", ".join(f.name for f in uploaded_files))

    if st.button("▶ Process"):
        for k in ("csv_bytes", "xlsx_bytes"):
            st.session_state.pop(k, None)
        df_complete, df_group = process_files(uploaded_files)
        st.session_state.df_complete = df_complete
        st.session_state.df_group = df_group
        st.success("Processing completed!")

# =========================
# RESULTS (persistem entre reruns)
# =========================
if "df_complete" in st.session_state:
    df_complete = st.session_state.df_complete
    df_group = st.session_state.df_group

    st.write(f"▤ Linhas processadas: {len(df_complete):,} | Linhas em grupos: {len(df_group):,}")

    # CSV
    if "csv_bytes" not in st.session_state:
        st.session_state.csv_bytes = df_complete.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "↓ CSV Download",
        data=st.session_state.csv_bytes,
        file_name="BOP_Output.csv",
        mime="text/csv",
    )

    # Excel (só gerado a pedido)
    if "xlsx_bytes" not in st.session_state:
        if st.button("⚙ Preparar Excel"):
            with st.spinner("A gerar Excel..."):
                st.session_state.xlsx_bytes = build_excel(df_complete, df_group)
            st.rerun()
    else:
        st.download_button(
            "↓ Export to Excel",
            data=st.session_state.xlsx_bytes,
            file_name="BOP_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
