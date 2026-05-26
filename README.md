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

1. Place one care guide PDF per species in `pdf_guides/`.
2. The GUI automatically loads the supported species from that folder.
3. Species standards are extracted from the bundled PDFs and cached in `extracted_data/extracted_species_data.json`.

## Notes

- Habitat standards are expected to come from the bundled PDFs and cached JSON data.
- The tool is not a veterinary diagnosis and recommends professional care for serious concerns.