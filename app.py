import re
from collections import defaultdict
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from stage1.atlas import Atlas, StudyGraph, DOMAINS, norm_date

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "hackathon-data" / "data"

app = Flask(__name__, template_folder="templates", static_folder="static")

GRAPH = StudyGraph(str(DATA_DIR))
GRAPH.build()
ATLAS = Atlas(GRAPH)


def _iter_records_by_domain(domains=None):
    for domain in (domains or DOMAINS):
        for row in GRAPH.data.get(domain, []):
            yield domain, row


def _first_date(row):
    for key in [
        "AESTDTC", "AEENDTC", "LBDTC", "VSDTC", "EXSTDTC", "CMSTDTC", "DSSTDTC", "MHSTDTC", "EGDTC",
        "RFSTDTC", "DMDTC", "VISITDTC", "DATE", "DATET", "DTC",
    ]:
        value = row.get(key)
        date = norm_date(value)
        if date is not None:
            return date
    return None


def _first_numeric_value(row, keys):
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        value = str(value).strip()
        if value and value.upper() not in {"NA", "N/A", "ND", "MISSING", "NULL"}:
            try:
                num = float(value.replace(",", "."))
                return num
            except ValueError:
                pass
    return None


def _bucket_counts(rows, key_name):
    counts = defaultdict(int)
    for item in rows:
        if item.get(key_name):
            counts[item[key_name]] += 1
    return [{"label": label, "value": value} for label, value in sorted(counts.items())]


def build_dashboard_charts():
    tables = {}
    for domain in DOMAINS:
        tables[domain] = len(GRAPH.data.get(domain, []))

    month_counts = defaultdict(int)
    for domain, row in _iter_records_by_domain():
        date = _first_date(row)
        if date is not None:
            month_counts[date.strftime("%Y-%m")] += 1

    domain_counts = [{"label": domain, "value": tables.get(domain, 0)} for domain in DOMAINS]
    records_by_month = [{"label": month, "value": count} for month, count in sorted(month_counts.items())]

    categories = {
        "Demographics": len(GRAPH.data.get("DM", [])),
        "Adverse events": len(GRAPH.data.get("AE", [])),
        "Laboratory": len(GRAPH.data.get("LB", [])),
        "Vital signs": len(GRAPH.data.get("VS", [])),
        "Exposure": len(GRAPH.data.get("EX", [])),
        "Concomitant meds": len(GRAPH.data.get("CM", [])),
        "Disposition": len(GRAPH.data.get("DS", [])),
        "Medical history": len(GRAPH.data.get("MH", [])),
        "ECG": len(GRAPH.data.get("EG", [])),
    }

    return {
        "table_counts": domain_counts,
        "records_over_time": records_by_month,
        "category_breakdown": [{"label": label, "value": value} for label, value in categories.items()],
    }


def patient_visual_payload(subject_id, patient_data):
    records = patient_data.get("records", {})

    timeline = []
    for domain in DOMAINS:
        for row in records.get(domain, []):
            date = _first_date(row)
            if date is None:
                continue
            label = row.get("VISIT") or row.get("LBTESTCD") or row.get("VSTESTCD") or row.get("AETERM") or row.get("CMTRT") or row.get("DSDECOD") or row.get("MHTERM") or row.get("EGTESTCD") or domain
            value = _first_numeric_value(row, ["LBORRES", "VSORRES", "EXDOSE", "CMDOSE", "EGORRES", "AGE"]) or row.get("AETERM") or row.get("DSDECOD")
            unit = row.get("LBORRESU") or row.get("VSORRESU") or row.get("EXDOSU") or row.get("EGORRESU") or ""
            timeline.append({
                "date": date.isoformat(),
                "domain": domain,
                "label": str(label),
                "value": value,
                "unit": str(unit),
            })

    timeline = sorted(timeline, key=lambda item: item["date"])

    lab_series = []
    for domain in ["LB"]:
        for row in records.get(domain, []):
            date = _first_date(row)
            if date is None:
                continue
            value = _first_numeric_value(row, ["LBORRES", "LBSTRESN", "LBSTRESC"])
            if value is None:
                continue
            unit = row.get("LBORRESU") or row.get("LBSTRESU") or ""
            lab_series.append({
                "date": date.isoformat(),
                "label": row.get("LBTESTCD") or "LAB",
                "value": value,
                "unit": str(unit),
            })

    vital_series = []
    for domain in ["VS"]:
        for row in records.get(domain, []):
            date = _first_date(row)
            if date is None:
                continue
            value = _first_numeric_value(row, ["VSORRES", "VSSTRESN", "VSSTRESC"])
            if value is None:
                continue
            vital_series.append({
                "date": date.isoformat(),
                "label": row.get("VSTESTCD") or "VS",
                "value": value,
                "unit": row.get("VSORRESU") or row.get("VSSTRESU") or "",
            })

    return {
        "timeline": timeline,
        "lab_series": sorted(lab_series, key=lambda item: item["date"]),
        "vital_series": sorted(vital_series, key=lambda item: item["date"]),
    }


def _risk_reference_limit(test_code, default_high=None):
    test_code = str(test_code or "").upper()
    for row in GRAPH.ranges:
        if str(row.get("LBTESTCD") or "").upper() == test_code:
            value = _first_numeric_value(row, ["HIGH", "LOW", "UPPER", "UPPERLIMIT", "RANGEHIGH", "HIGHVALUE"])
            if value is not None:
                return value
    if test_code in {"ALT", "AST", "BILI", "BILIRUBIN"}:
        return {"ALT": 60.0, "AST": 60.0, "BILI": 1.2, "BILIRUBIN": 1.2}.get(test_code, default_high or 1.0)
    return default_high or 1.0


def _build_subject_risk(subject_id):
    patient_data = GRAPH.patient360(subject_id)
    if not patient_data.get("found"):
        return {
            "subject_id": subject_id,
            "risk_score": 0,
            "risk_level": "Low",
            "summary": "No subject records were found for this ID.",
            "evidence": [],
            "details": {},
        }

    demographics = patient_data.get("demographics", {}) or {}
    records = patient_data.get("records", {}) or {}
    site_id = str(demographics.get("SITEID") or "").upper()
    score = 0
    evidence = []
    details = {"age": demographics.get("AGE"), "site": site_id, "lab_flags": [], "qtc_flags": [], "dose_flags": []}

    age_value = _first_numeric_value(demographics, ["AGE"])
    if age_value is not None and age_value >= 65:
        score += 10
        evidence.append({"category": "Demographics", "severity": "Moderate", "label": "Age >= 65 years", "value": age_value})

    for row in records.get("LB", []):
        test_code = str(row.get("LBTESTCD") or row.get("LBTEST") or "").upper()
        value = _first_numeric_value(row, ["LBSTRESN", "LBORRES", "LBSTRESC"])
        if value is None or not test_code:
            continue
        limit = _risk_reference_limit(test_code)
        if test_code in {"ALT", "AST"}:
            if value >= max(3 * limit, 180.0):
                score += 30
                evidence.append({"category": "Laboratory", "severity": "Critical", "label": f"{test_code} > 3x upper limit", "value": value})
                details["lab_flags"].append({"test": test_code, "value": value, "limit": limit})
        elif test_code in {"BILI", "BILIRUBIN"}:
            if value >= max(2 * limit, 2.0):
                score += 25
                evidence.append({"category": "Laboratory", "severity": "High", "label": f"{test_code} elevated beyond 2x upper limit", "value": value})
                details["lab_flags"].append({"test": test_code, "value": value, "limit": limit})

    for row in records.get("EG", []):
        test_code = str(row.get("EGTESTCD") or row.get("EGTEST") or "").upper()
        value = _first_numeric_value(row, ["EGORRES", "EGSTRESN", "EGSTRESC"])
        if value is None or not test_code:
            continue
        if test_code == "QTCF" and value >= 500:
            score += 25
            evidence.append({"category": "ECG", "severity": "High", "label": "QTc above danger threshold", "value": value})
            details["qtc_flags"].append({"test": test_code, "value": value})

    for row in records.get("EX", []):
        dose = _first_numeric_value(row, ["EXDOSE", "EXDOSN"])
        if dose is None:
            continue
        if dose not in {0.0, 10.0}:
            score += 20
            evidence.append({"category": "Exposure", "severity": "Moderate", "label": "Dose deviates from protocol 0 or 10 mg", "value": dose})
            details["dose_flags"].append({"dose": dose})

    for row in records.get("CM", []):
        class_name = str(row.get("CMCLAS") or "").upper()
        if "ACE" in class_name or "INHIBITOR" in class_name:
            score += 5
            evidence.append({"category": "Concomitant Medication", "severity": "Low", "label": "ACE inhibitor co-medication present", "value": row.get("CMTRT")})
            break

    for row in records.get("AE", []):
        if str(row.get("AESER") or "").upper() == "Y" or str(row.get("AESHOSP") or "").upper() == "Y":
            score += 18
            evidence.append({"category": "Adverse Event", "severity": "High", "label": "Serious AE or hospitalization flagged", "value": row.get("AETERM")})
            break

    if site_id in {"S03", "S07"}:
        score = max(0, score - 5)

    risk_score = min(max(score, 0), 100)
    if risk_score >= 75:
        risk_level = "Critical"
    elif risk_score >= 50:
        risk_level = "High"
    elif risk_score >= 25:
        risk_level = "Moderate"
    else:
        risk_level = "Low"

    summary = (
        f"Subject {subject_id} has a {risk_level.lower()} risk profile based on {len(evidence)} supporting signal(s) "
        f"drawn from the study records and protocol context."
    )

    return {
        "subject_id": subject_id,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "summary": summary,
        "evidence": evidence,
        "details": details,
    }


def _build_subject_replay(subject_id):
    patient_data = GRAPH.patient360(subject_id)
    if not patient_data.get("found"):
        return {
            "subject_id": subject_id,
            "events": [],
            "event_count": 0,
            "summary": "No replay timeline is available for this subject.",
        }

    events = []
    for domain in DOMAINS:
        for row in patient_data.get("records", {}).get(domain, []):
            date = _first_date(row)
            if date is None:
                continue
            label = row.get("VISIT") or row.get("LBTESTCD") or row.get("VSTESTCD") or row.get("AETERM") or row.get("CMTRT") or row.get("EXTRT") or row.get("DSDECOD") or row.get("MHTERM") or row.get("EGTESTCD") or domain
            value = _first_numeric_value(row, ["LBORRES", "LBSTRESN", "VSORRES", "VSSTRESN", "EXDOSE", "CMDOSE", "EGORRES", "EGSTRESN", "AGE"]) or row.get("AETERM") or row.get("DSDECOD") or row.get("MHTERM")
            unit = row.get("LBORRESU") or row.get("VSORRESU") or row.get("EXDOSU") or row.get("EGORRESU") or ""
            if label is None:
                label = domain
            events.append({
                "date": date.isoformat(),
                "domain": domain,
                "label": str(label),
                "value": value,
                "unit": str(unit),
                "source": f"{domain}.csv",
            })

    events = sorted(events, key=lambda item: item["date"])
    return {
        "subject_id": subject_id,
        "events": events,
        "event_count": len(events),
        "summary": f"{len(events)} study events were replayed for {subject_id} in chronological order.",
    }


def _matching_subject_ids(term):
    text = str(term or "").strip().upper()
    if not text:
        return[]
    if text in GRAPH.subjects:
        return [text]
    if re.fullmatch(r"S\d{2}", text):
        return sorted([sid for sid in GRAPH.subjects if sid.startswith(f"042-{text}-")])
    if re.fullmatch(r"\d{3}-S\d{2}-\d{3}", text):
        return [text] if text in GRAPH.subjects else []
    return []


def _graph_summary_for_subjects(subject_ids, limit=250):
    subject_nodes = []
    record_nodes = []
    record_edges = []
    node_details = {}
    seen_nodes = set()

    for sid in sorted(subject_ids):
        subject_id = f"subject:{sid}"
        if subject_id not in seen_nodes:
            subject_nodes.append({
                "id": subject_id,
                "label": sid,
                "type": "subject",
                "title": f"Subject {sid}",
                "color": "#1f5dbe",
                "shape": "dot",
                "size": 18,
                "meta": {"subject_id": sid, "type": "subject", "record_count": 0},
            })
            seen_nodes.add(subject_id)

    for node in GRAPH.nodes:
        sid = str(node.get("usubjid") or "")
        if sid not in subject_ids:
            continue
        record_id = str(node.get("id"))
        record_nodes.append({
            "id": record_id,
            "label": f"{node['domain']}\n{node.get('seq', '')}",
            "type": "record",
            "title": f"{node['domain']} record",
            "color": "#73b5a6",
            "shape": "box",
            "size": 12,
            "meta": {
                "type": "record",
                "domain": node.get("domain"),
                "subject_id": sid,
                "seq": node.get("seq"),
                "source_table": f"{node.get('domain')}.csv",
                "record_id": record_id,
            },
        })
        record_edges.append({
            "from": f"subject:{sid}",
            "to": record_id,
            "label": "HAS_RECORD",
            "color": "#5d8df0",
            "arrows": "to",
            "width": 1.5,
        })
        node_details[record_id] = {
            "subject_id": sid,
            "domain": node.get("domain"),
            "seq": node.get("seq"),
            "source_table": f"{node.get('domain')}.csv",
            "record_id": record_id,
            "record": node.get("record"),
        }
        if len(record_nodes) >= limit:
            break

    for sub in subject_nodes:
        sid = sub["meta"]["subject_id"]
        sub["meta"]["record_count"] = sum(1 for n in GRAPH.nodes if str(n.get("usubjid")) == sid)
        node_details[sub["id"]] = {
            "subject_id": sid,
            "type": "subject",
            "record_count": sub["meta"]["record_count"],
            "connected_records": [n["id"] for n in GRAPH.nodes if str(n.get("usubjid")) == sid][:25],
            "demographics": GRAPH.subjects.get(sid, {}),
        }

    nodes = subject_nodes + record_nodes
    edges = record_edges
    return {"nodes": nodes, "edges": edges, "node_details": node_details, "summary": {"total_subjects": len(GRAPH.subjects), "shown_subjects": len(subject_nodes), "shown_records": len(record_nodes)}}


def build_question_visualization(question, answer):
    question_text = str(question or "").lower()
    if not answer or not isinstance(answer, dict):
        return None

    chart = None
    if answer.get("question_type") == "count":
        labels = [item["label"] for item in build_dashboard_charts()["table_counts"]]
        values = [item["value"] for item in build_dashboard_charts()["table_counts"]]
        if labels and values:
            chart = {"type": "bar", "title": "Record counts by source table", "labels": labels, "values": values, "series_label": "Records"}
    elif answer.get("question_type") in {"lookup", "trend"}:
        patient_id = answer.get("answer", {}).get("usubjid") if isinstance(answer.get("answer"), dict) else None
        if patient_id and patient_id in GRAPH.subjects:
            patient_data = GRAPH.patient360(patient_id)
            visuals = patient_visual_payload(patient_id, patient_data)
            if visuals["lab_series"]:
                chart = {
                    "type": "line",
                    "title": f"Lab results over time for {patient_id}",
                    "labels": [item["date"] for item in visuals["lab_series"]],
                    "values": [item["value"] for item in visuals["lab_series"]],
                    "series_label": "Value",
                    "dataset_label": "Lab",
                }
            elif visuals["vital_series"]:
                chart = {
                    "type": "line",
                    "title": f"Vital signs over time for {patient_id}",
                    "labels": [item["date"] for item in visuals["vital_series"]],
                    "values": [item["value"] for item in visuals["vital_series"]],
                    "series_label": "Value",
                    "dataset_label": "Vital signs",
                }
    elif answer.get("question_type") in {"protocol", "trap"}:
        evidence = answer.get("evidence") or []
        if evidence:
            chart = {
                "type": "bar",
                "title": "Evidence check summary",
                "labels": ["Criteria met", "Criteria not met", "Insufficient evidence"],
                "values": [max(1, len(evidence)), 0, 0],
                "series_label": "Records",
            }

    return chart


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/overview")
def overview():
    tables = {domain: len(GRAPH.data.get(domain, [])) for domain in DOMAINS}
    total_records = sum(tables.values())
    stats = build_dashboard_charts()
    return jsonify({
        "subjects": len(GRAPH.subjects),
        "records": total_records,
        "tables": len(tables),
        "table_counts": tables,
        "charts": stats,
        "study_summary": (
            f"The study contains {len(GRAPH.subjects)} subjects with {total_records} linked records across "
            f"the nine core domains. The graph was indexed from the source CSV tables in hackathon-data/data."
        ),
        "available_tables": [
            {"name": name, "records": count}
            for name, count in sorted(tables.items())
        ],
    })


@app.route("/api/graph")
def graph_data():
    term = request.args.get("subject_id", "").strip()
    limit = int(request.args.get("limit", "250") or "250")
    limit = max(25, min(limit, 500))

    if term:
        subject_ids = _matching_subject_ids(term)
        if not subject_ids:
            return jsonify({
                "nodes": [],
                "edges": [],
                "message": f"No matching subject or site ID was found for '{term}'.",
                "summary": {"total_subjects": len(GRAPH.subjects), "shown_subjects": 0, "shown_records": 0},
            })
    else:
        subject_ids = list(GRAPH.subjects.keys())

    payload = _graph_summary_for_subjects(subject_ids, limit=limit)
    payload["legend"] = [
        {"label": "Subject", "type": "subject", "color": "#1f5dbe"},
        {"label": "Record", "type": "record", "color": "#73b5a6"},
        {"label": "Has record", "type": "edge", "color": "#5d8df0"},
    ]
    if term:
        payload["selected_subject"] = term.upper()
    return jsonify(payload)


@app.route("/api/ask", methods=["POST"])
def ask_atlas():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or payload.get("text") or ""
    question = str(question).strip()
    if not question:
        return jsonify({"error": "Please enter a question to ask ATLAS."}), 400

    try:
        answer = ATLAS.answer({"question": question})
        direct_answer = answer.answer if not isinstance(answer.answer, (dict, list)) else answer.answer
        evidence = answer.evidence or []
        limitations = None
        if not evidence:
            limitations = "Evidence is insufficient or absent in the supplied study data; no patient fact or protocol rule was inferred beyond the records available."
        elif answer.question_type in {"trap", "protocol"}:
            limitations = "The answer is limited to study-document and source-record evidence; no external adjudication or monitor guidance was assumed."

        visualization = build_question_visualization(question, {
            "answer": direct_answer,
            "question_type": answer.question_type,
            "evidence": evidence,
        })

        return jsonify({
            "question_type": answer.question_type,
            "confidence": answer.confidence,
            "direct_answer": direct_answer,
            "answer": direct_answer,
            "explanation": answer.explanation,
            "supporting_evidence": evidence,
            "evidence": evidence,
            "limitations": limitations,
            "visualization": visualization,
        })
    except Exception as exc:  # pragma: no cover - runtime guard for UI
        return jsonify({"error": "The ATLAS backend could not process the request.", "details": str(exc)}), 500


@app.route("/api/risk/predict")
def risk_prediction():
    subject_id = str(request.args.get("subject_id") or "").strip()
    if not subject_id:
        return jsonify({"error": "Please provide a subject_id."}), 400
    return jsonify(_build_subject_risk(subject_id))


@app.route("/api/risk/replay")
def risk_replay():
    subject_id = str(request.args.get("subject_id") or "").strip()
    if not subject_id:
        return jsonify({"error": "Please provide a subject_id."}), 400
    return jsonify(_build_subject_replay(subject_id))


@app.route("/api/patient", methods=["POST"])
def patient_lookup_post():
    payload = request.get_json(silent=True) or {}
    subject_id = str(payload.get("subject_id") or payload.get("usubjid") or "").strip()
    if not subject_id:
        return jsonify({"error": "Please enter a subject ID."}), 400
    return jsonify(patient_payload(subject_id))


@app.route("/api/patient/<subject_id>")
def patient_lookup(subject_id):
    return jsonify(patient_payload(subject_id))


def patient_payload(subject_id):
    data = GRAPH.patient360(subject_id)
    if not data["found"]:
        payload = {
            "found": False,
            "usubjid": subject_id,
            "demographics": {},
            "records": {domain: [] for domain in DOMAINS},
            "record_counts": {domain: 0 for domain in DOMAINS},
            "visuals": {"timeline": [], "lab_series": [], "vital_series": []},
        }
        return payload

    safe_records = {}
    for domain, records in data["records"].items():
        safe_records[domain] = records[:20]

    visuals = patient_visual_payload(subject_id, data)
    return {
        "found": True,
        "usubjid": data["usubjid"],
        "demographics": data["demographics"],
        "records": safe_records,
        "record_counts": {domain: len(data["records"].get(domain, [])) for domain in data["records"]},
        "visuals": visuals,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
