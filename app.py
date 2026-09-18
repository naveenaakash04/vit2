from pathlib import Path

from flask import Flask, jsonify, render_template, request

from stage1.atlas import Atlas, StudyGraph

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "hackathon-data" / "data"

app = Flask(__name__, template_folder="templates", static_folder="static")

GRAPH = StudyGraph(str(DATA_DIR))
GRAPH.build()
ATLAS = Atlas(GRAPH)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/overview")
def overview():
    tables = {"DM": len(GRAPH.data.get("DM", [])), "AE": len(GRAPH.data.get("AE", [])), "LB": len(GRAPH.data.get("LB", [])), "VS": len(GRAPH.data.get("VS", [])), "EX": len(GRAPH.data.get("EX", [])), "CM": len(GRAPH.data.get("CM", [])), "DS": len(GRAPH.data.get("DS", [])), "MH": len(GRAPH.data.get("MH", [])), "EG": len(GRAPH.data.get("EG", []))}
    total_records = sum(tables.values())
    return jsonify({
        "subjects": len(GRAPH.subjects),
        "records": total_records,
        "tables": len(tables),
        "table_counts": tables,
        "study_summary": (
            f"The study contains {len(GRAPH.subjects)} subjects with {total_records} linked records across "
            f"the nine core domains. The graph was indexed from the source CSV tables in hackathon-data/data."
        ),
        "available_tables": [
            {"name": name, "records": count}
            for name, count in sorted(tables.items())
        ],
    })


@app.route("/api/ask", methods=["POST"])
def ask_atlas():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or payload.get("text") or ""
    question = str(question).strip()
    if not question:
        return jsonify({"error": "Please enter a question to ask ATLAS."}), 400

    try:
        answer = ATLAS.answer({"question": question})
        return jsonify({
            "question_type": answer.question_type,
            "confidence": answer.confidence,
            "answer": answer.answer,
            "explanation": answer.explanation,
            "evidence": answer.evidence,
        })
    except Exception as exc:  # pragma: no cover - runtime guard for UI
        return jsonify({"error": "The ATLAS backend could not process the request.", "details": str(exc)}), 500


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
        return {
            "found": False,
            "usubjid": subject_id,
            "demographics": {},
            "records": {domain: [] for domain in ["DM", "AE", "LB", "VS", "EX", "CM", "DS", "MH", "EG"]},
        }

    safe_records = {}
    for domain, records in data["records"].items():
        safe_records[domain] = records[:20]

    return {
        "found": True,
        "usubjid": data["usubjid"],
        "demographics": data["demographics"],
        "records": safe_records,
        "record_counts": {domain: len(data["records"].get(domain, [])) for domain in data["records"]},
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
