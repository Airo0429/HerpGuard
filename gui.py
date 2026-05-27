from __future__ import annotations

import streamlit as st

from agent import generate_report
from pdf_extractor import list_available_species


def main() -> None:
    st.set_page_config(page_title="HerpGuard AI", layout="wide")
    st.title("HerpGuard AI")

    species_options = list_available_species()

    with st.form(key="input_form"):
        cols = st.columns([1, 2])
        with cols[0]:
            species = st.selectbox("Species", options=species_options, index=0 if species_options else -1)
            temperature = st.text_input("Temperature (C)")
            humidity = st.text_input("Humidity (%)")
            feeding = st.text_input("Feeding Behavior")
            activity = st.text_input("Activity Level")
            hydration = st.text_input("Hydration Notes")
        with cols[1]:
            observations = st.text_area("Owner Observations", height=160)

        submit = st.form_submit_button("Analyze")

    if submit:
        if not species:
            st.warning("Please select a supported species.")
        else:
            inputs = {
                "species": species,
                "temperature": temperature.strip(),
                "humidity": humidity.strip(),
                "feeding": feeding.strip(),
                "activity": activity.strip(),
                "hydration": hydration.strip(),
                "observations": observations.strip(),
            }

            try:
                report = generate_report(inputs)
                st.subheader("Monitoring Report")
                st.code(report, language="text")
            except RuntimeError as exc:
                st.error(f"Processing Error: {exc}")


def launch_app() -> None:
    main()


if __name__ == "__main__":
    main()
