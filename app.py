from __future__ import annotations

from dataclasses import dataclass
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs


SUPPORTED_SPECIES = {
    "tortoises",
    "turtles",
    "bearded dragons",
    "leopard geckos",
    "crested geckos",
    "iguanas",
    "snakes",
    "chameleons",
    "monitors",
    "amphibians",
    "exotic birds",
    "other reptiles/exotics",
}

SPECIES_RANGES = {
    "bearded dragons": {"basking_temp": (95, 110), "cool_side_temp": (75, 85), "humidity": (30, 40)},
    "leopard geckos": {"basking_temp": (88, 95), "cool_side_temp": (72, 80), "humidity": (30, 40)},
    "crested geckos": {"basking_temp": (72, 80), "cool_side_temp": (68, 75), "humidity": (55, 80)},
    "tortoises": {"basking_temp": (90, 100), "cool_side_temp": (70, 80), "humidity": (40, 70)},
    "snakes": {"basking_temp": (85, 95), "cool_side_temp": (72, 82), "humidity": (40, 70)},
    "chameleons": {"basking_temp": (82, 92), "cool_side_temp": (70, 80), "humidity": (50, 80)},
    "exotic birds": {"humidity": (40, 60)},
}

HIGH_RISK_TERMS = {
    "severe lethargy",
    "unable to move",
    "dramatic weight loss",
    "blood in stool",
    "wheezing",
    "respiratory distress",
    "severe dehydration",
    "burn",
    "seizure",
    "prolapse",
    "swollen limb",
    "swollen jaw",
    "persistent vomiting",
    "regurgitation",
    "neurological",
    "egg binding",
}


@dataclass
class AnalysisResult:
    severity: str
    overall_status: str
    observations: list[str]
    concerns: list[str]
    recommendations: list[str]
    monitoring: list[str]
    warning: str | None
    additional_info_needed: list[str]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_input(raw_text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in raw_text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower().replace(" ", "_")
        data[key] = value.strip()
    return data


def analyze_pet_data(data: dict[str, str]) -> AnalysisResult:
    species = data.get("species", "Unknown")
    species_key = species.lower()

    observations: list[str] = []
    concerns: list[str] = []
    recommendations: list[str] = []
    monitoring: list[str] = []
    additional_info_needed: list[str] = []
    warning = None

    severity_rank = {"Normal": 0, "Mild Concern": 1, "Moderate Concern": 2, "High Concern": 3}
    severity = "Normal"

    def raise_severity(target: str) -> None:
        nonlocal severity
        if severity_rank[target] > severity_rank[severity]:
            severity = target

    if species == "Unknown":
        additional_info_needed.append("species")
    elif species_key not in SUPPORTED_SPECIES:
        observations.append("Species is outside the explicit support list; recommendations are conservative and general.")

    notes_blob = " ".join(
        [
            data.get("owner_notes", ""),
            data.get("activity_level", ""),
            data.get("feces_observations", ""),
            data.get("hydration_observations", ""),
            data.get("food_intake", ""),
        ]
    ).lower()

    for term in HIGH_RISK_TERMS:
        if term in notes_blob:
            concerns.append(f"Potential high-risk sign mentioned: {term}.")
            raise_severity("High Concern")
            warning = (
                "Some reported signs can indicate serious illness. Please contact an exotic veterinarian promptly for guidance."
            )
            break

    ranges = SPECIES_RANGES.get(species_key, {})
    basking = _to_float(data.get("basking_temperature") or data.get("basking_temp"))
    cool = _to_float(data.get("cool_side_temperature") or data.get("cool_side_temp"))
    humidity = _to_float(data.get("humidity"))

    if basking is not None and "basking_temp" in ranges:
        low, high = ranges["basking_temp"]
        if basking < low:
            concerns.append(f"Basking temperature ({basking:.1f}°F) may be too low for digestion.")
            recommendations.append(f"Adjust basking zone toward {low}-{high}°F using safe thermostat control.")
            raise_severity("Moderate Concern")
        elif basking > high:
            concerns.append(f"Basking temperature ({basking:.1f}°F) may be dangerously high.")
            recommendations.append("Lower basking heat and verify probe placement to avoid overheating or burns.")
            raise_severity("High Concern")
        else:
            observations.append(f"Basking temperature is within a typical range ({low}-{high}°F).")

    if cool is not None and "cool_side_temp" in ranges:
        low, high = ranges["cool_side_temp"]
        if cool < low:
            concerns.append(f"Cool-side temperature ({cool:.1f}°F) is below a typical range.")
            raise_severity("Mild Concern")
        elif cool > high:
            concerns.append(f"Cool-side temperature ({cool:.1f}°F) is above a typical range.")
            raise_severity("Mild Concern")
        else:
            observations.append(f"Cool-side temperature is within a typical range ({low}-{high}°F).")

    if humidity is not None and "humidity" in ranges:
        low, high = ranges["humidity"]
        if humidity < low:
            concerns.append(f"Humidity ({humidity:.1f}%) may increase dehydration/shedding risk.")
            raise_severity("Mild Concern")
        elif humidity > high:
            concerns.append(f"Humidity ({humidity:.1f}%) may increase respiratory risk.")
            raise_severity("Mild Concern")
        else:
            observations.append(f"Humidity is within a typical range ({low}-{high}%).")

    uvb = data.get("uvb_setup")
    uvb_replacement = data.get("uvb_replacement_dates") or data.get("uvb_replacement_date")
    if not uvb:
        additional_info_needed.append("UVB setup")
    else:
        observations.append("UVB setup data provided.")
    if not uvb_replacement:
        additional_info_needed.append("UVB replacement date")

    weight = data.get("weight")
    historical = data.get("historical_logs")
    if weight and historical:
        observations.append("Current data includes weight and historical logs; trend checks should continue weekly.")
    elif not weight:
        additional_info_needed.append("weight")

    feeding = data.get("feeding_schedule")
    intake = data.get("food_intake")
    if not feeding:
        additional_info_needed.append("feeding schedule")
    if not intake:
        additional_info_needed.append("food intake")

    if not observations:
        observations.append("Limited quantitative data was provided.")

    if severity in {"Moderate Concern", "High Concern"}:
        recommendations.append("Arrange an exotic veterinarian consultation, especially if signs persist or worsen.")

    if not recommendations:
        recommendations.append("Maintain stable species-appropriate temperature gradients, humidity, and clean hydration access.")
        recommendations.append("Do not self-medicate; use conservative husbandry adjustments and monitor response.")

    monitoring.extend(
        [
            "Log weight at a consistent interval (for example, weekly).",
            "Track appetite, activity, hydration behavior, and stool quality.",
            "Set reminders for UVB bulb replacement and enclosure maintenance.",
        ]
    )

    overall_status = {
        "Normal": "No immediate red flags from provided data, but continue routine monitoring.",
        "Mild Concern": "Some husbandry parameters may need adjustment and closer monitoring.",
        "Moderate Concern": "Notable concerns detected; improve husbandry promptly and seek veterinary input.",
        "High Concern": "Potentially serious warning signs detected; prioritize prompt exotic veterinary guidance.",
    }[severity]

    return AnalysisResult(
        severity=severity,
        overall_status=overall_status,
        observations=observations,
        concerns=concerns or ["No clear major concerns detected from available information."],
        recommendations=recommendations,
        monitoring=monitoring,
        warning=warning,
        additional_info_needed=sorted(set(additional_info_needed)),
    )


def format_output(data: dict[str, str]) -> str:
    result = analyze_pet_data(data)
    species = data.get("species", "Unknown")
    lines = [
        "Pet Analysis Summary",
        f"- Species: {species}",
        f"- Severity: {result.severity}",
        f"- Overall Status: {result.overall_status}",
        "",
        "Observations",
    ]
    lines.extend([f"- {item}" for item in result.observations])

    lines.append("")
    lines.append("Possible Concerns")
    lines.extend([f"- {item}" for item in result.concerns])

    lines.append("")
    lines.append("Recommendations")
    lines.extend([f"- {item}" for item in result.recommendations])
    lines.append("- I am not a licensed veterinarian, and this guidance is not a diagnosis.")

    lines.append("")
    lines.append("Monitoring Suggestions")
    lines.extend([f"- {item}" for item in result.monitoring])

    if result.warning:
        lines.append("")
        lines.append("Warning")
        lines.append(f"- {result.warning}")

    if result.additional_info_needed:
        lines.append("")
        lines.append("Additional Information Needed")
        lines.extend([f"- {item}" for item in result.additional_info_needed])

    return "\n".join(lines)


HTML_PAGE = """<!DOCTYPE html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
<title>HerpGuard AI</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; max-width: 980px; }}
textarea {{ width: 100%; min-height: 220px; }}
button {{ margin-top: 12px; padding: 10px 16px; }}
pre {{ background: #f7f7f7; padding: 14px; white-space: pre-wrap; border-radius: 6px; }}
.hint {{ color: #444; }}
</style>
</head>
<body>
<h1>HerpGuard AI</h1>
<p class=\"hint\">Enter pet details as key:value lines (example: species: Bearded dragons).</p>
<form method=\"post\">
  <label for=\"input_text\">Input</label><br />
  <textarea id=\"input_text\" name=\"input_text\">{input_text}</textarea><br />
  <button type=\"submit\">Analyze</button>
</form>
<h2>Output</h2>
<pre>{output_text}</pre>
</body>
</html>
"""


class HerpGuardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self._respond("", "Provide input details, then click Analyze.")

    def do_POST(self) -> None:
        content_length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(content_length).decode("utf-8", errors="replace")
        form = parse_qs(payload)
        input_text = form.get("input_text", [""])[0]
        data = parse_input(input_text)
        output = format_output(data)
        self._respond(input_text, output)

    def _respond(self, input_text: str, output_text: str) -> None:
        page = HTML_PAGE.format(input_text=escape(input_text), output_text=escape(output_text))
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8000), HerpGuardHandler)
    print("HerpGuard UI running at http://127.0.0.1:8000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
