import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO


st.title("📊 BOP Processor")

# =========================
# CONFIG
# =========================
MAX_ROWS_PER_FILE = 999900

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
# UI - FILE UPLOAD
# =========================
uploaded_file = st.file_uploader("📂 Upload do ficheiro TXT", type=["txt"])

if uploaded_file:
    st.success("Arquivo carregado!")

    text_data = uploaded_file.read().decode("utf-8", errors="ignore")
    lines = text_data.splitlines()

    st.write(f"📏 Total de linhas: {len(lines):,}")

    if st.button("🚀 Processar"):
        rows_complete = []
        rows_group = []

        progress = st.progress(0)

        for i, line in enumerate(lines):
            line = line.strip()
            if not line or line.startswith("Level"):
                continue

            cols = parse_line(line, len(ALL_COLUMNS))
            row = dict(zip(ALL_COLUMNS, cols))

            group_name = identify_group(row["Final Usage"])

            if group_name:
                rows_group.append({
                    "Group": group_name,
                    "Part Number": row["Final Usage"],
                    "Level": row["Level"],
                    "Description DC": row["Description DC"],
                    "Item Quantity DU": row["Item Quantity DU"],
                    "Direct Usage": row["Direct Usage"],
                    "Final Usage": row["Final Usage"],
                    "Description FU": row["Description FU"],
                    "Plant FU (BOM)": row["Plant FU (BOM)"],
                    "FU Charact. 1 Value": row["FU Charact. 1 Value"]
                })

            rows_complete.append(row)

            # Atualiza barra
            if i % 1000 == 0:
                progress.progress(i / len(lines))

        df_complete = pd.DataFrame(rows_complete, columns=ALL_COLUMNS)
        df_group = pd.DataFrame(rows_group, columns=GROUP_COLUMNS)

        st.success("✅ Processamento concluído!")

        # =========================
        # DOWNLOAD CSV
        # =========================
        csv_buffer = StringIO()
        df_complete.to_csv(csv_buffer, index=False)

        st.download_button(
            label="⬇️ Download CSV Completo",
            data=csv_buffer.getvalue(),
            file_name="BOP_Output.csv",
            mime="text/csv"
        )

        # =========================
        # DOWNLOAD EXCEL
        # =========================
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_complete.to_excel(writer, sheet_name="Complete", index=False)
            df_group.to_excel(writer, sheet_name="ByGroups", index=False)

        st.download_button(
            label="⬇️ Download Excel",
            data=excel_buffer.getvalue(),
            file_name="BOP_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
