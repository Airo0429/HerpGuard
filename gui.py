from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

from agent import generate_report


class HerpGuardGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("HerpGuard Lite")
        self.pdf_path: str | None = None

        self._build_form()

    def _build_form(self) -> None:
        header = tk.Label(self.root, text="HerpGuard Lite", font=("Helvetica", 18, "bold"))
        header.grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 4))

        self._add_field("Species", "species", 1)
        self._add_field("Temperature (C)", "temperature", 2)
        self._add_field("Humidity (%)", "humidity", 3)
        self._add_field("Feeding Behavior", "feeding", 4)
        self._add_field("Activity Level", "activity", 5)
        self._add_field("Hydration Notes", "hydration", 6)

        notes_label = tk.Label(self.root, text="Owner Observations")
        notes_label.grid(row=7, column=0, sticky="nw", padx=12, pady=4)
        self.notes_text = tk.Text(self.root, width=52, height=5)
        self.notes_text.grid(row=7, column=1, sticky="we", padx=12, pady=4)

        pdf_button = tk.Button(self.root, text="Attach Care Guide PDF", command=self._select_pdf)
        pdf_button.grid(row=8, column=0, sticky="w", padx=12, pady=(6, 2))
        self.pdf_label = tk.Label(self.root, text="No PDF selected")
        self.pdf_label.grid(row=8, column=1, sticky="w", padx=12, pady=(6, 2))

        analyze_button = tk.Button(self.root, text="Analyze", command=self._analyze)
        analyze_button.grid(row=9, column=0, sticky="w", padx=12, pady=10)

        output_label = tk.Label(self.root, text="Monitoring Report")
        output_label.grid(row=10, column=0, sticky="nw", padx=12, pady=(4, 2))
        self.output_text = tk.Text(self.root, width=70, height=18, state="disabled")
        self.output_text.grid(row=10, column=1, sticky="we", padx=12, pady=(4, 12))

        self.root.grid_columnconfigure(1, weight=1)

    def _add_field(self, label_text: str, field_name: str, row: int) -> None:
        label = tk.Label(self.root, text=label_text)
        label.grid(row=row, column=0, sticky="w", padx=12, pady=4)
        entry = tk.Entry(self.root, width=40)
        entry.grid(row=row, column=1, sticky="we", padx=12, pady=4)
        setattr(self, f"{field_name}_entry", entry)

    def _select_pdf(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select Care Guide PDF",
            filetypes=[("PDF files", "*.pdf")],
        )
        if file_path:
            self.pdf_path = file_path
            self.pdf_label.config(text=file_path)

    def _collect_input(self) -> dict[str, str]:
        return {
            "species": self.species_entry.get().strip(),
            "temperature": self.temperature_entry.get().strip(),
            "humidity": self.humidity_entry.get().strip(),
            "feeding": self.feeding_entry.get().strip(),
            "activity": self.activity_entry.get().strip(),
            "hydration": self.hydration_entry.get().strip(),
            "observations": self.notes_text.get("1.0", tk.END).strip(),
        }

    def _analyze(self) -> None:
        inputs = self._collect_input()
        if not inputs.get("species"):
            messagebox.showwarning("Missing Data", "Please enter a species.")
            return

        try:
            report = generate_report(inputs, pdf_path=self.pdf_path)
        except RuntimeError as exc:
            messagebox.showerror("Processing Error", str(exc))
            return

        self.output_text.configure(state="normal")
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert(tk.END, report)
        self.output_text.configure(state="disabled")


def launch_app() -> None:
    root = tk.Tk()
    app = HerpGuardGUI(root)
    root.mainloop()


if __name__ == "__main__":
    launch_app()
