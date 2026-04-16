// ============================================================================
// Settings Tab -- Cascading provider to model selector
// ============================================================================

function initSettingsTab() {
  const btnSaveSettings = document.getElementById('btn-save-settings');
  const providerSelect = document.getElementById('settings-provider');
  const refreshBtn = document.getElementById('btn-refresh-models');

  btnSaveSettings.addEventListener('click', async () => {
    await saveSettingsRound2();
  });

  // Provider change -> show matching API key section + fetch models
  if (providerSelect) {
    providerSelect.addEventListener('change', () => {
      showProviderSection(providerSelect.value);
      fetchModels(providerSelect.value);
    });
  }

  // Refresh model list button
  if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
      if (providerSelect) fetchModels(providerSelect.value);
    });
  }

  // Load settings when tab is activated
  document.querySelectorAll('.nav-btn').forEach(btn => {
    if (btn.dataset.tab === 'settings') {
      btn.addEventListener('click', () => {
        loadSettings();
        loadLearningStats();
      });
    }
  });

  // Load settings on init
  loadSettings();
  loadLearningStats();

  // Reset learning button
  const btnResetLearning = document.getElementById('btn-reset-learning');
  if (btnResetLearning) {
    btnResetLearning.addEventListener('click', async () => {
      if (!confirm('Reset all AI learning data? This cannot be undone.')) return;
      try {
        await apiFetch('/api/learning/reset', { method: 'DELETE' });
        showToast('Learning data reset', 'info');
        loadLearningStats();
      } catch (error) {
        showToast('Failed to reset learning data', 'error');
      }
    });
  }
}

/** Load AI learning stats */
async function loadLearningStats() {
  try {
    const result = await apiFetch('/api/learning/stats');
    const totalEl = document.getElementById('learning-total');
    const uniqueEl = document.getElementById('learning-unique');
    const correctionsEl = document.getElementById('learning-top-corrections');
    if (totalEl) totalEl.textContent = result.total_corrections || 0;
    if (uniqueEl) uniqueEl.textContent = result.unique_patterns || 0;

    if (correctionsEl) {
      const top = result.top_corrections || [];
      if (top.length === 0) {
        correctionsEl.innerHTML = '<p class="settings-hint" style="margin-top:8px;">No corrections yet. Approve or edit tracks to start teaching the AI.</p>';
        return;
      }
      let html = '<table class="learning-table"><thead><tr><th>Pattern</th><th>Correction</th><th>Count</th></tr></thead><tbody>';
      for (const c of top.slice(0, 10)) {
        const parts = [];
        if (c.pattern && c.pattern.artist_contains) parts.push(`artist: ${c.pattern.artist_contains}`);
        if (c.pattern && c.pattern.bpm_range) parts.push(`BPM: ${c.pattern.bpm_range[0]}-${c.pattern.bpm_range[1]}`);
        if (c.pattern && c.pattern.energy_range) parts.push(`energy: ${c.pattern.energy_range[0]}-${c.pattern.energy_range[1]}`);
        const patternStr = parts.length ? parts.join(', ') : 'general';
        html += `<tr><td>${escapeHtml(patternStr)}</td><td>${escapeHtml(c.corrected_genre)} / ${escapeHtml(c.corrected_subgenre || '')}</td><td>${c.count || 1}</td></tr>`;
      }
      html += '</tbody></table>';
      correctionsEl.innerHTML = html;
    }
  } catch (error) {
    // Silently fail — learning is optional
  }
}

/** Show only the API key section matching the selected provider, hide others */
function showProviderSection(provider) {
  const sections = ['claude', 'openai', 'openrouter', 'gemini', 'qwen', 'deepseek', 'groq'];
  for (const sec of sections) {
    const el = document.getElementById('api-key-section-' + sec);
    if (el) el.style.display = sec === provider ? '' : 'none';
  }
}

/** Set options on the model select dropdown safely */
function setModelOptions(modelSelect, options) {
  modelSelect.textContent = '';
  for (const opt of options) {
    const el = document.createElement('option');
    el.value = opt.value;
    el.textContent = opt.text;
    modelSelect.appendChild(el);
  }
}

/**
 * Fetch models from the backend for the given provider.
 * Includes a saved API key from the input (if any) so the backend can use it.
 */
async function fetchModels(provider) {
  const modelSelect = document.getElementById('settings-model');
  if (!modelSelect) return;
  if (!provider) {
    setModelOptions(modelSelect, [{ value: '', text: 'Select a provider first' }]);
    return;
  }

  setModelOptions(modelSelect, [{ value: '', text: 'Loading models...' }]);

  // Grab a key from the input field if the user typed one, otherwise let
  // the backend use the saved key from .env
  let apiKey = '';
  if (provider === 'claude') {
    apiKey = document.getElementById('settings-anthropic-key')?.value.trim() || '';
  } else if (provider === 'openrouter') {
    apiKey = document.getElementById('settings-openrouter-key')?.value.trim() || '';
  } else if (provider === 'gemini') {
    apiKey = document.getElementById('settings-gemini-key')?.value.trim() || '';
  } else if (provider === 'openai') {
    apiKey = document.getElementById('settings-openai-key')?.value.trim() || '';
  } else if (provider === 'qwen') {
    apiKey = document.getElementById('settings-qwen-key')?.value.trim() || '';
  } else if (provider === 'deepseek') {
    apiKey = document.getElementById('settings-deepseek-key')?.value.trim() || '';
  } else if (provider === 'groq') {
    apiKey = document.getElementById('settings-groq-key')?.value.trim() || '';
  }

  try {
    const body = { provider };
    if (apiKey) body.api_key = apiKey;

    const result = await apiFetch('/api/list_models', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    if (result.error) {
      setModelOptions(modelSelect, [{ value: '', text: result.error }]);
      return;
    }

    const models = result.models || [];
    if (models.length === 0) {
      setModelOptions(modelSelect, [{ value: '', text: 'No models available' }]);
      return;
    }

    const options = [];
    for (const m of models) {
      const label = m.free ? m.name + ' (free)' : m.name;
      options.push({ value: m.id, text: label });
    }
    setModelOptions(modelSelect, options);
  } catch (error) {
    setModelOptions(modelSelect, [{ value: '', text: 'Error loading models' }]);
  }
}

async function loadSettings() {
  try {
    const response = await apiFetch('/api/settings');

    // Populate form fields with placeholder text for masked values
    const geminiInput = document.getElementById('settings-gemini-key');
    const spotifyIdInput = document.getElementById('settings-spotify-id');
    const spotifySecretInput = document.getElementById('settings-spotify-secret');
    const anthropicInput = document.getElementById('settings-anthropic-key');
    const openrouterInput = document.getElementById('settings-openrouter-key');
    const openaiInput = document.getElementById('settings-openai-key');
    const qwenInput = document.getElementById('settings-qwen-key');
    const deepseekInput = document.getElementById('settings-deepseek-key');
    const groqInput = document.getElementById('settings-groq-key');
    const lastfmInput = document.getElementById('settings-lastfm-key');

    // Show placeholder text for existing keys -- format: "sk-a...xyz1 -- saved"
    const keyLabel = (masked) => masked ? masked + '  --  saved' : 'saved';
    if (response.has_gemini_key) {
      geminiInput.placeholder = keyLabel(response.gemini_api_key);
    } else {
      geminiInput.placeholder = 'Paste your Gemini API key';
    }
    if (response.has_openrouter_key && openrouterInput) {
      openrouterInput.placeholder = keyLabel(response.openrouter_api_key);
    } else if (openrouterInput) {
      openrouterInput.placeholder = 'Paste your OpenRouter API key';
    }
    if (response.has_anthropic_key && anthropicInput) {
      anthropicInput.placeholder = keyLabel(response.anthropic_api_key);
    } else if (anthropicInput) {
      anthropicInput.placeholder = 'Paste your Anthropic API key';
    }
    if (response.has_openai_key && openaiInput) {
      openaiInput.placeholder = keyLabel(response.openai_api_key);
    } else if (openaiInput) {
      openaiInput.placeholder = 'Paste your OpenAI API key';
    }
    if (response.has_qwen_key && qwenInput) {
      qwenInput.placeholder = keyLabel(response.qwen_api_key);
    } else if (qwenInput) {
      qwenInput.placeholder = 'Paste your DashScope API key';
    }
    if (response.has_deepseek_key && deepseekInput) {
      deepseekInput.placeholder = keyLabel(response.deepseek_api_key);
    } else if (deepseekInput) {
      deepseekInput.placeholder = 'Paste your DeepSeek API key';
    }
    if (response.has_groq_key && groqInput) {
      groqInput.placeholder = keyLabel(response.groq_api_key);
    } else if (groqInput) {
      groqInput.placeholder = 'Paste your Groq API key';
    }
    if (response.has_lastfm_key && lastfmInput) {
      lastfmInput.placeholder = keyLabel(response.lastfm_api_key);
    } else if (lastfmInput) {
      lastfmInput.placeholder = 'Paste your Last.fm API key';
    }
    if (response.has_spotify) {
      spotifyIdInput.placeholder = keyLabel(response.spotify_client_id);
      spotifySecretInput.placeholder = keyLabel(response.spotify_client_secret);
    } else {
      spotifyIdInput.placeholder = 'Paste your Spotify Client ID';
      spotifySecretInput.placeholder = 'Paste your Spotify Client Secret';
    }

    // Clear the actual input values
    geminiInput.value = '';
    spotifyIdInput.value = '';
    spotifySecretInput.value = '';
    if (anthropicInput) anthropicInput.value = '';
    if (openrouterInput) openrouterInput.value = '';
    if (openaiInput) openaiInput.value = '';
    if (qwenInput) qwenInput.value = '';
    if (deepseekInput) deepseekInput.value = '';
    if (groqInput) groqInput.value = '';
    if (lastfmInput) lastfmInput.value = '';

    // Set enrichment toggles
    const spotifyEnabledEl = document.getElementById('settings-spotify-enabled');
    const deezerEnabledEl = document.getElementById('settings-deezer-enabled');
    const beatportEnabledEl = document.getElementById('settings-beatport-enabled');
    if (spotifyEnabledEl) spotifyEnabledEl.checked = response.spotify_enrich_enabled ?? true;
    if (deezerEnabledEl) deezerEnabledEl.checked = response.deezer_enrich_enabled ?? true;
    if (beatportEnabledEl) beatportEnabledEl.checked = response.beatport_enrich_enabled ?? false;

    // Sync provider selector
    const providerSelect = document.getElementById('settings-provider');
    const aiModel = response.ai_model || 'claude';
    if (providerSelect) {
      providerSelect.value = aiModel;
      showProviderSection(aiModel);
    }

    // Fetch models for the current provider
    await fetchModels(aiModel);

    // Select the saved model from populated dropdown
    const modelSelect = document.getElementById('settings-model');
    if (modelSelect) {
      let savedModel = '';
      if (aiModel === 'openrouter') {
        savedModel = response.openrouter_model || '';
      } else if (aiModel === 'ollama') {
        savedModel = response.ollama_model || '';
      } else if (aiModel === 'openai') {
        savedModel = response.openai_model || '';
      } else if (aiModel === 'qwen') {
        savedModel = response.qwen_model || '';
      } else if (aiModel === 'deepseek') {
        savedModel = response.deepseek_model || '';
      } else if (aiModel === 'groq') {
        savedModel = response.groq_model || '';
      }
      if (savedModel && modelSelect.querySelector('option[value="' + savedModel + '"]')) {
        modelSelect.value = savedModel;
      }
    }

    // Other Round 2 fields
    const batchSizeInput = document.getElementById('settings-batch-size');
    if (batchSizeInput && response.classify_batch_size) batchSizeInput.value = response.classify_batch_size;
    const autoApproveInput = document.getElementById('settings-auto-approve');
    if (autoApproveInput && response.auto_approve_threshold !== undefined) {
      autoApproveInput.value = response.auto_approve_threshold;
      const valDisplay = document.getElementById('settings-auto-approve-value');
      if (valDisplay) valDisplay.textContent = response.auto_approve_threshold + '%';
    }

  } catch (error) {
    // Error already shown in apiFetch
  }
}

// Deprecated -- kept for backward compat but round2 handler takes over
async function saveSettings() {
  try {
    const geminiKey = document.getElementById('settings-gemini-key').value.trim();
    const openrouterKey = document.getElementById('settings-openrouter-key').value.trim();
    const spotifyId = document.getElementById('settings-spotify-id').value.trim();
    const spotifySecret = document.getElementById('settings-spotify-secret').value.trim();
    const threshold = parseInt(document.getElementById('settings-auto-approve')?.value) || 80;

    // Always include threshold so there is always something to save
    const payload = { auto_approve_threshold: threshold };
    if (geminiKey) payload.gemini_api_key = geminiKey;
    if (openrouterKey) payload.openrouter_api_key = openrouterKey;
    if (spotifyId) payload.spotify_client_id = spotifyId;
    if (spotifySecret) payload.spotify_client_secret = spotifySecret;

    showSpinner('Saving settings...');
    const result = await apiFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    if (result.saved) {
      // Also save taxonomy in the same pass
      await apiFetch('/api/taxonomy', {
        method: 'PUT',
        body: JSON.stringify({ genres: window.taxonomy }),
      });
      showToast('All settings saved', 'success');
      // Clear key inputs and reload to show masked values in placeholders
      document.getElementById('settings-gemini-key').value = '';
      document.getElementById('settings-openrouter-key').value = '';
      document.getElementById('settings-spotify-id').value = '';
      document.getElementById('settings-spotify-secret').value = '';
      await loadSettings();
    }

  } catch (error) {
    // Error already shown in apiFetch
  } finally {
    hideSpinner();
  }
}

// ============================================================================
// Theme
// ============================================================================

const THEMES = ['dark', 'pro-booth', 'studio', 'pure-black'];

function initTheme() {
  const saved = localStorage.getItem('theme') || 'pure-black';
  applyTheme(saved);
}

function applyTheme(theme) {
  document.body.classList.remove('light', ...THEMES.filter(t => t !== 'dark'));
  if (theme !== 'dark') document.body.classList.add(theme);
  localStorage.setItem('theme', theme);
  document.querySelectorAll('.swatch').forEach(s => {
    s.classList.toggle('active', s.dataset.theme === theme);
  });
}

function initThemeSwatches() {
  document.querySelectorAll('.swatch').forEach(btn => {
    btn.addEventListener('click', () => applyTheme(btn.dataset.theme));
  });
}

