from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from habitat_checker import evaluate_habitat
from pdf_extractor import (
    extract_all_species_data,
    get_guide_path,
    list_available_species,
    load_extracted_data,
    save_extracted_data,
)
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


def _ensure_species_knowledge_base() -> tuple[dict[str, Any], dict[str, Any]]:
    data_path = Path("pet_data.json")
    extracted_path = Path("extracted_data/extracted_species_data.json")

    pet_data = _load_pet_data(data_path)
    extracted_data = load_extracted_data(extracted_path)

    available_species = list_available_species()
    missing_species = []
    for species in available_species:
        species_key = _get_species_key(species)
        if species_key not in pet_data and species_key not in extracted_data:
            missing_species.append(species)

    if missing_species or (available_species and not extracted_data):
        fresh_data = extract_all_species_data()
        if fresh_data:
            extracted_data.update(fresh_data)
            save_extracted_data(extracted_path, extracted_data)

            for species_key, standards in fresh_data.items():
                pet_data[species_key] = _merge_standards(pet_data.get(species_key, {}), standards)
            _save_pet_data(data_path, pet_data)

    return pet_data, extracted_data


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


def _build_local_ai_prompt(inputs: dict[str, str], standards: dict[str, Any], concerns: list[str]) -> str:
    return (
        "You are HerpGuard, an exotic pet husbandry assistant. "
        "Write a concise, non-diagnostic summary with practical husbandry guidance. "
        "Keep it to 3-5 short sentences.\n\n"
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


def _normalize_gemini_model_name(model: str) -> str:
    name = model.strip()
    if name.startswith("models/"):
        return name[len("models/") :]
    return name


def _list_gemini_models(api_key: str) -> list[str]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    request = Request(endpoint, headers={"Content-Type": "application/json"}, method="GET")
    with urlopen(request, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    models: list[str] = []
    for item in data.get("models", []):
        methods = item.get("supportedGenerationMethods", [])
        name = str(item.get("name", "")).strip()
        if "generateContent" in methods and name.startswith("models/"):
            models.append(name[len("models/") :])
    return models


def _pick_gemini_model(configured_model: str, available_models: list[str]) -> str:
    configured = _normalize_gemini_model_name(configured_model)
    if configured and configured in available_models:
        return configured

    preferred = [
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-latest",
    ]
    for model in preferred:
        if model in available_models:
            return model

    return configured or (available_models[0] if available_models else "gemini-2.5-flash")


def _generate_gemini_notes(inputs: dict[str, str], standards: dict[str, Any], concerns: list[str]) -> str | None:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return "AI summary unavailable (Gemini API key missing)."

    configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    prompt = _build_local_ai_prompt(inputs, standards, concerns)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\n{prompt}"},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 500,
        },
    }

    available_models: list[str] = []
    try:
        available_models = _list_gemini_models(api_key)
        model = _pick_gemini_model(configured_model, available_models)
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent?key={api_key}"
        )

        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(str(part.get("text", "")) for part in parts).strip()
            if text:
                return text

        return "AI summary unavailable (Gemini returned an empty response)."
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        if exc.code in {400, 401, 403}:
            return "AI summary unavailable (Gemini API key invalid or missing permissions)."
        if exc.code == 404:
            if available_models:
                preview = ", ".join(available_models[:5])
                return f"AI summary unavailable (Gemini model not found. Available models for this key include: {preview})."
            if configured_model:
                return f"AI summary unavailable (Gemini model '{configured_model}' not found for this key/project)."
            return "AI summary unavailable (Gemini model not found for this key/project)."
        if exc.code == 429:
            return "AI summary unavailable (Gemini rate limit reached)."
        if error_body:
            return f"AI summary unavailable (Gemini HTTP {exc.code}: {error_body[:300]})."
        return f"AI summary unavailable (Gemini HTTP {exc.code})."
    except URLError:
        return "AI summary unavailable (Gemini API not reachable)."
    except Exception as exc:
        return f"AI summary unavailable (Gemini error: {exc})."


def _generate_ai_notes(inputs: dict[str, str], standards: dict[str, Any], concerns: list[str]) -> str | None:
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    # If there's very little user-provided detail, skip asking the API.
    if not inputs.get("observations") and not concerns:
        return "AI summary skipped due to limited observation detail."
    if not gemini_key:
        return "AI summary unavailable (Gemini API key missing)."

    return _generate_gemini_notes(inputs, standards, concerns)


def generate_report(inputs: dict[str, str]) -> str:
    species = inputs.get("species", "").strip()
    if not species:
        raise RuntimeError("Species is required for analysis.")

    if get_guide_path(species) is None:
        available = ", ".join(list_available_species()) or "no supported species"
        raise RuntimeError(f"Unsupported species. Choose one of: {available}.")

    pet_data, extracted_data = _ensure_species_knowledge_base()

    species_key = _get_species_key(species)
    standards = pet_data.get(species_key) or extracted_data.get(species_key) or {}

    sections = _build_report_sections(inputs, standards)
    ai_note = _generate_ai_notes(inputs, standards, sections.concerns)
    return _format_report(sections, ai_note)

