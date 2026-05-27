from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from prompts import DIAGNOSTIC_SYSTEM_PROMPT, DIAGNOSTIC_USER_PROMPT


def _load_pet_data() -> dict[str, Any]:
    """Load pet_data.json"""
    path = Path("pet_data.json")
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_pdf_content(species: str) -> str | None:
    """Extract text content from PDF guide for a species"""
    pdf_guides_dir = Path("pdf_guides")
    if not pdf_guides_dir.exists():
        return None
    
    # Normalize species name to match PDF filename patterns
    species_normalized = species.lower().replace(" ", "_")
    
    for pdf_file in pdf_guides_dir.glob("*.pdf"):
        # Try to match the PDF file with the species
        if species_normalized in pdf_file.stem.lower():
            try:
                from pdf_extractor import extract_text
                content = extract_text(str(pdf_file))
                # Limit content to first 3000 chars to avoid token overflow
                return content[:3000] if content else None
            except Exception:
                return None
    
    return None


def _get_species_data(species: str) -> dict[str, Any]:
    """Get data for a specific species"""
    pet_data = _load_pet_data()
    species_key = species.lower().strip()
    return pet_data.get(species_key, {})


def _detect_keywords(observations: str) -> dict[str, list[str]]:
    """Detect health/care keywords in observations"""
    obs_lower = observations.lower()
    
    keywords = {
        "temperature": [
            "hot", "cold", "warm", "cool", "temperature", "too warm", "too cold",
            "basking", "thermostat", "heat lamp", "under heating", "overheating"
        ],
        "humidity": [
            "humid", "moisture", "dry", "damp", "wet", "humidity", "water", "mist",
            "spray", "shedding", "stuck shed"
        ],
        "feeding": [
            "eating", "feeding", "appetite", "refuse", "won't eat", "food", "diet",
            "meal", "hungry", "digestion"
        ],
        "behavior": [
            "lethargy", "active", "sluggish", "lethargic", "behavior", "aggressive",
            "hide", "basking", "movement", "unresponsive"
        ],
        "health": [
            "injury", "wound", "bleeding", "discharge", "scale", "skin", "shell",
            "respiratory", "breathing", "wheeze", "sneeze", "sick", "illness",
            "disease", "parasite", "mite", "rot", "deformity"
        ],
        "emergency": [
            "seizure", "prolapse", "impaction", "severe", "emergency", "dying",
            "death", "urgent", "critical"
        ]
    }
    
    detected = {}
    for category, terms in keywords.items():
        found = [term for term in terms if term in obs_lower]
        if found:
            detected[category] = found
    
    return detected


def _build_diagnostic_prompt(species: str, observations: str, standards: dict[str, Any], keywords: dict[str, list[str]], pdf_content: str | None) -> str:
    """Build comprehensive prompt for Gemini AI with severity assessment"""
    temperature_range = ""
    if standards.get("temp_min") and standards.get("temp_max"):
        temperature_range = f"Ambient: {standards['temp_min']}-{standards['temp_max']}°C"
    if standards.get("basking_temp_min") and standards.get("basking_temp_max"):
        temperature_range += f" | Basking: {standards['basking_temp_min']}-{standards['basking_temp_max']}°C"
    
    humidity_range = ""
    if standards.get("humidity_min") and standards.get("humidity_max"):
        humidity_range = f"{standards['humidity_min']}-{standards['humidity_max']}%"
    
    uvb_range = ""
    if standards.get("uvb_min") and standards.get("uvb_max"):
        uvb_range = f"{standards['uvb_min']}-{standards['uvb_max']} hours/day"
    
    std_info = f"""
AVAILABLE CARE STANDARDS FOR {species.upper()}:
- Temperature: {temperature_range or 'NO STANDARD PROVIDED'}
- Humidity: {humidity_range or 'NO STANDARD PROVIDED'}
- UVB: {uvb_range or 'NO STANDARD PROVIDED'}
- Diet: {standards.get('diet', 'NO STANDARD PROVIDED')}
- Feeding Notes: {standards.get('feeding_notes', 'NO STANDARD PROVIDED')}
- UVB Notes: {standards.get('uvb_notes', 'NO STANDARD PROVIDED')}
- Nighttime Temp: {standards.get('nighttime_temp', 'NO STANDARD PROVIDED')}°C
- Substrate: {standards.get('substrate', 'NO STANDARD PROVIDED')}
- Other Care: {standards.get('other_care', 'NO STANDARD PROVIDED')}

DETECTED KEYWORDS IN OBSERVATIONS:
{format_keywords_for_display(keywords)}
    """
    
    pdf_section = ""
    if pdf_content:
        pdf_section = f"""
EXTRACTED FROM CARE GUIDE (Use ONLY this information, not general knowledge):
{pdf_content}
    """
    else:
        pdf_section = "\nNO CARE GUIDE PDF PROVIDED - Use only the standards above."
    
    prompt_end = f"""
OWNER'S OBSERVATIONS:
{observations}

IMPORTANT REMINDER: Base your entire response ONLY on the standards and care guide provided above.
Do NOT use any general knowledge about {species}. If information is missing, acknowledge it."""
    
    return std_info + pdf_section + prompt_end


def format_keywords_for_display(keywords: dict[str, list[str]]) -> str:
    """Format detected keywords for display"""
    if not keywords:
        return "  - None detected"
    
    lines = []
    for category, found_keywords in keywords.items():
        lines.append(f"  • {category.title()}: {', '.join(found_keywords)}")
    return "\n".join(lines)


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
    
    # Prefer gemini-2.5-flash first, then fallbacks
    preferred = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest",
    ]
    for model in preferred:
        if model in available_models:
            return model
    
    return configured or (available_models[0] if available_models else "gemini-2.5-flash")


def _call_gemini_api(species: str, observations: str, standards: dict[str, Any]) -> str | None:
    """Call Gemini API for diagnostic advice with severity assessment"""
    # Load .env from the project root directory
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path, override=True)
    
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    if not api_key:
        return None
    
    keywords = _detect_keywords(observations)
    pdf_content = _extract_pdf_content(species)
    diagnostic_prompt = _build_diagnostic_prompt(species, observations, standards, keywords, pdf_content)
    
    # Simplified payload - combine everything into user message
    user_message = f"""{DIAGNOSTIC_SYSTEM_PROMPT}

{DIAGNOSTIC_USER_PROMPT}

{diagnostic_prompt}"""
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": user_message},
                ],
            }
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
        },
    }
    
    try:
        available_models = _list_gemini_models(api_key)
        configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
        model = _pick_gemini_model(configured_model, available_models)
        
        # Ensure model name doesn't have "models/" prefix
        if model.startswith("models/"):
            model = model[len("models/"):]
        
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
        
        return None
    
    except HTTPError as exc:
        error_body = ""
        try:
            error_body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        
        if exc.code == 400:
            return f"[API CONFIG ERROR: 400 Bad Request - Invalid request format. {error_body[:100] if error_body else ''}]"
        elif exc.code == 403:
            return "[API CONFIG ERROR: 403 Forbidden - Your API key may be invalid, expired, or doesn't have permission for this model. Please verify your GEMINI_API_KEY and GEMINI_MODEL in .env are correct.]"
        elif exc.code == 401:
            return "[API CONFIG ERROR: 401 Unauthorized - Your API key is invalid. Check your GEMINI_API_KEY in .env]"
        elif exc.code == 429:
            return "[API QUOTA EXCEEDED: 429 - Your free tier quota is exceeded, or billing isn't enabled. Enable billing at https://console.cloud.google.com/billing or wait for quota reset.]"
        elif exc.code == 503:
            return "[API UNAVAILABLE: 503 Service Unavailable - The model is experiencing high demand. Try using a different model in .env (e.g., gemini-2.0-flash-lite)]"
        else:
            return f"[API HTTP Error {exc.code}]"
    except Exception as exc:
        return f"[API Error: {str(exc)[:150]}]"


def generate_diagnostic_report(species: str, observations: str) -> str:
    """Generate diagnostic report based on species and observations"""
    if not species or not observations:
        raise RuntimeError("Species and observations are required.")
    
    # Get species data
    standards = _get_species_data(species)
    
    # Detect keywords
    keywords = _detect_keywords(observations)
    
    # Extract PDF content
    pdf_content = _extract_pdf_content(species)
    
    # Build report sections
    lines = [
        "=" * 70,
        "HERPGUARD DIAGNOSTIC REPORT",
        "=" * 70,
        "",
        f"Species: {species.title()}",
        "",
    ]
    
    # Show care standards
    lines.extend([
        "CARE STANDARDS FOR THIS SPECIES:",
        ""
    ])
    
    if standards:
        if standards.get("temp_min") and standards.get("temp_max"):
            lines.append(f"  • Ambient Temperature: {standards['temp_min']}-{standards['temp_max']}°C")
        if standards.get("basking_temp_min") and standards.get("basking_temp_max"):
            lines.append(f"  • Basking Temperature: {standards['basking_temp_min']}-{standards['basking_temp_max']}°C")
        if standards.get("humidity_min") and standards.get("humidity_max"):
            lines.append(f"  • Humidity: {standards['humidity_min']}-{standards['humidity_max']}%")
        if standards.get("uvb_min") and standards.get("uvb_max"):
            lines.append(f"  • UVB Exposure: {standards['uvb_min']}-{standards['uvb_max']} hours/day")
        if standards.get("nighttime_temp"):
            lines.append(f"  • Nighttime Temperature: {standards['nighttime_temp']}°C")
        if standards.get("diet"):
            lines.append(f"  • Diet: {standards['diet']}")
        if standards.get("feeding_notes"):
            lines.append(f"  • Feeding Notes: {standards['feeding_notes']}")
        if standards.get("uvb_notes"):
            lines.append(f"  • UVB Notes: {standards['uvb_notes']}")
        if standards.get("substrate"):
            lines.append(f"  • Substrate: {standards['substrate']}")
        if standards.get("other_care"):
            lines.append(f"  • Other Care: {standards['other_care']}")
    else:
        lines.append("  (No standards found for this species)")
    
    # Show observations
    lines.extend(["", "YOUR OBSERVATIONS:", ""])
    for obs_line in observations.split("\n"):
        if obs_line.strip():
            lines.append(f"  {obs_line}")
    
    # Try to get AI advice if Gemini is available
    ai_advice = _call_gemini_api(species, observations, standards)
    
    if ai_advice and not ai_advice.startswith("["):
        lines.extend(["", "=" * 70, "AI DIAGNOSTIC ANALYSIS & RECOMMENDATIONS:", "=" * 70, ""])
        lines.append(ai_advice)
    elif ai_advice:
        # API error occurred
        lines.extend(["", "=" * 70, "AI ANALYSIS STATUS:", "=" * 70, ""])
        lines.append(ai_advice)
    else:
        lines.extend(["", "[AI-powered recommendations unavailable]"])
        lines.extend(["", "To enable personalized AI recommendations:"])
        lines.extend(["  1. Visit https://aistudio.google.com/apikey to create a free API key"])
        lines.extend(["  2. Enable billing at https://console.cloud.google.com/billing"])
        lines.extend(["  3. Add your key to .env: GEMINI_API_KEY=your_key_here"])
        lines.extend(["", "The care standards above are still available for your reference."])
    
    lines.extend(["", "=" * 70])
    lines.append("DISCLAIMER: This tool is advisory only and not a replacement for")
    lines.append("professional veterinary care. For serious concerns or emergencies,")
    lines.append("contact an exotic veterinarian immediately.")
    lines.append("=" * 70)
    
    return "\n".join(lines)

