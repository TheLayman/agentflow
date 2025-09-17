/* global mermaid, renderMermaidIn, cleanMermaidForExport, fallbackDownloadSvg, saveLastWorkflowResponse */

// Global variable to store LLM raw data for download
let currentLlmData = null;

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
  // Add event listeners
  const decomposeBtn = document.getElementById('decompose');
  const downloadJsonBtn = document.getElementById('downloadJson');
  
  if (decomposeBtn) {
    decomposeBtn.addEventListener('click', decompose);
  }
  if (downloadJsonBtn) {
    downloadJsonBtn.addEventListener('click', downloadLlmJson);
  }
});

async function decompose() {
  const inputEl = document.getElementById('input');
  const titleEl = document.getElementById('title');
  const decomposeBtn = document.getElementById('decompose');
  const loaderEl = document.getElementById('loader');
  const renderEl = document.getElementById('render');
  
  if (!inputEl || !titleEl) {
    console.error('Required DOM elements not found:', {
      input: !!inputEl,
      title: !!titleEl,
    });
    alert('Page not fully loaded. Please try again.');
    return;
  }
  
  const text = inputEl.value.trim();
  const title = titleEl.value.trim();
  if (!text) { alert('Please describe the process'); return; }

  // Show loader and disable button
  if (loaderEl) loaderEl.style.display = 'flex';
  if (renderEl) renderEl.style.display = 'none';
  if (decomposeBtn) {
    decomposeBtn.disabled = true;
    decomposeBtn.textContent = 'Decomposing...';
  }

  try {
    const res = await fetch('/decompose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, title: title || null }),
    });
    if (!res.ok) { 
      throw new Error('Failed to decompose'); 
    }
    const data = await res.json();
    // Persist latest workflow/response for Agentic page
    saveLastWorkflowResponse(data);
    const mer = data.mermaid;
    
    const mermaidEl = document.getElementById('mermaid');
    if (mermaidEl) {
      mermaidEl.textContent = mer;
    }
    
    // Render mermaid diagram with error handling
    if (mer && mer.trim()) {
      renderMermaidIn('render', mer).catch(err => {
        console.error('Failed to render mermaid in main:', err);
        const mount = document.getElementById('render');
        if (mount) {
          mount.innerHTML = '<pre style="color:#ef4444; background:#1f1f1f; padding:10px; border-radius:4px;">Failed to render diagram</pre>';
        }
      });
    } else {
      const mount = document.getElementById('render');
      if (mount) {
        mount.innerHTML = '<pre style="color:#f59e0b; background:#1f1f1f; padding:10px; border-radius:4px;">No mermaid diagram available</pre>';
      }
    }
    
    renderIssues(data.issues || []);
    renderDebug(data);
  } catch (error) {
    console.error('Decompose error:', error);
    alert('Failed to decompose. Please try again.');
  } finally {
    // Hide loader and re-enable button
    if (loaderEl) loaderEl.style.display = 'none';
    if (renderEl) renderEl.style.display = 'block';
    if (decomposeBtn) {
      decomposeBtn.disabled = false;
      decomposeBtn.textContent = 'Decompose';
    }
  }
}

// renderMermaid moved to common.js as renderMermaidIn(containerId, code)

function renderIssues(issues) {
  const ul = document.getElementById('issues');
  if (!ul) {
    console.error('Issues element not found');
    return;
  }
  
  ul.innerHTML = '';
  if (!issues.length) { ul.innerHTML = '<li>No issues detected</li>'; return; }
  for (const i of issues) {
    const li = document.createElement('li');
    li.textContent = i;
    ul.appendChild(li);
  }
}

function renderDebug(data) {
  const engineEl = document.getElementById('engine');
  const errEl = document.getElementById('llm_error');
  const rawEl = document.getElementById('llm_raw');
  
  if (!engineEl || !errEl || !rawEl) {
    console.error('Debug elements not found');
    return;
  }
  
  // Store the entire response data for potential JSON download
  currentLlmData = data;
  
  engineEl.textContent = data.engine || '';
  errEl.textContent = data.llm_error || '';
  rawEl.textContent = data.llm_raw || '';
}

// cleanMermaidForExport and fallbackDownloadSvg moved to common.js

function downloadLlmJson() {
  if (!currentLlmData) {
    alert('No LLM data available to download. Please decompose a workflow first.');
    return;
  }
  
  let jsonData;
  
  // Try to parse the llm_raw field as JSON if it exists
  if (currentLlmData.llm_raw) {
    try {
      // Parse the raw LLM response which should be JSON
      jsonData = JSON.parse(currentLlmData.llm_raw);
    } catch (e) {
      // If parsing fails, include the raw text in the download
      jsonData = {
        raw_text: currentLlmData.llm_raw,
        parse_error: e.message,
        engine: currentLlmData.engine,
        llm_error: currentLlmData.llm_error
      };
    }
  } else {
    // Fallback to the entire response data if no raw LLM data
    jsonData = currentLlmData;
  }
  
  // Create the JSON blob and download
  const jsonString = JSON.stringify(jsonData, null, 2);
  const blob = new Blob([jsonString], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  a.download = `llm-response-${timestamp}.json`;
  a.href = url;
  a.click();
  
  // Clean up the URL object
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
