from __future__ import annotations

import streamlit as st

from src.config import is_shared_core_read_only_mode
from src.data_loader import import_dataframe, load_template, read_import_file
from src.pages import football_data_setup


IMPORT_TYPES = {
    "teams": "Teams",
    "groups": "Groups",
    "fixtures": "Fixtures",
    "fifa_rankings": "FIFA Rankings",
    "odds": "Odds",
}


def render() -> None:
    st.title("Data Imports")
    if is_shared_core_read_only_mode():
        st.info("Shared mode protects official World Cup data. Data uploads, imports, and API setup changes are disabled.")
        return

    tab_manual, tab_football_data = st.tabs(["Manual Imports", "football-data.org Setup"])

    with tab_manual:
        st.caption("Manual CSV/JSON imports. Imports use upserts to avoid duplicates.")
        kind = st.selectbox("Import type", list(IMPORT_TYPES.keys()), format_func=IMPORT_TYPES.get)
        if kind == "fifa_rankings":
            st.info(
                "You can import the full FIFA ranking list here, including all 211 teams. "
                "Rows matching World Cup teams also update the tournament rankings table. "
                "Required columns: team, ranking_date, rank. Recommended: points, previous_rank, source, notes."
            )
        tab_upload, tab_template = st.tabs(["Upload", "Template"])

        with tab_upload:
            uploaded = st.file_uploader("Choose a CSV or JSON file", type=["csv", "json"])
            if uploaded:
                df = read_import_file(uploaded)
                if df.empty:
                    st.warning("That file did not contain any rows to import.")
                else:
                    st.write("Preview")
                    st.dataframe(df.head(50), width="stretch")
                    if st.button("Import into SQLite", type="primary"):
                        rows, errors = import_dataframe(kind, df)
                        if errors:
                            for error in errors:
                                st.error(error)
                        else:
                            st.success(f"Imported or updated {rows} {IMPORT_TYPES[kind].lower()} rows.")
                            st.cache_data.clear()

        with tab_template:
            template = load_template(kind)
            if template.empty:
                st.warning(f"Template file not found or empty: data/imports/{kind}.csv")
            else:
                st.write("Expected columns and example rows")
                st.dataframe(template, width="stretch", hide_index=True)
                st.caption(f"Template file: data/imports/{kind}.csv")

    with tab_football_data:
        football_data_setup.render()
