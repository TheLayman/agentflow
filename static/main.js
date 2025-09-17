/* global mermaid */

// Global variable to store LLM raw data for download
let currentLlmData = null;

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
  mermaid.initialize({
    startOnLoad: false,
    theme: 'base',
    themeVariables: {
      lineColor: '#cbd5e1',
      arrowheadColor: '#cbd5e1',
      primaryTextColor: '#000000',
      textColor: '#000000',
      edgeLabelBackground: '#0a1324',
      primaryColor: '#f1f5f9',
      primaryBorderColor: '#94a3b8',
      secondaryColor: '#f8fafc',
      tertiaryColor: '#cbd5e1',
      background: '#0f172a',
      mainBkg: '#f1f5f9',
      secondBkg: '#f8fafc',
      tertiaryBkg: '#cbd5e1',
      // Additional text color overrides
      nodeBkg: '#f1f5f9',
      clusterBkg: '#f8fafc',
      edgeLabelText: '#000000',
      nodeTextColor: '#000000'
    },
    flowchart: { 
      useMaxWidth: true,
      htmlLabels: true,
      curve: 'basis',
      nodeSpacing: 50,
      rankSpacing: 60,
      padding: 20
    }
  });

  // Add event listeners
  const decomposeBtn = document.getElementById('decompose');
  const downloadBtn = document.getElementById('downloadJpg');
  const downloadJsonBtn = document.getElementById('downloadJson');
  
  if (decomposeBtn) {
    decomposeBtn.addEventListener('click', decompose);
  }
  if (downloadBtn) {
    downloadBtn.addEventListener('click', downloadJpg);
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
    // Persist latest workflow/response for Agentic page to reuse without asking input again
    try {
      window.localStorage.setItem('lastWorkflowResponse', JSON.stringify(data));
    } catch (e) {
      try { window.sessionStorage.setItem('lastWorkflowResponse', JSON.stringify(data)); } catch (_) {}
    }
    const mer = data.mermaid;
    
    const mermaidEl = document.getElementById('mermaid');
    if (mermaidEl) {
      mermaidEl.textContent = mer;
    }
    
    renderMermaid(mer);
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

async function renderMermaid(code) {
  const el = document.createElement('div');
  el.className = 'mermaid';
  el.textContent = code;
  const mount = document.getElementById('render');
  
  if (!mount) {
    console.error('Render element not found');
    return;
  }
  
  mount.innerHTML = '';
  mount.appendChild(el);
  try {
    await mermaid.run({ nodes: [el] });
  } catch (e) {
    el.innerHTML = '<pre style="color:red">' + String(e) + '</pre>';
  }
}

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

async function downloadJpg() {
  // Prefer re-rendering Mermaid without HTML labels to avoid foreignObject tainting
  const mermaidPre = document.getElementById('mermaid');
  let svgString = '';
  const code = mermaidPre ? mermaidPre.textContent : '';
  if (!code || !code.trim()) {
    alert('Nothing to download yet');
    return;
  }

  try {
    // Render a clean SVG for export
    const exportCode = cleanMermaidForExport(code);
    const result = await mermaid.render('export-graph', exportCode, undefined, {
      securityLevel: 'strict',
      theme: 'base',
      themeVariables: {
        lineColor: '#94a3b8',
        arrowheadColor: '#94a3b8',
        primaryTextColor: '#1f2937',
        edgeLabelBackground: '#ffffff'
      },
      flowchart: { htmlLabels: false, useMaxWidth: true },
    });
    svgString = result.svg;
  } catch (e) {
    // Fallback to current on-screen SVG
    const svg = document.querySelector('#render svg');
    if (!svg) { alert('Nothing to download yet'); return; }
    svgString = new XMLSerializer().serializeToString(svg);
  }

  if (!/^<\?xml/.test(svgString)) {
    svgString = '<?xml version="1.0" standalone="no"?>\n' + svgString;
  }
  const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.onload = function () {
    const canvas = document.createElement('canvas');
    const ratio = window.devicePixelRatio || 2;
    const w = Math.ceil(img.width || 1200);
    const h = Math.ceil(img.height || 800);
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    if (canvas.toBlob) {
      canvas.toBlob((blob) => {
        if (!blob) { fallbackDownloadSvg(svgString); return; }
        const a = document.createElement('a');
        a.download = 'workflow.jpg';
        a.href = URL.createObjectURL(blob);
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      }, 'image/jpeg', 0.95);
    } else {
      const a = document.createElement('a');
      a.download = 'workflow.jpg';
      a.href = canvas.toDataURL('image/jpeg', 0.95);
      a.click();
    }
  };
  img.onerror = () => { URL.revokeObjectURL(url); fallbackDownloadSvg(svgString); };
  img.src = url;
}

function fallbackDownloadSvg(svgString) {
  try {
    const blob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' });
    const a = document.createElement('a');
    a.download = 'workflow.svg';
    a.href = URL.createObjectURL(blob);
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } catch (e) {
    alert('Failed to export image');
  }
}

function cleanMermaidForExport(code) {
  try {
    // Remove HTML tags like <b>, <span>, and convert <br> to newline to avoid invalid XML inside labels
    let c = code;
    c = c.replace(/<br\s*\/?>/gi, '\\n');
    c = c.replace(/<\/?(b|strong|i|em|u|span|small|sup|sub)[^>]*>/gi, '');
    // Strip any remaining tags as final safety
    c = c.replace(/<[^>]+>/g, '');
    return c;
  } catch (_) {
    return code;
  }
}

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
