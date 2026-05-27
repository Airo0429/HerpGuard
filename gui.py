from __future__ import annotations

import streamlit as st
import json
from pathlib import Path
from typing import Any

from agent import generate_diagnostic_report


def load_pet_data() -> dict[str, Any]:
    """Load pet_data.json"""
    path = Path("pet_data.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_pet_data(data: dict[str, Any]) -> None:
    """Save pet_data.json"""
    path = Path("pet_data.json")
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def find_species_pdf(species: str) -> Path | None:
    """Find the PDF guide for a species"""
    pdf_dir = Path("pdf_guides")
    if not pdf_dir.exists():
        return None
    
    species_normalized = species.lower().replace(" ", "_")
    
    for pdf_file in pdf_dir.glob("*.pdf"):
        if species_normalized in pdf_file.stem.lower():
            return pdf_file
    
    return None


def main() -> None:
    st.set_page_config(page_title="HerpGuard AI", layout="wide")
    st.title("HerpGuard AI - Exotic Pet Monitoring")

    # Create tabs for navigation
    tab1, tab2 = st.tabs(["Diagnostics", "Add Species"])

    # ============ TAB 1: DIAGNOSTICS ============
    with tab1:
        st.header("Pet Diagnostics")
        st.markdown("Enter your pet's species and observations to get care recommendations.")

        with st.form(key="diagnostics_form"):
            pet_data = load_pet_data()
            available_species = sorted(pet_data.keys())

            col1, col2 = st.columns(2)
            with col1:
                species = st.selectbox(
                    "Species",
                    options=available_species,
                    index=0 if available_species else -1,
                    key="diag_species"
                )

            observations = st.text_area(
                "Observations & Symptoms",
                height=150,
                placeholder="Describe your pet's current state, behavior, environment, etc.",
                key="observations"
            )

            submit_diag = st.form_submit_button("Analyze Pet", use_container_width=True)

        if submit_diag:
            if not species:
                st.error("❌ Please select a species.")
            elif not observations.strip():
                st.error("❌ Please provide observations.")
            else:
                try:
                    with st.spinner("Running diagnostics..."):
                        report = generate_diagnostic_report(species, observations)
                    st.subheader("Diagnostic Report")
                    st.code(report, language="text")
                    
                    # Add PDF download button if guide exists
                    pdf_path = find_species_pdf(species)
                    if pdf_path and pdf_path.exists():
                        pdf_bytes = pdf_path.read_bytes()
                        st.download_button(
                            label=f"📥 Download {species.title()} Care Guide (PDF)",
                            data=pdf_bytes,
                            file_name=pdf_path.name,
                            mime="application/pdf",
                            use_container_width=True
                        )
                except RuntimeError as exc:
                    st.error(f"❌ Error: {exc}")

    # ============ TAB 2: ADD SPECIES ============
    with tab2:
        st.header("Add or Update Species")
        st.markdown("Add a new species to your knowledge base or update an existing one.")

        pet_data = load_pet_data()

        with st.form(key="add_species_form"):
            # Required fields
            species_name = st.text_input(
                "Species Name *",
                placeholder="e.g., Bearded Dragon",
                key="species_name"
            )

            pdf_file = st.file_uploader(
                "PDF Care Guide",
                type="pdf",
                key="pdf_guide"
            )

            st.markdown("---")
            st.subheader("Numerical Parameters (Optional)")

            col1, col2 = st.columns(2)
            with col1:
                temp_min = st.number_input(
                    "Temperature Minimum (°C)",
                    value=None,
                    step=0.1,
                    key="temp_min"
                )
                temp_max = st.number_input(
                    "Temperature Maximum (°C)",
                    value=None,
                    step=0.1,
                    key="temp_max"
                )
                basking_temp_min = st.number_input(
                    "Basking Temperature Minimum (°C)",
                    value=None,
                    step=0.1,
                    key="basking_temp_min"
                )
                basking_temp_max = st.number_input(
                    "Basking Temperature Maximum (°C)",
                    value=None,
                    step=0.1,
                    key="basking_temp_max"
                )

            with col2:
                humidity_min = st.number_input(
                    "Humidity Minimum (%)",
                    value=None,
                    step=0.1,
                    key="humidity_min"
                )
                humidity_max = st.number_input(
                    "Humidity Maximum (%)",
                    value=None,
                    step=0.1,
                    key="humidity_max"
                )
                uvb_min = st.number_input(
                    "UVB Minimum (hours/day)",
                    value=None,
                    step=0.1,
                    key="uvb_min"
                )
                uvb_max = st.number_input(
                    "UVB Maximum (hours/day)",
                    value=None,
                    step=0.1,
                    key="uvb_max"
                )

            nighttime_temp = st.number_input(
                "Night Time Temperature (°C)",
                value=None,
                step=0.1,
                key="nighttime_temp"
            )

            st.markdown("---")
            st.subheader("Text Parameters (Optional)")

            diet = st.text_area(
                "Diet",
                height=80,
                placeholder="Describe the recommended diet...",
                key="diet"
            )

            feeding_notes = st.text_area(
                "Feeding Notes",
                height=80,
                placeholder="Special feeding guidelines...",
                key="feeding_notes"
            )

            uvb_notes = st.text_area(
                "UVB Notes",
                height=80,
                placeholder="UVB lighting requirements...",
                key="uvb_notes"
            )

            substrate = st.text_area(
                "Substrate",
                height=80,
                placeholder="Recommended substrate composition...",
                key="substrate"
            )

            other_care = st.text_area(
                "Other Care",
                height=80,
                placeholder="Additional care guidelines (lifespan, housing, etc.)...",
                key="other_care"
            )

            st.markdown("---")
            submit_species = st.form_submit_button("Save Species", use_container_width=True)

        if submit_species:
            if not species_name.strip():
                st.error("❌ Species Name is required.")
            else:
                species_key = species_name.lower().strip()

                # Handle PDF upload
                if pdf_file is not None:
                    pdf_dir = Path("pdf_guides")
                    pdf_dir.mkdir(exist_ok=True)
                    pdf_path = pdf_dir / f"{species_key.replace(' ', '_')}.pdf"
                    pdf_path.write_bytes(pdf_file.read())
                    st.success(f"📄 PDF saved: {pdf_path}")

                # Build species data
                species_data: dict[str, Any] = {}

                # Add numerical fields if provided
                if temp_min is not None:
                    species_data["temp_min"] = float(temp_min)
                if temp_max is not None:
                    species_data["temp_max"] = float(temp_max)
                if basking_temp_min is not None:
                    species_data["basking_temp_min"] = float(basking_temp_min)
                if basking_temp_max is not None:
                    species_data["basking_temp_max"] = float(basking_temp_max)
                if humidity_min is not None:
                    species_data["humidity_min"] = float(humidity_min)
                if humidity_max is not None:
                    species_data["humidity_max"] = float(humidity_max)
                if uvb_min is not None:
                    species_data["uvb_min"] = float(uvb_min)
                if uvb_max is not None:
                    species_data["uvb_max"] = float(uvb_max)
                if nighttime_temp is not None:
                    species_data["nighttime_temp"] = float(nighttime_temp)

                # Add text fields if provided
                if diet.strip():
                    species_data["diet"] = diet.strip()
                if feeding_notes.strip():
                    species_data["feeding_notes"] = feeding_notes.strip()
                if uvb_notes.strip():
                    species_data["uvb_notes"] = uvb_notes.strip()
                if substrate.strip():
                    species_data["substrate"] = substrate.strip()
                if other_care.strip():
                    species_data["other_care"] = other_care.strip()

                # Merge with existing data
                pet_data[species_key] = species_data
                save_pet_data(pet_data)

                st.success(f"✅ Species '{species_name}' saved successfully!")
                st.rerun()


def launch_app() -> None:
    main()


if __name__ == "__main__":
    main()
