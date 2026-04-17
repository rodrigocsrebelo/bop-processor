import streamlit as st
import pandas as pd
import re
import csv
from io import BytesIO
import tempfile
import gc

# =========================
# APP META
# =========================
APP_VERSION = "v2.0.0"
APP_OWNER = "Rebelo Rodrigo (SO/OPM2.6.1-Lis)"

st.set_page_config(page_title="BOP Dashboard PRO", layout="wide")

st.title("📊 BOP Dashboard - Enterprise Edition")
st.caption(f"{APP_VERSION} | Owner: {APP_OWNER}")
st.caption("1M+ lines safe | Streaming engine | Power BI style dashboard")

# =========================
# CONFIG
# =========================
ALL_COLUMNS = [
    "Level","Search Object (SO)","Description DC","Item Quantity DU","Direct Usage","Description DU",
    "Status DU (MMA/DOC)","Plant status DU (MMA)","Status DU (BOM)","System Desc. DU","Plant DU (BOM)",
    "Plant Name DU","Final Usage","Description FU","Status FU(MMA/DOC)","Plant status FU (MMA)",
    "Status FU (BOM)","System Description FU","Plant FU (BOM)","FU Charact. 1 Value","Subitem Number",
    "Install. Point","Sub Item Quantity","Valid from CMA DU","Valid from date DU","Valid to CMA DU",
    "Valid to date DU","Status Text","WU Status Code"
]

GROUP_COLUMNS = [
    "Group","Part Number","Level","Description DC","Item Quantity DU","Direct Usage",
    "Final Usage","Description FU","Plant FU (BOM)","FU Charact. 1 Value"
]

# =========================
# FUNCTIONS
# =========================
def normalize_number(v):
    return re.sub(r"\D", "", v or "")

def identify_group(fu):
    fu = normalize_number(fu)
    if fu.startswith(("7612","7609","764","750","751","752")):
        return "CP1"
    if fu.startswith("0263"):
        return "CP2"
    if fu.startswith(("7620","7607")):
        return "CP1-PRO"
    if fu.startswith("8613600"):
        return "Bombardier"
    if fu.startswith("1270020"):
        return "E-bike"
    return ""

def parse_line(line, ncols):
    line = line.strip()
    cols = line.split("\t")

    if len(cols) == 1:
        cols = re.split(r'(?<!\S)\s{2,}(?!\S)', line)

    if len(cols) < ncols:
        cols += [""] * (ncols - len(cols))

    return cols[:ncols]


# =========================
# SIDEBAR
# =========================
st.sidebar.header("Controls")

files = st.sidebar.file_uploader(
    "Upload TXT files",
    type=["txt"],
    accept_multiple_files=True
)

run = st.sidebar.button("🚀 Process Data")

group_filter = st.sidebar.multiselect("Filter Group", [])
search = st.sidebar.text_input("Search")

# =========================
# SESSION STATE
# =========================
if "df_group" not in st.session_state:
    st.session_state.df_group = None

if "csv_path" not in st.session_state:
    st.session_state.csv_path = None


# =========================
# PROCESSING
# =========================
if files and run:

    progress = st.progress(0)
    status = st.empty()

    tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", newline="", encoding="utf-8")

    writer_csv = csv.writer(tmp)
    writer_csv.writerow(ALL_COLUMNS)

    group_rows = []

    total = sum(
        len(f.getvalue().decode("utf-8", errors="ignore").splitlines())
        for f in files
    )

    processed = 0

    for f in files:
        text = f.getvalue().decode("utf-8", errors="ignore")

        for line in text.splitlines():

            if not line or line.startswith("Level"):
                continue

            cols = parse_line(line, len(ALL_COLUMNS))
            cols = (cols + [""] * len(ALL_COLUMNS))[:len(ALL_COLUMNS)]

            writer_csv.writerow(cols)

            fu = cols[12]
            group = identify_group(fu)

            if group:
                group_rows.append([
                    group,
                    fu,
                    cols[0],
                    cols[2],
                    cols[3],
                    cols[4],
                    cols[12],
                    cols[13],
                    cols[18],
                    cols[19],
                ])

            processed += 1

            if processed % 5000 == 0:
                progress.progress(min(processed / total, 1.0))
                status.text(f"Processing {processed:,} lines")

    tmp.close()

    st.session_state.df_group = pd.DataFrame(group_rows, columns=GROUP_COLUMNS)
    st.session_state.csv_path = tmp.name

    status.text("Ready")


# =========================
# DASHBOARD (ONLY IF DATA EXISTS)
# =========================
if st.session_state.df_group is not None:

    df_group = st.session_state.df_group

    # =========================
    # FILTERS APPLY
    # =========================
    df_view = df_group.copy()

    if group_filter:
        df_view = df_view[df_view["Group"].isin(group_filter)]

    if search:
        df_view = df_view[df_view.astype(str).apply(
            lambda x: x.str.contains(search, case=False, na=False)
        ).any(axis=1)]

    # =========================
    # KPIs
    # =========================
    st.divider()
    st.subheader("📊 Dashboard Overview")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Rows", len(df_group))
    col2.metric("Filtered Rows", len(df_view))
    col3.metric("Groups", df_group["Group"].nunique())
    col4.metric("CP1 Count", (df_group["Group"] == "CP1").sum())

    # =========================
    # CHARTS
    # =========================
    st.divider()
    st.subheader("📈 Analytics")

    col1, col2 = st.columns(2)

    with col1:
        st.write("Group Distribution")
        st.bar_chart(df_group["Group"].value_counts())

    with col2:
        st.write("Filtered Distribution")
        st.bar_chart(df_view["Group"].value_counts())

    # =========================
    # TABLE
    # =========================
    st.divider()
    st.subheader("📋 Data Explorer")

    st.dataframe(df_view, use_container_width=True, height=500, hide_index=True)

    # =========================
    # DOWNLOAD CSV FULL
    # =========================
    st.divider()

    with open(st.session_state.csv_path, "r", encoding="utf-8") as f:
        csv_data = f.read()

    st.download_button(
        "⬇️ Download FULL CSV (1M+)",
        csv_data,
        "BOP_Output.csv",
        "text/csv"
    )

    # =========================
    # EXCEL FILTERED
    # =========================
    excel_1 = BytesIO()

    status = st.empty()
    status.text("Generating Excel (Filtered)...")

    with pd.ExcelWriter(excel_1, engine="openpyxl") as writer:
        df_view.to_excel(writer, sheet_name="Filtered", index=False)

    excel_1.seek(0)

    st.download_button(
        "⬇️ Download Excel (Filtered)",
        excel_1.getvalue(),
        "BOP_Filtered.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # =========================
    # EXCEL FULL
    # =========================
    excel_2 = BytesIO()

    status.text("Generating Excel (Usage List)...")

    df_usage = pd.read_csv(st.session_state.csv_path)

    with pd.ExcelWriter(excel_2, engine="openpyxl") as writer:
        df_usage.to_excel(writer, sheet_name="Usage List", index=False)

    excel_2.seek(0)

    st.download_button(
        "⬇️ Download Excel (Usage List FULL)",
        excel_2.getvalue(),
        "BOP_Usage_List.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    status.text("Done")
    st.success("Dashboard ready")

    gc.collect()
