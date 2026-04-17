import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO

st.title("📊 BOP Processor")

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
def normalize_number(value: str) -> str:
    return re.sub(r"\D", "", value)

def identify_group(final_usage: str) -> str:
    fu = normalize_number(final_usage)
    if fu.startswith(("7612","7609","764","750","751","752")):
        return "Group CP1"
    if fu.startswith("0263"):
        return "Group CP2"
    if fu.startswith(("7620","7607")):
        return "Group CP1-PRO"
    if fu.startswith("8613600"):
        return "Group Bombardier"
    if fu.startswith("1270020"):
        return "Group E-bike"
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
uploaded_file = st.file_uploader("📂 Upload TXT file", type=["txt"])

if uploaded_file:
    st.success("File uploaded successfully!")

    text_data = uploaded_file.read().decode("utf-8", errors="ignore")
    lines = text_data.splitlines()

    st.write(f"📏 Total lines: {len(lines):,}")

    if st.button("🚀 Process"):

        rows_complete = []
        rows_group = []

        progress = st.progress(0)
        total = len(lines)

        # local bindings (speed boost)
        parse_line_local = parse_line
        identify_group_local = identify_group

        for i, line in enumerate(lines):

            if not line or line.startswith("Level"):
                continue

            cols = parse_line_local(line, len(ALL_COLUMNS))

            # FAST: avoid dict(zip)
            row = [cols[j] if j < len(cols) else "" for j in range(len(ALL_COLUMNS))]

            rows_complete.append(row)

            final_usage = row[12]  # "Final Usage"
            group_name = identify_group_local(final_usage)

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

            if i % 5000 == 0:
                progress.progress(i / total)

        # =========================
        # DATAFRAMES
        # =========================
        df_complete = pd.DataFrame(rows_complete, columns=ALL_COLUMNS)
        df_group = pd.DataFrame(rows_group, columns=GROUP_COLUMNS)

        st.success("✅ Processing completed!")

        # =========================
        # CSV DOWNLOAD
        # =========================
        csv_buffer = StringIO()
        df_complete.to_csv(csv_buffer, index=False)

        st.download_button(
            "⬇️ Download Full CSV",
            csv_buffer.getvalue(),
            "BOP_Output.csv",
            "text/csv"
        )

        # =========================
        # EXCEL DOWNLOAD
        # =========================
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_complete.to_excel(writer, sheet_name="Complete", index=False)
            df_group.to_excel(writer, sheet_name="ByGroups", index=False)

        st.download_button(
            "⬇️ Download Excel",
            excel_buffer.getvalue(),
            "BOP_Report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
