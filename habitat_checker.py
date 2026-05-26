from __future__ import annotations

from dataclasses import dataclass


@dataclass
class HabitatEvaluation:
    severity: str
    overall_status: str
    observations: list[str]
    concerns: list[str]
    recommendations: list[str]
    warning: str | None


def _to_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.strip().replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def evaluate_habitat(inputs: dict[str, str], standards: dict[str, float | str]) -> HabitatEvaluation:
    severity_rank = {"Normal": 0, "Mild Concern": 1, "Moderate Concern": 2, "High Concern": 3}
    severity = "Normal"

    observations: list[str] = []
    concerns: list[str] = []
    recommendations: list[str] = []
    warning: str | None = None

    def raise_severity(target: str) -> None:
        nonlocal severity
        if severity_rank[target] > severity_rank[severity]:
            severity = target

    temp = _to_float(inputs.get("temperature"))
    humidity = _to_float(inputs.get("humidity"))

    if standards:
        observations.append("Habitat standards loaded from care data.")
    else:
        concerns.append("No habitat standards available for this species yet.")
        recommendations.append("Upload a care guide PDF or populate pet_data.json with standards.")
        raise_severity("Mild Concern")

    temp_min = standards.get("temp_min") if standards else None
    temp_max = standards.get("temp_max") if standards else None
    humidity_min = standards.get("humidity_min") if standards else None
    humidity_max = standards.get("humidity_max") if standards else None

    if temp is not None and temp_min is not None and temp_max is not None:
        if temp < temp_min:
            concerns.append(f"Temperature ({temp:.1f} C) is below the recommended range.")
            recommendations.append(f"Increase enclosure temperature toward {temp_min}-{temp_max} C.")
            raise_severity("Moderate Concern")
        elif temp > temp_max:
            concerns.append(f"Temperature ({temp:.1f} C) is above the recommended range.")
            recommendations.append("Reduce heat output to avoid overheating.")
            raise_severity("Moderate Concern")
        else:
            observations.append(f"Temperature is within the recommended range ({temp_min}-{temp_max} C).")
    elif temp is None:
        concerns.append("No temperature data provided.")
        raise_severity("Mild Concern")

    if humidity is not None and humidity_min is not None and humidity_max is not None:
        if humidity < humidity_min:
            concerns.append(f"Humidity ({humidity:.1f}%) is below the recommended range.")
            recommendations.append("Increase humidity using safe misting or substrate adjustments.")
            raise_severity("Mild Concern")
        elif humidity > humidity_max:
            concerns.append(f"Humidity ({humidity:.1f}%) is above the recommended range.")
            recommendations.append("Improve ventilation and reduce excess moisture.")
            raise_severity("Mild Concern")
        else:
            observations.append(
                f"Humidity is within the recommended range ({humidity_min}-{humidity_max}%)."
            )
    elif humidity is None:
        concerns.append("No humidity data provided.")
        raise_severity("Mild Concern")

    feeding = inputs.get("feeding")
    if feeding:
        observations.append(f"Feeding behavior noted: {feeding}.")
    else:
        concerns.append("Feeding behavior was not provided.")

    activity = inputs.get("activity")
    if activity:
        observations.append(f"Activity level noted: {activity}.")
    else:
        concerns.append("Activity level was not provided.")

    hydration = inputs.get("hydration")
    if hydration:
        observations.append(f"Hydration notes: {hydration}.")
    else:
        concerns.append("Hydration notes were not provided.")

    observations_text = (inputs.get("observations") or "").lower()
    high_risk_terms = [
        "severe lethargy",
        "unable to move",
        "blood in stool",
        "respiratory distress",
        "seizure",
        "prolapse",
        "persistent vomiting",
    ]
    for term in high_risk_terms:
        if term in observations_text:
            concerns.append(f"High-risk sign mentioned: {term}.")
            warning = "Some signs can indicate serious illness. Consult an exotic veterinarian promptly."
            raise_severity("High Concern")
            break

    if not recommendations:
        recommendations.append("Keep habitat parameters stable and aligned with care guidance.")

    overall_status = {
        "Normal": "Conditions look stable; continue routine monitoring.",
        "Mild Concern": "Some parameters need attention and closer monitoring.",
        "Moderate Concern": "Multiple concerns detected; adjust husbandry promptly.",
        "High Concern": "Serious signs detected; seek veterinary guidance quickly.",
    }[severity]

    return HabitatEvaluation(
        severity=severity,
        overall_status=overall_status,
        observations=observations or ["No observations recorded."],
        concerns=concerns or ["No clear concerns detected."],
        recommendations=recommendations,
        warning=warning,
    )
