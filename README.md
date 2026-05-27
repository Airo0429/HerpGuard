# HerpGuard AI

HerpGuard AI is an exotic pet monitoring assistant. It gathers habitat inputs, checks care guide standards, and produces a structured report with safety-oriented recommendations.

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file to enable the Gemini API:

```text
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.5-flash
```

## Run

Install dependencies and run with Streamlit:

```bash
pip install -r requirements.txt
streamlit run gui.py
```

## Using Care Guide PDFs

1. Place one care guide PDF per species in `pdf_guides/`.
2. The GUI automatically loads the supported species from that folder.
3. Species standards are extracted from the bundled PDFs and cached in `extracted_data/extracted_species_data.json`.

## Notes

- Habitat standards are expected to come from the bundled PDFs and cached JSON data.
- The tool is not a veterinary diagnosis and recommends professional care for serious concerns.