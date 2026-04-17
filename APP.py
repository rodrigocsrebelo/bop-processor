import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO

st.set_page_config(page_title="BOP Processor", layout="wide")

st.title("📊 BOP Processor PRO")

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
# CACHE (IMPORTANT SPEED BOOST)
# =========================
@st.cache_data
def process_files(file_data):
    rows_complete = []
    rows_group = []

    total_lines = sum(len(lines) for lines in file_data)
    processed = 0

    for lines in file_data:
        for line in lines:

            if not line or line.startswith("Level"):
                continue

            cols = parse_line(line, len(ALL_COLUMNS))
            row = [cols[j] if j < len(cols) else "" for j in range(len(ALL_COLUMNS))]
            rows_complete.append(row)

            final_usage = row[12]
            group_name = identify_group(final_usage)

            if group_name:
                rows_group.append([
                    group_name,
                    final_usage,
                    row[0],
                    row[2],
                    row[3],
                    row[4],
                    row[12],
                    row[13],
                    row[18],
                    row[19],
                ])

            processed += 1

    df_complete = pd.DataFrame(rows_complete, columns=ALL_COLUMNS)
    df_group = pd.DataFrame(rows_group, columns=GROUP_COLUMNS)

    return df_complete, df_group


# =========================
# FUNCTIONS (FAST)
# =========================
def normalize_number(value: str) -> str:
    return re.sub(r"\D", "", value)

def identify_group(final_usage: str) -> str:
    fu = normalize_number(final_usage)
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

def parse_line(line, num_columns):
    cols = line.strip().split("\t")
    if len(cols) == 1:
        cols = re.split(r'(?<!\S)\s{2,}(?!\S)', line.strip())
    if len(cols) < num_columns:
        cols += [""] * (num_columns - len(cols))
    return cols[:num_columns]


# =========================
# UI
# =========================
uploaded_files = st.file_uploader(
    "📂 Upload TXT files",
    type=["txt"],
    accept_multiple_files=True
)

if uploaded_files:

    st.success(f"{len(uploaded_files)} file(s) loaded")

    if st.button("🚀 Process"):

        # =========================
        # LOAD FILES
        # =========================
        file_data = []

        for f in uploaded_files:
            text = f.read().decode("utf-8", errors="ignore")
            file_data.append(text.splitlines())

        progress = st.progress(0)
        status = st.empty()

        status.text("⚡ Processing files...")

        df_complete, df_group = process_files(file_data)

        progress.progress(1.0)
        status.text("✅ Done!")

        st.success("Processing complete!")

        # =========================
        # FILTER UI
        # =========================
        st.subheader("🔍 Filters")

        group_filter = st.multiselect(
            "Filter by Group",
            options=df_group["Group"].unique()
        )

        search_text = st.text_input("Search (Description / Part Number)")

        # =========================
        # APPLY FILTERS
        # =========================
        df_view = df_group.copy()

        if group_filter:
            df_view = df_view[df_view["Group"].isin(group_filter)]

        if search_text:
            mask = df_view.astype(str).apply(
                lambda x: x.str.contains(search_text, case=False, na=False)
            ).any(axis=1)
            df_view = df_view[mask]

        st.subheader("📊 Results")
        st.dataframe(df_view, use_container_width=True)

        # =========================
        # DOWNLOAD CSV
        # =========================
        csv_buffer = StringIO()
        df_complete.to_csv(csv_buffer, index=False)

        st.download_button(
            "⬇️ Download CSV",
            csv_buffer.getvalue(),
            "BOP_Output.csv",
            "text/csv"
        )

        # =========================
        # DOWNLOAD EXCEL
        # =========================
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_complete.to_excel(writer, sheet_name="Complete", index=False)
            df_group.to_excel(writer, sheet_name="ByGroups", index=False)

        excel_buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            excel_buffer.getvalue(),
            "BOP_Report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
