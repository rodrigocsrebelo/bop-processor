
import streamlit as st
import pandas as pd
import re
from io import StringIO, BytesIO

# =========================
# PAGE CONFIGURATION
# =========================
st.set_page_config(
    page_title="BOP Processor",
    page_icon="☁",
    layout="wide"
)

st.title("☁ BOP Processor")
st.caption("Bill of Process | Data Processing & Group Classification")

st.divider()

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
    "Valid to date CMA DU","Status Text","WU Status Code"
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

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

st.subheader("File Upload")

st.write("Upload one or multiple TXT files for combined processing.")

uploaded_files = st.file_uploader(
    "Select TXT files",
    type=["txt"],
    accept_multiple_files=True,
    key=f"txt_uploader_{st.session_state.uploader_key}"
)

col1, col2 = st.columns([4, 1])

with col1:
    if uploaded_files:
        st.success(f"{len(uploaded_files)} file(s) successfully uploaded.")

with col2:
    if st.button(
        "✕ Remove All Files",
        use_container_width=True,
        disabled=not uploaded_files
    ):
        st.session_state.uploader_key += 1
        st.rerun()

# =========================
# FILE INFORMATION
# =========================

if uploaded_files:

    total_lines = 0
    file_data = []

    for uploaded_file in uploaded_files:

        text_data = uploaded_file.getvalue().decode(
            "utf-8", errors="ignore"
        )

        lines = text_data.splitlines()

        file_data.append((uploaded_file.name, lines))
        total_lines += len(lines)

    st.divider()

    st.subheader("Upload Summary")

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Uploaded Files", len(uploaded_files))

    with col2:
        st.metric("Total Rows", f"{total_lines:,}")

    with st.expander("View Uploaded Files"):
        for file_name, lines in file_data:
            st.write(f"▤ **{file_name}** — {len(lines):,} rows")

    st.divider()

    # =========================
    # PROCESSING
    # =========================

    if st.button("▶ Process Files", use_container_width=True):

        rows_complete = []
        rows_group = []

        progress = st.progress(0)
        status_text = st.empty()

        processed_lines = 0

        for file_name, lines in file_data:

            status_text.caption(f"Processing: {file_name}")

            for i, line in enumerate(lines):

                line = line.strip()

                if not line or line.startswith("Level"):
                    processed_lines += 1
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

                processed_lines += 1

                if processed_lines % 1000 == 0:
                    progress.progress(
                        min(processed_lines / max(total_lines, 1), 1.0)
                    )

        progress.progress(1.0)
        status_text.empty()

        # =========================
        # DATAFRAMES
        # =========================

        df_complete = pd.DataFrame(
            rows_complete,
            columns=ALL_COLUMNS
        )

        df_group = pd.DataFrame(
            rows_group,
            columns=GROUP_COLUMNS
        )

        st.success("Processing completed successfully!")

        st.divider()

        # =========================
        # PROCESSING SUMMARY
        # =========================

        st.subheader("Processing Results")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Total Records", f"{len(df_complete):,}")

        with col2:
            st.metric("Grouped Records", f"{len(df_group):,}")

        with col3:
            st.metric(
                "Identified Groups",
                df_group["Group"].nunique()
            )

        # =========================
        # DOWNLOAD CSV
        # =========================

        st.divider()
        st.subheader("Export Results")

        csv_buffer = StringIO()
        df_complete.to_csv(csv_buffer, index=False)

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                label="↓ Download Complete CSV",
                data=csv_buffer.getvalue(),
                file_name="BOP_Output.csv",
                mime="text/csv",
                use_container_width=True
            )

        # =========================
        # DOWNLOAD EXCEL
        # =========================

        excel_buffer = BytesIO()

        with pd.ExcelWriter(
            excel_buffer,
            engine="openpyxl"
        ) as writer:

            df_complete.to_excel(
                writer,
                sheet_name="Complete",
                index=False
            )

            df_group.to_excel(
                writer,
                sheet_name="ByGroups",
                index=False
            )

        with col2:
            st.download_button(
                label="↓ Download Excel Report",
                data=excel_buffer.getvalue(),
                file_name="BOP_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
