from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


GUIDE_DIRECTORY = Path("pdf_guides")
EXTRACTED_DATA_PATH = Path("extracted_data/extracted_species_data.json")
PET_DATA_PATH = Path("pet_data.json")

_DISPLAY_NAME_OVERRIDES = {
    "BEARDEDDRAGON": "Bearded Dragon",
    "CHERRYHEADREDFOOTEDTORTOISE": "Cherry Head Red Footed Tortoise",
    "INDIANSTARTORTOISE": "Indian Star Tortoise",
    "PACMANFROG": "Pacman Frog",
    "PINKBELLIEDSIDENECKTURTLE": "Pink Bellied Side Neck Turtle",
    "REDFOOTEDTORTOISE": "Red Footed Tortoise",
    "SULCATATORTOISE": "Sulcata Tortoise",
    "SUN CONURE": "Sun Conure",
}


def _species_key(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", name.lower())).strip()


def _display_name_from_stem(stem: str) -> str:
    override = _DISPLAY_NAME_OVERRIDES.get(stem.upper())
    if override:
        return override

    normalized = re.sub(r"[_-]+", " ", stem).strip()
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.title()


def list_available_species() -> list[str]:
    if not GUIDE_DIRECTORY.exists():
        return []

    species = [_display_name_from_stem(path.stem) for path in sorted(GUIDE_DIRECTORY.glob("*.pdf"))]
    return sorted(species)


def get_guide_path(species: str) -> Path | None:
    target_key = _species_key(species)
    if not GUIDE_DIRECTORY.exists():
        return None

    for path in GUIDE_DIRECTORY.glob("*.pdf"):
        if _species_key(_display_name_from_stem(path.stem)) == target_key:
            return path
    return None


def _extract_text_with_pdfplumber(pdf_path: Path) -> str:
    import pdfplumber

    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def _extract_text_with_pypdf2(pdf_path: Path) -> str:
    from PyPDF2 import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text(pdf_path: str) -> str:
    path = Path(pdf_path)
    if not path.exists():
        raise RuntimeError(f"PDF not found: {pdf_path}")

    try:
        return _extract_text_with_pdfplumber(path)
    except Exception:
        return _extract_text_with_pypdf2(path)


def _parse_range(pattern: str, text: str) -> tuple[float, float] | None:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    low = float(match.group(1))
    high = float(match.group(2))
    return low, high


def parse_species_standards(text: str) -> dict[str, Any]:
    standards: dict[str, Any] = {}

    temp_range = _parse_range(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*°?c", text)
    if temp_range:
        standards["temp_min"], standards["temp_max"] = temp_range

    humidity_range = _parse_range(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*%", text)
    if humidity_range:
        standards["humidity_min"], standards["humidity_max"] = humidity_range

    uvb_match = re.search(r"uvb\s*:?\s*(low|moderate|medium|high)", text, re.IGNORECASE)
    if uvb_match:
        standards["uvb"] = uvb_match.group(1).capitalize()

    feeding_match = re.search(r"feeding\s*(?:schedule|frequency)?\s*:?\s*([\w\s-]+)", text, re.IGNORECASE)
    if feeding_match:
        standards["feeding_notes"] = feeding_match.group(1).strip()

    return standards


def extract_species_data(pdf_path: str) -> tuple[str, dict[str, Any]]:
    text = extract_text(pdf_path)
    standards = parse_species_standards(text)
    species_key = _species_key(_display_name_from_stem(Path(pdf_path).stem))
    return species_key, standards


def extract_all_species_data() -> dict[str, Any]:
    species_data: dict[str, Any] = {}
    if not GUIDE_DIRECTORY.exists():
        return species_data

    for pdf_path in sorted(GUIDE_DIRECTORY.glob("*.pdf")):
        species_key, standards = extract_species_data(str(pdf_path))
        if standards:
            species_data[species_key] = standards

    return species_data


def load_extracted_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_extracted_data(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
