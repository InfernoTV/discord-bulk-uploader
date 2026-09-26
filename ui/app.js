/**
 * BulkCord Uploader - High-Performance Web Frontend Engine
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
  targetProgress: 0.0
};

// DOM Cache
const dom = {
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
  filterSelect: document.getElementById('filter-select'),
  fileSummaryText: document.getElementById('file-summary-text'),

  batchSegmented: document.getElementById('batch-segmented'),
  batchValBadge: document.getElementById('batch-val-badge'),
  batchNote: document.getElementById('batch-note'),
  delaySlider: document.getElementById('delay-slider'),
  delayValBadge: document.getElementById('delay-val-badge'),

  startBtn: document.getElementById('start-btn'),
  pauseBtn: document.getElementById('pause-btn'),
  stopBtn: document.getElementById('stop-btn'),

  hudEta: document.getElementById('hud-eta'),
  hudSpeed: document.getElementById('hud-speed'),
  hudSent: document.getElementById('hud-sent'),

  progressFill: document.getElementById('progress-fill'),
  progressPct: document.getElementById('progress-pct'),
  statusMsg: document.getElementById('status-msg'),

  globalStatusDot: document.getElementById('global-status-dot'),
  globalStatusText: document.getElementById('global-status-text'),

  discordMosaicGrid: document.getElementById('discord-mosaic-grid'),
  mosaicBadge: document.getElementById('mosaic-badge'),
  discordUsername: document.getElementById('discord-username'),
  discordTime: document.getElementById('discord-time'),

  queueList: document.getElementById('queue-list'),
  queueCountBadge: document.getElementById('queue-count-badge'),
  terminalBody: document.getElementById('terminal-body'),
  clearConsoleBtn: document.getElementById('clear-console-btn')
};

// ================= DISCORD CLIENT MOSAIC PREVIEW ENGINE =================
// Exact Discord native algorithm: groups bottom into 3s, expands top row
const DISCORD_MOSAIC_RULES = {
  1: [{ span: 6, h: 160 }],
  2: [{ span: 3, h: 120 }, { span: 3, h: 120 }],
  3: [{ span: 6, h: 100 }, { span: 3, h: 85 }, { span: 3, h: 85 }],
  4: [{ span: 3, h: 85 }, { span: 3, h: 85 }, { span: 3, h: 85 }, { span: 3, h: 85 }],
  5: [
    { span: 3, h: 90 }, { span: 3, h: 90 }, // Top 2 big
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 } // Bottom 3
  ],
  6: [
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 },
    { span: 2, h: 72 }, { span: 2, h: 72 }, { span: 2, h: 72 }
  ],
  7: [
    { span: 6, h: 90 }, // Top 1 big full width
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 },
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 }
  ],
  8: [
    { span: 3, h: 85 }, { span: 3, h: 85 }, // Top 2 big
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 },
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 }
  ],
  9: [
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 },
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 },
    { span: 2, h: 65 }, { span: 2, h: 65 }, { span: 2, h: 65 }
  ],
  10: [
    { span: 6, h: 65 }, // Top 1 big
    { span: 2, h: 52 }, { span: 2, h: 52 }, { span: 2, h: 52 },
    { span: 2, h: 52 }, { span: 2, h: 52 }, { span: 2, h: 52 },
    { span: 2, h: 52 }, { span: 2, h: 52 }, { span: 2, h: 52 }
  ]
};

function renderDiscordMosaic() {
  const count = state.selectedBatchSize;
  const layout = DISCORD_MOSAIC_RULES[count] || [{ span: 6, h: 100 }];
  dom.discordMosaicGrid.innerHTML = '';

  dom.mosaicBadge.textContent = `${count}-Item Client Mosaic`;

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
      label.className = 'mosaic-tile-name';
      label.textContent = file.name;
      tile.appendChild(label);
    } else {
      const placeholder = document.createElement('div');
      placeholder.className = 'mosaic-tile-placeholder';
      placeholder.innerHTML = `<span class="placeholder-icon">🖼️</span><span style="font-size:10px">${file ? file.name : `img_${i+1}.png`}</span>`;
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
        <div class="empty-icon">📁</div>
        <p>No files loaded. Select or drag a folder above.</p>
      </div>`;
    dom.queueCountBadge.textContent = '0 Assets';
    return;
  }

  dom.queueCountBadge.textContent = `${state.loadedFiles.length} Assets`;
  dom.queueList.innerHTML = '';

  const frag = document.createDocumentFragment();

  state.loadedFiles.forEach((file, idx) => {
    const row = document.createElement('div');
    row.className = 'queue-item';
    row.id = `queue-item-${idx}`;

    const thumbHtml = file.thumb
      ? `<img src="${file.thumb}" class="queue-thumb" alt="" />`
      : `<div class="queue-thumb-doc">📄</div>`;

    row.innerHTML = `
      <div class="queue-item-left">
        ${thumbHtml}
        <div class="queue-meta">
          <span class="queue-filename">${idx + 1}. ${file.name}</span>
          <span class="queue-filesize">${file.size_kb.toFixed(1)} KB</span>
        </div>
      </div>
      <span class="queue-pill upcoming" id="queue-pill-${idx}">Upcoming</span>
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
    pill.textContent = '● Sending';
  } else if (status === 'sent') {
    pill.classList.add('sent');
    pill.textContent = '✓ Sent';
  } else if (status === 'failed') {
    pill.classList.add('failed');
    pill.textContent = '✗ Failed';
  } else {
    pill.classList.add('upcoming');
    pill.textContent = 'Upcoming';
  }
}

function scrollToQueueIndex(idx) {
  const target = document.getElementById(`queue-item-${idx}`);
  if (target && dom.queueList) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

// ================= REAL-TIME 60 FPS TELEMETRY & SMOOTH EXTRAPOLATION =================
function formatDuration(sec) {
  if (sec <= 0 || !isFinite(sec)) return '0s';
  const s = Math.ceil(sec);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}m ${rem < 10 ? '0' : ''}${rem}s`;
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
  dom.statusMsg.textContent = `Transmitting Batch #${batchNum} (${startIdx + 1}-${startIdx + batchCount} of ${totalFiles})...`;
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
  dom.pauseBtn.textContent = '⏸ Pause';
  dom.stopBtn.disabled = true;

  dom.progressFill.style.width = '100%';
  dom.progressPct.textContent = '100%';

  dom.globalStatusDot.className = 'status-dot success';
  dom.globalStatusText.textContent = 'Transmission Complete';

  const elapsedStr = formatDuration(elapsedSec);
  dom.hudEta.textContent = `Done (${elapsedStr})`;
  dom.statusMsg.textContent = `✓ Complete: ${successCount} sent, ${failedCount} failed in ${elapsedStr}`;
};

// ================= USER INTERACTION EVENT LISTENERS =================

// 1. Token Visibility Toggle
dom.toggleTokenBtn.addEventListener('click', () => {
  if (dom.tokenInput.type === 'password') {
    dom.tokenInput.type = 'text';
    dom.toggleTokenBtn.style.color = 'var(--blurple)';
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
    appendLog('WARN', new Date().toLocaleTimeString(), 'Please input a token before verifying.');
    return;
  }

  dom.verifyTokenBtn.disabled = true;
  dom.verifyTokenBtn.textContent = 'Verifying...';

  try {
    const res = await window.pywebview.api.verify_token(token, isBot);
    if (res.success) {
      dom.authBadge.className = 'auth-badge verified';
      dom.authBadgeText.textContent = `✓ ${res.username} [${res.role}]`;
      dom.discordUsername.textContent = res.username;
      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Verified: ${res.username} (ID: ${res.id})`);
    } else {
      dom.authBadge.className = 'auth-badge error';
      dom.authBadgeText.textContent = `✗ ${res.error}`;
      appendLog('ERROR', new Date().toLocaleTimeString(), `Token verification failed: ${res.error}`);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `API call error: ${err}`);
  } finally {
    dom.verifyTokenBtn.disabled = false;
    dom.verifyTokenBtn.textContent = 'Verify Token';
  }
});

// 3. Channel Verification
dom.verifyChanBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const channel = dom.channelInput.value.trim();
  if (!token || !channel) {
    appendLog('WARN', new Date().toLocaleTimeString(), 'Token and Channel ID/Link required.');
    return;
  }

  dom.verifyChanBtn.disabled = true;
  dom.verifyChanBtn.textContent = 'Checking...';

  try {
    const res = await window.pywebview.api.verify_channel(token, dom.isBotChk.checked, channel);
    if (res.success) {
      dom.channelInput.value = res.channel_id;
      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Channel verified: #${res.channel_name} (ID: ${res.channel_id})`);
    } else {
      appendLog('ERROR', new Date().toLocaleTimeString(), `Channel check failed: ${res.error}`);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Network error: ${err}`);
  } finally {
    dom.verifyChanBtn.disabled = false;
    dom.verifyChanBtn.textContent = 'Verify Channel';
  }
});

// 4. Fetch Guild Channels
dom.fetchChannelsBtn.addEventListener('click', async () => {
  const token = dom.tokenInput.value.trim();
  const guild = dom.guildInput.value.trim();
  if (!token || !guild) {
    appendLog('WARN', new Date().toLocaleTimeString(), 'Token and Server ID required to fetch tree.');
    return;
  }

  dom.fetchChannelsBtn.disabled = true;
  dom.fetchChannelsBtn.textContent = 'Fetching...';

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
      appendLog('SUCCESS', new Date().toLocaleTimeString(), `Fetched ${res.channels.length} text channels.`);
    } else {
      appendLog('WARN', new Date().toLocaleTimeString(), res.error || 'No text channels found.');
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Error fetching server tree: ${err}`);
  } finally {
    dom.fetchChannelsBtn.disabled = false;
    dom.fetchChannelsBtn.textContent = 'Fetch Channels';
  }
});

dom.channelSelect.addEventListener('change', () => {
  if (dom.channelSelect.value) {
    dom.channelInput.value = dom.channelSelect.value;
  }
});

// 5. Folder Browsing & Loading
dom.browseFolderBtn.addEventListener('click', async () => {
  try {
    const folder = await window.pywebview.api.select_folder_dialog();
    if (folder) {
      dom.folderInput.value = folder;
      loadFolder(folder);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Folder picker error: ${err}`);
  }
});

dom.folderInput.addEventListener('change', () => {
  const folder = dom.folderInput.value.trim();
  if (folder) loadFolder(folder);
});

dom.filterSelect.addEventListener('change', () => {
  const folder = dom.folderInput.value.trim();
  if (folder) loadFolder(folder);
});

async function loadFolder(folder) {
  dom.fileSummaryText.textContent = 'Loading directory...';
  try {
    const filter = dom.filterSelect.value;
    const res = await window.pywebview.api.load_folder_files(folder, filter);
    if (res.success) {
      state.loadedFiles = res.files;
      state.totalFiles = res.files.length;
      dom.fileSummaryText.textContent = `✓ ${res.files.length} files (${res.total_mb.toFixed(1)} MB)`;
      dom.hudSent.textContent = `0 / ${res.files.length}`;
      renderDiscordMosaic();
      renderQueueList();
      appendLog('INFO', new Date().toLocaleTimeString(), `Loaded ${res.files.length} files from ${folder}`);
    } else {
      dom.fileSummaryText.textContent = 'Failed to load folder';
      appendLog('ERROR', new Date().toLocaleTimeString(), res.error);
    }
  } catch (err) {
    appendLog('ERROR', new Date().toLocaleTimeString(), `Load folder error: ${err}`);
  }
}

// 6. Batch Size Segmented Button (1 to 10)
dom.batchSegmented.querySelectorAll('button').forEach(btn => {
  btn.addEventListener('click', () => {
    dom.batchSegmented.querySelectorAll('button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const val = parseInt(btn.getAttribute('data-val'), 10);
    state.selectedBatchSize = val;
    dom.batchValBadge.textContent = `${val} files / msg`;

    if (state.loadedFiles.length > 0) {
      const msgs = Math.ceil(state.loadedFiles.length / val);
      dom.batchNote.textContent = `⚡ Groups ${state.loadedFiles.length} files into ${msgs} Discord messages (saves ${state.loadedFiles.length - msgs} API calls).`;
    } else {
      dom.batchNote.textContent = `⚡ Groups ${val} files per Discord message. Applies dynamically mid-upload.`;
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
    dom.delayValBadge.className = 'badge-value';
    dom.delayValBadge.style.color = 'var(--yellow)';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (⚠️ Aggressive)`;
  } else if (v <= 3.5) {
    dom.delayValBadge.className = 'badge-value text-green';
    dom.delayValBadge.style.color = '';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (🛡️ Recommended Safe)`;
  } else {
    dom.delayValBadge.className = 'badge-value';
    dom.delayValBadge.style.color = 'var(--blurple)';
    dom.delayValBadge.textContent = `${v.toFixed(1)}s (🐢 Conservative)`;
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

  if (!token) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Cannot start: Discord token required.');
  if (!channel) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Cannot start: Destination channel required.');
  if (!state.loadedFiles || state.loadedFiles.length === 0) return appendLog('ERROR', new Date().toLocaleTimeString(), 'Cannot start: No files loaded.');

  state.isUploading = true;
  state.isPaused = false;
  state.processedFiles = 0;
  state.uploadStartTime = performance.now() / 1000;
  state.displayProgress = 0.0;
  state.targetProgress = 0.0;

  dom.startBtn.disabled = true;
  dom.pauseBtn.disabled = false;
  dom.pauseBtn.textContent = '⏸ Pause';
  dom.stopBtn.disabled = false;

  dom.globalStatusDot.className = 'status-dot active';
  dom.globalStatusText.textContent = '● Transmitting';

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
    appendLog('ERROR', new Date().toLocaleTimeString(), `Transmission start failed: ${err}`);
  }
});

dom.pauseBtn.addEventListener('click', async () => {
  if (!state.isPaused) {
    state.isPaused = true;
    dom.pauseBtn.textContent = '▶ Resume';
    dom.globalStatusDot.className = 'status-dot warn';
    dom.globalStatusText.textContent = 'Paused';
    dom.statusMsg.textContent = 'Status: PAUSED';
    await window.pywebview.api.pause_upload();
  } else {
    state.isPaused = false;
    dom.pauseBtn.textContent = '⏸ Pause';
    dom.globalStatusDot.className = 'status-dot active';
    dom.globalStatusText.textContent = '● Transmitting';
    dom.statusMsg.textContent = 'Status: Resuming transmission...';
    await window.pywebview.api.resume_upload();
  }
});

dom.stopBtn.addEventListener('click', async () => {
  dom.statusMsg.textContent = 'Status: Stopping stream...';
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
  appendLog('INFO', new Date().toLocaleTimeString(), 'BulkCord WebView2 bridge established.');
});
