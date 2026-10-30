// Elements
const codeInput = document.getElementById('codeInput');
const language = document.getElementById('language');
const lineNumbers = document.getElementById('lineNumbers');
const charCount = document.getElementById('charCount');
const toast = document.getElementById('toast');

// Topbar & Modal elements
const aiSettingsBtn = document.getElementById('aiSettingsBtn');
const topbarAiDot = document.getElementById('topbarAiDot');
const topbarAiText = document.getElementById('topbarAiText');
const activeModeHint = document.getElementById('activeModeHint');
const privacyDesc = document.getElementById('privacyDesc');

const aiModalBackdrop = document.getElementById('aiModalBackdrop');
const closeAiModal = document.getElementById('closeAiModal');
const providerSelect = document.getElementById('providerSelect');
const providerHint = document.getElementById('providerHint');
const apiKeyField = document.getElementById('apiKeyField');
const apiKeyInput = document.getElementById('apiKeyInput');
const toggleApiKeyVis = document.getElementById('toggleApiKeyVis');
const getKeyLink = document.getElementById('getKeyLink');
const modelField = document.getElementById('modelField');
const modelInput = document.getElementById('modelInput');
const baseUrlField = document.getElementById('baseUrlField');
const baseUrlInput = document.getElementById('baseUrlInput');
const testFeedback = document.getElementById('testFeedback');
const testConnectionBtn = document.getElementById('testConnectionBtn');
const saveAiConfigBtn = document.getElementById('saveAiConfigBtn');
const bannerSettingsBtn = document.getElementById('bannerSettingsBtn');

// Results elements
const fixedBadge = document.getElementById('fixBadge');
const unfixedBanner = document.getElementById('unfixedBanner');
const unfixedHeading = document.getElementById('unfixedHeading');
const unfixedMessage = document.getElementById('unfixedMessage');
const fixedStatusDot = document.getElementById('fixedStatusDot');
const fixedPlaceholder = document.getElementById('fixedPlaceholder');

let lastResult = null;
let toastTimer;

// Provider Defaults & Documentation Links
const PROVIDER_INFO = {
  none: {
    name: 'Offline Mode',
    hint: 'Rule-based analysis for Python, JS, Java, C++, and C. Works 100% offline without any API key.',
    hasKey: false,
    hasModel: false,
    hasUrl: false
  },
  gemini: {
    name: 'Google Gemini',
    hint: 'Fast & accurate. Google AI Studio offers a free tier (no credit card required).',
    link: 'https://aistudio.google.com/apikey',
    linkText: 'Get Free Gemini Key ↗',
    defaultModel: 'gemini-1.5-flash',
    hasKey: true,
    hasModel: true,
    hasUrl: false
  },
  groq: {
    name: 'Groq Cloud (120B)',
    hint: 'Ultra-fast inference & complex bug fixing with OpenAI 120B model on Groq.',
    link: 'https://console.groq.com/keys',
    linkText: 'Get Free Groq Key ↗',
    defaultModel: 'openai/gpt-oss-120b',
    hasKey: true,
    hasModel: true,
    hasUrl: false
  },
  openai: {
    name: 'OpenAI',
    hint: 'Industry standard models (GPT-4o, GPT-4o-mini). Requires OpenAI account credits.',
    link: 'https://platform.openai.com/api-keys',
    linkText: 'OpenAI Dashboard ↗',
    defaultModel: 'gpt-4o-mini',
    hasKey: true,
    hasModel: true,
    hasUrl: false
  },
  ollama: {
    name: 'Ollama (Local)',
    hint: 'Runs locally on your computer. Free, private, and does not require an API key or internet.',
    link: 'https://ollama.com',
    linkText: 'Download Ollama ↗',
    defaultModel: 'llama3',
    defaultUrl: 'http://localhost:11434/v1/chat/completions',
    hasKey: false,
    hasModel: true,
    hasUrl: true
  },
  custom: {
    name: 'Custom API',
    hint: 'Any OpenAI-compatible chat completions endpoint (LM Studio, LocalAI, vLLM, OpenRouter).',
    hasKey: true,
    hasModel: true,
    hasUrl: true
  }
};

const exampleCode = {
  Python: 'def add_numbers(a, b)\n    result = a + b\n    return result\n\nprint(add_numbers(5, 3))',
  JavaScript: 'function addNumbers(a, b) {\n    return a + b\n}\n\nconsol.log(addNumbers(5, 3))',
  Java: 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello world")\n    }\n}',
  'C++': '#include <iostream>\nusing namespace std;\n\nint main() {\n    cout << "Hello world" << endl\n    return 0\n}',
  C: '#include <stdio.h>\n\nint main(void) {\n    printf("Hello world\\n")\n    return 0\n}'
};

// Config Persistence
function getStoredConfig() {
  try {
    const raw = localStorage.getItem('codefix_ai_config');
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.error('Could not parse stored config:', e);
  }
  return { provider: 'none', api_key: '', model: '', base_url: '' };
}

function saveStoredConfig(cfg) {
  try {
    localStorage.setItem('codefix_ai_config', JSON.stringify(cfg));
  } catch (e) {
    console.error('Could not save config:', e);
  }
}

function updateUiForConfig() {
  const cfg = getStoredConfig();
  const provider = cfg.provider || 'none';
  const info = PROVIDER_INFO[provider] || PROVIDER_INFO.none;

  if (provider === 'none') {
    topbarAiDot.className = 'status-dot-sm offline';
    topbarAiText.textContent = 'Offline Mode';
    activeModeHint.innerHTML = '● Heuristic Rules Active';
    privacyDesc.textContent = 'Running in smart offline mode. Click "AI Settings" to enable deep AI debugging.';
  } else {
    topbarAiDot.className = 'status-dot-sm active';
    topbarAiText.textContent = `AI: ${info.name}`;
    activeModeHint.innerHTML = `<span style="color:var(--green)">● AI Ready (${cfg.model || info.defaultModel || 'connected'})</span>`;
    privacyDesc.textContent = `Connected to ${info.name}. Code is securely analyzed by your chosen model.`;
  }
}

// Modal Form Logic
function refreshModalFields(changedByUser = false) {
  const provider = providerSelect.value;
  const info = PROVIDER_INFO[provider] || PROVIDER_INFO.none;

  providerHint.textContent = info.hint;

  if (info.hasKey) {
    apiKeyField.style.display = 'flex';
    if (info.link) {
      getKeyLink.style.display = 'inline';
      getKeyLink.href = info.link;
      getKeyLink.textContent = info.linkText || 'Get Key ↗';
    } else {
      getKeyLink.style.display = 'none';
    }
  } else {
    apiKeyField.style.display = 'none';
  }

  if (info.hasModel) {
    modelField.style.display = 'flex';
    // Update model if user changed provider, or if empty, or if model belongs to another provider
    if (changedByUser || !modelInput.value.trim() || (provider === 'gemini' && modelInput.value.startsWith('gpt-')) || (provider === 'openai' && modelInput.value.startsWith('gemini'))) {
      modelInput.value = info.defaultModel || '';
    }
  } else {
    modelField.style.display = 'none';
  }

  if (info.hasUrl) {
    baseUrlField.style.display = 'flex';
    if (changedByUser || !baseUrlInput.value.trim()) {
      baseUrlInput.value = info.defaultUrl || '';
    }
  } else {
    baseUrlField.style.display = 'none';
    if (changedByUser) {
      baseUrlInput.value = '';
    }
  }

  testConnectionBtn.style.display = provider === 'none' ? 'none' : 'inline-flex';
  testFeedback.style.display = 'none';
}

function openSettingsModal() {
  const cfg = getStoredConfig();
  providerSelect.value = cfg.provider || 'none';
  apiKeyInput.value = cfg.api_key || '';
  let m = cfg.model || '';
  if (providerSelect.value === 'gemini') {
    if (m.toLowerCase().startsWith('models/')) m = m.replace(/^models\//i, '');
    if (!m.toLowerCase().startsWith('gemini-')) m = 'gemini-1.5-flash';
  }
  modelInput.value = m;
  baseUrlInput.value = cfg.base_url || '';
  refreshModalFields(false);
  aiModalBackdrop.style.display = 'grid';
}

function closeSettingsModal() {
  aiModalBackdrop.style.display = 'none';
}

// Editor Utilities
function updateEditorMeta() {
  const count = codeInput.value.length;
  charCount.textContent = `${count.toLocaleString()} character${count === 1 ? '' : 's'}`;
  const lineCount = Math.max(1, codeInput.value.split('\n').length);
  lineNumbers.textContent = Array.from({ length: lineCount }, (_, i) => i + 1).join('\n');
}

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove('show'), 3000);
}

function selectTab(name) {
  document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === name));
  document.querySelectorAll('.result-view').forEach(view => view.classList.toggle('active', view.id === `view-${name}`));
}

function escapeText(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
}

// Result Display Logic
function showResult(result) {
  lastResult = result;
  fixedPlaceholder.style.display = 'none';

  const hasFix = Boolean(result.has_fix);
  const changes = Array.isArray(result.changes) ? result.changes : [];
  const fixedCode = result.fixed_code ?? '';

  document.getElementById('fixedCode').textContent = fixedCode;

  // Handle Fixed Code Tab Badges & Warnings
  if (hasFix && changes.length > 0) {
    unfixedBanner.style.display = 'none';
    fixedBadge.style.display = 'inline-block';
    fixedBadge.textContent = `✓ ${changes.length} Fix${changes.length === 1 ? '' : 'es'} Applied`;
    fixedBadge.className = 'fix-badge';
    fixedStatusDot.className = 'status-dot green';
  } else if (!hasFix && (result.error_type === 'No syntax error detected' || result.error_type === 'No basic syntax errors found' || result.error_type === 'Static check passed')) {
    unfixedBanner.style.display = 'none';
    fixedBadge.style.display = 'inline-block';
    fixedBadge.textContent = 'No syntax errors';
    fixedBadge.className = 'fix-badge';
    fixedStatusDot.className = 'status-dot green';
  } else {
    // There was an error or issue, but no automated fix was generated
    unfixedBanner.style.display = 'flex';
    if (result.ai_notice) {
      unfixedHeading.textContent = 'AI Service Notice';
      unfixedMessage.textContent = `${result.ai_notice} Showing offline fallback: ${result.explanation || ''}`;
    } else {
      unfixedHeading.textContent = result.error_type ? `${result.error_type} Detected` : 'Could not auto-fix locally';
      unfixedMessage.textContent = result.explanation || 'An error was detected, but offline heuristic rules could not automatically fix it. Connect an AI API to get deep fixes and explanations.';
    }
    fixedBadge.style.display = 'none';
    fixedStatusDot.className = 'status-dot red';
  }

  // Explanation Tab
  document.getElementById('explanationText').textContent = result.explanation || 'No explanation provided.';
  document.getElementById('explanationText').classList.remove('muted');

  document.getElementById('changesList').innerHTML = changes.length
    ? changes.map(item => `
        <div class="change-item">
          <strong>Line ${escapeText(item.line ?? '—')}: ${escapeText(item.problem ?? 'Suggested change')}</strong>
          <p>${escapeText(item.fix ?? '')}</p>
        </div>
      `).join('')
    : `<div class="change-item">
        <strong>${hasFix ? 'Fixes applied' : 'No line changes'}</strong>
        <p>${hasFix ? 'Code was corrected. See the fixed code tab.' : 'No automated code modification was made. Review the Error Analysis tab or connect an AI API.'}</p>
      </div>`;

  // Error Analysis Tab
  document.getElementById('errorType').textContent = result.error_type || 'Analysis complete';
  document.getElementById('errorMessage').textContent = result.error_message || 'See explanation for details.';
  document.getElementById('errorLine').textContent = result.error_line ? `Line: ${result.error_line}` : 'Line: not identified';
  document.getElementById('resultNotes').textContent = [result.notes, result.ai_notice].filter(Boolean).join(' ');

  // Bottom bar
  const isHealthy = hasFix || result.error_type === 'No syntax error detected' || result.error_type === 'No basic syntax errors found';
  document.getElementById('resultStatus').innerHTML = `
    <span class="status-dot ${isHealthy ? 'green' : 'purple'}"></span> ${escapeText(result.status || 'Analysis complete')}
  `;
  document.getElementById('resultLanguage').textContent = result.language || language.value;

  selectTab('fixed');
}

// API Call
async function debugCode(mode) {
  const code = codeInput.value;
  if (!code.trim()) {
    showToast('Paste some code first.');
    codeInput.focus();
    return;
  }

  const button = mode === 'fix' ? document.getElementById('fixButton') : document.getElementById('explainButton');
  const oldText = button.innerHTML;
  button.disabled = true;
  button.innerHTML = '<span>◌</span> Analyzing...';
  document.getElementById('resultStatus').innerHTML = '<span class="status-dot purple"></span> Analyzing code...';

  const cfg = getStoredConfig();
  // Sanitize stored config model before sending
  const sendConfig = cfg.provider !== 'none' ? {
    ...cfg,
    model: sanitizeModelName(cfg.provider, cfg.model)
  } : null;

  try {
    const response = await fetch('/api/debug', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        code,
        language: language.value,
        mode,
        ai_config: sendConfig
      })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Unable to analyze code.');

    showResult(data);

    if (data.ai_notice) {
      if (cfg.provider === 'none') {
        showToast('Offline analysis shown. Click "AI Settings" for AI mode.');
      } else {
        showToast(data.ai_notice);
      }
    }
  } catch (error) {
    showToast(error.message || 'Something went wrong.');
    document.getElementById('resultStatus').textContent = 'Analysis failed';
  } finally {
    button.disabled = false;
    button.innerHTML = oldText;
  }
}

// Event Listeners
codeInput.addEventListener('input', updateEditorMeta);
codeInput.addEventListener('scroll', () => { lineNumbers.scrollTop = codeInput.scrollTop; });
codeInput.addEventListener('keydown', event => {
  if (event.key === 'Tab') {
    event.preventDefault();
    const start = codeInput.selectionStart, end = codeInput.selectionEnd;
    codeInput.setRangeText('    ', start, end, 'end');
    updateEditorMeta();
  }
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    debugCode('fix');
  }
});

document.getElementById('fixButton').addEventListener('click', () => debugCode('fix'));
document.getElementById('explainButton').addEventListener('click', () => debugCode('explain'));
document.getElementById('clearCode').addEventListener('click', () => {
  codeInput.value = '';
  updateEditorMeta();
  codeInput.focus();
  showToast('Editor cleared.');
});

document.getElementById('tryExample').addEventListener('click', () => {
  codeInput.value = exampleCode[language.value] || exampleCode.Python;
  updateEditorMeta();
  codeInput.focus();
  document.getElementById('workspace').scrollIntoView({ behavior: 'smooth', block: 'start' });
  showToast('Example loaded. Click "Fix my code" to analyze it.');
});

language.addEventListener('change', () => {
  document.getElementById('resultLanguage').textContent = language.value;
  showToast(`${language.value} selected.`);
});

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => selectTab(tab.dataset.tab));
});

document.getElementById('copyCode').addEventListener('click', async () => {
  const text = lastResult?.fixed_code;
  if (!text) {
    showToast('Run a debug check first.');
    return;
  }
  try {
    await navigator.clipboard.writeText(text);
    showToast('Suggested code copied to clipboard!');
  } catch {
    showToast('Clipboard access was blocked. Select and copy the code manually.');
  }
});

// Modal Actions
aiSettingsBtn.addEventListener('click', openSettingsModal);
bannerSettingsBtn.addEventListener('click', openSettingsModal);
closeAiModal.addEventListener('click', closeSettingsModal);
aiModalBackdrop.addEventListener('click', e => {
  if (e.target === aiModalBackdrop) closeSettingsModal();
});

providerSelect.addEventListener('change', () => refreshModalFields(true));

toggleApiKeyVis.addEventListener('click', () => {
  if (apiKeyInput.type === 'password') {
    apiKeyInput.type = 'text';
    toggleApiKeyVis.textContent = '🔒';
  } else {
    apiKeyInput.type = 'password';
    toggleApiKeyVis.textContent = '👁';
  }
});

function sanitizeModelName(provider, model) {
  let m = (model || '').trim();
  if (provider === 'gemini') {
    if (m.toLowerCase().startsWith('models/')) m = m.replace(/^models\//i, '');
    if (!m.toLowerCase().startsWith('gemini-')) {
      m = 'gemini-1.5-flash';
    }
  } else if (provider === 'groq') {
    if (!m || m.startsWith('gemini') || m.toLowerCase().includes('llama')) {
      m = 'openai/gpt-oss-120b';
    }
  } else if (provider === 'openai') {
    if (!m || m.startsWith('gemini') || m.startsWith('llama')) {
      m = 'gpt-4o-mini';
    }
  }
  return m;
}

// Test Connection
testConnectionBtn.addEventListener('click', async () => {
  testFeedback.style.display = 'block';
  testFeedback.className = 'test-feedback';
  testFeedback.textContent = 'Testing connection to AI service...';
  testConnectionBtn.disabled = true;

  const provider = providerSelect.value;
  const cleanModel = sanitizeModelName(provider, modelInput.value);
  modelInput.value = cleanModel;

  try {
    const res = await fetch('/api/test_ai', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider,
        api_key: apiKeyInput.value.trim(),
        model: cleanModel,
        base_url: (provider === 'custom' || provider === 'ollama') ? baseUrlInput.value.trim() : ''
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'Connection failed.');
    testFeedback.className = 'test-feedback success';
    testFeedback.textContent = data.message || 'Connected successfully!';
  } catch (err) {
    testFeedback.className = 'test-feedback error';
    testFeedback.textContent = err.message || 'Could not connect. Check your API key and model name.';
  } finally {
    testConnectionBtn.disabled = false;
  }
});

// Save Settings
saveAiConfigBtn.addEventListener('click', () => {
  const provider = providerSelect.value;
  const cleanModel = sanitizeModelName(provider, modelInput.value);
  modelInput.value = cleanModel;

  const newConfig = {
    provider,
    api_key: apiKeyInput.value.trim(),
    model: cleanModel,
    base_url: (provider === 'custom' || provider === 'ollama') ? baseUrlInput.value.trim() : ''
  };
  saveStoredConfig(newConfig);
  updateUiForConfig();
  closeSettingsModal();
  showToast(newConfig.provider === 'none' ? 'Switched to smart offline mode.' : `AI settings saved (${newConfig.provider}).`);
});

// Initial boot check
(async function init() {
  updateEditorMeta();
  // Check if server already has environment variables set
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    const stored = getStoredConfig();

    if (data.has_server_key) {
      // Always sync model from server config if it's a managed provider (key in .env)
      const needsUpdate = (
        stored.provider === 'none' ||
        (stored.provider === data.default_provider && (!stored.model || stored.model !== data.default_model))
      );
      if (needsUpdate) {
        stored.provider = data.default_provider;
        stored.model = data.default_model;
        saveStoredConfig(stored);
      }
    }
  } catch (e) {
    console.warn('Config fetch error:', e);
  }
  updateUiForConfig();
})();
