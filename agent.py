from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from habitat_checker import evaluate_habitat
from pdf_extractor import extract_species_data, load_extracted_data, save_extracted_data
from prompts import SYSTEM_PROMPT


@dataclass
class ReportSections:
    summary: list[str]
    observations: list[str]
    concerns: list[str]
    recommendations: list[str]
    warning: str | None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return path.read_text(encoding="utf-8")


def _load_pet_data(path: Path) -> dict[str, Any]:
    import json

    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_pet_data(path: Path, data: dict[str, Any]) -> None:
    import json

    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _merge_standards(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for key, value in secondary.items():
        if value is not None:
            merged[key] = value
    return merged


def _get_species_key(species: str) -> str:
    return species.strip().lower()


def _build_report_sections(inputs: dict[str, str], standards: dict[str, Any]) -> ReportSections:
    evaluation = evaluate_habitat(inputs, standards)
    summary = [
        f"Species: {inputs.get('species', 'Unknown')}",
        f"Severity: {evaluation.severity}",
        evaluation.overall_status,
    ]

    observations = evaluation.observations
    concerns = evaluation.concerns
    recommendations = evaluation.recommendations
    warning = evaluation.warning

    return ReportSections(
        summary=summary,
        observations=observations,
        concerns=concerns,
        recommendations=recommendations,
        warning=warning,
    )


def _format_report(sections: ReportSections, ai_note: str | None) -> str:
    lines: list[str] = [
        "Pet Summary",
        *[f"- {item}" for item in sections.summary],
        "",
        "Observations",
        *[f"- {item}" for item in sections.observations],
        "",
        "Concerns",
        *[f"- {item}" for item in sections.concerns],
        "",
        "Recommendations",
        *[f"- {item}" for item in sections.recommendations],
        "- I am not a licensed veterinarian, and this guidance is not a diagnosis.",
    ]

    if ai_note:
        lines.extend(["", "AI Notes", f"- {ai_note}"])

    if sections.warning:
        lines.extend(["", "Warning", f"- {sections.warning}"])

    return "\n".join(lines)


def _generate_ai_notes(inputs: dict[str, str], standards: dict[str, Any], concerns: list[str]) -> str | None:
    load_dotenv()
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
    except ImportError:
        return "AI summary unavailable (LangChain not installed)."

    if not Path(".env").exists():
        return "AI summary unavailable (missing .env with OPENAI_API_KEY)."

    if not inputs.get("observations") and not concerns:
        return "AI summary skipped due to limited observation detail."

    prompt = (
        "Species: {species}\n"
        "Temperature: {temperature}\n"
        "Humidity: {humidity}\n"
        "Feeding: {feeding}\n"
        "Activity: {activity}\n"
        "Hydration: {hydration}\n"
        "Observations: {observations}\n"
        "Standards: {standards}\n"
        "Concerns: {concerns}\n"
    ).format(
        species=inputs.get("species", "Unknown"),
        temperature=inputs.get("temperature", "Unknown"),
        humidity=inputs.get("humidity", "Unknown"),
        feeding=inputs.get("feeding", "Unknown"),
        activity=inputs.get("activity", "Unknown"),
        hydration=inputs.get("hydration", "Unknown"),
        observations=inputs.get("observations", "None"),
        standards=standards or "None",
        concerns="; ".join(concerns) if concerns else "None",
    )

    model = ChatOpenAI(model="gpt-4o-mini", temperature=0.2)
    messages = [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    response = model.invoke(messages)
    return response.content.strip()


def generate_report(inputs: dict[str, str], pdf_path: str | None = None) -> str:
    species = inputs.get("species", "").strip()
    if not species:
        raise RuntimeError("Species is required for analysis.")

    data_path = Path("pet_data.json")
    extracted_path = Path("extracted_data/extracted_species_data.json")
    pet_data = _load_pet_data(data_path)
    extracted_data = load_extracted_data(extracted_path)

    if pdf_path:
        species_key, extracted = extract_species_data(pdf_path)
        if extracted:
            extracted_data[species_key] = extracted
            save_extracted_data(extracted_path, extracted_data)
            pet_data.setdefault(species_key, {})
            pet_data[species_key] = _merge_standards(pet_data[species_key], extracted)
            _save_pet_data(data_path, pet_data)

    species_key = _get_species_key(species)
    standards = pet_data.get(species_key) or extracted_data.get(species_key) or {}

    sections = _build_report_sections(inputs, standards)
    ai_note = _generate_ai_notes(inputs, standards, sections.concerns)
    return _format_report(sections, ai_note)
