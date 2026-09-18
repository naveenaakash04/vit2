from app import app


def test_index_page_renders():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    text = response.get_data(as_text=True).lower()
    assert 'atlas' in text
    assert 'study data intelligence agent' in text.lower()


def test_overview_endpoint_uses_real_data():
    client = app.test_client()
    response = client.get('/api/overview')
    assert response.status_code == 200
    data = response.get_json()
    assert data['subjects'] == 241
    assert data['records'] > 0
    assert 'available_tables' in data
    assert data['tables'] == 9


def test_ask_endpoint_uses_real_agent():
    client = app.test_client()
    response = client.post('/api/ask', json={'question': 'How many subjects are in the study?'})
    assert response.status_code == 200
    data = response.get_json()
    assert data['question_type'] == 'count'
    assert data['answer'] == 241


def test_patient_endpoint_real_lookup():
    client = app.test_client()
    response = client.get('/api/patient/042-S01-001')
    assert response.status_code == 200
    data = response.get_json()
    assert data['found'] is True
    assert data['usubjid'] == '042-S01-001'
    assert 'demographics' in data


def test_missing_patient_is_handled_gracefully():
    client = app.test_client()
    response = client.get('/api/patient/042-S99-999')
    assert response.status_code == 200
    data = response.get_json()
    assert data['found'] is False


def test_index_page_lists_risk_sections():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert 'Risk Prediction' in text
    assert 'Risk Replay' in text


def test_risk_prediction_endpoint_uses_real_subject_data():
    client = app.test_client()
    response = client.get('/api/risk/predict?subject_id=042-S01-001')
    assert response.status_code == 200
    data = response.get_json()
    assert data['subject_id'] == '042-S01-001'
    assert 0 <= data['risk_score'] <= 100
    assert data['risk_level'] in {'Low', 'Moderate', 'High', 'Critical'}
    assert data['evidence']


def test_risk_replay_endpoint_orders_real_events_by_time():
    client = app.test_client()
    response = client.get('/api/risk/replay?subject_id=042-S01-001')
    assert response.status_code == 200
    data = response.get_json()
    assert data['subject_id'] == '042-S01-001'
    assert data['events']
    dates = [event['date'] for event in data['events']]
    assert dates == sorted(dates)
