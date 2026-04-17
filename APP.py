import streamlit as st
import pandas as pd
import re
import csv
from io import BytesIO
import tempfile
import gc

# =========================
# APP CONFIG
# =========================
APP_VERSION = "v3.0.0"
APP_OWNER = "Rebelo Rodrigo (SO/OPM2.6.1-Lis)"

st.set_page_config(page_title="BOP Dashboard PRO", layout="wide")

st.title("📊 BOP Dashboard PRO")
st.caption(f"{APP_VERSION} | Owner: {APP_OWNER}")
st.caption("Enterprise BI Engine | 1M+ lines safe processing")

# =========================
# DATA CONFIG
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
    return "Other"

def parse_line(line, ncols):
    line = line.strip()
    cols = line.split("\t")

    if len(cols) == 1:
        cols = re.split(r'(?<!\S)\s{2,}(?!\S)', line)

    if len(cols) < ncols:
        cols += [""] * (ncols - len(cols))

    return cols[:ncols]


# =========================
# SIDEBAR CONTROLS
# =========================
st.sidebar.header("⚙ Controls")

files = st.sidebar.file_uploader(
    "Upload TXT files",
    type=["txt"],
    accept_multiple_files=True
)

run = st.sidebar.button("🚀 Process")

reset = st.sidebar.button("🔄 Reset Filters")

# reset filters
if reset:
    st.session_state.clear()
    st.rerun()

# =========================
# SESSION STATE
# =========================
if "df_group" not in st.session_state:
    st.session_state.df_group = None

if "csv_path" not in st.session_state:
    st.session_state.csv_path = None


# =========================
# PROCESS DATA
# =========================
if files and run:

    progress = st.progress(0)
    status = st.empty()

    tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", newline="", encoding="utf-8")

    writer = csv.writer(tmp)
    writer.writerow(ALL_COLUMNS)

    group_rows = []

    total = sum(len(f.getvalue().decode("utf-8", errors="ignore").splitlines()) for f in files)
    processed = 0

    for f in files:
        text = f.getvalue().decode("utf-8", errors="ignore")

        for line in text.splitlines():

            if not line or line.startswith("Level"):
                continue

            cols = parse_line(line, len(ALL_COLUMNS))
            cols = (cols + [""] * len(ALL_COLUMNS))[:len(ALL_COLUMNS)]

            writer.writerow(cols)

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

    status.text("Processing completed")


# =========================
# DASHBOARD
# =========================
if st.session_state.df_group is not None:

    df_group = st.session_state.df_group.copy()

    # =========================
    # FILTER OPTIONS (FIXED)
    # =========================
    group_options = sorted(df_group["Group"].dropna().unique())

    group_filter = st.sidebar.multiselect(
        "Filter Group",
        options=group_options,
        default=st.session_state.get("group_filter", [])
    )

    search = st.sidebar.text_input(
        "Search",
        value=st.session_state.get("search", "")
    )

    st.session_state.group_filter = group_filter
    st.session_state.search = search

    # =========================
    # APPLY FILTERS
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

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Rows", len(df_group))
    c2.metric("Filtered", len(df_view))
    c3.metric("Groups", df_group["Group"].nunique())
    c4.metric("CP1", (df_group["Group"] == "CP1").sum())

    # =========================
    # CHARTS
    # =========================
    st.divider()
    st.subheader("📈 Analytics")

    c1, c2 = st.columns(2)

    with c1:
        st.bar_chart(df_group["Group"].value_counts())

    with c2:
        st.bar_chart(df_view["Group"].value_counts())

    # =========================
    # FULL PREVIEW
    # =========================
    st.divider()
    st.subheader("📦 FULL DATA (Usage List)")

    st.dataframe(df_group, use_container_width=True, height=300)

    # =========================
    # FILTERED TABLE
    # =========================
    st.divider()
    st.subheader("📋 Filtered Data")

    st.dataframe(df_view, use_container_width=True, height=500)

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
    excel1 = BytesIO()

    with pd.ExcelWriter(excel1, engine="openpyxl") as writer:
        df_view.to_excel(writer, sheet_name="Filtered", index=False)

    excel1.seek(0)

    st.download_button(
        "⬇️ Download Excel (Filtered)",
        excel1.getvalue(),
        "BOP_Filtered.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # =========================
    # EXCEL FULL
    # =========================
    excel2 = BytesIO()

    with pd.ExcelWriter(excel2, engine="openpyxl") as writer:
        df_group.to_excel(writer, sheet_name="Usage List", index=False)

    excel2.seek(0)

    st.download_button(
        "⬇️ Download Excel (FULL Usage List)",
        excel2.getvalue(),
        "BOP_Usage_List.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.success("Ready ✔")

    gc.collect()
