/* global mermaid */

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
  mermaid.initialize({ startOnLoad: false, theme: 'default' });

  // Add event listeners
  const decomposeBtn = document.getElementById('decompose');
  const downloadBtn = document.getElementById('downloadJpg');
  
  if (decomposeBtn) {
    decomposeBtn.addEventListener('click', decompose);
  }
  if (downloadBtn) {
    downloadBtn.addEventListener('click', downloadJpg);
  }
});

async function decompose() {
  const inputEl = document.getElementById('input');
  const titleEl = document.getElementById('title');
  const granularityEl = document.getElementById('granularity');
  const decomposeBtn = document.getElementById('decompose');
  const loaderEl = document.getElementById('loader');
  const renderEl = document.getElementById('render');
  
  if (!inputEl || !titleEl || !granularityEl) {
    console.error('Required DOM elements not found:', {
      input: !!inputEl,
      title: !!titleEl,
      granularity: !!granularityEl
    });
    alert('Page not fully loaded. Please try again.');
    return;
  }
  
  const text = inputEl.value.trim();
  const title = titleEl.value.trim();
  const granularity = granularityEl.value;
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
      body: JSON.stringify({ text, title: title || null, granularity }),
    });
    if (!res.ok) { 
      throw new Error('Failed to decompose'); 
    }
    const data = await res.json();
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
  
  engineEl.textContent = data.engine || '';
  errEl.textContent = data.llm_error || '';
  rawEl.textContent = data.llm_raw || '';
}

async function downloadJpg() {
  const svg = document.querySelector('#render svg');
  if (!svg) { alert('Nothing to download yet'); return; }
  const serializer = new XMLSerializer();
  let source = serializer.serializeToString(svg);
  // Add XML declaration if missing
  if (!source.match(/^<\?xml/)) {
    source = '<?xml version="1.0" standalone="no"?>\r\n' + source;
  }
  const svgBlob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.onload = function () {
    const canvas = document.createElement('canvas');
    const ratio = window.devicePixelRatio || 2;
    const w = Math.ceil(img.width);
    const h = Math.ceil(img.height);
    canvas.width = w * ratio;
    canvas.height = h * ratio;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    canvas.toBlob((blob) => {
      const a = document.createElement('a');
      a.download = 'workflow.jpg';
      a.href = URL.createObjectURL(blob);
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    }, 'image/jpeg', 0.95);
  };
  img.onerror = () => { URL.revokeObjectURL(url); alert('Failed to render image'); };
  img.src = url;
}
