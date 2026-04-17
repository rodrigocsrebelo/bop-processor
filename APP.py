import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO
import gc

st.title("📊 BOP Processor - Stable Version")

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
files = st.file_uploader(
    "📂 Upload TXT files",
    type=["txt"],
    accept_multiple_files=True
)

if files:

    if st.button("🚀 Process"):

        progress = st.progress(0)
        status = st.empty()

        # CSV streaming (no RAM explosion)
        csv_buffer = StringIO()
        csv_buffer.write(",".join(ALL_COLUMNS) + "\n")

        group_rows = []  # small only

        total_lines = sum(len(f.read().decode("utf-8", errors="ignore").splitlines()) for f in files)

        # reset file pointers
        files = [f for f in files]

        processed = 0

        # =========================
        # PROCESS STREAMING
        # =========================
        for f in files:

            text = f.read().decode("utf-8", errors="ignore")
            lines = text.splitlines()

            for line in lines:

                if not line or line.startswith("Level"):
                    continue

                cols = parse_line(line, len(ALL_COLUMNS))
                cols = cols + [""] * (len(ALL_COLUMNS) - len(cols))

                # WRITE DIRECTLY TO CSV (NO RAM LIST)
                csv_buffer.write(",".join(cols) + "\n")

                # GROUP (small memory only)
                final_usage = cols[12]
                group = identify_group(final_usage)

                if group:
                    group_rows.append([
                        group,
                        final_usage,
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

                if processed % 2000 == 0:
                    progress.progress(min(processed / total_lines, 1.0))
                    status.text(f"Processing... {processed}/{total_lines}")

        status.text("Generating outputs...")

        # =========================
        # GROUP DF (small)
        # =========================
        df_group = pd.DataFrame(group_rows, columns=GROUP_COLUMNS)

        # =========================
        # DOWNLOAD CSV
        # =========================
        st.download_button(
            "⬇️ Download CSV",
            csv_buffer.getvalue(),
            "BOP_Output.csv",
            "text/csv"
        )

        # =========================
        # EXCEL (SAFE)
        # =========================
        excel_buffer = BytesIO()

        status.text("Creating Excel...")

        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            df_group.to_excel(writer, sheet_name="ByGroups", index=False)

        excel_buffer.seek(0)

        st.download_button(
            "⬇️ Download Excel",
            excel_buffer.getvalue(),
            "BOP_Report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        progress.progress(1.0)
        status.text("Done!")

        gc.collect()
