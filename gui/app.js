const STORAGE_KEY_CONFIG = 'oci_last_config';
const STORAGE_KEY_WORKING_DIR = 'oci_working_dir';

function showToast(message, type) {
    const root = document.getElementById('toast-root');
    const toast = document.createElement('div');
    toast.className = 'toast toast-' + (type || 'info');
    toast.textContent = message;
    root.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}

function setButtonLoading(btn, loading, loadingText) {
    if (!btn) return;
    if (loading) {
        if (!btn.dataset.originalText) btn.dataset.originalText = btn.textContent;
        btn.textContent = loadingText || t('processing');
        btn.classList.add('is-loading');
        btn.disabled = true;
        return;
    }
    if (btn.dataset.originalText) btn.textContent = btn.dataset.originalText;
    btn.classList.remove('is-loading');
}

async function apiFetch(url, options = {}) {
    const response = await fetch(url, options);
    let data = {};
    try {
        data = await response.json();
    } catch (_) {
        if (!response.ok) {
            throw new Error(response.statusText || 'Request failed');
        }
        return {};
    }
    if (!response.ok) {
        throw new Error((data && data.error) || response.statusText || 'Request failed');
    }
    return data;
}

function fillConfigSelect(selectEl, configs, emptyKey) {
    selectEl.innerHTML = '';
    if (!configs.length) {
        const opt = document.createElement('option');
        opt.value = '';
        opt.textContent = t(emptyKey);
        selectEl.appendChild(opt);
        return;
    }
    configs.forEach((name) => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        selectEl.appendChild(opt);
    });
}

function refreshDynamicI18n() {
    document.querySelectorAll('button[data-i18n]').forEach((btn) => {
        if (!btn.classList.contains('is-loading')) {
            delete btn.dataset.originalText;
            btn.textContent = t(btn.dataset.i18n);
        }
    });
    const scrollBtn = document.getElementById('log-autoscroll-btn');
    if (scrollBtn) {
        scrollBtn.textContent = logAutoScroll ? t('logAutoscroll') : t('logAutoscrollOff');
    }
    updateAppStatusBadge();
}

const logPanel = document.getElementById('log-panel');
const logEmpty = document.getElementById('log-empty');
const startBtn = document.getElementById('start-btn');
const stopBtn = document.getElementById('stop-btn');
const configSelect = document.getElementById('config-select');
const sessionInput = document.getElementById('session-id');
const workingDirInput = document.getElementById('working-dir');
const copySessionBtn = document.getElementById('copy-session-btn');
const statusRun = document.getElementById('status-run');
const statusConn = document.getElementById('status-conn');
const statusConfig = document.getElementById('status-config');
let eventSource = null;
let statusInterval = null;
let appRunning = false;
let appConnected = false;
let logAutoScroll = true;
let activeConfigName = '';
const STATUS_POLL_IDLE_MS = 8000;
const STATUS_POLL_ACTIVE_MS = 2000;

function updateAppStatusBadge() {
    statusRun.textContent = appRunning ? t('statusRunning') : t('statusIdle');
    statusRun.className = 'status-pill ' + (appRunning ? 'status-running' : 'status-idle');
    statusConn.textContent = appConnected ? t('statusConnected') : t('statusDisconnected');
    statusConn.className = 'status-pill ' + (appConnected ? 'status-connected' : 'status-disconnected');
    if (appRunning && activeConfigName) {
        statusConfig.hidden = false;
        statusConfig.textContent = activeConfigName;
        statusConfig.title = t('statusRunningConfig', { name: activeConfigName });
    } else {
        statusConfig.hidden = true;
        statusConfig.textContent = '';
    }
    copySessionBtn.disabled = !sessionInput.value.trim();
}

function syncConfigSelection(name) {
    if (!name) return;
    if (configSelect.querySelector('option[value="' + name + '"]')) configSelect.value = name;
    localStorage.setItem(STORAGE_KEY_CONFIG, name);
    prefillWorkingDirFromConfig(name);
}

function prefillWorkingDirFromConfig(name) {
    if (!name || !workingDirInput) return;
    const saved = localStorage.getItem(STORAGE_KEY_WORKING_DIR);
    if (saved) {
        workingDirInput.value = saved;
        return;
    }
    apiFetch('/api/config/' + encodeURIComponent(name))
        .then((data) => {
            if (data.working_dir) workingDirInput.value = data.working_dir;
        })
        .catch(() => {});
}

function loadConfigList(selectName) {
    const preferred = selectName || localStorage.getItem(STORAGE_KEY_CONFIG) || '';
    return apiFetch('/api/configs')
        .then((data) => {
            const configs = data.configs || [];
            fillConfigSelect(configSelect, configs, 'noConfigs');
            if (configs.length > 0) {
                const pick = preferred && configs.includes(preferred) ? preferred : configs[0];
                syncConfigSelection(pick);
                updateStartButtonState();
            } else {
                startBtn.disabled = true;
            }
        })
        .catch(() => {
            fillConfigSelect(configSelect, [], 'loadFailed');
            startBtn.disabled = true;
            showToast(t('toastConfigsLoadFailed'), 'error');
        });
}

function createFactoryTemplates(btn) {
    if (btn) setButtonLoading(btn, true, t('btnCreateTemplates'));
    return fetch('/api/config/create-templates', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({})
    })
    .then(r => r.json())
    .then(data => {
        if (btn) setButtonLoading(btn, false);
        if (!data.ok && data.errors && data.errors.length) {
            showToast(data.errors.join('; ') || t('toastTemplatesFailed'), 'error');
            return data;
        }
        const created = data.created || [];
        const skipped = data.skipped || [];
        if (created.length) showToast(t('toastTemplatesCreated', { names: created.join(', ') }), 'success');
        else if (skipped.length) showToast(t('toastTemplatesSkipped', { names: skipped.join(', ') }), 'info');
        else showToast(t('toastTemplatesNone'), 'info');
        return loadConfigList(created[0] || configSelect.value).then(() => data);
    })
    .catch(() => {
        if (btn) setButtonLoading(btn, false);
        showToast(t('toastTemplatesFailed'), 'error');
    });
}

function updateStartButtonState() {
    if (appRunning) return;
    startBtn.disabled = !configSelect.value;
}

function hideLogEmpty() {
    if (logEmpty) logEmpty.hidden = true;
}

function addLog(msg) {
    hideLogEmpty();
    const div = document.createElement('div');
    let cls = '';
    if (msg.includes('\u2705') || msg.includes('完成') || msg.includes('complete')) cls = ' log-success';
    else if (msg.includes('\u274c') || msg.includes('失敗') || msg.includes('failed')) cls = ' log-error';
    else if (msg.includes('\u26a0') || msg.includes('WARNING')) cls = ' log-warning';
    else if (msg.includes('  | +')) cls = ' log-diff-add';
    else if (msg.includes('  | -')) cls = ' log-diff-del';
    else if (msg.includes('  | ')) cls = ' log-cli';
    div.className = cls;
    div.textContent = msg;
    logPanel.appendChild(div);
    if (logAutoScroll) logPanel.scrollTop = logPanel.scrollHeight;
    while (logPanel.children.length > 501) {
        const first = logPanel.firstElementChild;
        if (first && first.id !== 'log-empty') first.remove();
    }
}

function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource('/api/logs');
    eventSource.onopen = () => {
        appConnected = true;
        updateAppStatusBadge();
    };
    eventSource.onmessage = (e) => {
        if (e.data && e.data !== ':keepalive') addLog(e.data);
    };
    eventSource.onerror = () => {
        appConnected = false;
        updateAppStatusBadge();
        eventSource.close();
        setTimeout(connectSSE, 3000);
    };
}

function scheduleStatusPoll() {
    if (statusInterval) clearInterval(statusInterval);
    if (document.hidden) return;
    const ms = appRunning ? STATUS_POLL_ACTIVE_MS : STATUS_POLL_IDLE_MS;
    updateStatus();
    statusInterval = setInterval(updateStatus, ms);
}

let elapsedTicker = null;
let elapsedStartMs = 0;

function formatElapsedSeconds(totalSeconds) {
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes + ':' + String(seconds).padStart(2, '0');
}

function startElapsedTicker() {
    elapsedStartMs = Date.now();
    if (elapsedTicker) clearInterval(elapsedTicker);
    elapsedTicker = setInterval(() => {
        if (!appRunning) return;
        const seconds = Math.floor((Date.now() - elapsedStartMs) / 1000);
        document.getElementById('stat-elapsed').textContent = formatElapsedSeconds(seconds);
    }, 1000);
}

function stopElapsedTicker() {
    if (elapsedTicker) clearInterval(elapsedTicker);
    elapsedTicker = null;
}

function updateStatus() {
    apiFetch('/api/status').then((data) => {
        document.getElementById('stat-rounds').textContent = data.round_count || 0;
        document.getElementById('stat-sessions').textContent = data.session_count || 0;
        document.getElementById('stat-elapsed').textContent = data.elapsed || '0:00';
        const wasRunning = appRunning;
        appRunning = !!data.running;
        activeConfigName = data.running ? (data.config_name || '') : '';
        if (data.session_id) sessionInput.value = data.session_id;
        updateAppStatusBadge();

        if (data.running) {
            startBtn.disabled = true;
            stopBtn.disabled = false;
            document.getElementById('stat-card-rounds')?.classList.add('is-active');
        } else {
            stopBtn.disabled = true;
            document.getElementById('stat-card-rounds')?.classList.remove('is-active');
            updateStartButtonState();
        }
        if (wasRunning !== appRunning) {
            scheduleStatusPoll();
            if (appRunning) startElapsedTicker();
            else stopElapsedTicker();
        }
    }).catch(() => {
        appConnected = false;
        updateAppStatusBadge();
    });
}

startBtn.addEventListener('click', () => {
    const config = configSelect.value;
    if (!config) {
        showToast(t('toastSelectConfig'), 'error');
        return;
    }
    const sid = sessionInput.value.trim();
    const workingDir = workingDirInput ? workingDirInput.value.trim() : '';
    if (workingDir) localStorage.setItem(STORAGE_KEY_WORKING_DIR, workingDir);
    else localStorage.removeItem(STORAGE_KEY_WORKING_DIR);
    setButtonLoading(startBtn, true, t('starting'));
    apiFetch('/api/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({config: config, session_id: sid, working_dir: workingDir})
    })
    .then((data) => {
        setButtonLoading(startBtn, false);
        addLog(t('logStartSent'));
        sessionInput.value = data.session_id || '';
        activeConfigName = config;
        syncConfigSelection(config);
        startBtn.disabled = true;
        stopBtn.disabled = false;
        appRunning = true;
        startElapsedTicker();
        scheduleStatusPoll();
        updateAppStatusBadge();
        showToast(t('toastTaskStarted'), 'success');
    })
    .catch((e) => {
        setButtonLoading(startBtn, false);
        updateStartButtonState();
        addLog(t('logStartFailed', { error: e.message || t('unknownError') }));
        showToast(e.message || t('toastStartFailed'), 'error');
    });
});

stopBtn.addEventListener('click', () => {
    setButtonLoading(stopBtn, true, t('stopping'));
    apiFetch('/api/stop', { method: 'POST' })
    .then(() => {
        setButtonLoading(stopBtn, false);
        addLog(t('logStopSent'));
        showToast(t('toastStopSent'), 'info');
    })
    .catch((e) => {
        setButtonLoading(stopBtn, false);
        addLog('\u26a0\ufe0f ' + (e.message || t('toastStopFailed')));
        showToast(e.message || t('toastStopFailed'), 'error');
    });
});

configSelect.addEventListener('change', () => {
    syncConfigSelection(configSelect.value);
    updateStartButtonState();
});

document.getElementById('refresh-configs-btn').addEventListener('click', () => {
    loadConfigList(configSelect.value).then(() => showToast(t('toastConfigsRefreshed'), 'info'));
});

document.querySelectorAll('.js-create-templates-btn').forEach((btn) => {
    btn.addEventListener('click', () => createFactoryTemplates(btn));
});

document.getElementById('log-clear-btn').addEventListener('click', () => {
    [...logPanel.children].forEach(child => {
        if (child.id !== 'log-empty') child.remove();
    });
    if (logEmpty) logEmpty.hidden = false;
});

document.getElementById('log-autoscroll-btn').addEventListener('click', (e) => {
    logAutoScroll = !logAutoScroll;
    e.currentTarget.classList.toggle('active', logAutoScroll);
    e.currentTarget.textContent = logAutoScroll ? t('logAutoscroll') : t('logAutoscrollOff');
});

copySessionBtn.addEventListener('click', () => {
    const value = sessionInput.value.trim();
    if (!value) return;
    navigator.clipboard.writeText(value)
        .then(() => showToast(t('toastSessionCopied'), 'success'))
        .catch(() => showToast(t('toastCopyFailed'), 'error'));
});

sessionInput.addEventListener('input', updateAppStatusBadge);

if (workingDirInput) {
    const savedWorkingDir = localStorage.getItem(STORAGE_KEY_WORKING_DIR);
    if (savedWorkingDir) workingDirInput.value = savedWorkingDir;
    workingDirInput.addEventListener('change', () => {
        const value = workingDirInput.value.trim();
        if (value) localStorage.setItem(STORAGE_KEY_WORKING_DIR, value);
        else localStorage.removeItem(STORAGE_KEY_WORKING_DIR);
    });
}

updateAppStatusBadge();
connectSSE();
scheduleStatusPoll();
updateStatus();
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        if (statusInterval) clearInterval(statusInterval);
        statusInterval = null;
    } else {
        updateStatus();
        scheduleStatusPoll();
    }
});
loadConfigList();
