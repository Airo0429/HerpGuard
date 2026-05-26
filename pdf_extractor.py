from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


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
    species_key = Path(pdf_path).stem.replace("_", " ").replace("-", " ").lower()
    return species_key, standards


def load_extracted_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_extracted_data(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
