/**
 * BulkCord Uploader - High-Performance Web Frontend Engine
 * Design: Dark Graphite / Ayran Laser UI
 * Strictly Zero Emojis - Pure Vector SVGs
 */

// Application State
const state = {
  loadedFiles: [],
  totalFiles: 0,
  selectedBatchSize: 4,
  selectedDelay: 2.5,
  isUploading: false,
  isPaused: false,
  activeBatchIndices: [],
  processedFiles: 0,
  uploadStartTime: 0,
  batchStartTime: 0,
  currentBatchCount: 0,
  measuredBatchDuration: 0.8,
  displayProgress: 0.0,
  targetProgress: 0.0,
  activeFilters: new Set(['all'])
};

// DOM Cache
const dom = {
  accentSwatches: document.getElementById('accent-swatches'),
  customAccentPicker: document.getElementById('custom-accent-picker'),

  tokenInput: document.getElementById('token-input'),
  toggleTokenBtn: document.getElementById('toggle-token-btn'),
  verifyTokenBtn: document.getElementById('verify-token-btn'),
  isBotChk: document.getElementById('is-bot-chk'),
  authBadge: document.getElementById('auth-badge'),
  authBadgeText: document.getElementById('auth-badge-text'),

  channelInput: document.getElementById('channel-input'),
  verifyChanBtn: document.getElementById('verify-chan-btn'),
  guildInput: document.getElementById('guild-input'),
  fetchChannelsBtn: document.getElementById('fetch-channels-btn'),
  channelSelect: document.getElementById('channel-select'),

  folderInput: document.getElementById('folder-input'),
  browseFolderBtn: document.getElementById('browse-folder-btn'),
  filterPills: document.getElementById('filter-pills'),
  fileSummaryText: document.getElementById('file-summary-text'),

  batchSegmented: document.getElementById('batch-segmented'),
  batchValBadge: document.getElementById('batch-val-badge'),
  batchNote: document.getElementById('batch-note'),
  delaySlider: document.getElementById('delay-slider'),
  delayValBadge: document.getElementById('delay-val-badge'),

  startBtn: document.getElementById('start-btn'),
  pauseBtn: document.getElementById('pause-btn'),
  stopBtn: document.getElementById('stop-btn'),
  controlCard: document.getElementById('control-card'),

  hudEta: document.getElementById('hud-eta'),
  hudSpeed: document.getElementById('hud-speed'),
  hudSent: document.getElementById('hud-sent'),

  progressFill: document.getElementById('progress-fill'),
  progressPct: document.getElementById('progress-pct'),
  statusMsg: document.getElementById('status-msg'),

  globalStatusPill: document.getElementById('global-status-pill'),
  globalStatusDot: document.getElementById('global-status-dot'),
  globalStatusText: document.getElementById('global-status-text'),

  discordMosaicGrid: document.getElementById('discord-mosaic-grid'),
  mosaicBadge: document.getElementById('mosaic-badge'),
  discordAvatar: document.getElementById('discord-avatar'),
  discordUsername: document.getElementById('discord-username'),
  discordTag: document.getElementById('discord-tag'),
  discordTime: document.getElementById('discord-time'),

  queueList: document.getElementById('queue-list'),
  queueCountBadge: document.getElementById('queue-count-badge'),
  terminalBody: document.getElementById('terminal-body'),
  clearConsoleBtn: document.getElementById('clear-console-btn')
};

// ================= DISCORD CLIENT MOSAIC PREVIEW ENGINE =================
// Native Discord logic: groups bottom rows into triplets (3s) and expands remainder on top
const DISCORD_MOSAIC_RULES = {
  1: [{ span: 6, h: 180 }],
  2: [{ span: 3, h: 130 }, { span: 3, h: 130 }],
  3: [
    { span: 6, h: 100 },
    { span: 3, h: 85 }, { span: 3, h: 85 }
  ],
  4: [
    { span: 3, h: 85 }, { span: 3, h: 85 },
    { span: 3, h: 85 }, { span: 3, h: 85 }
  ],
  5: [
    { span: 3, h: 92 }, { span: 3, h: 92 }, // Top 2 big
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 } // Bottom 3
  ],
  6: [
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 },
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 }
  ],
  7: [
    { span: 6, h: 88 }, // Top 1 big full width
    { span: 2, h: 64 }, { span: 2, h: 64 }, { span: 2, h: 64 },
    { span: 2, h: 64 }, { span: 2, h: 64 }, { span: 2, h: 64 }
  ],
  8: [
    { span: 3, h: 84 }, { span: 3, h: 84 }, // Top 2 big
    { span: 2, h: 64 }, { span: 2, h: 64 }, { span: 2, h: 64 },
    { span: 2, h: 64 }, { span: 2, h: 64 }, { span: 2, h: 64 }
  ],
  9: [
    { span: 2, h: 62 }, { span: 2, h: 62 }, { span: 2, h: 62 },
    { span: 2, h: 62 }, { span: 2, h: 62 }, { span: 2, h: 62 },
    { span: 2, h: 62 }, { span: 2, h: 62 }, { span: 2, h: 62 }
  ],
  10: [
    { span: 6, h: 68 }, // Top 1 big
    { span: 2, h: 54 }, { span: 2, h: 54 }, { span: 2, h: 54 },
    { span: 2, h: 54 }, { span: 2, h: 54 }, { span: 2, h: 54 },
    { span: 2, h: 54 }, { span: 2, h: 54 }, { span: 2, h: 54 }
  ]
};

function renderDiscordMosaic() {
  const count = state.selectedBatchSize;
  const layout = DISCORD_MOSAIC_RULES[count] || [{ span: 6, h: 100 }];
  dom.discordMosaicGrid.innerHTML = '';

  dom.mosaicBadge.textContent = `${count}-ITEM PAYLOAD MOSAIC`;

  const sampleFiles = state.loadedFiles.slice(0, count);

  layout.forEach((itemRule, i) => {
    const tile = document.createElement('div');
    tile.className = 'mosaic-tile';
    tile.style.gridColumn = `span ${itemRule.span}`;
    tile.style.height = `${itemRule.h}px`;

    const file = sampleFiles[i];
    if (file && file.thumb) {
      const img = document.createElement('img');
      img.src = file.thumb;
      img.alt = file.name;
      tile.appendChild(img);

      const label = document.createElement('div');
      label.className = 'mosaic-tile-name font-mono';
      label.textContent = file.name;
      tile.appendChild(label);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'mosaic-tile-placeholder';
      placeholder.innerHTML = `
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>
          <circle cx="9" cy="9" r="2"/>
          <path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>
        </svg>
        <span class="placeholder-text font-mono">${file ? file.name : `payload_${i+1}.png`}</span>
      `;
      tile.appendChild(placeholder);
    }

    dom.discordMosaicGrid.appendChild(tile);
  });
}

// ================= FILE QUEUE RENDERING =================
function renderQueueList() {
  if (!state.loadedFiles || state.loadedFiles.length === 0) {
    dom.queueList.innerHTML = `
      <div class="queue-empty-state">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
        </div>
        <p class="font-mono">NO ASSETS LOADED</p>
        <span class="empty-subtext">Select a folder on the left to queue files</span>
      </div>`;
    dom.queueCountBadge.textContent = '0 ASSETS';
    return;
  }

  dom.queueCountBadge.textContent = `${state.loadedFiles.length} ASSETS`;
  dom.queueList.innerHTML = '';

  const frag = document.createDocumentFragment();

  state.loadedFiles.forEach((file, idx) => {
    const row = document.createElement('div');
    row.className = 'queue-item';
    row.id = `queue-item-${idx}`;

    const thumbHtml = file.thumb
      ? `<img src="${file.thumb}" class="queue-thumb" alt="" />`
      : `<div class="queue-thumb-doc">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
        </div>`;

    row.innerHTML = `
      <div class="queue-item-left">
        ${thumbHtml}
        <div class="queue-meta">
          <span class="queue-filename">${idx + 1}. ${escapeHtml(file.name)}</span>
          <span class="queue-filesize font-mono">${file.size_kb.toFixed(1)} KB</span>
        </div>
      </div>
      <span class="queue-pill upcoming" id="queue-pill-${idx}">QUEUED</span>
    `;

    frag.appendChild(row);
  });

  dom.queueList.appendChild(frag);
}

function updateQueueItemState(idx, status) {
  const row = document.getElementById(`queue-item-${idx}`);
  const pill = document.getElementById(`queue-pill-${idx}`);
  if (!row || !pill) return;

  row.classList.remove('active');
  pill.className = 'queue-pill';

  if (status === 'sending') {
    row.classList.add('active');
    pill.classList.add('sending');
    pill.textContent = 'TRANSMITTING';
  } else if (status === 'sent') {
    pill.classList.add('sent');
    pill.textContent = 'COMPLETED';
  } else if (status === 'failed') {
    pill.classList.add('failed');
    pill.textContent = 'FAILED';
  } else {
    pill.classList.add('upcoming');
    pill.textContent = 'QUEUED';
  }
}

function scrollToQueueIndex(idx) {
  const target = document.getElementById(`queue-item-${idx}`);
  if (target && dom.queueList) {
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
}

// ================= REAL-TIME 60 FPS TELEMETRY & SMOOTH EXTRAPOLATION =================
function formatDuration(sec) {
  if (sec <= 0 || !isFinite(sec)) return '00:00';
  const s = Math.ceil(sec);
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m < 10 ? '0' : ''}${m}:${rem < 10 ? '0' : ''}${rem}`;
}

function telemetryTick() {
  if (state.isUploading && !state.isPaused) {
    // 1. Extrapolate sub-batch progress smoothly
    if (state.totalFiles > 0) {
      const now = performance.now() / 1000;
      const elapsedInBatch = Math.max(0, now - state.batchStartTime);
      const expectedCycle = state.measuredBatchDuration + state.selectedDelay;
      const fraction = Math.min(0.96, Math.max(0, elapsedInBatch / Math.max(0.3, expectedCycle)));

      const extrapolatedCount = state.processedFiles + (fraction * state.currentBatchCount);
      state.targetProgress = Math.min(1.0, extrapolatedCount / state.totalFiles);

      // Smooth lerp (linear interpolation) towards target
      state.displayProgress += (state.targetProgress - state.displayProgress) * 0.18;
      const pct = (state.displayProgress * 100).toFixed(1);
      dom.progressFill.style.width = `${pct}%`;
      dom.progressPct.textContent = `${Math.round(pct)}%`;
    }

    // 2. Dynamic ETA calculation based on real network latency and live batch slider
    const remainingFiles = Math.max(0, state.totalFiles - state.processedFiles);
    const remBatches = Math.ceil(remainingFiles / state.selectedBatchSize);
    const etaSec = remBatches * (state.selectedDelay + state.measuredBatchDuration);
    dom.hudEta.textContent = formatDuration(etaSec);

    // 3. Transmission Speed
    const now = performance.now() / 1000;
    const totalElapsed = Math.max(0.1, now - state.uploadStartTime);
    const speed = (state.processedFiles / totalElapsed).toFixed(1);
    dom.hudSpeed.textContent = `${speed} f/s`;
    dom.hudSent.textContent = `${state.processedFiles} / ${state.totalFiles}`;
  } else if (state.isPaused) {
    dom.hudEta.textContent = 'PAUSED';
  }

  requestAnimationFrame(telemetryTick);
}
requestAnimationFrame(telemetryTick);

// ================= TERMINAL CONSOLE LOGGING =================
function appendLog(level, timeStr, message) {
  const row = document.createElement('div');
  row.className = 'log-entry';

  row.innerHTML = `
    <span class="log-time">[${timeStr}]</span>
    <span class="log-level ${level}">[${level}]</span>
    <span class="log-msg">${escapeHtml(message)}</span>
  `;

  dom.terminalBody.appendChild(row);
  dom.terminalBody.scrollTop = dom.terminalBody.scrollHeight;
}

function escapeHtml(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ================= BACKEND EVENT HOOKS =================
window.onLog = function(level, timeStr, message) {
  appendLog(level, timeStr, message);
};

window.onBatchStart = function(batchNum, startIdx, batchCount, totalFiles, etaSec) {
  state.currentBatchCount = batchCount;
  state.batchStartTime = performance.now() / 1000;
  state.activeBatchIndices = [];

  for (let i = 0; i < batchCount; i++) {
    const idx = startIdx + i;
    state.activeBatchIndices.push(idx);
    updateQueueItemState(idx, 'sending');
  }

  scrollToQueueIndex(startIdx);
  dom.statusMsg.textContent = `TRANSMITTING BATCH #${batchNum} (${startIdx + 1}-${startIdx + batchCount} OF ${totalFiles})...`;
};

window.onBatchEnd = function(batchIndices, success, batchLatency) {
  if (batchLatency && batchLatency > 0.1) {
    state.measuredBatchDuration = 0.65 * state.measuredBatchDuration + 0.35 * batchLatency;
  }

  batchIndices.forEach(idx => {
    updateQueueItemState(idx, success ? 'sent' : 'failed');
  });

  state.processedFiles += batchIndices.length;
};

window.onUploadFinished = function(successCount, failedCount, totalFiles, elapsedSec) {
  state.isUploading = false;
  state.isPaused = false;
  dom.startBtn.disabled = false;
  dom.pauseBtn.disabled = true;
  setPauseButtonMode(false);
  dom.stopBtn.disabled = true;
  dom.controlCard.classList.remove('active-transmitting');

  dom.progressFill.style.width = '100%';
  dom.progressPct.textContent = '100%';

  dom.globalStatusDot.className = 'status-dot success';
  dom.globalStatusText.textContent = 'SYSTEM COMPLETE';

  const elapsedStr = formatDuration(elapsedSec);
  dom.hudEta.textContent = `DONE (${elapsedStr})`;
  dom.statusMsg.textContent = `COMPLETED: ${successCount} TRANSMITTED, ${failedCount} FAILED (${elapsedStr})`;
};

function setPauseButtonMode(isPaused) {
  const span = dom.pauseBtn.querySelector('span');
  if (isPaused) {
    // Resume mode
    dom.pauseBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <polygon points="6 3 20 12 6 21 6 3"/>
      </svg>
      <span>RESUME</span>
    `;
  } else {
    // Pause mode
    dom.pauseBtn.innerHTML = `
      <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
        <rect x="6" y="4" width="4" height="16" rx="1"/>
        <rect x="14" y="4" width="4" height="16" rx="1"/>
      </svg>
      <span>PAUSE</span>
    `;
  }
}

// ================= ACCENT COLOR PALETTE ENGINE =================
function hexToRgba(hex, alpha) {
  let r = 0, g = 0, b = 0;
  const clean = hex.replace('#', '');
  if (clean.length === 3) {
    r = parseInt(clean[0] + clean[0], 16);
    g = parseInt(clean[1] + clean[1], 16);
    b = parseInt(clean[2] + clean[2], 16);
  } else if (clean.length >= 6) {
    r = parseInt(clean.substring(0, 2), 16);
    g = parseInt(clean.substring(2, 4), 16);
    b = parseInt(clean.substring(4, 6), 16);
  }
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function darkenColor(hex, factor) {
  let r = 0, g = 0, b = 0;
  const clean = hex.replace('#', '');
  if (clean.length === 3) {
    r = parseInt(clean[0] + clean[0], 16);
    g = parseInt(clean[1] + clean[1], 16);
    b = parseInt(clean[2] + clean[2], 16);
  } else if (clean.length >= 6) {
    r = parseInt(clean.substring(0, 2), 16);
    g = parseInt(clean.substring(2, 4), 16);
    b = parseInt(clean.substring(4, 6), 16);
  }
  r = Math.max(0, Math.floor(r * (1 - factor)));
  g = Math.max(0, Math.floor(g * (1 - factor)));
  b = Math.max(0, Math.floor(b * (1 - factor)));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}

function setAccentColor(hex) {
  if (!hex) return;
  document.documentElement.style.setProperty('--accent', hex);
  document.documentElement.style.setProperty('--accent-dim', hexToRgba(hex, 0.16));
  document.documentElement.style.setProperty('--accent-glow', hexToRgba(hex, 0.38));
  document.documentElement.style.setProperty('--aurora-2', hex);
  document.documentElement.style.setProperty('--aurora-1', darkenColor(hex, 0.28));

  try {
    localStorage.setItem('bulkcord_accent', hex);
  } catch (e) {}

  if (dom.accentSwatches) {
    dom.accentSwatches.querySelectorAll('.swatch-btn').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-color').toLowerCase() === hex.toLowerCase());
    });
  }

  if (dom.customAccentPicker) {
    dom.customAccentPicker.value = hex;
  }
}

if (dom.accentSwatches) {
  dom.accentSwatches.querySelectorAll('.swatch-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      setAccentColor(btn.getAttribute('data-color'));
    });
  });
}

if (dom.customAccentPicker) {
  dom.customAccentPicker.addEventListener('input', (e) => {
    setAccentColor(e.target.value);
  });
}

// Restore saved accent color preference
try {
  const savedAccent = localStorage.getItem('bulkcord_accent');
  if (savedAccent) {
    setAccentColor(savedAccent);
  }
} catch (e) {}

// ================= USER INTERACTION EVENT LISTENERS =================

// 1. Token Visibility Toggle
dom.toggleTokenBtn.addEventListener('click', () => {
  if (dom.tokenInput.type === 'password') {
    dom.tokenInput.type = 'text';
    dom.toggleTokenBtn.style.color = 'var(--accent)';
  } else {
    dom.tokenInput.type = 'password';
    dom.toggleTokenBtn.style.color = '';
  }
});

// 2. Token Verification
dom.verifyTokenBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const isBot = dom.isBotChk.checked;
  if (!token) {
    appendLog('WARN', new Date().toLocaleTimeString(), 'Discord token required for verification.');
    return;
  }

  const span = dom.verifyTokenBtn.querySelector('span');
  if (span) span.textContent = 'CHECKING...';
  dom.verifyTokenBtn.disabled = true;

  try {
    const res = await window.pywebview.api.verify_token(token, isBot);
    if (res.success) {
      dom.authBadge.className = 'auth-badge verified';
      dom.authBadgeText.textContent = `VERIFIED: ${res.username.toUpperCase()} [${res.role.toUpperCase()}]`;

      // Update Client Simulation Box with actual Avatar and Global Username
      if (res.avatar_url && dom.discordAvatar) {
        dom.discordAvatar.innerHTML = `<img src="${res.avatar_url}" alt="Avatar" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover; display: block;">`;
      }
      dom.discordUsername.textContent = res.global_name || res.username;
      if (dom.discordTag) {
        dom.discordTag.textContent = res.is_bot ? 'VERIFIED BOT' : 'USER';
      }

      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Verified: ${res.global_name || res.username} (Snowflake ID: ${res.id})`);
    } else {
      dom.authBadge.className = 'auth-badge error';
      dom.authBadgeText.textContent = `FAILED: ${res.error.toUpperCase()}`;
      appendLog('ERROR', new Date().toLocaleTimeString(), `Token verification failed: ${res.error}`);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `API invocation error: ${err}`);
  } finally {
    dom.verifyTokenBtn.disabled = false;
    if (span) span.textContent = 'VERIFY';
  }
});

// 3. Channel Verification
dom.verifyChanBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const channel = dom.channelInput.value.trim();
  if (!token || !channel) {
    appendLog('WARN', new Date().toLocaleTimeString(), 'Discord token and channel snowflake ID required.');
    return;
  }

  dom.verifyChanBtn.disabled = true;
  dom.verifyChanBtn.textContent = 'CHECKING...';

  try {
    const res = await window.pywebview.api.verify_channel(token, dom.isBotChk.checked, channel);
    if (res.success) {
      dom.channelInput.value = res.channel_id;
      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Channel validated: #${res.channel_name} (${res.channel_id})`);
    } else {
      appendLog('ERROR', new Date().toLocaleTimeString(), `Channel check failed: ${res.error}`);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Network request error: ${err}`);
  } finally {
    dom.verifyChanBtn.disabled = false;
    dom.verifyChanBtn.textContent = 'CHECK';
  }
});

// 4. Fetch Guild Channels
dom.fetchChannelsBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const guild = dom.guildInput.value.trim();
  if (!token || !guild) {
    appendLog('WARN', new Date().toLocaleTimeString(), 'Token and Server ID required to fetch channel tree.');
    return;
  }

  dom.fetchChannelsBtn.disabled = true;
  dom.fetchChannelsBtn.textContent = 'FETCHING...';

  try {
    const res = await window.pywebview.api.fetch_guild_channels(token, dom.isBotChk.checked, guild);
    if (res.success && res.channels.length > 0) {
      dom.channelSelect.innerHTML = '';
      dom.channelSelect.disabled = false;

      res.channels.forEach(ch => {
        const opt = document.createElement('option');
        opt.value = ch.id;
        opt.textContent = ch.label;
        dom.channelSelect.appendChild(opt);
      });

      dom.channelInput.value = res.channels[0].id;
      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Discovered ${res.channels.length} text channel targets.`);
    } else {
      appendLog('WARN', new Date().toLocaleTimeString(), res.error || 'No text channels discovered in server.');
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Channel tree query error: ${err}`);
  } finally {
    dom.fetchChannelsBtn.disabled = false;
    dom.fetchChannelsBtn.textContent = 'FETCH';
  }
});

dom.channelSelect.addEventListener('change', () => {
  if (dom.channelSelect.value) {
    dom.channelInput.value = dom.channelSelect.value;
  }
});

// 5. Folder Browsing & Multi-Filter Loading
dom.browseFolderBtn.addEventListener('click', async () => {
  try {
    const folder = await window.pywebview.api.select_folder_dialog();
    if (folder) {
      dom.folderInput.value = folder;
      loadFolder(folder);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Directory dialog error: ${err}`);
  }
});

dom.folderInput.addEventListener('change', () => {
  const folder = dom.folderInput.value.trim();
  if (folder) loadFolder(folder);
});

// Multi-select Filter Pills Handling
if (dom.filterPills) {
  dom.filterPills.querySelectorAll('.pill-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const filterKey = btn.getAttribute('data-filter');

      if (filterKey === 'all') {
        state.activeFilters.clear();
        state.activeFilters.add('all');
      } else {
        state.activeFilters.delete('all');
        if (state.activeFilters.has(filterKey)) {
          state.activeFilters.delete(filterKey);
          if (state.activeFilters.size === 0) {
            state.activeFilters.add('all');
          }
        } else {
          state.activeFilters.add(filterKey);
        }
      }

      // Update active styling on buttons
      dom.filterPills.querySelectorAll('.pill-btn').forEach(b => {
        const k = b.getAttribute('data-filter');
        b.classList.toggle('active', state.activeFilters.has(k));
      });

      const folder = dom.folderInput.value.trim();
      if (folder) loadFolder(folder);
    });
  });
}

async function loadFolder(folder) {
  dom.fileSummaryText.textContent = 'INDEXING DIRECTORY...';
  try {
    const filterTokens = state.activeFilters.has('all') ? 'all' : Array.from(state.activeFilters).join(',');
    const res = await window.pywebview.api.load_folder_files(folder, filterTokens);
    if (res.success) {
      state.loadedFiles = res.files;
      state.totalFiles = res.files.length;
      dom.fileSummaryText.textContent = `${res.files.length} ASSETS (${res.total_mb.toFixed(1)} MB)`;
      dom.hudSent.textContent = `0 / ${res.files.length}`;
      renderDiscordMosaic();
      renderQueueList();
      appendLog('INFO', new Date().toLocaleTimeString(), `Indexed ${res.files.length} assets [Filters: ${filterTokens.toUpperCase()}] from ${folder}`);
    } else {
      dom.fileSummaryText.textContent = 'INDEXING FAILED';
      appendLog('ERROR', new Date().toLocaleTimeString(), res.error);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Folder load error: ${err}`);
  }
}

// 6. Batch Size Segmented Button (1 to 10)
dom.batchSegmented.querySelectorAll('button').forEach(btn => {
  btn.addEventListener('click', () => {
    dom.batchSegmented.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const val = parseInt(btn.getAttribute('data-val'), 10);
    state.selectedBatchSize = val;
    dom.batchValBadge.textContent = `${val} FILES / MSG`;

    if (state.loadedFiles.length > 0) {
      const msgs = Math.ceil(state.loadedFiles.length / val);
      dom.batchNote.textContent = `DYNAMIC SLICING: Groups ${state.loadedFiles.length} assets into ${msgs} payload messages.`;
    } else {
      dom.batchNote.textContent = `DYNAMIC SLICING: Groups ${val} assets per Discord message. Applies mid-upload.`;
    }

    renderDiscordMosaic();

    if (window.pywebview && window.pywebview.api) {
      window.pywebview.api.update_batch_size(val);
    }
  });
});

// 7. Delay Slider
dom.delaySlider.addEventListener('input', (e) => {
  const v = parseFloat(e.target.value);
  state.selectedDelay = v;

  if (v < 1.5) {
    dom.delayValBadge.className = 'badge-value font-mono';
    dom.delayValBadge.style.color = 'var(--signal-amber)';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (AGGRESSIVE)`;
  } else if (v <= 3.5) {
    dom.delayValBadge.className = 'badge-value font-mono text-accent';
    dom.delayValBadge.style.color = '';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (OPTIMAL SAFE)`;
  } else {
    dom.delayValBadge.className = 'badge-value font-mono';
    dom.delayValBadge.style.color = 'var(--text-secondary)';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (CONSERVATIVE)`;
  }

  if (window.pywebview && window.pywebview.api) {
    window.pywebview.api.update_delay(v);
  }
});

// 8. Transmission Controls
dom.startBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const channel = dom.channelInput.value.trim();
  const folder = dom.folderInput.value.trim();

  if (!token) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Abort: Discord authorization token required.');
  if (!channel) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Abort: Destination channel snowflake ID required.');
  if (!state.loadedFiles || state.loadedFiles.length === 0) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Abort: No assets queued for transmission.');

  state.isUploading = true;
  state.isPaused = false;
  state.processedFiles = 0;
  state.uploadStartTime = performance.now() / 1000;
  state.displayProgress = 0.0;
  state.targetProgress = 0.0;

  dom.startBtn.disabled = true;
  dom.pauseBtn.disabled = false;
  setPauseButtonMode(false);
  dom.stopBtn.disabled = false;
  dom.controlCard.classList.add('active-transmitting');

  dom.globalStatusDot.className = 'status-dot active';
  dom.globalStatusText.textContent = 'TRANSMITTING';

  try {
    await window.pywebview.api.start_upload({
      token,
      is_bot: dom.isBotChk.checked,
      channel_id: channel,
      folder,
      batch_size: state.selectedBatchSize,
      delay: state.selectedDelay
    });
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Transmission initialization error: ${err}`);
  }
});

dom.pauseBtn.addEventListener('click', async () => {
  if (!state.isPaused) {
    state.isPaused = true;
    setPauseButtonMode(true);
    dom.globalStatusDot.className = 'status-dot warn';
    dom.globalStatusText.textContent = 'PAUSED';
    dom.statusMsg.textContent = 'TRANSMISSION PAUSED BY USER';
    await window.pywebview.api.pause_upload();
  } else {
    state.isPaused = false;
    setPauseButtonMode(false);
    dom.globalStatusDot.className = 'status-dot active';
    dom.globalStatusText.textContent = 'TRANSMITTING';
    dom.statusMsg.textContent = 'RESUMING TRANSMISSION STREAM...';
    await window.pywebview.api.resume_upload();
  }
});

dom.stopBtn.addEventListener('click', async () => {
  dom.statusMsg.textContent = 'TERMINATING TRANSMISSION STREAM...';
  await window.pywebview.api.stop_upload();
});

// Clear console
dom.clearConsoleBtn.addEventListener('click', () => {
  dom.terminalBody.innerHTML = '';
});

// Set current time in Discord message
dom.discordTime.textContent = 'Today at ' + new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

// Init initial blank preview
renderDiscordMosaic();

// Webview Ready Hook
window.addEventListener('pywebviewready', () => {
  appendLog('INFO', new Date().toLocaleTimeString(), 'BulkCord WebView2 native bridge active.');
});
