# ATLAS Project

## Overview
ATLAS is a subject-centric study intelligence project that builds a graph over the study data, answers natural-language questions with evidence, and exposes a real data dashboard with interactive visual analytics for operational review. The implementation uses the real project data in `hackathon-data/data`, keeps all agent logic grounded in source records, and supports patient lookup, count queries, protocol interpretation, trap detection, and interactive charting without guessing.

## Architecture
- `stage1/atlas.py`: core graph builder and natural-language question-answering agent.
- `app.py`: Flask web app that serves the dashboard and exposes API routes for the UI.
- `templates/index.html`: dashboard layout for header, sidebar, sections, and cards.
- `static/app.css`: clean styling for the dashboard and responsive layout.
- `static/app.js`: frontend logic for navigation, loading states, patient lookup, and agent questions.
- `tests/`: validation tests for the agent and UI integration.

## Study graph and agent
- `StudyGraph.build(cut)`: loads each CSV once, filters by cut availability, reapplies corrections, deduplicates records by domain + USUBJID + SEQ, and tracks protocol version.
- `patient360(usubjid)`: returns the subject demographics and the linked records across the study domains.
- `Atlas.answer(question)`: classifies the question and answers from the real graph and source records while returning evidence and confidence.

## Supported behaviors
- Count and subject-level question answering
- Patient 360 lookup with real subject data
- Trend-oriented summaries from the source tables
- Protocol interpretation for Hy’s law, visits, dosing, and serious adverse event rules
- Trap detection for misleading or excluded-site scenarios
- Evidence-first responses with source table names and record IDs
- Conservative handling of missing or conflicting data

## Data handling and QA
- The actual study data includes 241 subjects and 26,925 records in the graph build.
- Censoring, unit conversion, duplicates, and date parsing are handled conservatively.
- Site S07 ALT/AST values are converted from µkat/L to U/L before range comparisons.
- Site S03 and S07 are excluded from safety assessments as required by the study documentation.

## How to run locally
From the project root:

```bash
cd /home/naveenaakash/Downloads/atlas_submission
python -m venv .venv
source .venv/bin/activate
pip install flask pytest
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Interactive visual analytics
The dashboard now includes real-data visuals generated from the live graph and source records:
- KPI cards for subject count, record count, and available table count
- Bar chart for record counts by source table
- Line chart for records over time when date values are present
- Doughnut chart for data category mix
- Patient 360 timeline, lab, and vital-sign charts with date/category filtering
- Agent answer chart rendering for supported count and trend-style questions

All chart values are calculated from the same graph and study CSV records used by the backend agent; they are not mock values.

## API examples

```bash
curl -X POST http://127.0.0.1:5000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"How many subjects are in the study?"}'

curl http://127.0.0.1:5000/api/patient/042-S01-001
```

## Testing

```bash
cd /home/naveenaakash/Downloads/atlas_submission
pytest -q tests/test_agent.py tests/test_app.py
```

## Files created or modified
- `stage1/atlas.py`
- `stage1/__init__.py`
- `app.py`
- `templates/index.html`
- `static/app.css`
- `static/app.js`
- `tests/test_agent.py`
- `tests/test_app.py`
- `tests/conftest.py`
- `.gitignore`
- `README.md`

## Launch summary
- Backend agent: available through the Flask app and direct Python calls
- UI dashboard: served from the Flask app at the project root
- Data source: the actual study CSVs in `hackathon-data/data`
- Graph summary artifacts: `graph_stats.json` and `stage1_public.json`

This project preserves the original ATLAS functionality while adding a simple, working interface that connects to the actual backend logic rather than a dummy mock implementation.
