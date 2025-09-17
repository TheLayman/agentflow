/* Shared utilities for both pages */

// Initialize Mermaid with a common theme once
(() => {
  if (typeof mermaid !== 'undefined' && !window.__mermaidInitialized) {
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
    window.__mermaidInitialized = true;
    console.log('Mermaid initialized successfully');
  } else if (typeof mermaid === 'undefined') {
    console.warn('Mermaid library not available during initialization');
  }
})();

// Wait for mermaid to be available
function waitForMermaid(maxWait = 5000) {
  return new Promise((resolve, reject) => {
    if (typeof mermaid !== 'undefined') {
      resolve(mermaid);
      return;
    }
    
    const startTime = Date.now();
    const checkInterval = setInterval(() => {
      if (typeof mermaid !== 'undefined') {
        clearInterval(checkInterval);
        resolve(mermaid);
      } else if (Date.now() - startTime > maxWait) {
        clearInterval(checkInterval);
        reject(new Error('Mermaid library failed to load within timeout'));
      }
    }, 100);
  });
}

// Render mermaid code into a container by id
async function renderMermaidIn(containerId, code) {
  const mount = document.getElementById(containerId);
  if (!mount) {
    console.warn(`Container with id '${containerId}' not found`);
    return;
  }
  
  // Validate code
  if (!code || typeof code !== 'string') {
    console.warn('Invalid mermaid code provided:', code);
    mount.innerHTML = '<pre style="color:#f59e0b; background:#1f1f1f; padding:10px; border-radius:4px;">Warning: No valid mermaid code provided</pre>';
    return;
  }
  
  mount.innerHTML = '';
  const el = document.createElement('div');
  el.className = 'mermaid';
  el.textContent = code;
  mount.appendChild(el);
  
  try { 
    // Wait for mermaid to be available
    await waitForMermaid();
    await mermaid.run({ nodes: [el] }); 
  } catch (e) { 
    console.error('Mermaid rendering error:', e);
    const errorMsg = e?.message || e?.toString() || 'Unknown mermaid rendering error';
    el.innerHTML = `<pre style="color:#ef4444; background:#1f1f1f; padding:10px; border-radius:4px;">Mermaid Error: ${escapeHtml(errorMsg)}</pre>`; 
  }
}

function escapeHtml(s) {
  return String(s || '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function cleanMermaidForExport(code) {
  try {
    let c = code;
    c = c.replace(/<br\s*\/?>/gi, '\\n');
    c = c.replace(/<\/?(b|strong|i|em|u|span|small|sup|sub)[^>]*>/gi, '');
    c = c.replace(/<[^>]+>/g, '');
    return c;
  } catch (_) {
    return code;
  }
}

function fallbackDownloadSvg(svgString) {
  try {
    // Clean up the SVG string and ensure it's properly formatted
    let cleanSvg = svgString;
    if (!/^<\?xml/.test(cleanSvg)) {
      cleanSvg = '<?xml version="1.0" standalone="no"?>\n' + cleanSvg;
    }
    
    // Ensure proper encoding
    cleanSvg = cleanSvg.replace(/\s+/g, ' ').trim();
    
    const blob = new Blob([cleanSvg], { type: 'image/svg+xml;charset=utf-8' });
    const a = document.createElement('a');
    const timestamp = new Date().toISOString().slice(0,10);
    a.download = `workflow-${timestamp}.svg`;
    a.href = URL.createObjectURL(blob);
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    console.log('SVG downloaded successfully as fallback');
  } catch (e) {
    console.error('SVG export failed:', e);
    alert('Failed to export image. Please try again or check browser console for details.');
  }
}

function saveLastWorkflowResponse(data) {
  try {
    window.localStorage.setItem('lastWorkflowResponse', JSON.stringify(data));
  } catch (e) {
    try { window.sessionStorage.setItem('lastWorkflowResponse', JSON.stringify(data)); } catch (_) {}
  }
}

function getLastWorkflowResponse() {
  let raw = null;
  try { raw = window.localStorage.getItem('lastWorkflowResponse'); } catch (_) {}
  if (!raw) { try { raw = window.sessionStorage.getItem('lastWorkflowResponse'); } catch (_) {} }
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return null; }
}

// Expose on window for clarity in non-module context
window.renderMermaidIn = renderMermaidIn;
window.escapeHtml = escapeHtml;
window.cleanMermaidForExport = cleanMermaidForExport;
window.fallbackDownloadSvg = fallbackDownloadSvg;
window.saveLastWorkflowResponse = saveLastWorkflowResponse;
window.getLastWorkflowResponse = getLastWorkflowResponse;
window.waitForMermaid = waitForMermaid;

