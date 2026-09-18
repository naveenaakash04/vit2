const navButtons = document.querySelectorAll('.nav-item');
const panes = document.querySelectorAll('.pane');
const chartRegistry = {};

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
  document.getElementById('answer-visualization').classList.add('hidden');
  document.getElementById('evidence-card').classList.add('hidden');
}

function safeText(value) {
  return value === null || value === undefined ? 'n/a' : String(value);
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
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

function destroyChart(id) {
  if (chartRegistry[id]) {
    chartRegistry[id].destroy();
    delete chartRegistry[id];
  }
}

function renderBarChart(canvasId, labels, values, title, color, labelText) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  destroyChart(canvasId);
  if (!labels || labels.length === 0 || !values || values.length === 0) {
    ctx.parentElement.classList.add('empty-state');
    return;
  }
  ctx.parentElement.classList.remove('empty-state');
  chartRegistry[canvasId] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: labelText,
        data: values,
        backgroundColor: Array.from({ length: labels.length }, (_, index) => {
          const palette = ['#1f5dbe', '#5d8df0', '#73b5a6', '#f0ad4e', '#7b9a32', '#d97575', '#34a3a0', '#9f7aea', '#4b5d8a'];
          return palette[index % palette.length];
        }),
        borderColor: 'rgba(31,93,190,0.7)',
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: { display: true, text: title, color: '#1a2233', font: { weight: '700', size: 13 } },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { precision: 0 },
          title: { display: true, text: labelText, color: '#5a6b88' },
        },
        x: {
          ticks: { autoSkip: false, maxRotation: 45, minRotation: 30 },
        },
      },
    },
  });
}

function renderLineChart(canvasId, labels, values, title, labelText) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  destroyChart(canvasId);
  if (!labels || labels.length === 0 || !values || values.length === 0) {
    ctx.parentElement.classList.add('empty-state');
    return;
  }
  ctx.parentElement.classList.remove('empty-state');
  chartRegistry[canvasId] = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: labelText,
        data: values,
        borderColor: '#1f5dbe',
        backgroundColor: 'rgba(31, 93, 190, 0.12)',
        borderWidth: 2,
        pointBackgroundColor: '#1f5dbe',
        pointRadius: 3,
        fill: true,
        tension: 0.25,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { display: true },
        title: { display: true, text: title, color: '#1a2233', font: { weight: '700', size: 13 } },
      },
      scales: {
        y: { beginAtZero: false, title: { display: true, text: labelText, color: '#5a6b88' } },
        x: { title: { display: true, text: 'Date', color: '#5a6b88' } },
      },
    },
  });
}

function renderDoughnutChart(canvasId, labels, values, title) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  destroyChart(canvasId);
  if (!labels || labels.length === 0 || !values || values.length === 0) {
    ctx.parentElement.classList.add('empty-state');
    return;
  }
  ctx.parentElement.classList.remove('empty-state');
  chartRegistry[canvasId] = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        label: 'Records',
        data: values,
        backgroundColor: ['#1f5dbe', '#5d8df0', '#73b5a6', '#f0ad4e', '#7b9a32', '#d97575', '#34a3a0', '#9f7aea', '#4b5d8a'],
        borderWidth: 1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom' },
        title: { display: true, text: title, color: '#1a2233', font: { weight: '700', size: 13 } },
      },
    },
  });
}

function renderAnswer(data) {
  const card = document.getElementById('answer-card');
  const evidenceCard = document.getElementById('evidence-card');
  const answerValue = document.getElementById('answer-value');
  const answerExplanation = document.getElementById('answer-explanation');
  const answerType = document.getElementById('answer-type');
  const evidenceList = document.getElementById('evidence-list');
  const visCard = document.getElementById('answer-visualization');

  const directAnswer = data.direct_answer ?? data.answer ?? 'No answer available';
  const explanation = data.explanation || 'No explanation returned.';
  const limitations = data.limitations || '';
  const evidence = Array.isArray(data.supporting_evidence) ? data.supporting_evidence : (Array.isArray(data.evidence) ? data.evidence : []);
  const visualization = data.visualization || null;

  let summaryText = formatAnswerValue(directAnswer);
  if (directAnswer && typeof directAnswer === 'object' && directAnswer.total_matching_records !== undefined) {
    summaryText = `${safeText(directAnswer.usubjid)} • ${safeText(directAnswer.total_matching_records)} records • ${safeText(directAnswer.source_tables ? directAnswer.source_tables.join(', ') : '')}`;
  }

  answerType.textContent = data.question_type || 'unknown';
  answerValue.textContent = summaryText;
  const shortExplanation = explanation && explanation.includes(':') ? explanation.split(':').slice(1).join(':').trim() : explanation;
  answerExplanation.innerHTML = `<strong>Summary:</strong> ${escapeHtml(shortExplanation || 'No extra detail.')}${limitations ? `<br><br><strong>Note:</strong> ${escapeHtml(limitations)}` : ''}`;
  card.classList.remove('hidden');

  if (visualization && visualization.type) {
    visCard.classList.remove('hidden');
    if (visualization.type === 'bar') {
      renderBarChart('answer-chart', visualization.labels, visualization.values, visualization.title, '#1f5dbe', visualization.series_label || 'Value');
    } else if (visualization.type === 'line') {
      renderLineChart('answer-chart', visualization.labels, visualization.values, visualization.title, visualization.series_label || 'Value');
    }
  } else {
    visCard.classList.add('hidden');
    destroyChart('answer-chart');
  }

  evidenceList.innerHTML = '';
  if (evidence.length > 0) {
    evidence.forEach((item) => {
      const li = document.createElement('li');
      li.className = 'evidence-item';
      const recordId = item.record_id || item.record?.id || 'record';
      const table = item.source_table || (item.domain ? `${item.domain}.csv` : 'source table');
      const subject = item.usubjid || item.record?.USUBJID || 'unknown';
      const seq = item.seq || item.record?.SEQ || item.record?.LBSEQ || item.record?.AESEQ || 'n/a';
      li.innerHTML = `
        <strong>${escapeHtml(subject)}</strong>
        <div class="evidence-meta">
          Source table: ${escapeHtml(table)}<br />
          Record ID: ${escapeHtml(recordId)}<br />
          Sequence: ${escapeHtml(seq)}
        </div>
      `;
      evidenceList.appendChild(li);
    });
    evidenceCard.classList.remove('hidden');
  } else {
    evidenceCard.classList.add('hidden');
  }
}

function applyPatientFilters(records, startDate, endDate, domainFilter) {
  let filtered = records;
  if (domainFilter && domainFilter !== 'all') {
    filtered = filtered.filter((row) => row.domain === domainFilter);
  }
  if (startDate) {
    filtered = filtered.filter((row) => row.date >= startDate);
  }
  if (endDate) {
    filtered = filtered.filter((row) => row.date <= endDate);
  }
  return filtered;
}

function renderPatientCharts(data) {
  const startDate = document.getElementById('date-from').value;
  const endDate = document.getElementById('date-to').value;
  const domainFilter = document.getElementById('category-filter').value;

  const timeline = applyPatientFilters(data.visuals?.timeline || [], startDate, endDate, domainFilter);
  const labSeries = applyPatientFilters(data.visuals?.lab_series || [], startDate, endDate, 'LB');
  const vitalSeries = applyPatientFilters(data.visuals?.vital_series || [], startDate, endDate, 'VS');

  if (timeline.length > 0) {
    renderLineChart('timeline-chart', timeline.map((entry) => entry.date), timeline.map((entry) => Number(entry.value) || 0), 'Subject timeline', 'Value');
  } else {
    destroyChart('timeline-chart');
    document.getElementById('timeline-chart').parentElement.classList.add('empty-state');
  }

  if (labSeries.length > 0) {
    renderLineChart('lab-chart', labSeries.map((entry) => entry.date), labSeries.map((entry) => Number(entry.value) || 0), 'Lab results over time', 'Result');
  } else {
    destroyChart('lab-chart');
    document.getElementById('lab-chart').parentElement.classList.add('empty-state');
  }

  if (vitalSeries.length > 0) {
    renderLineChart('vital-chart', vitalSeries.map((entry) => entry.date), vitalSeries.map((entry) => Number(entry.value) || 0), 'Vital signs over time', 'Result');
  } else {
    destroyChart('vital-chart');
    document.getElementById('vital-chart').parentElement.classList.add('empty-state');
  }
}

let activeGraphNetwork = null;
let selectedGraphNode = null;

function setGraphStatus(message, kind = 'info') {
  const el = document.getElementById('graph-status');
  el.textContent = message;
  el.className = 'graph-status';
  if (kind === 'error') {
    el.style.color = '#c23b3b';
  } else if (kind === 'success') {
    el.style.color = '#1d7f5a';
  } else {
    el.style.color = '#5a6b88';
  }
}

function renderGraphLegend(legend = []) {
  const container = document.getElementById('graph-legend');
  if (!container) return;
  container.innerHTML = '';
  if (!legend.length) return;
  legend.forEach((item) => {
    const node = document.createElement('div');
    node.className = 'legend-item';
    node.innerHTML = `<span class="legend-dot" style="background:${item.color || '#1f5dbe'}"></span><span>${escapeHtml(item.label)}</span>`;
    container.appendChild(node);
  });
}

function showGraphDetails(node, details) {
  const info = document.getElementById('graph-node-info');
  const panel = document.getElementById('graph-details');
  if (!info || !panel) return;

  selectedGraphNode = node && node.id ? node.id : null;
  const nodeType = node && node.type ? node.type : 'record';
  const recordMeta = details && details.record ? details.record : {};
  const payload = [];

  if (nodeType === 'subject') {
    payload.push({ label: 'Subject ID', value: node.label || 'Unknown subject' });
    payload.push({ label: 'Type', value: 'Subject node' });
    payload.push({ label: 'Connected records', value: details && details.connected_records ? details.connected_records.length : 0 });
    const demo = details && details.demographics ? details.demographics : {};
    Object.entries(demo).slice(0, 4).forEach(([key, value]) => {
      payload.push({ label: key, value: String(value) });
    });
  } else {
    payload.push({ label: 'Domain', value: details && details.domain ? details.domain : (node.domain || 'Unknown') });
    payload.push({ label: 'Subject', value: details && details.subject_id ? details.subject_id : 'Unknown' });
    payload.push({ label: 'Sequence', value: details && details.seq ? details.seq : 'n/a' });
    payload.push({ label: 'Source table', value: details && details.source_table ? details.source_table : 'n/a' });
    Object.entries(recordMeta).slice(0, 5).forEach(([key, value]) => {
      if (value !== null && value !== undefined && String(value).trim() !== '') {
        payload.push({ label: key, value: String(value) });
      }
    });
  }

  info.innerHTML = '';
  payload.forEach((entry) => {
    const item = document.createElement('div');
    item.className = 'graph-node-card';
    item.innerHTML = `<div class="label">${escapeHtml(entry.label)}</div><strong>${escapeHtml(entry.value)}</strong>`;
    info.appendChild(item);
  });

  panel.classList.remove('hidden');
}

function hideGraphDetails() {
  const panel = document.getElementById('graph-details');
  if (panel) {
    panel.classList.add('hidden');
  }
  selectedGraphNode = null;
}

function renderGraph(data) {
  const container = document.getElementById('graph-canvas');
  const legendContainer = document.getElementById('graph-legend');
  if (!container) return;

  renderGraphLegend(data.legend || []);

  if (!data || !Array.isArray(data.nodes) || !Array.isArray(data.edges)) {
    setGraphStatus('The graph is empty or unavailable.', 'error');
    container.innerHTML = '<div class="graph-empty">No graph data available.</div>';
    return;
  }

  if (!data.nodes.length) {
    setGraphStatus('No graph nodes were returned for this subject or search term.', 'error');
    container.innerHTML = '<div class="graph-empty">No matching records in the study graph.</div>';
    hideGraphDetails();
    return;
  }

  const nodes = new vis.DataSet(data.nodes.map((node) => ({
    id: node.id,
    label: node.label || node.id,
    type: node.type || 'subject',
    color: {
      background: node.color || '#1f5dbe',
      border: '#143a6b',
      highlight: { background: '#5d8df0', border: '#143a6b' }
    },
    title: node.title || node.label || node.id,
    font: { color: '#12263d', face: 'Arial', size: 12 },
    shape: node.shape || 'dot',
    size: node.size || 18,
    value: node.size || 18,
    borderWidth: 2,
    mass: 2,
    meta: node.meta || {},
  })));
  const edges = new vis.DataSet(data.edges.map((edge) => ({
    id: `${edge.from}-${edge.to}`,
    from: edge.from,
    to: edge.to,
    label: edge.label || '',
    arrows: edge.arrows || 'to',
    color: { color: edge.color || '#5d8df0', highlight: '#1f5dbe' },
    width: edge.width || 1.5,
    font: { color: '#5a6b88', size: 10 },
  })));

  const options = {
    interaction: {
      hover: true,
      dragView: true,
      dragNodes: true,
      zoomView: true,
      navigationButtons: true,
      keyboard: true,
      selectConnectedEdges: false,
    },
    nodes: {
      shape: 'dot',
      scaling: { min: 12, max: 30 },
      font: { size: 12, color: '#102031' },
      borderWidth: 2,
      shadow: true,
    },
    edges: {
      smooth: { type: 'dynamic', forceDirection: 'none' },
      arrows: { to: { enabled: true, scaleFactor: 0.7 } },
      selectionWidth: 2,
    },
    physics: {
      enabled: true,
      barnesHut: { gravitationalConstant: -3000 },
      stabilization: { iterations: 80 },
    },
    layout: { improvedLayout: true },
    autoResize: true,
  };

  if (activeGraphNetwork) {
    activeGraphNetwork.setData({ nodes, edges });
    activeGraphNetwork.setOptions(options);
    activeGraphNetwork.fit({ animation: true });
  } else {
    activeGraphNetwork = new vis.Network(container, { nodes, edges }, options);
  }

  if (data.selected_subject) {
    const target = `subject:${data.selected_subject}`;
    const targetNode = nodes.get(target);
    if (targetNode) {
      activeGraphNetwork.selectNodes([target]);
      activeGraphNetwork.focus(target, { scale: 1.1, animation: true });
      showGraphDetails(targetNode, data.node_details && data.node_details[target]);
    }
  }

  activeGraphNetwork.on('click', (params) => {
    if (!params.nodes || !params.nodes.length) {
      hideGraphDetails();
      return;
    }
    const nodeId = params.nodes[0];
    const node = nodes.get(nodeId);
    const detail = data.node_details && data.node_details[nodeId];
    showGraphDetails(node, detail);
  });

  setGraphStatus(data.message || `Graph loaded: ${data.summary?.shown_subjects || 0} subject(s) and ${data.summary?.shown_records || 0} record(s) shown.`, 'success');
  if (legendContainer) {
    legendContainer.classList.remove('hidden');
  }
}

async function loadGraph(subjectId = '') {
  const input = document.getElementById('graph-search');
  const value = subjectId || (input ? input.value.trim() : '');
  const container = document.getElementById('graph-canvas');
  if (!container) return;

  setGraphStatus('Loading study graph…', 'info');
  try {
    const data = await fetchJson(`/api/graph?subject_id=${encodeURIComponent(value)}`);
    if (data && data.message && !data.nodes.length) {
      setGraphStatus(data.message, 'error');
      renderGraphLegend(data.legend || []);
      hideGraphDetails();
      return;
    }
    if (input) {
      input.value = data.selected_subject || value || '';
    }
    renderGraph(data);
  } catch (error) {
    setGraphStatus(error.message || 'Unable to load graph data.', 'error');
  }
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

    const tableCounts = Array.isArray(data.charts?.table_counts) ? data.charts.table_counts : [];
    const timeSeries = Array.isArray(data.charts?.records_over_time) ? data.charts.records_over_time : [];
    const categoryBreakdown = Array.isArray(data.charts?.category_breakdown) ? data.charts.category_breakdown : [];

    renderBarChart('table-chart', tableCounts.map((entry) => entry.label), tableCounts.map((entry) => entry.value), 'Records by source table', '#1f5dbe', 'Records');
    renderLineChart('time-chart', timeSeries.map((entry) => entry.label), timeSeries.map((entry) => entry.value), 'Records over time', 'Count');
    renderDoughnutChart('category-chart', categoryBreakdown.map((entry) => entry.label), categoryBreakdown.map((entry) => entry.value), 'Data category mix');

    tableList.innerHTML = '';
    data.available_tables.forEach((entry) => {
      const item = document.createElement('div');
      item.className = 'table-item';
      item.innerHTML = `
        <strong>${escapeHtml(entry.name)}</strong>
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
      card.innerHTML = `<span>${escapeHtml(key)}</span><strong>${escapeHtml(formatAnswerValue(value))}</strong>`;
      demographics.appendChild(card);
    });

    recordsContainer.innerHTML = '';
    Object.entries(data.records || {}).forEach(([domain, entries]) => {
      if (!entries || entries.length === 0) {
        return;
      }
      const group = document.createElement('div');
      group.className = 'record-group';
      group.innerHTML = `<h4>${escapeHtml(domain)}</h4>`;
      const table = document.createElement('table');
      table.className = 'record-table';
      const rows = entries.slice(0, 10);
      const keys = Object.keys(rows[0] || {});
      const header = document.createElement('thead');
      header.innerHTML = `<tr>${keys.map((key) => `<th>${escapeHtml(key)}</th>`).join('')}</tr>`;
      table.appendChild(header);
      const tbody = document.createElement('tbody');
      rows.forEach((row) => {
        const tr = document.createElement('tr');
        tr.innerHTML = keys.map((key) => `<td>${escapeHtml(formatAnswerValue(row[key]))}</td>`).join('');
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);
      group.appendChild(table);
      recordsContainer.appendChild(group);
    });

    renderPatientCharts(data);
    showStatus(status, 'Patient profile loaded.', 'success');
    patientCard.classList.remove('hidden');
  } catch (error) {
    showStatus(status, error.message, 'error');
  }
}

function renderRiskPrediction(data) {
  const card = document.getElementById('risk-predict-card');
  const status = document.getElementById('risk-predict-status');
  const scorePill = document.getElementById('risk-score-pill');
  const scoreNumber = document.getElementById('risk-score-number');
  const meterFill = document.getElementById('risk-meter-fill');
  const summaryText = document.getElementById('risk-summary-text');
  const evidenceList = document.getElementById('risk-evidence-list');

  if (!data || !data.subject_id || !card) {
    showStatus(status, 'Risk prediction could not be generated.', 'error');
    return;
  }

  const riskScore = Number(data.risk_score || 0);
  const riskLevel = data.risk_level || 'Low';
  scorePill.textContent = riskLevel;
  scoreNumber.textContent = `${riskScore}`;
  meterFill.style.width = `${Math.min(Math.max(riskScore, 0), 100)}%`;
  meterFill.style.background = riskScore >= 75 ? '#c23b3b' : riskScore >= 50 ? '#c77500' : riskScore >= 25 ? '#f0ad4e' : '#1d7f5a';
  summaryText.textContent = data.summary || 'No summary available.';
  evidenceList.innerHTML = '';

  const evidence = Array.isArray(data.evidence) ? data.evidence : [];
  if (!evidence.length) {
    const li = document.createElement('li');
    li.textContent = 'No active risk signals were identified for this subject in the current records.';
    evidenceList.appendChild(li);
  }

  evidence.forEach((entry) => {
    const item = document.createElement('li');
    item.className = 'evidence-item';
    item.innerHTML = `
      <strong>${escapeHtml(entry.label || 'Risk signal')}</strong>
      <div class="evidence-meta">
        Category: ${escapeHtml(entry.category || 'study record')}<br />
        Severity: ${escapeHtml(entry.severity || 'Unknown')}<br />
        Value: ${escapeHtml(formatAnswerValue(entry.value))}
      </div>
    `;
    evidenceList.appendChild(item);
  });

  card.classList.remove('hidden');
  showStatus(status, `Risk prediction loaded for ${data.subject_id}.`, 'success');
}

async function loadRiskPrediction() {
  const input = document.getElementById('risk-predict-input');
  const subjectId = (input ? input.value.trim() : '').trim();
  const status = document.getElementById('risk-predict-status');

  if (!subjectId) {
    showStatus(status, 'Please enter a subject ID to calculate risk.', 'error');
    return;
  }

  try {
    const data = await fetchJson(`/api/risk/predict?subject_id=${encodeURIComponent(subjectId)}`);
    renderRiskPrediction(data);
  } catch (error) {
    showStatus(status, error.message, 'error');
  }
}

function renderRiskReplay(data) {
  const card = document.getElementById('risk-replay-card');
  const status = document.getElementById('risk-replay-status');
  const countEl = document.getElementById('risk-replay-count');
  const listEl = document.getElementById('risk-replay-list');

  if (!data || !data.subject_id || !card) {
    showStatus(status, 'No replay data is available for this subject.', 'error');
    return;
  }

  const events = Array.isArray(data.events) ? data.events : [];
  countEl.textContent = `${events.length} events`;
  listEl.innerHTML = '';

  if (!events.length) {
    const empty = document.createElement('div');
    empty.className = 'timeline-empty';
    empty.textContent = 'No event timeline was found for this subject.';
    listEl.appendChild(empty);
  } else {
    events.forEach((event) => {
      const item = document.createElement('div');
      item.className = 'timeline-entry';
      const valueText = event.value === null || event.value === undefined ? 'n/a' : formatAnswerValue(event.value);
      item.innerHTML = `
        <div class="timeline-date">${escapeHtml(event.date || 'Unknown')}</div>
        <div class="timeline-body">
          <strong>${escapeHtml(event.domain || 'Study')}</strong>
          <div>${escapeHtml(event.label || 'Study event')}</div>
          <small>${escapeHtml(valueText)} ${escapeHtml(event.unit || '')}</small>
        </div>
      `;
      listEl.appendChild(item);
    });
  }

  card.classList.remove('hidden');
  showStatus(status, `Replay loaded for ${data.subject_id}.`, 'success');
}

async function loadRiskReplay() {
  const input = document.getElementById('risk-replay-input');
  const subjectId = (input ? input.value.trim() : '').trim();
  const status = document.getElementById('risk-replay-status');

  if (!subjectId) {
    showStatus(status, 'Please enter a subject ID to replay the timeline.', 'error');
    return;
  }

  try {
    const data = await fetchJson(`/api/risk/replay?subject_id=${encodeURIComponent(subjectId)}`);
    renderRiskReplay(data);
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
document.getElementById('risk-predict-button').addEventListener('click', loadRiskPrediction);
document.getElementById('risk-replay-button').addEventListener('click', loadRiskReplay);
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
document.getElementById('risk-predict-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    loadRiskPrediction();
  }
});
document.getElementById('risk-replay-input').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    loadRiskReplay();
  }
});
document.getElementById('date-from').addEventListener('change', () => {
  const subjectId = document.getElementById('patient-input').value.trim();
  if (subjectId) {
    loadPatientLookup();
  }
});
document.getElementById('date-to').addEventListener('change', () => {
  const subjectId = document.getElementById('patient-input').value.trim();
  if (subjectId) {
    loadPatientLookup();
  }
});
document.getElementById('category-filter').addEventListener('change', () => {
  const subjectId = document.getElementById('patient-input').value.trim();
  if (subjectId) {
    loadPatientLookup();
  }
});

bindExampleQuestions();
loadOverview();
document.getElementById('risk-predict-input').value = '042-S01-001';
document.getElementById('risk-replay-input').value = '042-S01-001';
loadRiskPrediction();
loadRiskReplay();
setActivePane('dashboard');
