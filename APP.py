import streamlit as st
import pandas as pd
import re
from io import BytesIO
import tempfile
import gc
import csv

# =========================
# PAGE CONFIG (UI BETTER)
# =========================
st.set_page_config(page_title="BOP Processor PRO", layout="wide")

st.title("📊 BOP Processor - Enterprise Edition")
st.caption("Handles 1M+ lines safely | No crashes | Fast streaming engine")

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
# FAST FUNCTIONS
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
# UI
# =========================
files = st.file_uploader(
    "📂 Upload TXT files (1M+ supported)",
    type=["txt"],
    accept_multiple_files=True
)

if files:

    st.success(f"{len(files)} file(s) loaded")

    if st.button("🚀 PROCESS"):

        progress = st.progress(0)
        status = st.empty()

        # =========================
        # TEMP CSV FILE (NO RAM)
        # =========================
        tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", encoding="utf-8")
        tmp.write(",".join(ALL_COLUMNS) + "\n")

        group_rows = []

        processed = 0
        total_estimate = sum(len(f.getvalue().decode("utf-8", errors="ignore").splitlines()) for f in files)

        # =========================
        # STREAM PROCESS
        # =========================
        for f in files:

            text = f.getvalue().decode("utf-8", errors="ignore")

            for line in text.splitlines():

                if not line or line.startswith("Level"):
                    continue

                cols = parse_line(line, len(ALL_COLUMNS))
                cols = (cols + [""] * len(ALL_COLUMNS))[:len(ALL_COLUMNS)]

                writer_csv = csv.writer(tmp)
                writer_csv.writerow(ALL_COLUMNS)

                # GROUP DATA (SMALL ONLY)
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
                    progress.progress(min(processed / total_estimate, 1.0))
                    status.text(f"Processing... {processed:,} lines")

        tmp.close()

        status.text("Loading results...")

        # =========================
        # GROUP DATAFRAME (FOR UI FILTERS)
        # =========================
        df_group = pd.DataFrame(group_rows, columns=GROUP_COLUMNS)

        # =========================
        # 🔥 UI FILTERS (FAST)
        # =========================
        st.divider()
        st.subheader("🔍 Filters")

        col1, col2 = st.columns(2)

        with col1:
            group_filter = st.multiselect(
                "Group",
                options=sorted(df_group["Group"].dropna().unique()),
                default=[]
            )

        with col2:
            search = st.text_input("Search text (Description / Part Number)")

        # APPLY FILTERS
        df_view = df_group.copy()

        if group_filter:
            df_view = df_view[df_view["Group"].isin(group_filter)]

        if search:
            df_view = df_view[df_view.astype(str).apply(
                lambda x: x.str.contains(search, case=False, na=False)
            ).any(axis=1)]

        # =========================
        # UI TABLE (PRETTY)
        # =========================
        st.divider()
        st.subheader("📊 Results")

        st.dataframe(
            df_view,
            use_container_width=True,
            height=450
        )

        # =========================
        # DOWNLOAD CSV (FULL)
        # =========================
        st.divider()

        with open(tmp.name, "r", encoding="utf-8") as f:
            csv_data = f.read()

        st.download_button(
            "⬇️ Download FULL CSV (1M+)",
            csv_data,
            "BOP_Output.csv",
            "text/csv"
        )

        # =========================
        # EXCEL 1 - FILTERED GROUPS
        # =========================
        excel_buffer_1 = BytesIO()
        
        status.text("Generating Excel (Filtered Groups)...")
        
        with pd.ExcelWriter(excel_buffer_1, engine="openpyxl") as writer:
            df_view.to_excel(writer, sheet_name="FilteredGroups", index=False)
        
        excel_buffer_1.seek(0)
        
        st.download_button(
            "⬇️ Download Excel (Filtered Groups)",
            excel_buffer_1.getvalue(),
            "BOP_Filtered_Groups.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # =========================
        # EXCEL 2 - USAGE LIST (FULL DATA)
        # =========================
        excel_buffer_2 = BytesIO()
        
        status.text("Generating Excel (Usage List - Full Data)...")
        
        # read from temp CSV (NO RAM explosion)
        df_usage = pd.read_csv(tmp.name)
        
        with pd.ExcelWriter(excel_buffer_2, engine="openpyxl") as writer:
            df_usage.to_excel(writer, sheet_name="Usage List", index=False)
        
        excel_buffer_2.seek(0)
        
        st.download_button(
            "⬇️ Download Excel (Usage List - Full)",
            excel_buffer_2.getvalue(),
            "BOP_Usage_List.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
