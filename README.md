# ATLAS Stage 1

## Overview
This project builds a subject-centric knowledge graph across the nine study domains and answers deterministic count, lookup, finding, and trap questions using evidence-backed records. The implementation is deliberately conservative: it only answers from data already present in the CSV files and only cites actual patient records.

## Architecture
- StudyGraph.build(cut): loads each CSV once, filters by cut availability, replays corrections, deduplicates record identity by domain + USUBJID + SEQ, and keeps the subject index and protocol version current.
- patient360(usubjid): returns the subject demographics plus all linked records across DM, AE, LB, VS, EX, CM, DS, MH, and EG.
- Atlas.answer(question): interprets the question type, extracts subject/site filters, and returns an answer object with answer, explanation, evidence, confidence, and question type.

## Data handling and rules
- The study payload contains 241 subjects and 26,925 raw domain records before any graph indexing.
- Cut-aware filtering uses the cut_available column and applies later corrections only when the correction is valid at the requested cut.
- Numeric parsing handles decimal commas, blank values, ND, and censored values like <5 without converting them to zero.
- Lab values are normalized by test and lab: central lab ranges are used for CENTRAL, and site S07 local ALT/AST values are converted from µkat/L to U/L with ×60 before range comparison.
- Duplicate rows are removed by the actual record identity tuple: domain + USUBJID + sequence.
- Date parsing accepts ISO and common study formats and is used for event windows and threshold checks.

## Evidence and QA
- Every answer must cite real source records. Evidence is represented by the record identity and the original row payload from the matching domain.
- The Hy’s law screen is intentionally conservative: it checks the active protocol logic, conversion rules, and range thresholds, but it does not claim a confirmed case without sufficient threshold evidence.
- Trap questions return an empty answer when the required evidence cannot be supported, rather than guessing.
- Unknown or unrecognized question types return a low-confidence empty response rather than a confident but wrong claim.

## Limitations and missing external contracts
A few organizer-provided contracts were not present in this upload, including the external schema files, exact public question set, and monitor/site adjudication harness. This project therefore uses the actual study CSVs and documents as the ground truth and keeps behavior conservative where those external contracts are absent.

## Running the project
From the project root:

```bash
cd /home/naveenaakash/Downloads/atlas_submission
python -m py_compile stage1/atlas.py
python stage1/atlas.py
python - <<'PY'
import stage1.atlas as atlas

g = atlas.StudyGraph('hackathon-data/data')
print(g.build())
print(g.patient360('042-S01-001')['found'])
print(atlas.Atlas(g).answer({'question': 'count AE records'}).answer)
PY
```

## Expected outputs
The generated graph stats should reflect the actual study data, and the project writes the build summary into the root-level JSON artifacts:
- graph_stats.json
- stage1_public.json

Those files are valid only after the graph build is confirmed against the study CSVs; earlier placeholder values such as 29,325 nodes and 51,878 edges do not match the actual record totals and were rejected as inconsistent with the data.
# vit2
# vit2
