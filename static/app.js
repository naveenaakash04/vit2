const navButtons = document.querySelectorAll('.nav-item');
const panes = document.querySelectorAll('.pane');

function setActivePane(id) {
  navButtons.forEach((button) => {
    const active = button.dataset.target === id;
    button.classList.toggle('active', active);
  });

  panes.forEach((pane) => {
    pane.classList.toggle('active', pane.id === id);
  });
}

navButtons.forEach((button) => {
  button.addEventListener('click', () => setActivePane(button.dataset.target));
});

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || 'Request failed.');
  }

  return data;
}

function showStatus(el, message, kind) {
  el.textContent = message;
  el.className = 'status';
  if (kind) {
    el.classList.add(kind);
  }
  el.classList.remove('hidden');
}

function clearAnswerUI() {
  document.getElementById('answer-card').classList.add('hidden');
  document.getElementById('evidence-card').classList.add('hidden');
}

function renderAnswer(data) {
  const card = document.getElementById('answer-card');
  const evidenceCard = document.getElementById('evidence-card');
  const answerValue = document.getElementById('answer-value');
  const answerExplanation = document.getElementById('answer-explanation');
  const answerType = document.getElementById('answer-type');
  const evidenceList = document.getElementById('evidence-list');

  answerType.textContent = data.question_type || 'unknown';
  answerValue.textContent = formatAnswerValue(data.answer);
  answerExplanation.textContent = data.explanation || 'No explanation returned.';
  card.classList.remove('hidden');

  evidenceList.innerHTML = '';
  if (Array.isArray(data.evidence) && data.evidence.length > 0) {
    data.evidence.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'evidence-item';
      const recordId = item.record_id || item.record?.id || 'record';
      const table = item.source_table || item.domain ? `${item.domain || 'source'}.csv` : 'source table';
      const subject = item.usubjid || item.record?.USUBJID || 'unknown';
      const seq = item.seq || item.record?.SEQ || item.record?.LBSEQ || item.record?.AESEQ || 'n/a';
      li.innerHTML = `
        <strong>${subject}</strong>
        <div class="evidence-meta">
          Source table: ${table}<br />
          Record ID: ${recordId}<br />
          Sequence: ${seq}
        </div>
      `;
      evidenceList.appendChild(li);
    });
    evidenceCard.classList.remove('hidden');
  } else {
    evidenceCard.classList.add('hidden');
  }
}

function formatAnswerValue(value) {
  if (value === null || value === undefined) {
    return 'No data available';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
}

async function askAtlasQuestion() {
  const input = document.getElementById('question-input');
  const question = input.value.trim();
  const status = document.getElementById('ask-status');

  if (!question) {
    showStatus(status, 'Please enter a question before asking ATLAS.', 'error');
    return;
  }

  showStatus(status, 'Loading answer...', 'loading');
  clearAnswerUI();

  try {
    const data = await fetchJson('/api/ask', {
      method: 'POST',
      body: JSON.stringify({ question }),
    });

    if (data.error) {
      throw new Error(data.error);
    }

    showStatus(status, 'Answer ready.', 'success');
    renderAnswer(data);
  } catch (error) {
    showStatus(status, error.message, 'error');
  }
}

async function loadOverview() {
  const summary = document.getElementById('study-summary');
  const totalSubjects = document.getElementById('total-subjects');
  const totalRecords = document.getElementById('total-records');
  const tableCount = document.getElementById('available-tables');
  const tableList = document.getElementById('table-list');

  try {
    const data = await fetchJson('/api/overview');
    totalSubjects.textContent = data.subjects;
    totalRecords.textContent = data.records;
    tableCount.textContent = data.tables;
    summary.textContent = data.study_summary;

    tableList.innerHTML = '';
    data.available_tables.forEach((entry) => {
      const item = document.createElement('div');
      item.className = 'table-item';
      item.innerHTML = `
        <strong>${entry.name}</strong>
        <span>${entry.records} records</span>
      `;
      tableList.appendChild(item);
    });
  } catch (error) {
    summary.textContent = 'The dashboard could not load the study summary.';
    totalSubjects.textContent = '--';
    totalRecords.textContent = '--';
    tableCount.textContent = '--';
  }
}

async function loadPatientLookup() {
  const input = document.getElementById('patient-input');
  const subjectId = input.value.trim();
  const status = document.getElementById('patient-status');
  const patientCard = document.getElementById('patient-card');
  const demographics = document.getElementById('patient-demographics');
  const recordsContainer = document.getElementById('patient-records');

  if (!subjectId) {
    showStatus(status, 'Please enter a subject ID to look up.', 'error');
    return;
  }

  showStatus(status, 'Loading patient profile...', 'loading');
  patientCard.classList.add('hidden');

  try {
    const data = await fetchJson(`/api/patient/${encodeURIComponent(subjectId)}`);
    if (!data.found) {
      showStatus(status, `Subject ${subjectId} was not found in the study graph.`, 'error');
      return;
    }

    document.getElementById('patient-header').textContent = `Subject ${data.usubjid}`;
    demographics.innerHTML = '';

    const demographicEntries = data.demographics || {};
    Object.entries(demographicEntries).forEach(([key, value]) => {
      const card = document.createElement('div');
      card.className = 'meta-card';
      card.innerHTML = `<span>${key}</span><strong>${formatAnswerValue(value)}</strong>`;
      demographics.appendChild(card);
    });

    recordsContainer.innerHTML = '';
    Object.entries(data.records || {}).forEach(([domain, entries]) => {
      if (!entries || entries.length === 0) {
        return;
      }

      const group = document.createElement('div');
      group.className = 'record-group';
      group.innerHTML = `<h4>${domain}</h4>`;

      const table = document.createElement('table');
      table.className = 'record-table';
      const rows = entries.slice(0, 10);
      const keys = Object.keys(rows[0] || {});

      const header = document.createElement('thead');
      header.innerHTML = `<tr>${keys.map((key) => `<th>${key}</th>`).join('')}</tr>`;
      table.appendChild(header);

      const tbody = document.createElement('tbody');
      rows.forEach((row) => {
        const tr = document.createElement('tr');
        tr.innerHTML = keys.map((key) => `<td>${formatAnswerValue(row[key])}</td>`).join('');
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      group.appendChild(table);
      recordsContainer.appendChild(group);
    });

    showStatus(status, 'Patient profile loaded.', 'success');
    patientCard.classList.remove('hidden');
  } catch (error) {
    showStatus(status, error.message, 'error');
  }
}

function bindExampleQuestions() {
  document.querySelectorAll('.example-button').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById('question-input');
      input.value = button.dataset.question;
      setActivePane('ask');
      input.focus();
    });
  });
}

document.getElementById('ask-button').addEventListener('click', askAtlasQuestion);
document.getElementById('patient-button').addEventListener('click', loadPatientLookup);
document.getElementById('question-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
    askAtlasQuestion();
  }
});
document.getElementById('patient-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    loadPatientLookup();
  }
});

bindExampleQuestions();
loadOverview();
setActivePane('dashboard');
