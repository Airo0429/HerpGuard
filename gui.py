from __future__ import annotations

import PySimpleGUI as sg

from agent import generate_report
from pdf_extractor import list_available_species

sg.theme("DarkBlue3")


def launch_app() -> None:
    species_options = list_available_species()

    input_section = [
        [sg.Text("HerpGuard Lite", font=("Helvetica", 18, "bold"))],
        [sg.Text("")],  # spacer
        [
            sg.Text("Species", size=(20, 1)),
            sg.Combo(
                values=species_options,
                default_value=species_options[0] if species_options else "",
                readonly=True,
                size=(30, 1),
                key="-SPECIES-",
            ),
        ],
        [
            sg.Text("Temperature (C)", size=(20, 1)),
            sg.InputText(size=(30, 1), key="-TEMPERATURE-"),
        ],
        [
            sg.Text("Humidity (%)", size=(20, 1)),
            sg.InputText(size=(30, 1), key="-HUMIDITY-"),
        ],
        [
            sg.Text("Feeding Behavior", size=(20, 1)),
            sg.InputText(size=(30, 1), key="-FEEDING-"),
        ],
        [
            sg.Text("Activity Level", size=(20, 1)),
            sg.InputText(size=(30, 1), key="-ACTIVITY-"),
        ],
        [
            sg.Text("Hydration Notes", size=(20, 1)),
            sg.InputText(size=(30, 1), key="-HYDRATION-"),
        ],
        [
            sg.Text("Owner Observations", size=(20, 1)),
            sg.Multiline(size=(40, 5), key="-OBSERVATIONS-"),
        ],
        [sg.Button("Analyze"), sg.Button("Clear"), sg.Button("Exit")],
    ]

    output_section = [
        [sg.Text("Monitoring Report")],
        [
            sg.Multiline(
                size=(80, 25),
                key="-OUTPUT-",
                disabled=True,
                autoscroll=True,
            )
        ],
    ]

    layout = [[sg.Column(input_section), sg.Column(output_section)]]

    window = sg.Window("HerpGuard Lite", layout)

    while True:
        event, values = window.read()

        if event == sg.WINDOW_CLOSED or event == "Exit":
            break

        if event == "Clear":
            window["-SPECIES-"].update(value=species_options[0] if species_options else "")
            window["-TEMPERATURE-"].update(value="")
            window["-HUMIDITY-"].update(value="")
            window["-FEEDING-"].update(value="")
            window["-ACTIVITY-"].update(value="")
            window["-HYDRATION-"].update(value="")
            window["-OBSERVATIONS-"].update(value="")
            window["-OUTPUT-"].update(value="")

        if event == "Analyze":
            species = values["-SPECIES-"].strip()
            if not species:
                sg.popup_warning("Missing Data", "Please select a supported species.")
                continue

            inputs = {
                "species": species,
                "temperature": values["-TEMPERATURE-"].strip(),
                "humidity": values["-HUMIDITY-"].strip(),
                "feeding": values["-FEEDING-"].strip(),
                "activity": values["-ACTIVITY-"].strip(),
                "hydration": values["-HYDRATION-"].strip(),
                "observations": values["-OBSERVATIONS-"].strip(),
            }

            try:
                report = generate_report(inputs)
                window["-OUTPUT-"].update(value=report)
            except RuntimeError as exc:
                sg.popup_error("Processing Error", str(exc))

    window.close()


if __name__ == "__main__":
    launch_app()
