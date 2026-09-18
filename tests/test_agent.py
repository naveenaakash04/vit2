import json
import pytest

from stage1.atlas import StudyGraph, Atlas


@pytest.fixture
def graph():
    g = StudyGraph('hackathon-data/data')
    g.build()
    return g


def test_graph_build_counts(graph):
    assert graph.subjects and len(graph.subjects) == 241
    assert len(graph.nodes) == 26925
    assert len(graph.edges) == 26925


def test_lookup_subject(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Show records for 042-S01-001'})
    assert answer.answer['usubjid'] == '042-S01-001'
    assert answer.confidence >= 0.8
    assert answer.evidence


def test_count_by_domain(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'How many AE records are in the study?'})
    assert isinstance(answer.answer, int)
    assert answer.answer >= 1
    assert answer.question_type == 'count'


def test_protocol_interp(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'What does the protocol say about Hy\'s law?'})
    assert 'ALT' in answer.answer
    assert answer.question_type == 'protocol'


def test_trap_detection_site_s07(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Is S07 a valid Hy\'s law site without conversion?'})
    assert answer.question_type == 'trap'
    assert 'µkat' in str(answer.answer) or 'unreliable' in str(answer.answer).lower()


def test_missing_subject_is_admitted(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Show records for 042-S99-999'})
    assert answer.answer['found'] is False
    assert answer.question_type == 'lookup'


def test_short_site_candidate_is_resolved_to_real_site_records(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Show me the Patient 360 summary for S07, with source records.'})
    assert answer.question_type == 'lookup'
    assert answer.answer != []
    assert answer.answer['usubjid'] == 'S07'
    assert answer.answer['found'] is True
    assert answer.answer['site'] == 'S07'
    assert answer.answer['subject_count'] > 0
    assert answer.answer['total_matching_records'] > 0
    assert 'Site S07 contains' in answer.explanation


def test_full_subject_id_lookup_with_source_records(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Patient 360 summary for 042-S02-001 with source records.'})
    assert answer.question_type == 'lookup'
    assert answer.answer['usubjid'] == '042-S02-001'
    assert answer.answer['found'] is True
    assert answer.answer['total_matching_records'] > 0
    assert answer.answer['source_tables']


def test_unknown_subject_id_is_reported_cleanly(graph):
    atlas = Atlas(graph)
    answer = atlas.answer({'question': 'Please show patient 360 for 042-S99-999 with source records.'})
    assert answer.question_type == 'lookup'
    assert answer.answer['found'] is False
    assert answer.answer['usubjid'] == '042-S99-999'
    assert 'No matching subject ID 042-S99-999' in answer.explanation


def test_short_subject_id_variants_are_recognized(graph):
    atlas = Atlas(graph)
    for question in [
        'Show records for 042-S01-001',
        'Patient 360 summary for 042-S01-001',
        'show me the source records for 042-S01-001',
    ]:
        answer = atlas.answer({'question': question})
        assert answer.question_type == 'lookup'
        assert answer.answer['usubjid'] == '042-S01-001'


def test_cli_export_smoke(tmp_path):
    from pathlib import Path
    import subprocess, sys

    root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, 'stage1/atlas.py', '--question', 'How many subjects are in the study?', '--export']
    result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True)
    payload = json.loads((root / 'graph_stats.json').read_text(encoding='utf-8'))
    assert payload['subjects'] == 241
    assert 'How many subjects' not in result.stdout or 'subjects' in result.stdout

