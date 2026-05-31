from __future__ import annotations

import streamlit as st
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from agent import generate_diagnostic_report
import pdfplumber


PET_MONITORING_PATH = Path("pet_monitoring.json")
PET_UPDATES_PATH = Path("pet_updates.json")
CARE_PDF_DIR = Path("pdf_guides/care")
MEDICAL_PDF_DIR = Path("pdf_guides/medical")
EXTRACTED_DIR = Path("extracted_data")


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


def normalize_species_key(species_name: str) -> str:
    """Normalize a species name for dictionary and file lookups."""
    return species_name.lower().strip()


def display_species_name(species_key: str, species_record: dict[str, Any]) -> str:
    """Return the best display label for a species record."""
    stored_name = str(species_record.get("Species Name", "")).strip()
    if stored_name:
        return stored_name
    return species_key.replace("_", " ").title()


def species_pdf_path(species_name: str) -> Path:
    """Build the expected PDF path for a species guide."""
    species_key = normalize_species_key(species_name).replace(" ", "_")
    return CARE_PDF_DIR / f"{species_key}.pdf"


def safe_session_key(prefix: str, species_name: str) -> str:
    """Create a stable Streamlit session key for a species row."""
    slug = re.sub(r"[^a-zA-Z0-9_]+", "_", normalize_species_key(species_name).replace(" ", "_"))
    return f"{prefix}_{slug}"


def load_pet_monitoring_data() -> list[dict[str, Any]]:
    """Load the pet database table data."""
    if not PET_MONITORING_PATH.exists():
        return []

    try:
        data = json.loads(PET_MONITORING_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]

    if isinstance(data, dict):
        pets = data.get("pets")
        if isinstance(pets, list):
            return [record for record in pets if isinstance(record, dict)]

    return []


def save_pet_monitoring_data(data: list[dict[str, Any]]) -> None:
    """Save the pet database table data."""
    PET_MONITORING_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_pet_updates_data() -> list[dict[str, Any]]:
    """Load the pet monitoring update-history table data."""
    if not PET_UPDATES_PATH.exists():
        return []

    try:
        data = json.loads(PET_UPDATES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]

    if isinstance(data, dict):
        updates = data.get("updates")
        if isinstance(updates, list):
            return [record for record in updates if isinstance(record, dict)]

    return []


def save_pet_updates_data(data: list[dict[str, Any]]) -> None:
    """Save the pet monitoring update-history table data."""
    PET_UPDATES_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_species_pdf(species: str) -> Path | None:
    """Find the care PDF guide for a species in the care folder."""
    if not CARE_PDF_DIR.exists():
        return None

    species_normalized = species.lower().replace(" ", "_")

    for pdf_file in CARE_PDF_DIR.glob("*.pdf"):
        if species_normalized in pdf_file.stem.lower():
            return pdf_file

    return None


def find_species_medical_pdf(species: str) -> Path | None:
    """Find the medical PDF guide for a species in the medical folder."""
    if not MEDICAL_PDF_DIR.exists():
        return None

    species_normalized = species.lower().replace(" ", "_")

    for pdf_file in MEDICAL_PDF_DIR.glob("*.pdf"):
        if species_normalized in pdf_file.stem.lower():
            return pdf_file

    return None


def species_medical_pdf_path(species_name: str) -> Path:
    species_key = normalize_species_key(species_name).replace(" ", "_")
    return MEDICAL_PDF_DIR / f"{species_key}.pdf"


def extract_pdf_to_json(pdf_path: Path, out_json_path: Path, species_name: str, kind: str) -> None:
    """Extract text from a PDF and save structured JSON with pages and full_text."""
    try:
        EXTRACTED_DIR.mkdir(exist_ok=True)
        if not pdf_path.exists():
            return

        pages: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                raw = page.extract_text() or ""
                # Split into lines and intelligently join them to preserve sentence flow
                lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                joined_lines: list[str] = []
                buffer = ""
                for ln in lines:
                    # Handle hyphenated word at line end: join without space
                    if buffer.endswith("-"):
                        buffer = buffer[:-1] + ln
                        continue

                    if not buffer:
                        buffer = ln
                        continue

                    # If buffer ends with sentence-ending punctuation, start new line
                    if re.search(r"[\.\!\?\:\;\)\]\"\'\’\”]\s*$", buffer):
                        joined_lines.append(buffer)
                        buffer = ln
                    else:
                        # Otherwise join with a space to preserve flow
                        buffer = buffer + " " + ln

                if buffer:
                    joined_lines.append(buffer)

                # Normalize whitespace within the joined page text
                text = re.sub(r"\s+", " ", "\n\n".join(joined_lines)).strip()
                pages.append(text)

        full_text = "\n\n".join([p for p in pages if p])

        data = {
            "Species": species_name,
            "type": kind,
            "pages": pages,
            "full_text": full_text,
        }

        out_json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        # Extraction is best-effort; don't crash app on failure
        return


def render_pet_monitoring_section() -> None:
    """Render the pet database table and add-pet form."""
    if "show_add_pet_form" not in st.session_state:
        st.session_state.show_add_pet_form = False
    if "edit_pet_index" not in st.session_state:
        st.session_state.edit_pet_index = None

    header_col, button_col = st.columns([5, 1])
    with header_col:
        st.header("Pet Database")
        st.markdown("Track every pet in one place. Status will be filled in later.")

    with button_col:
        toggle_label = "Hide Form" if st.session_state.show_add_pet_form else "Add Pet"
        if st.button(toggle_label, use_container_width=True, key="toggle_add_pet_form"):
            st.session_state.show_add_pet_form = not st.session_state.show_add_pet_form
            st.session_state.edit_pet_index = None

    st.markdown("---")

    pet_records = load_pet_monitoring_data()
    species_data = load_pet_data()
    available_species = sorted(
        {
            display_species_name(species_key, species_record)
            for species_key, species_record in species_data.items()
            if display_species_name(species_key, species_record).strip()
        }
    )

    # Show add pet form
    if st.session_state.show_add_pet_form:
        with st.form(key="add_pet_form"):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                if available_species:
                    pet_species = st.selectbox(
                        "Pet Species",
                        options=available_species,
                        key="pet_species_dropdown",
                    )
                else:
                    st.selectbox(
                        "Pet Species",
                        options=["No species available"],
                        key="pet_species_dropdown_empty",
                        disabled=True,
                    )
                    pet_species = ""
                pet_name = st.text_input(
                    "Pet Name",
                    placeholder="e.g., Nova",
                    key="pet_name",
                )

            with form_col2:
                gender = st.selectbox(
                    "Gender",
                    options=["Male", "Female"],
                    key="pet_gender",
                )
                certificate_number = st.text_input(
                    "Certificate Number (Optional)",
                    placeholder="Optional certificate number",
                    key="pet_certificate_number",
                )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                cancel_pet = st.form_submit_button("Cancel", use_container_width=True, key="cancel_add_pet")
            with button_col2:
                submit_pet = st.form_submit_button("Save Pet", use_container_width=True, key="submit_add_pet")

        if cancel_pet:
            st.session_state.show_add_pet_form = False
            st.rerun()

        if submit_pet:
            if not available_species:
                st.error("ERROR: Add at least one species in Species Database first.")
            elif not pet_species.strip():
                st.error("ERROR: Pet Species is required.")
            elif not pet_name.strip():
                st.error("ERROR: Pet Name is required.")
            else:
                new_record: dict[str, Any] = {
                    "Pet Species": pet_species.strip(),
                    "Pet Name": pet_name.strip(),
                    "Gender": gender,
                    "Certificate Number": certificate_number.strip(),
                }

                pet_records.append(new_record)
                save_pet_monitoring_data(pet_records)
                st.session_state.show_add_pet_form = False
                st.success("SUCCESS: Pet added to the monitoring table.")
                st.rerun()

    # Show edit pet form
    if st.session_state.edit_pet_index is not None:
        edit_idx = st.session_state.edit_pet_index
        edit_pet = pet_records[edit_idx]
        
        st.subheader(f"Edit Pet: {edit_pet.get('Pet Name', 'Unknown')}")
        
        with st.form(key="edit_pet_form"):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                current_species = str(edit_pet.get("Pet Species", "")).strip()
                species_options_edit = list(available_species)
                if current_species and current_species not in species_options_edit:
                    species_options_edit.append(current_species)

                if species_options_edit:
                    selected_species_index = (
                        species_options_edit.index(current_species)
                        if current_species in species_options_edit
                        else 0
                    )
                    pet_species_edit = st.selectbox(
                        "Pet Species",
                        options=species_options_edit,
                        index=selected_species_index,
                        key="pet_species_edit_dropdown",
                    )
                else:
                    st.selectbox(
                        "Pet Species",
                        options=["No species available"],
                        key="pet_species_edit_dropdown_empty",
                        disabled=True,
                    )
                    pet_species_edit = ""
                pet_name_edit = st.text_input(
                    "Pet Name",
                    value=edit_pet.get("Pet Name", ""),
                    key="pet_name_edit",
                )

            with form_col2:
                gender_edit = st.selectbox(
                    "Gender",
                    options=["Male", "Female"],
                    index=0 if edit_pet.get("Gender") == "Male" else 1,
                    key="pet_gender_edit",
                )
                certificate_number_edit = st.text_input(
                    "Certificate Number (Optional)",
                    value=edit_pet.get("Certificate Number", ""),
                    key="pet_certificate_number_edit",
                )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                cancel_edit = st.form_submit_button("Cancel", use_container_width=True, key="cancel_edit_pet")
            with button_col2:
                submit_edit = st.form_submit_button("Save Changes", use_container_width=True, key="submit_edit_pet")

        if cancel_edit:
            st.session_state.edit_pet_index = None
            st.rerun()

        if submit_edit:
            if not pet_species_edit.strip():
                st.error("ERROR: Pet Species is required.")
            elif not pet_name_edit.strip():
                st.error("ERROR: Pet Name is required.")
            else:
                pet_records[edit_idx] = {
                    "Pet Species": pet_species_edit.strip(),
                    "Pet Name": pet_name_edit.strip(),
                    "Gender": gender_edit,
                    "Certificate Number": certificate_number_edit.strip(),
                }
                save_pet_monitoring_data(pet_records)
                st.session_state.edit_pet_index = None
                st.success("SUCCESS: Pet updated.")
                st.rerun()

    # Check for any pending delete confirmations and display at top with buttons
    for i in range(len(pet_records)):
        if st.session_state.get(f"confirm_delete_{i}", False):
            pet_name = pet_records[i].get('Pet Name', 'this pet')
            st.warning(f"Are you sure you want to delete '{pet_name}'?")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                if st.button("Cancel", use_container_width=True, key=f"cancel_delete_{i}"):
                    st.session_state[f"confirm_delete_{i}"] = False
                    st.rerun()
            with confirm_cols[1]:
                if st.button("Delete", use_container_width=True, key=f"confirm_delete_btn_{i}"):
                    pet_records.pop(i)
                    save_pet_monitoring_data(pet_records)
                    st.session_state[f"confirm_delete_{i}"] = False
                    st.success("Pet deleted successfully.")
                    st.rerun()
            break

    # Display table with actions
    if pet_records:
        # Display table header
        header_cols = st.columns([1.2, 2.2, 2.0, 1.4, 1.2])
        with header_cols[0]:
            st.markdown("**Actions**")
        with header_cols[1]:
            st.markdown("**Pet Species**")
        with header_cols[2]:
            st.markdown("**Pet Name**")
        with header_cols[3]:
            st.markdown("**Gender**")
        with header_cols[4]:
            st.markdown("**Certificate Number**")
        # Display each pet as a row with action buttons
        for idx, record in enumerate(pet_records):
            row_cols = st.columns([1.2, 2.2, 2.0, 1.4, 1.2])
            
            with row_cols[0]:
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button("✏️", key=f"edit_btn_{idx}", help="Edit", use_container_width=True):
                        st.session_state.edit_pet_index = idx
                        st.rerun()
                with action_cols[1]:
                    if st.button("🗑️", key=f"delete_btn_{idx}", help="Delete", use_container_width=True):
                        confirm_key = f"confirm_delete_{idx}"
                        st.session_state[confirm_key] = True
                        st.rerun()
            
            with row_cols[1]:
                st.text(record.get("Pet Species", ""))
            with row_cols[2]:
                st.text(record.get("Pet Name", ""))
            with row_cols[3]:
                st.text(record.get("Gender", ""))
            with row_cols[4]:
                st.text(record.get("Certificate Number", ""))
    else:
        st.info("No pets have been added yet. Use Add Pet to start monitoring.")


def render_pet_updates_section() -> None:
    """Render pet update-history section for tracking growth over time."""
    if "show_update_pet_form" not in st.session_state:
        st.session_state.show_update_pet_form = False
    if "edit_update_index" not in st.session_state:
        st.session_state.edit_update_index = None

    header_col, button_col = st.columns([5, 1])
    with header_col:
        st.header("Pet Monitoring")
        st.markdown("Track growth and improvements by saving timestamped pet updates.")

    with button_col:
        toggle_label = "Hide Form" if st.session_state.show_update_pet_form else "Update"
        if st.button(toggle_label, use_container_width=True, key="toggle_update_pet_form"):
            st.session_state.show_update_pet_form = not st.session_state.show_update_pet_form
            st.session_state.edit_update_index = None

    st.markdown("---")

    pet_records = load_pet_monitoring_data()
    update_records = load_pet_updates_data()

    pet_options = [
        f"{record.get('Pet Name', '').strip()} ({record.get('Pet Species', '').strip()})"
        for record in pet_records
    ]
    pet_options = [option for option in pet_options if option.strip()]

    monitor_options = ["All Pets", *pet_options] if pet_options else ["All Pets"]
    selected_monitor_pet = st.selectbox(
        "Choose Pet to Monitor",
        options=monitor_options,
        key="monitor_pet_filter",
    )

    def update_record_label(record: dict[str, Any]) -> str:
        label = str(record.get("Pet Label", "")).strip()
        if label:
            return label
        pet_name = str(record.get("Pet Name", "")).strip()
        pet_species = str(record.get("Pet Species", "")).strip()
        if pet_name and pet_species:
            return f"{pet_name} ({pet_species})"
        return ""

    if st.session_state.show_update_pet_form:
        if not pet_records:
            st.warning("Add at least one pet in the Pet Database tab before creating updates.")
        else:
            if not pet_options:
                st.warning("No valid pets found to update. Add a pet with species and name first.")
            else:
                with st.form(key="update_pet_form"):
                    selected_pet = st.selectbox(
                        "Select Pet to Update",
                        options=pet_options,
                        key="selected_pet_update",
                    )
                    selected_index = pet_options.index(selected_pet)
                    selected_record = pet_records[selected_index]

                    form_col1, form_col2 = st.columns(2)

                    with form_col1:
                        pet_weight = st.text_input(
                            "Pet Weight (g)",
                            value=selected_record.get("Pet Weight", ""),
                            key="update_pet_weight",
                        )
                        pet_width = st.text_input(
                            "Pet Width (Inches)",
                            value=selected_record.get("Pet Width", ""),
                            key="update_pet_width",
                        )
                        pet_height = st.text_input(
                            "Pet Height (Inches)",
                            value=selected_record.get("Pet Height", ""),
                            key="update_pet_height",
                        )

                    with form_col2:

                        morph = st.text_input(
                            "Morph (Optional)",
                            value=selected_record.get("Morph", ""),
                            key="update_pet_morph",
                        )
                        color = st.text_input(
                            "Color (Optional)",
                            value=selected_record.get("Color", ""),
                            key="update_pet_color",
                        )
                        status = st.text_input(
                            "Status",
                            value=selected_record.get("Status", "N/A"),
                            key="update_pet_status",
                        )

                    button_col1, button_col2 = st.columns(2)
                    with button_col1:
                        cancel_update = st.form_submit_button(
                            "Cancel",
                            use_container_width=True,
                            key="cancel_update_pet",
                        )
                    with button_col2:
                        submit_update = st.form_submit_button(
                            "Save Update",
                            use_container_width=True,
                            key="submit_update_pet",
                        )

                if cancel_update:
                    st.session_state.show_update_pet_form = False
                    st.rerun()

                if submit_update:
                    if not pet_weight.strip():
                        st.error("ERROR: Pet Weight is required.")
                    else:
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        updated_pet_record: dict[str, Any] = {
                            "Pet Species": selected_record.get("Pet Species", "").strip(),
                            "Pet Name": selected_record.get("Pet Name", "").strip(),
                            "Pet Weight": pet_weight.strip(),
                            "Pet Width": pet_width.strip(),
                            "Pet Height": pet_height.strip(),
                            "Gender": selected_record.get("Gender", ""),
                            "Morph": morph.strip(),
                            "Color": color.strip(),
                            "Certificate Number": selected_record.get("Certificate Number", ""),
                            "Status": status.strip() if status.strip() else "N/A",
                        }

                        pet_records[selected_index] = updated_pet_record
                        save_pet_monitoring_data(pet_records)

                        update_record = {
                            "Pet Weight": updated_pet_record["Pet Weight"],
                            "Pet Width": updated_pet_record["Pet Width"],
                            "Pet Height": updated_pet_record["Pet Height"],
                            "Morph": updated_pet_record["Morph"],
                            "Color": updated_pet_record["Color"],
                            "Status": updated_pet_record["Status"],
                            "Pet Label": selected_pet,
                            "Time & Date": timestamp,
                        }
                        update_records.append(update_record)
                        save_pet_updates_data(update_records)

                        st.session_state.show_update_pet_form = False
                        st.success("SUCCESS: Pet update saved.")
                        st.rerun()

    edit_update_index = st.session_state.edit_update_index
    if edit_update_index is not None and 0 <= edit_update_index < len(update_records):
        edit_record = update_records[edit_update_index]
        st.subheader(f"Edit Monitoring Record: {edit_record.get('Time & Date', 'Unknown Time')}")

        with st.form(key="edit_update_record_form"):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                edit_weight = st.text_input(
                    "Pet Weight (g)",
                    value=edit_record.get("Pet Weight", ""),
                    key="edit_update_weight",
                )
                edit_width = st.text_input(
                    "Pet Width (Inches)",
                    value=edit_record.get("Pet Width", ""),
                    key="edit_update_width",
                )
                edit_height = st.text_input(
                    "Pet Height (Inches)",
                    value=edit_record.get("Pet Height", ""),
                    key="edit_update_height",
                )

            with form_col2:
                edit_morph = st.text_input(
                    "Morph (Optional)",
                    value=edit_record.get("Morph", ""),
                    key="edit_update_morph",
                )
                edit_color = st.text_input(
                    "Color (Optional)",
                    value=edit_record.get("Color", ""),
                    key="edit_update_color",
                )
                edit_status = st.text_input(
                    "Status",
                    value=edit_record.get("Status", "N/A"),
                    key="edit_update_status",
                )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                cancel_edit_update = st.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                    key="cancel_edit_update",
                )
            with button_col2:
                save_edit_update = st.form_submit_button(
                    "Save Changes",
                    use_container_width=True,
                    key="save_edit_update",
                )

        if cancel_edit_update:
            st.session_state.edit_update_index = None
            st.rerun()

        if save_edit_update:
            if not edit_weight.strip():
                st.error("ERROR: Pet Weight is required.")
            else:
                update_records[edit_update_index] = {
                    **edit_record,
                    "Pet Weight": edit_weight.strip(),
                    "Pet Width": edit_width.strip(),
                    "Pet Height": edit_height.strip(),
                    "Morph": edit_morph.strip(),
                    "Color": edit_color.strip(),
                    "Status": edit_status.strip() if edit_status.strip() else "N/A",
                    "Time & Date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                save_pet_updates_data(update_records)
                st.session_state.edit_update_index = None
                st.success("SUCCESS: Monitoring record updated.")
                st.rerun()

    for i in range(len(update_records)):
        if st.session_state.get(f"confirm_delete_update_{i}", False):
            update_time = update_records[i].get("Time & Date", "this update")
            st.warning(f"Are you sure you want to delete update '{update_time}'?")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                if st.button("Cancel", use_container_width=True, key=f"cancel_delete_update_{i}"):
                    st.session_state[f"confirm_delete_update_{i}"] = False
                    st.rerun()
            with confirm_cols[1]:
                if st.button("Delete", use_container_width=True, key=f"confirm_delete_update_btn_{i}"):
                    update_records.pop(i)
                    save_pet_updates_data(update_records)
                    st.session_state[f"confirm_delete_update_{i}"] = False
                    st.success("Update deleted successfully.")
                    st.rerun()
            break

    filtered_update_records: list[tuple[int, dict[str, Any]]] = [
        (idx, record)
        for idx, record in enumerate(update_records)
        if selected_monitor_pet == "All Pets" or update_record_label(record) == selected_monitor_pet
    ]

    if filtered_update_records:
        header_cols = st.columns([1.4, 1.3, 1.3, 1.3, 1.2, 1.2, 1.2, 1.8])
        with header_cols[0]:
            st.markdown("**Actions**")
        with header_cols[1]:
            st.markdown("**Weight (g)**")
        with header_cols[2]:
            st.markdown("**Width (in)**")
        with header_cols[3]:
            st.markdown("**Height (in)**")
        with header_cols[4]:
            st.markdown("**Morph**")
        with header_cols[5]:
            st.markdown("**Color**")
        with header_cols[6]:
            st.markdown("**Status**")
        with header_cols[7]:
            st.markdown("**Time & Date**")

        for display_idx, record in reversed(filtered_update_records):
            row_cols = st.columns([1.4, 1.3, 1.3, 1.3, 1.2, 1.2, 1.2, 1.8])

            with row_cols[0]:
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button("✏️", key=f"edit_update_btn_{display_idx}", help="Edit", use_container_width=True):
                        st.session_state.edit_update_index = display_idx
                        st.rerun()
                with action_cols[1]:
                    if st.button("🗑️", key=f"delete_update_btn_{display_idx}", help="Delete", use_container_width=True):
                        st.session_state[f"confirm_delete_update_{display_idx}"] = True
                        st.rerun()

            with row_cols[1]:
                st.text(record.get("Pet Weight", ""))
            with row_cols[2]:
                st.text(record.get("Pet Width", ""))
            with row_cols[3]:
                st.text(record.get("Pet Height", ""))
            with row_cols[4]:
                st.text(record.get("Morph", ""))
            with row_cols[5]:
                st.text(record.get("Color", ""))
            with row_cols[6]:
                st.text(record.get("Status", ""))
            with row_cols[7]:
                st.text(record.get("Time & Date", ""))
    else:
        if update_records:
            st.info("No monitoring updates for the selected pet.")
        else:
            st.info("No pet updates yet. Use Update to start tracking growth history.")


def render_species_database_section() -> None:
    """Render the species database table and add/edit forms."""
    if "show_add_species_form" not in st.session_state:
        st.session_state.show_add_species_form = False
    if "edit_species_key" not in st.session_state:
        st.session_state.edit_species_key = None

    header_col, button_col = st.columns([5, 1])
    with header_col:
        st.header("Species Database")
        st.markdown("Manage species care standards, PDF guides, and notes in one place.")

    with button_col:
        toggle_label = "Hide Form" if st.session_state.show_add_species_form else "Add Species"
        if st.button(toggle_label, use_container_width=True, key="toggle_add_species_form"):
            st.session_state.show_add_species_form = not st.session_state.show_add_species_form
            st.session_state.edit_species_key = None

    st.markdown("---")

    pet_data = load_pet_data()

    def get_species_items() -> list[tuple[str, dict[str, Any]]]:
        return sorted(
            pet_data.items(),
            key=lambda item: display_species_name(item[0], item[1]).lower(),
        )

    if st.session_state.show_add_species_form:
        with st.form(key="add_species_form"):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                species_name = st.text_input(
                    "Species Name",
                    placeholder="e.g., Bearded Dragon",
                    key="species_name",
                )
                pdf_file = st.file_uploader(
                    "PDF Care Guide (Optional)",
                    type="pdf",
                    key="pdf_guide",
                )
                pdf_medical_file = st.file_uploader(
                    "PDF Medical Guide (Optional)",
                    type="pdf",
                    key="pdf_medical_guide",
                )
                temp_min = st.number_input("Temperature Minimum (°C)", value=None, step=0.1, key="temp_min")
                temp_max = st.number_input("Temperature Maximum (°C)", value=None, step=0.1, key="temp_max")
                basking_temp_min = st.number_input(
                    "Basking Temperature Minimum (°C)",
                    value=None,
                    step=0.1,
                    key="basking_temp_min",
                )
                basking_temp_max = st.number_input(
                    "Basking Temperature Maximum (°C)",
                    value=None,
                    step=0.1,
                    key="basking_temp_max",
                )

            with form_col2:
                humidity_min = st.number_input("Humidity Minimum (%)", value=None, step=0.1, key="humidity_min")
                humidity_max = st.number_input("Humidity Maximum (%)", value=None, step=0.1, key="humidity_max")
                uvb_min = st.number_input("UVB Minimum (hours/day)", value=None, step=0.1, key="uvb_min")
                uvb_max = st.number_input("UVB Maximum (hours/day)", value=None, step=0.1, key="uvb_max")
                nighttime_temp = st.number_input(
                    "Night Time Temperature (°C)",
                    value=None,
                    step=0.1,
                    key="nighttime_temp",
                )

            st.markdown("---")
            st.subheader("Text Parameters")

            diet = st.text_area("Diet", height=80, placeholder="Describe the recommended diet...", key="diet")
            feeding_notes = st.text_area(
                "Feeding Notes",
                height=80,
                placeholder="Special feeding guidelines...",
                key="feeding_notes",
            )
            uvb_notes = st.text_area("UVB Notes", height=80, placeholder="UVB lighting requirements...", key="uvb_notes")
            substrate = st.text_area(
                "Substrate",
                height=80,
                placeholder="Recommended substrate composition...",
                key="substrate",
            )
            other_care = st.text_area(
                "Other Care",
                height=80,
                placeholder="Additional care guidelines (lifespan, housing, etc.)...",
                key="other_care",
            )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                cancel_species = st.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                    key="cancel_add_species",
                )
            with button_col2:
                submit_species = st.form_submit_button(
                    "Save Species",
                    use_container_width=True,
                    key="submit_add_species",
                )

        if cancel_species:
            st.session_state.show_add_species_form = False
            st.rerun()

        if submit_species:
            if not species_name.strip():
                st.error("ERROR: Species Name is required.")
            else:
                species_key = normalize_species_key(species_name)
                species_data: dict[str, Any] = {"Species Name": species_name.strip()}

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

                if pdf_file is not None:
                    CARE_PDF_DIR.mkdir(parents=True, exist_ok=True)
                    pdf_path = species_pdf_path(species_name)
                    pdf_path.write_bytes(pdf_file.read())
                    # extract to JSON
                    extract_pdf_to_json(pdf_path, EXTRACTED_DIR / f"{normalize_species_key(species_name)}_care.json", species_name, "care")

                if pdf_medical_file is not None:
                    MEDICAL_PDF_DIR.mkdir(parents=True, exist_ok=True)
                    med_pdf_path = species_medical_pdf_path(species_name)
                    med_pdf_path.write_bytes(pdf_medical_file.read())
                    extract_pdf_to_json(med_pdf_path, EXTRACTED_DIR / f"{normalize_species_key(species_name)}_medical.json", species_name, "medical")

                pet_data[species_key] = species_data
                save_pet_data(pet_data)
                st.session_state.show_add_species_form = False
                st.success("SUCCESS: Species added to the database.")
                st.rerun()

    edit_species_key = st.session_state.edit_species_key
    if edit_species_key is not None and edit_species_key in pet_data:
        edit_species = pet_data[edit_species_key]
        edit_species_name = display_species_name(edit_species_key, edit_species)

        st.subheader(f"Edit Species: {edit_species_name}")

        with st.form(key="edit_species_form"):
            form_col1, form_col2 = st.columns(2)

            with form_col1:
                species_name_edit = st.text_input(
                    "Species Name",
                    value=edit_species_name,
                    key="species_name_edit",
                )
                pdf_file_edit = st.file_uploader(
                    "Replace PDF Care Guide (Optional)",
                    type="pdf",
                    key="pdf_guide_edit",
                )
                pdf_medical_file_edit = st.file_uploader(
                    "Replace PDF Medical Guide (Optional)",
                    type="pdf",
                    key="pdf_medical_guide_edit",
                )
                temp_min_edit = st.number_input(
                    "Temperature Minimum (°C)",
                    value=edit_species.get("temp_min"),
                    step=0.1,
                    key="temp_min_edit",
                )
                temp_max_edit = st.number_input(
                    "Temperature Maximum (°C)",
                    value=edit_species.get("temp_max"),
                    step=0.1,
                    key="temp_max_edit",
                )
                basking_temp_min_edit = st.number_input(
                    "Basking Temperature Minimum (°C)",
                    value=edit_species.get("basking_temp_min"),
                    step=0.1,
                    key="basking_temp_min_edit",
                )
                basking_temp_max_edit = st.number_input(
                    "Basking Temperature Maximum (°C)",
                    value=edit_species.get("basking_temp_max"),
                    step=0.1,
                    key="basking_temp_max_edit",
                )

            with form_col2:
                humidity_min_edit = st.number_input(
                    "Humidity Minimum (%)",
                    value=edit_species.get("humidity_min"),
                    step=0.1,
                    key="humidity_min_edit",
                )
                humidity_max_edit = st.number_input(
                    "Humidity Maximum (%)",
                    value=edit_species.get("humidity_max"),
                    step=0.1,
                    key="humidity_max_edit",
                )
                uvb_min_edit = st.number_input(
                    "UVB Minimum (hours/day)",
                    value=edit_species.get("uvb_min"),
                    step=0.1,
                    key="uvb_min_edit",
                )
                uvb_max_edit = st.number_input(
                    "UVB Maximum (hours/day)",
                    value=edit_species.get("uvb_max"),
                    step=0.1,
                    key="uvb_max_edit",
                )
                nighttime_temp_edit = st.number_input(
                    "Night Time Temperature (°C)",
                    value=edit_species.get("nighttime_temp"),
                    step=0.1,
                    key="nighttime_temp_edit",
                )

            st.markdown("---")
            st.subheader("Text Parameters")

            diet_edit = st.text_area("Diet", value=str(edit_species.get("diet", "")), height=80, key="diet_edit")
            feeding_notes_edit = st.text_area(
                "Feeding Notes",
                value=str(edit_species.get("feeding_notes", "")),
                height=80,
                key="feeding_notes_edit",
            )
            uvb_notes_edit = st.text_area(
                "UVB Notes",
                value=str(edit_species.get("uvb_notes", "")),
                height=80,
                key="uvb_notes_edit",
            )
            substrate_edit = st.text_area(
                "Substrate",
                value=str(edit_species.get("substrate", "")),
                height=80,
                key="substrate_edit",
            )
            other_care_edit = st.text_area(
                "Other Care",
                value=str(edit_species.get("other_care", "")),
                height=80,
                key="other_care_edit",
            )

            button_col1, button_col2 = st.columns(2)
            with button_col1:
                cancel_edit = st.form_submit_button("Cancel", use_container_width=True, key="cancel_edit_species")
            with button_col2:
                submit_edit = st.form_submit_button("Save Changes", use_container_width=True, key="submit_edit_species")

        if cancel_edit:
            st.session_state.edit_species_key = None
            st.rerun()

        if submit_edit:
            if not species_name_edit.strip():
                st.error("ERROR: Species Name is required.")
            else:
                new_species_key = normalize_species_key(species_name_edit)
                updated_species: dict[str, Any] = {"Species Name": species_name_edit.strip()}

                if temp_min_edit is not None:
                    updated_species["temp_min"] = float(temp_min_edit)
                if temp_max_edit is not None:
                    updated_species["temp_max"] = float(temp_max_edit)
                if basking_temp_min_edit is not None:
                    updated_species["basking_temp_min"] = float(basking_temp_min_edit)
                if basking_temp_max_edit is not None:
                    updated_species["basking_temp_max"] = float(basking_temp_max_edit)
                if humidity_min_edit is not None:
                    updated_species["humidity_min"] = float(humidity_min_edit)
                if humidity_max_edit is not None:
                    updated_species["humidity_max"] = float(humidity_max_edit)
                if uvb_min_edit is not None:
                    updated_species["uvb_min"] = float(uvb_min_edit)
                if uvb_max_edit is not None:
                    updated_species["uvb_max"] = float(uvb_max_edit)
                if nighttime_temp_edit is not None:
                    updated_species["nighttime_temp"] = float(nighttime_temp_edit)

                if diet_edit.strip():
                    updated_species["diet"] = diet_edit.strip()
                if feeding_notes_edit.strip():
                    updated_species["feeding_notes"] = feeding_notes_edit.strip()
                if uvb_notes_edit.strip():
                    updated_species["uvb_notes"] = uvb_notes_edit.strip()
                if substrate_edit.strip():
                    updated_species["substrate"] = substrate_edit.strip()
                if other_care_edit.strip():
                    updated_species["other_care"] = other_care_edit.strip()

                if pdf_file_edit is not None:
                    CARE_PDF_DIR.mkdir(parents=True, exist_ok=True)
                    pdf_path = species_pdf_path(species_name_edit)
                    pdf_path.write_bytes(pdf_file_edit.read())
                    extract_pdf_to_json(pdf_path, EXTRACTED_DIR / f"{normalize_species_key(species_name_edit)}_care.json", species_name_edit, "care")
                elif new_species_key != edit_species_key:
                    old_pdf = find_species_pdf(edit_species_name)
                    if old_pdf and old_pdf.exists():
                        new_pdf = species_pdf_path(species_name_edit)
                        if not new_pdf.exists():
                            try:
                                old_pdf.rename(new_pdf)
                            except OSError:
                                pass

                if pdf_medical_file_edit is not None:
                    MEDICAL_PDF_DIR.mkdir(parents=True, exist_ok=True)
                    med_pdf_path = species_medical_pdf_path(species_name_edit)
                    med_pdf_path.write_bytes(pdf_medical_file_edit.read())
                    extract_pdf_to_json(med_pdf_path, EXTRACTED_DIR / f"{normalize_species_key(species_name_edit)}_medical.json", species_name_edit, "medical")
                elif new_species_key != edit_species_key:
                    old_med_pdf = find_species_medical_pdf(edit_species_name)
                    if old_med_pdf and old_med_pdf.exists():
                        new_med_pdf = species_medical_pdf_path(species_name_edit)
                        if not new_med_pdf.exists():
                            try:
                                old_med_pdf.rename(new_med_pdf)
                            except OSError:
                                pass

                if new_species_key != edit_species_key:
                    del pet_data[edit_species_key]
                pet_data[new_species_key] = updated_species
                save_pet_data(pet_data)
                st.session_state.edit_species_key = None
                st.success("SUCCESS: Species updated.")
                st.rerun()

    for species_key, species_record in get_species_items():
        confirm_key = safe_session_key("confirm_delete_species", species_key)
        if st.session_state.get(confirm_key, False):
            species_name = display_species_name(species_key, species_record)
            st.warning(f"Are you sure you want to delete '{species_name}'?")
            confirm_cols = st.columns(2)
            with confirm_cols[0]:
                if st.button(
                    "Cancel",
                    use_container_width=True,
                    key=safe_session_key("cancel_delete_species", species_key),
                ):
                    st.session_state[confirm_key] = False
                    st.rerun()
            with confirm_cols[1]:
                if st.button(
                    "Delete",
                    use_container_width=True,
                    key=safe_session_key("confirm_delete_species_btn", species_key),
                ):
                    pet_data.pop(species_key, None)
                    save_pet_data(pet_data)
                    st.session_state[confirm_key] = False
                    st.success("Species deleted successfully.")
                    st.rerun()
            break

    species_items = get_species_items()

    if species_items:
        header_cols = st.columns([1.8, 1.8, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.5, 1.5, 1.5, 1.5, 1.5, 1.0])
        headers = [
            "Actions",
            "Species Name",
            "Temp Min",
            "Temp Max",
            "Bask Min",
            "Bask Max",
            "Hum Min",
            "Hum Max",
            "UVB Min",
            "UVB Max",
            "Night Temp",
            "Diet",
            "Feeding Notes",
            "UVB Notes",
            "Substrate",
            "Other Care",
            "PDF",
        ]

        for column, header in zip(header_cols, headers, strict=False):
            with column:
                st.markdown(f"**{header}**")

        for species_key, species_record in species_items:
            row_cols = st.columns([1.8, 1.8, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 0.9, 1.5, 1.5, 1.5, 1.5, 1.5, 1.0])
            species_name = display_species_name(species_key, species_record)
            pdf_exists = species_pdf_path(species_name).exists() or species_pdf_path(species_key).exists()

            with row_cols[0]:
                action_cols = st.columns(2)
                with action_cols[0]:
                    if st.button(
                        "✏️",
                        key=safe_session_key("edit_species_btn", species_key),
                        help="Edit",
                        use_container_width=True,
                    ):
                        st.session_state.edit_species_key = species_key
                        st.session_state.show_add_species_form = False
                        st.rerun()
                with action_cols[1]:
                    if st.button(
                        "🗑️",
                        key=safe_session_key("delete_species_btn", species_key),
                        help="Delete",
                        use_container_width=True,
                    ):
                        st.session_state[safe_session_key("confirm_delete_species", species_key)] = True
                        st.rerun()

            values = [
                species_name,
                species_record.get("temp_min", ""),
                species_record.get("temp_max", ""),
                species_record.get("basking_temp_min", ""),
                species_record.get("basking_temp_max", ""),
                species_record.get("humidity_min", ""),
                species_record.get("humidity_max", ""),
                species_record.get("uvb_min", ""),
                species_record.get("uvb_max", ""),
                species_record.get("nighttime_temp", ""),
                species_record.get("diet", ""),
                species_record.get("feeding_notes", ""),
                species_record.get("uvb_notes", ""),
                species_record.get("substrate", ""),
                species_record.get("other_care", ""),
                "Yes" if pdf_exists else "No",
            ]

            for idx, value in enumerate(values, start=1):
                with row_cols[idx]:
                    if isinstance(value, (int, float)):
                        st.text(f"{value}")
                    else:
                        st.markdown(
                            f"<div style='white-space: pre-wrap; font-size: 0.92rem;'>{value if value not in (None, '') else ''}</div>",
                            unsafe_allow_html=True,
                        )
    else:
        st.info("No species have been added yet. Use Add Species to start building the database.")


def main() -> None:
    st.set_page_config(page_title="HerpGuard AI", layout="wide", initial_sidebar_state="collapsed")

    # Hide the header and adjust layout
    st.markdown(
        """
        <style>
        [data-testid="stAppHeader"] {
            display: none !important;
        }
        header {
            display: none !important;
        }
        .stAppHeader {
            display: none !important;
        }
        /* Adjust top padding of main container (modify the value in px) */
        [data-testid="stMainBlockContainer"] {
            padding-top: 0px !important;
        }
        
        /* Button styling */
        /* White buttons for regular actions (edit/delete) */
        [data-testid="stButton"] button {
            background-color: #ffffff !important;
            color: #262730 !important;
            border: 1px solid #d3d3d3 !important;
        }
        [data-testid="stButton"] button:hover {
            background-color: #f0f0f0 !important;
            border-color: #808080 !important;
        }

        [data-testid="stHorizontalBlock"] {
            gap: 5px !important;
            padding-right: 20px !important;
        }
        
        /* Green default for save actions */
        button[data-testid="FormSubmitButton"] {
            background-color: #28a745 !important;
            color: white !important;
        }
        button[data-testid="FormSubmitButton"]:hover {
            background-color: #218838 !important;
        }
        
        /* Red buttons for first button in form columns (Cancel buttons) */
        form button[data-testid="FormSubmitButton"]:nth-of-type(odd) {
            background-color: #dc3545 !important;
            color: white !important;
        }
        form button[data-testid="FormSubmitButton"]:nth-of-type(odd):hover {
            background-color: #c82333 !important;
        }
        
        /* Download buttons styling */
        [data-testid="stDownloadButton"] button {
            background-color: #1f77b4 !important;
            color: white !important;
        }
        [data-testid="stDownloadButton"] button:hover {
            background-color: #1560a0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    # Add custom header on top left with slogan on the right
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 20px;">
            <h1 style="margin: 0; font-size: 32px; font-weight: 600;">HerpGuard AI</h1>
            <p style="margin-top: 30px; margin-left: -30px; font-size: 14px; color: #666; font-style: italic;">AI Monitoring Assistant for Exotic Pets</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Create tabs for navigation
    tab1, tab2, tab3, tab4 = st.tabs(["Pet Monitoring", "Pet Database", "Pet Diagnostics", "Species Database"])

    # ============ TAB 1: PET MONITORING ============
    with tab1:
        render_pet_updates_section()

    # ============ TAB 2: PET DATABASE ============
    with tab2:
        render_pet_monitoring_section()

    # ============ TAB 3: DIAGNOSTICS ============
    with tab3:
        st.header("Pet Diagnostics")
        st.markdown("Enter your pet's species and observations to get care recommendations.")

        st.markdown("---")
        st.markdown("")

        with st.form(key="diagnostics_form"):
            pet_data = load_pet_data()
            available_species = sorted(
                {
                    display_species_name(species_key, species_record)
                    for species_key, species_record in pet_data.items()
                }
            )

            col1, col2 = st.columns(2)
            with col1:
                if available_species:
                    species = st.selectbox(
                        "Species",
                        options=available_species,
                        index=0,
                        key="diag_species",
                    )
                else:
                    species = ""
                    st.info("Add species to the database before running diagnostics.")

            observations = st.text_area(
                "Observations & Symptoms",
                height=150,
                placeholder="Describe your pet's current state, behavior, environment, etc.",
                key="observations"
            )

            submit_diag = st.form_submit_button("Analyze Pet", use_container_width=True)

        if submit_diag:
            if not species:
                st.error("ERROR: Please select a species.")
            elif not observations.strip():
                st.error("ERROR: Please provide observations.")
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
                    # Add Medical PDF download if exists
                    med_pdf_path = find_species_medical_pdf(species)
                    if med_pdf_path and med_pdf_path.exists():
                        med_pdf_bytes = med_pdf_path.read_bytes()
                        st.download_button(
                            label=f"📥 Download {species.title()} Medical Guide (PDF)",
                            data=med_pdf_bytes,
                            file_name=med_pdf_path.name,
                            mime="application/pdf",
                            use_container_width=True
                        )
                except RuntimeError as exc:
                    st.error(f"❌ Error: {exc}")

    # ============ TAB 4: SPECIES DATABASE ============
    with tab4:
        render_species_database_section()


def launch_app() -> None:
    main()


if __name__ == "__main__":
    main()
