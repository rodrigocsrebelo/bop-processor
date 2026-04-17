import streamlit as st
import pandas as pd
import re
from io import BytesIO
import tempfile

st.title("📊 BOP Processor - Bosch Export")

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

# =========================
# FUNCTIONS
# =========================
def parse_line(line, ncols):
    cols = line.strip().split("\t")
    if len(cols) == 1:
        cols = re.split(r'(?<!\S)\s{2,}(?!\S)', line.strip())
    if len(cols) < ncols:
        cols += [""] * (ncols - len(cols))
    return cols[:ncols]


# =========================
# UI
# =========================
files = st.file_uploader("📂 Upload TXT files", type=["txt"], accept_multiple_files=True)

logo_path = "bosch_logo.png"  # coloca este ficheiro no repo

if files:

    if st.button("🚀 PROCESS"):

        progress = st.progress(0)
        status = st.empty()

        tmp_csv = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")
        tmp_csv.write(",".join(ALL_COLUMNS) + "\n")

        processed = 0
        total = sum(len(f.getvalue().decode("utf-8", errors="ignore").splitlines()) for f in files)

        for f in files:
            text = f.getvalue().decode("utf-8", errors="ignore")

            for line in text.splitlines():

                if not line or line.startswith("Level"):
                    continue

                cols = parse_line(line, len(ALL_COLUMNS))
                cols = (cols + [""] * len(ALL_COLUMNS))[:len(ALL_COLUMNS)]

                tmp_csv.write(",".join(cols) + "\n")

                processed += 1

                if processed % 5000 == 0:
                    progress.progress(min(processed / total, 1.0))
                    status.text(f"Processing... {processed:,}")

        tmp_csv.close()

        status.text("Generating Excel...")

        # =========================
        # READ CSV BACK (FAST & SAFE)
        # =========================
        df = pd.read_csv(tmp_csv.name)

        # =========================
        # EXCEL WITH LOGO (xlsxwriter)
        # =========================
        excel_buffer = BytesIO()

        with pd.ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:

            df.to_excel(writer, sheet_name="BOP_Data", index=False)

            workbook = writer.book
            worksheet = writer.sheets["BOP_Data"]

            # =========================
            # ADD BOSCH LOGO
            # =========================
            try:
                worksheet.insert_image("A1", logo_path, {
                    "x_scale": 0.3,
                    "y_scale": 0.3
                })
            except Exception as e:
                st.warning(f"Logo not found: {e}")

        excel_buffer.seek(0)

        status.text("Done!")

        st.download_button(
            "⬇️ Download Excel (with Bosch logo)",
            excel_buffer,
            "BOP_Bosch_Report.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
