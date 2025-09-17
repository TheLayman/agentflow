/* global mermaid */

let currentAgenticData = null;

document.addEventListener('DOMContentLoaded', function() {
  mermaid.initialize({ startOnLoad: false, theme: 'default' });
  const btn = document.getElementById('generate');
  const downloadJsonBtn = document.getElementById('downloadJson');
  if (btn) btn.addEventListener('click', generateAgentic);
  if (downloadJsonBtn) downloadJsonBtn.addEventListener('click', downloadAgenticJson);
  // Try to populate latest metadata and auto-enable button
  const latest = getLastWorkflowResponse();
  const meta = document.getElementById('latestMeta');
  if (latest && meta) {
    const tasks = (latest.workflow && latest.workflow.tasks) ? latest.workflow.tasks.length : 0;
    meta.textContent = `${latest.workflow?.title || 'Workflow'} — ${tasks} tasks ready.`;
  }
});

async function generateAgentic() {
  const btn = document.getElementById('generate');
  const loaderEl = document.getElementById('loader');
  const planEl = document.getElementById('plan');
  const latest = getLastWorkflowResponse();
  if (!latest || !latest.workflow) { alert('No decomposed workflow found. Go back and click Decompose first.'); return; }

  // Show loader and disable button
  if (loaderEl) loaderEl.style.display = 'flex';
  if (planEl) planEl.style.display = 'none';
  if (btn) { btn.disabled = true; btn.textContent = 'Generating...'; }

  try {
    const ddata = latest;
    // Agentic plan
    const pres = await fetch('/agentic_plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ workflow: ddata.workflow }),
    });
    if (!pres.ok) throw new Error('Failed to generate agentic plan');
    const pdata = await pres.json();

    currentAgenticData = pdata;
    renderAgentic(pdata, ddata.workflow);
  } catch (e) {
    console.error(e);
    alert('Generation failed. Check console/logs and try again.');
  } finally {
    if (loaderEl) loaderEl.style.display = 'none';
    if (planEl) planEl.style.display = 'block';
    if (btn) { btn.disabled = false; btn.textContent = 'Agentic Workflow'; }
  }
}

function renderAgentic(data, workflow) {
  const engineEl = document.getElementById('engine');
  const errEl = document.getElementById('llm_error');
  const rawEl = document.getElementById('llm_raw');
  if (engineEl) engineEl.textContent = data.engine || '';
  if (errEl) errEl.textContent = data.llm_error || '';
  if (rawEl) rawEl.textContent = data.llm_raw || '';

  // Agents
  const agentsEl = document.getElementById('agents');
  agentsEl.innerHTML = '';
  for (const a of data.agents || []) {
    const div = document.createElement('div');
    div.className = 'card';
    const skills = (a.skills || []).map(s => `<span class="pill">${escapeHtml(s)}</span>`).join(' ');
    const tools = (a.tools || []).map(t => `<span class="pill">${escapeHtml(t)}</span>`).join(' ');
    div.innerHTML = `
      <div style="display:flex; align-items:center; justify-content:space-between;">
        <div><strong>${escapeHtml(a.name)}</strong> <span class="muted">(${escapeHtml(a.id)})</span></div>
      </div>
      <div class="muted" style="margin:6px 0;">${escapeHtml(a.description || '')}</div>
      ${skills ? `<div style="margin:4px 0;">${skills}</div>` : ''}
      ${tools ? `<div style="margin:4px 0;">${tools}</div>` : ''}
    `;
    agentsEl.appendChild(div);
  }

  // Humans
  const humansEl = document.getElementById('humans');
  humansEl.innerHTML = '';
  for (const h of data.humans || []) {
    const div = document.createElement('div');
    div.className = 'card';
    div.innerHTML = `
      <div><strong>${escapeHtml(h.name)}</strong> <span class="muted">(${escapeHtml(h.id)})</span></div>
      <div class="muted" style="margin-top:6px;">${escapeHtml(h.description || '')}</div>
    `;
    humansEl.appendChild(div);
  }

  // Assignments table
  const tbody = document.querySelector('#assignments tbody');
  tbody.innerHTML = '';
  const taskById = Object.fromEntries((workflow.tasks || []).map(t => [t.id, t]));
  for (const asg of data.assignments || []) {
    const tr = document.createElement('tr');
    const t = taskById[asg.task_id] || { title: asg.task_id };
    tr.innerHTML = `
      <td><div><strong>${escapeHtml(t.title || t.name || asg.task_id)}</strong></div><div class="muted">${escapeHtml(asg.task_id)}</div></td>
      <td><span class="pill">${escapeHtml(asg.owner_type === 'human' ? 'Human' : 'Agent')}</span> <code>${escapeHtml(asg.owner_id)}</code></td>
      <td>${(asg.inputs || []).map(x => `<code>${escapeHtml(x)}</code>`).join(', ')}</td>
      <td>${(asg.outputs || []).map(x => `<code>${escapeHtml(x)}</code>`).join(', ')}</td>
      <td>${escapeHtml(asg.instructions || '')}</td>
    `;
    tbody.appendChild(tr);
  }
}

function downloadAgenticJson() {
  if (!currentAgenticData) {
    alert('No agentic data available. Generate first.');
    return;
  }
  const jsonString = JSON.stringify(currentAgenticData, null, 2);
  const blob = new Blob([jsonString], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  const ts = new Date().toISOString().replace(/[:.]/g, '-');
  a.download = `agentic-plan-${ts}.json`;
  a.href = url;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

function getLastWorkflowResponse() {
  let raw = null;
  try { raw = window.localStorage.getItem('lastWorkflowResponse'); } catch (_) {}
  if (!raw) { try { raw = window.sessionStorage.getItem('lastWorkflowResponse'); } catch (_) {} }
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

function escapeHtml(s) {
  return String(s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
