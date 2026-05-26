# HerpGuard Lite

HerpGuard Lite is a lightweight exotic pet monitoring assistant. It gathers habitat inputs, checks care guide standards, and produces a structured report with safety-oriented recommendations.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file with your OpenAI key if you want AI summaries:

```text
OPENAI_API_KEY=your_key_here
```

## Run

```bash
python app.py
```

## Using Care Guide PDFs

1. Place care guide PDFs in `pdf_guides/` or select one from the GUI.
2. Use filenames that include the species name (for example, `sulcata_tortoise.pdf`).
3. Extracted standards are stored in `extracted_data/extracted_species_data.json` and merged into `pet_data.json`.

## Notes

- Habitat standards are expected to come from PDFs or `pet_data.json`.
- The tool is not a veterinary diagnosis and recommends professional care for serious concerns.