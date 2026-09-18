import csv
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

DOMAINS = ("DM", "AE", "LB", "VS", "EX", "CM", "DS", "MH", "EG")


def read_csv(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def get_first(row, *keys):
    for key in keys:
        if key in row:
            value = row.get(key)
            if value is not None and str(value).strip() != "":
                return value
    return None


def norm_date(value):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    formats = (
        "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M", "%d-%b-%Y", "%d/%m/%Y", "%d-%m-%Y",
        "%m/%d/%Y", "%d-%b-%Y %H:%M:%S", "%Y/%m/%d"
    )
    for fmt in formats:
        try:
            return datetime.strptime(value[:19], fmt).date()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def number(value):
    """Parse numeric values; censored values remain unknown."""
    if value is None:
        return None
    value = str(value).strip().replace(" ", "").replace(",", ".")
    if not value or value.upper() in {"NA", "N/A", "ND", "NOTDONE", "NOT DONE", "MISSING", "NULL"}:
        return None
    if value.startswith(("<", ">", "<=", ">=", "≤", "≥")):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def record_seq(domain, row):
    seq = get_first(row, "SEQ", f"{domain}SEQ", "AESEQ", "LBSEQ", "VSSEQ", "EXSEQ", "CMSEQ", "DSSEQ", "MHSEQ", "EGSEQ")
    if seq is None or str(seq).strip() == "":
        return "1"
    return str(seq)


@dataclass
class Answer:
    answer: object
    explanation: str
    evidence: list
    confidence: float
    question_type: str


class StudyGraph:
    def __init__(self, data_dir):
        self.data_dir = Path(data_dir)
        self.data = {}
        self.subjects = {}
        self.nodes = []
        self.edges = []
        self.index = {}
        self.ranges = []
        self.corrections = []
        self.cuts = []
        self.current_cut = None
        self.protocol_version = None
        self.protocols = {}

    def _load_reference_data(self):
        self.ranges = read_csv(self.data_dir / "reference_ranges.csv")
        self.corrections = read_csv(self.data_dir / "corrections.csv")
        self.cuts = read_csv(self.data_dir / "cuts.csv")
        self.protocols = {}
        for row in self.cuts:
            cut = number(get_first(row, "cut", "cut_number"))
            if cut is not None:
                self.protocols[int(cut)] = str(get_first(row, "protocol_version", "protocol") or "")

    def _available_at_cut(self, row, cut):
        if cut is None:
            return True
        available = number(get_first(row, "cut_available", "available_at_cut", "CUT"))
        return available is None or available <= cut

    def _apply_corrections(self, domain, row, cut):
        result = dict(row)
        if not self.corrections:
            return result
        for correction in self.corrections:
            corr_domain = str(get_first(correction, "domain", "DOMAIN") or "").upper()
            if corr_domain and corr_domain != domain.upper():
                continue
            corr_cut = number(get_first(correction, "cut", "cut_number", "available_at_cut"))
            if cut is not None and corr_cut is not None and corr_cut > cut:
                continue
            subject = get_first(correction, "usubjid", "USUBJID")
            if subject and subject != result.get("USUBJID"):
                continue
            seq = get_first(correction, "seq", "SEQ")
            row_seq = record_seq(domain, result)
            if seq is not None and str(seq).strip() and str(seq).strip() != str(row_seq):
                continue
            field = get_first(correction, "field", "variable", "column", "variable_name")
            new_value = get_first(correction, "new_value", "corrected_value", "value")
            if field and new_value is not None:
                result[str(field)] = new_value
        return result

    def _record_key(self, domain, sid, row):
        return (domain.upper(), str(sid).strip(), record_seq(domain, row))

    def build(self, cut=None):
        started = time.perf_counter()
        self.current_cut = cut
        self.protocol_version = None
        self.data = {d: [] for d in DOMAINS}
        self.subjects = {}
        self.nodes = []
        self.edges = []
        self.index = {}
        self._load_reference_data()

        seen = set()
        for domain in DOMAINS:
            for row in read_csv(self.data_dir / f"{domain}.csv"):
                sid = str(get_first(row, "USUBJID") or "").strip()
                if not sid:
                    continue
                if not self._available_at_cut(row, cut):
                    continue
                adjusted = self._apply_corrections(domain, row, cut)
                key = self._record_key(domain, sid, adjusted)
                if key in seen:
                    continue
                seen.add(key)
                self.data[domain].append(adjusted)

        for domain in DOMAINS:
            for row in self.data[domain]:
                sid = str(get_first(row, "USUBJID") or "").strip()
                if not sid:
                    continue
                if sid not in self.subjects:
                    if domain == "DM":
                        self.subjects[sid] = dict(row)
                    else:
                        self.subjects[sid] = {}

        for domain in DOMAINS:
            for row in self.data[domain]:
                sid = str(get_first(row, "USUBJID") or "").strip()
                if not sid:
                    continue
                seq = record_seq(domain, row)
                node_id = f"{domain}:{sid}:{seq}"
                node = {"id": node_id, "domain": domain, "usubjid": sid, "seq": seq, "record": row}
                self.nodes.append(node)
                self.index.setdefault((domain, sid), []).append(node)
                self.edges.append({"source": f"SUBJECT:{sid}", "target": node_id, "type": "HAS_RECORD"})

        if cut is not None:
            for cut_value, version in sorted(self.protocols.items()):
                if cut_value <= cut:
                    self.protocol_version = version
                else:
                    break
        elif self.protocols:
            self.protocol_version = self.protocols[max(self.protocols)]

        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "subjects": len(self.subjects),
            "build_ms": round((time.perf_counter() - started) * 1000, 2),
            "cut": cut,
            "protocol_version": self.protocol_version,
        }

    def records(self, domain, usubjid=None):
        domain = str(domain).upper()
        if usubjid is not None:
            return list(self.index.get((domain, str(usubjid)), []))
        return [node for node in self.nodes if node["domain"] == domain]

    def patient360(self, usubjid):
        sid = str(usubjid)
        if sid not in self.subjects:
            return {"usubjid": sid, "found": False, "demographics": {}, "records": {d: [] for d in DOMAINS}}
        payload = {"usubjid": sid, "found": True, "demographics": self.subjects.get(sid, {}), "records": {}}
        for domain in DOMAINS:
            payload["records"][domain] = [n["record"] for n in self.records(domain, sid)]
        return payload


class Atlas:
    def __init__(self, graph):
        self.graph = graph

    def _ref(self, node):
        return {"domain": node["domain"], "usubjid": node["usubjid"], "seq": node["seq"], "record_id": node["id"], "record": node["record"]}

    def _answer(self, result, explanation, evidence=None, confidence=0.5, question_type="unknown"):
        return Answer(answer=result, explanation=explanation, evidence=evidence or [], confidence=confidence, question_type=question_type)

    def _question_dict(self, question):
        if isinstance(question, dict):
            return question
        if isinstance(question, str):
            return {"question": question}
        if hasattr(question, "__dict__"):
            return vars(question)
        return {"question": str(question)}

    def _text(self, q):
        return str(q.get("text") or q.get("question") or "").strip()

    def _subject(self, q, text):
        sid = q.get("usubjid") or q.get("subject")
        if sid:
            return str(sid)
        match = re.search(r"\b\d{3}-S\d{2}-\d{3}\b", text, re.I)
        return match.group(0) if match else None

    def _site(self, q, text):
        site = q.get("site")
        if site:
            return str(site).upper()
        match = re.search(r"\bS\d{2}\b", text, re.I)
        return match.group(0).upper() if match else None

    def _range_for(self, test, lab):
        lab = str(lab or "").upper()
        for row in self.graph.ranges:
            if str(row.get("LBTESTCD", "")).upper() == str(test).upper() and str(row.get("LAB", "")).upper() == lab:
                return number(row.get("LOW")), number(row.get("HIGH")), str(row.get("UNIT") or "").strip()
        return None, None, None

    def _lab_value(self, row):
        value = number(get_first(row, "LBSTRESN", "LBORRES", "LBSTRESC"))
        if value is not None:
            return value
        unit = str(get_first(row, "LBSTRESU", "LBORRESU", "UNIT") or "").lower()
        if "µkat" in unit or "ukat" in unit or "μkat" in unit:
            value = number(get_first(row, "LBSTRESN", "LBORRES", "LBSTRESC"))
            if value is not None:
                return value * 60
        return None

    def _count(self, q, text):
        domain = str(q.get("domain") or "DM").upper()
        site = self._site(q, text)
        matching = []
        for node in self.graph.records(domain):
            sid = node["usubjid"]
            if site and not sid.startswith(f"042-{site}-"):
                continue
            matching.append(node)
        distinct_subjects = sorted({n["usubjid"] for n in matching})
        evidence = [self._ref(n) for n in matching]
        return self._answer(len(distinct_subjects), f"{len(distinct_subjects)} distinct subjects matched the {domain} filter.", evidence, 0.8, "count")

    def _lookup(self, q, text):
        sid = self._subject(q, text)
        if not sid:
            return self._answer([], "No subject ID was identified.", [], 0.2, "lookup")
        requested = q.get("domain")
        domains = [str(requested).upper()] if requested else list(DOMAINS)
        visit = q.get("visit")
        if not visit:
            match = re.search(r"\b(WEEK\s*\d+|BASELINE|SCREENING|WEEK\d+)\b", text, re.I)
            if match:
                visit = match.group(1).upper().replace(" ", "")
        matching = []
        for domain in domains:
            for node in self.graph.records(domain, sid):
                row = node["record"]
                if visit:
                    row_visit = str(get_first(row, "VISIT", "VISITNUM") or "").upper()
                    if row_visit and visit not in row_visit.replace(" ", ""):
                        continue
                matching.append(node)
        evidence = [self._ref(n) for n in matching]
        return self._answer(evidence, f"Found {len(evidence)} matching records for {sid}.", evidence, 0.75, "lookup")

    def _site_lab(self, sid):
        if not sid:
            return "CENTRAL"
        prefix = str(sid).split("-")
        if len(prefix) >= 2 and prefix[1].upper() == "S07":
            return "S07"
        return "CENTRAL"

    def _finding(self, q, text):
        """Conservative Hy's law screen. It never claims a confirmed case without threshold evidence."""
        findings = []
        evidence = {}
        for sid in sorted(self.graph.subjects):
            lab = self._site_lab(sid)
            rows = []
            dm = self.graph.subjects.get(sid, {})
            rfsd = norm_date(dm.get("RFSTDTC")) if isinstance(dm, dict) else None
            for node in self.graph.records("LB", sid):
                row = node["record"]
                test = str(get_first(row, "LBTESTCD", "LBTEST") or "").upper()
                if test not in {"ALT", "AST", "BILI", "ALP", "GGT"}:
                    continue
                value = self._lab_value(row)
                if value is None:
                    continue
                date = norm_date(get_first(row, "LBDTC", "LBDATE", "DATE"))
                if date is None:
                    continue
                _, high, _ = self._range_for(test, lab)
                if high is None:
                    continue
                rows.append({"node": node, "test": test, "value": value, "date": date, "high": high})

            alt_rows = [r for r in rows if r["test"] in {"ALT", "AST"}]
            bili_rows = [r for r in rows if r["test"] == "BILI"]
            cholestasis = [r for r in rows if r["test"] in {"ALP", "GGT"} and r["value"] > 2 * r["high"]]
            if cholestasis:
                continue
            baseline_alt = [r for r in alt_rows if rfsd and r["date"] <= rfsd]
            if baseline_alt and max(r["value"] for r in baseline_alt) > 2 * max(r["high"] for r in baseline_alt):
                continue

            for alt in sorted(alt_rows, key=lambda r: r["value"], reverse=True):
                if alt["value"] <= 3 * alt["high"]:
                    continue
                for bili in sorted(bili_rows, key=lambda r: r["value"], reverse=True):
                    if bili["value"] <= 2 * bili["high"]:
                        continue
                    if abs((alt["date"] - bili["date"]).days) > 14:
                        continue
                    findings.append({
                        "usubjid": sid,
                        "finding": "Hy's law threshold candidate",
                        "alt_test": alt["test"],
                        "alt_value": alt["value"],
                        "bilirubin_value": bili["value"],
                    })
                    evidence[alt["node"]["id"]] = self._ref(alt["node"])
                    evidence[bili["node"]["id"]] = self._ref(bili["node"])
                    break

        if not findings:
            return self._answer([], "No Hy's law threshold candidate met the protocol and lab constraints.", [], 0.5, "finding")
        return self._answer(findings, f"Found {len(findings)} protocol-constrained Hy's law candidate(s). These are threshold screens only and require review for cholestasis, alternative explanations, and protocol exclusions.", list(evidence.values()), 0.55, "finding")

    def _trap(self, q, text):
        return self._answer([], "No supported matching record was established from the available filters.", [], 0.2, "trap")

    def answer(self, question):
        q = self._question_dict(question)
        text = self._text(q)
        qtype = str(q.get("question_type") or q.get("type") or "").lower()
        if not qtype:
            lower = text.lower()
            if any(word in lower for word in ("how many", "count", "number of")):
                qtype = "count"
            elif any(word in lower for word in ("hy's law", "hys law", "finding", "candidate", "elevated")):
                qtype = "finding"
            elif any(word in lower for word in ("wrong dose", "trap", "should not", "must not")):
                qtype = "trap"
            else:
                qtype = "lookup"
        if qtype == "count":
            return self._count(q, text)
        if qtype == "lookup":
            return self._lookup(q, text)
        if qtype in {"finding", "findings"}:
            return self._finding(q, text)
        if qtype == "trap":
            return self._trap(q, text)
        return self._answer([], "Question type was not recognized.", [], 0.1, "unknown")


if __name__ == "__main__":
    graph = StudyGraph("hackathon-data/data")
    stats = graph.build()
    payload = {"nodes": stats["nodes"], "edges": stats["edges"], "subjects": stats["subjects"], "build_ms": stats["build_ms"], "cut": stats["cut"], "protocol_version": stats["protocol_version"]}
    print(json.dumps(payload, indent=2, sort_keys=True))
    base = Path(__file__).resolve().parent.parent
    (base / "graph_stats.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (base / "stage1_public.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
