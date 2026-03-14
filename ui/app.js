/**
 * Nestify — frontend SPA
 */

const API = '';

// ── Utils ────────────────────────────────────────────────────────────────────

async function api(method, path, body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || 'Ошибка запроса');
  }
  return res.json();
}

function showToast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type} show`;
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove('show'), 3000);
}

function showScreen(id) {
  ['screen-token', 'screen-dashboard'].forEach(s =>
    document.getElementById(s).classList.toggle('hidden', s !== id));
}

function showPage(name) {
  document.querySelectorAll('[id^="page-"]').forEach(p => p.classList.add('hidden'));
  const page = document.getElementById(`page-${name}`);
  if (page) page.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(b =>
    b.classList.toggle('active', b.dataset.page === name));
}

function fmt(n) {
  if (!n && n !== 0) return '—';
  return Number(n).toLocaleString('ru-RU');
}

// ── Onboarding ───────────────────────────────────────────────────────────────

async function checkOnboarding() {
  try {
    const { has_token } = await api('GET', '/api/auth/gemini-token/status');
    if (has_token) { showScreen('screen-dashboard'); initDashboard(); }
    else showScreen('screen-token');
  } catch (e) { showScreen('screen-token'); }
}

document.getElementById('btn-save-token').addEventListener('click', async () => {
  const token = document.getElementById('gemini-token-input').value.trim();
  if (!token) { showToast('Введите токен', 'error'); return; }
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен сохранён ✓');
    showScreen('screen-dashboard');
    initDashboard();
  } catch (e) { showToast(e.message, 'error'); }
});

// ── Dashboard ────────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
  btn.addEventListener('click', () => {
    showPage(btn.dataset.page);
    if (btn.dataset.page === 'listings') loadListings();
    if (btn.dataset.page === 'clients')  loadClients();
    if (btn.dataset.page === 'messages') loadMessages();
    if (btn.dataset.page === 'settings') loadSettingsPage();
    if (btn.dataset.page === 'map')      initMap();
  });
});

async function initDashboard() {
  showPage('overview');
  initEmojiPicker();
  await loadStats();
  await loadOverviewListings();
  await loadAgentLog();
  await updateAgentStatus();
  setInterval(async () => {
    await loadStats();
    await loadOverviewListings();
    await loadAgentLog();
    await updateAgentStatus();
  }, 15_000);
}

// Stats
async function loadStats() {
  try {
    const s = await api('GET', '/api/listings/stats');
    document.getElementById('stat-clients').textContent  = s.clients;
    document.getElementById('stat-listings').textContent = s.listings;
    document.getElementById('stat-approved').textContent = s.approved;
    document.getElementById('stat-messages').textContent = s.messaged;
    document.getElementById('stat-actions').textContent  = s.actions_today;
  } catch (_) {}
}

// ── Listings rendering ────────────────────────────────────────────────────────

function renderListingRow(r) {
  const clientChip = r.client_name
    ? `<span class="client-chip"><span class="client-avatar">${r.client_emoji || '🏠'}</span>${r.client_name}</span>`
    : '';

  // Parse area from title if area field is wrong
  let area = r.area;
  if (!area || area < 5) {
    const m = (r.title || '').match(/([\d]+[,.]?\d*)\s*м²/);
    if (m) area = parseFloat(m[1]);
  }

  // Parse district from title if not stored
  let district = r.district || '';

  const areaStr = area ? `${area} м²` : '—';
  const score = r.ai_score;
  let scoreHtml;
  if (score === null || score === undefined || score === 0) {
    scoreHtml = `<span class="score-pill none">—</span>`;
  } else if (score >= 7) {
    scoreHtml = `<span class="score-pill high">${score}</span>`;
  } else if (score >= 5) {
    scoreHtml = `<span class="score-pill mid">${score}</span>`;
  } else {
    scoreHtml = `<span class="score-pill low">${score}</span>`;
  }

  const statusMap = {
    new:      ['badge-info',    'Новое'],
    approved: ['badge-success', 'Одобрено'],
    rejected: ['badge-danger',  'Отклонено'],
    messaged: ['badge-warning', 'Написали'],
  };
  const [sCls, sLabel] = statusMap[r.status] || ['badge-info', r.status || '—'];

  const meta = [district, areaStr].filter(x => x && x !== '—').join(' · ');

  return `<div class="listing-row">
    <div>
      <a class="listing-title" href="${r.url || '#'}" target="_blank">${r.title || r.krisha_id || '—'}</a>
      <div class="listing-meta">${meta || '—'}</div>
    </div>
    <div>${clientChip}</div>
    <div class="listing-price">${fmt(r.price)} ₸</div>
    ${scoreHtml}
    <span class="badge ${sCls}">${sLabel}</span>
  </div>`;
}

async function loadOverviewListings() {
  try {
    const rows = await api('GET', '/api/listings/?limit=10');
    const el = document.getElementById('overview-listings-body');
    if (!rows.length) return;
    el.innerHTML = rows.map(renderListingRow).join('');
  } catch (_) {}
}

async function loadListings() {
  try {
    const rows = await api('GET', '/api/listings/');
    const el = document.getElementById('listings-body');
    if (!rows.length) {
      el.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-muted);">Нет объявлений</div>';
      return;
    }
    el.innerHTML = rows.map(renderListingRow).join('');
  } catch (e) { showToast(e.message, 'error'); }
}

// ── Agent log ────────────────────────────────────────────────────────────────

async function loadAgentLog() {
  try {
    const rows = await api('GET', '/api/agent/log?limit=20');
    const tbody = document.getElementById('agent-log-body');
    if (!rows.length) return;
    const label = { search: '🔍 Поиск', analyze: '🤖 Анализ', search_error: '❌ Поиск', send_message: '💬 Сообщение', browser_open: '🌐 Браузер', browser_error: '⚠️ Браузер', agent_error: '❌ Агент', analyze_error: '⚠️ Gemini', message_error: '⚠️ Сообщение' };
    tbody.innerHTML = rows.map(r => {
      const time = new Date(r.created_at + 'Z').toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      return `<tr>
        <td style="color:var(--text-muted);white-space:nowrap;">${time}</td>
        <td>${label[r.action] || r.action}</td>
        <td style="color:var(--text-muted);">${r.details || ''}</td>
      </tr>`;
    }).join('');
  } catch (_) {}
}

// ── Emoji picker ─────────────────────────────────────────────────────────────

const EMOJIS = ['🏠','🏡','🏢','💎','🌟','🔥','🎯','🦁','🐻','🦊','🌺','🍀','⭐','👑','🚀','💫','🎨','🌈','🏆','🐬'];

function initEmojiPicker() {
  const picker = document.getElementById('emoji-picker');
  if (picker.children.length > 0) return;
  EMOJIS.forEach(e => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'emoji-option' + (e === '🏠' ? ' selected' : '');
    btn.textContent = e;
    btn.onclick = () => {
      picker.querySelectorAll('.emoji-option').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      document.getElementById('c-emoji').value = e;
    };
    picker.appendChild(btn);
  });
}

// ── Clients ───────────────────────────────────────────────────────────────────

let _clientsCache = [];

async function loadClients() {
  try {
    const rows = await api('GET', '/api/listings/clients');
    _clientsCache = rows;
    const el = document.getElementById('clients-body');
    if (!rows.length) {
      el.innerHTML = '<div style="color:var(--text-muted);padding:24px;">Нет клиентов</div>';
      return;
    }
    el.innerHTML = rows.map(c => {
      const params = [];
      if (c.district) params.push(c.district);
      if (c.budget_min || c.budget_max) params.push(`${fmt(c.budget_min)} – ${fmt(c.budget_max)} ₸`);
      if (c.area_min || c.area_max) params.push(`${c.area_min || '—'}–${c.area_max || '—'} м²`);
      if (c.rooms) params.push(`${c.rooms} комн.`);
      const typeLabel = c.deal_type === 'rent' ? 'Аренда' : 'Покупка';
      const hasMap = !!c.area_polygon;
      const hasMsg = !!c.message_template;

      return `<div class="client-card" onclick="openClientModal(${c.id})">
        <div class="client-card-header">
          <div class="client-card-avatar">${c.emoji || '🏠'}</div>
          <div>
            <div class="client-card-name">${c.name}</div>
            <div class="client-card-type">${typeLabel}${hasMap ? ' · 🗺️ область' : ''}${hasMsg ? ' · 💬 шаблон' : ''}</div>
          </div>
        </div>
        <div class="client-card-params">
          ${params.map(p => `<span class="param-tag">${p}</span>`).join('')}
        </div>
      </div>`;
    }).join('');
  } catch (e) { showToast(e.message, 'error'); }
}

document.getElementById('btn-add-client').addEventListener('click', async () => {
  const body = {
    name:             document.getElementById('c-name').value.trim(),
    district:         document.getElementById('c-district').value.trim() || null,
    budget_min:       parseInt(document.getElementById('c-budget-min').value) || null,
    budget_max:       parseInt(document.getElementById('c-budget-max').value) || null,
    area_min:         parseInt(document.getElementById('c-area-min').value)   || null,
    area_max:         parseInt(document.getElementById('c-area-max').value)   || null,
    rooms:            document.getElementById('c-rooms').value     || null,
    deal_type:        document.getElementById('c-deal-type').value,
    message_template: document.getElementById('c-message-template').value.trim() || null,
    emoji:            document.getElementById('c-emoji').value || '🏠',
  };
  if (!body.name) { showToast('Введите имя клиента', 'error'); return; }
  try {
    await api('POST', '/api/listings/clients', body);
    showToast('Клиент добавлен ✓');
    loadClients();
    loadStats();
    ['c-name','c-district','c-budget-min','c-budget-max','c-area-min','c-area-max','c-message-template'].forEach(id => {
      document.getElementById(id).value = '';
    });
    // reset emoji
    document.getElementById('c-emoji').value = '🏠';
    document.querySelectorAll('.emoji-option').forEach((b, i) => b.classList.toggle('selected', i === 0));
  } catch (e) { showToast(e.message, 'error'); }
});

// ── Client modal ──────────────────────────────────────────────────────────────

let _modalMap = null;
let _currentClientId = null;

function openClientModal(clientId) {
  const client = _clientsCache.find(c => c.id === clientId);
  if (!client) return;
  _currentClientId = clientId;

  document.getElementById('modal-avatar').textContent = client.emoji || '🏠';
  document.getElementById('modal-name').textContent = client.name;

  // Params
  const params = [];
  if (client.district) params.push({ label: '📍 Район', val: client.district });
  if (client.budget_min || client.budget_max) params.push({ label: '💰 Бюджет', val: `${fmt(client.budget_min)} – ${fmt(client.budget_max)} ₸` });
  if (client.area_min || client.area_max) params.push({ label: '📐 Площадь', val: `${client.area_min || '—'} – ${client.area_max || '—'} м²` });
  if (client.rooms) params.push({ label: '🚪 Комнат', val: client.rooms });
  params.push({ label: '🏷️ Тип', val: client.deal_type === 'rent' ? 'Аренда' : 'Покупка' });

  document.getElementById('modal-params').innerHTML = params.map(p =>
    `<span class="param-tag"><strong style="color:var(--text-dim)">${p.label}:</strong> ${p.val}</span>`
  ).join('');

  // Message
  const msgSection = document.getElementById('modal-message-section');
  if (client.message_template) {
    document.getElementById('modal-message').textContent = client.message_template;
    msgSection.classList.remove('hidden');
  } else {
    document.getElementById('modal-message').textContent = 'Не задан — Gemini напишет самостоятельно';
    msgSection.classList.remove('hidden');
  }

  // Map
  const mapSection = document.getElementById('modal-map-section');
  if (client.area_polygon) {
    mapSection.classList.remove('hidden');
    // Init mini map after modal shown
    setTimeout(() => initModalMap(client.area_polygon), 100);
  } else {
    mapSection.classList.add('hidden');
  }

  document.getElementById('client-modal').classList.remove('hidden');
}

function initModalMap(polygonStr) {
  if (_modalMap) { _modalMap.remove(); _modalMap = null; }
  _modalMap = L.map('modal-map-container', { zoomControl: false, dragging: false, scrollWheelZoom: false })
    .setView([51.1694, 71.4491], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(_modalMap);

  const parts = polygonStr.split(',').map(Number);
  const points = [];
  for (let i = 0; i < parts.length - 1; i += 2) points.push([parts[i], parts[i+1]]);

  if (points.length >= 3) {
    const poly = L.polygon(points, { color: '#4f8ef7', fillColor: '#4f8ef7', fillOpacity: 0.15, weight: 2 }).addTo(_modalMap);
    _modalMap.fitBounds(poly.getBounds(), { padding: [10, 10] });
  }
}

document.getElementById('btn-close-modal').addEventListener('click', () => {
  document.getElementById('client-modal').classList.add('hidden');
  if (_modalMap) { _modalMap.remove(); _modalMap = null; }
});

document.getElementById('client-modal').addEventListener('click', e => {
  if (e.target === document.getElementById('client-modal')) {
    document.getElementById('btn-close-modal').click();
  }
});

document.getElementById('btn-modal-delete').addEventListener('click', async () => {
  if (!_currentClientId) return;
  try {
    await api('DELETE', `/api/listings/clients/${_currentClientId}`);
    showToast('Клиент удалён');
    document.getElementById('btn-close-modal').click();
    loadClients();
    loadStats();
  } catch (e) { showToast(e.message, 'error'); }
});

document.getElementById('btn-modal-open-map').addEventListener('click', () => {
  document.getElementById('btn-close-modal').click();
  showPage('map');
  setTimeout(() => {
    initMap();
    const sel = document.getElementById('map-client-select');
    if (sel) {
      sel.value = _currentClientId;
      sel.dispatchEvent(new Event('change'));
    }
  }, 200);
});

// ── Messages ──────────────────────────────────────────────────────────────────

async function loadMessages() {
  try {
    const rows = await api('GET', '/api/listings/messages');
    const tbody = document.getElementById('messages-body');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:32px;">Агент ещё не отправлял сообщений</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => {
      const time = new Date(r.sent_at + 'Z').toLocaleString('ru-RU', { day:'2-digit', month:'2-digit', hour:'2-digit', minute:'2-digit' });
      return `<tr>
        <td style="color:var(--text-muted);white-space:nowrap;">${time}</td>
        <td><span class="client-chip"><span class="client-avatar">🏠</span>${r.client_name || '—'}</span></td>
        <td><a href="${r.url || '#'}" target="_blank" style="color:var(--accent);text-decoration:none;">${r.title || r.krisha_id || '—'}</a></td>
        <td style="max-width:280px;color:var(--text-muted);">${r.text || ''}</td>
        <td><span class="badge badge-success">Отправлено</span></td>
      </tr>`;
    }).join('');
  } catch (e) { showToast(e.message, 'error'); }
}

// ── Agent ─────────────────────────────────────────────────────────────────────

let _agentRunning = false;

async function updateAgentStatus() {
  try {
    const { running, last_error } = await api('GET', '/api/agent/status');
    _agentRunning = running;
    const dot      = document.getElementById('agent-dot');
    const text     = document.getElementById('agent-status-text');
    const btn      = document.getElementById('btn-toggle-agent');
    const errorBox = document.getElementById('agent-error-box');

    dot.classList.toggle('running', running);
    text.textContent = running ? 'Агент работает' : 'Агент остановлен';
    btn.textContent  = running ? 'Остановить агента' : 'Запустить агента';
    btn.style.background = running
      ? 'linear-gradient(135deg,var(--danger) 0%,#e55b5b 100%)'
      : '';

    if (last_error) {
      errorBox.textContent = '⚠️ ' + last_error;
      errorBox.classList.remove('hidden');
    } else {
      errorBox.classList.add('hidden');
    }
  } catch (_) {}
}

document.getElementById('btn-toggle-agent').addEventListener('click', async () => {
  try {
    if (_agentRunning) {
      await api('POST', '/api/agent/stop');
      showToast('Агент остановлен');
    } else {
      await api('POST', '/api/agent/start');
      showToast('Агент запущен ✓');
    }
    await updateAgentStatus();
  } catch (e) { showToast(e.message, 'error'); }
});

// ── Settings ──────────────────────────────────────────────────────────────────

async function loadSettingsPage() {
  try {
    const { has_token, masked } = await api('GET', '/api/auth/gemini-token/status');
    const el = document.getElementById('settings-token-status');
    if (has_token && masked) { el.textContent = masked; el.style.color = 'var(--success)'; }
    else { el.textContent = 'не задан'; el.style.color = 'var(--danger)'; }
  } catch (_) {}
  try {
    const { model } = await api('GET', '/api/auth/gemini-model');
    if (model) {
      document.getElementById('settings-model').value = model;
      const sel = document.getElementById('settings-model-select');
      // Выбираем в дропдауне если есть такой вариант
      if (sel) {
        const opt = [...sel.options].find(o => o.value === model);
        if (opt) sel.value = model;
      }
    }
  } catch (_) {}
}

document.getElementById('btn-update-token').addEventListener('click', async () => {
  const token = document.getElementById('settings-token').value.trim();
  if (!token) { showToast('Введите токен', 'error'); return; }
  const btn = document.getElementById('btn-update-token');
  btn.disabled = true; btn.textContent = 'Сохраняем...';
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен сохранён ✓');
    document.getElementById('settings-token').value = '';
    await loadSettingsPage();
  } catch (e) { showToast(e.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = 'Сохранить токен'; }
});

document.getElementById('btn-save-model').addEventListener('click', async () => {
  const model = (document.getElementById('settings-model').value || '').trim();
  if (!model) { showToast('Введите название модели', 'error'); return; }
  const btn = document.getElementById('btn-save-model');
  btn.disabled = true; btn.textContent = 'Сохраняем...';
  try {
    await api('POST', '/api/auth/gemini-model', { model });
    showToast(`Модель сохранена: ${model}`);
  } catch (e) { showToast(e.message, 'error'); }
  finally { btn.disabled = false; btn.textContent = '💾 Сохранить модель'; }
});

document.getElementById('btn-test-gemini').addEventListener('click', async () => {
  const btn = document.getElementById('btn-test-gemini');
  const result = document.getElementById('gemini-test-result');
  btn.disabled = true; btn.textContent = '⏳ Проверяем...';
  result.textContent = '';
  try {
    const data = await api('POST', '/api/auth/test-gemini');
    if (data.status === 'ok') {
      result.style.color = 'var(--success)';
      result.textContent = '✓ ' + data.message;
    } else {
      result.style.color = 'var(--danger)';
      result.textContent = '✗ Ошибка: ' + data.message;
    }
  } catch (e) {
    result.style.color = 'var(--danger)';
    result.textContent = '✗ ' + e.message;
  } finally {
    btn.disabled = false; btn.textContent = '🧪 Тест Gemini';
  }
});

document.getElementById('btn-install-playwright').addEventListener('click', async () => {
  const btn = document.getElementById('btn-install-playwright');
  const result = document.getElementById('browser-open-result');
  btn.disabled = true; btn.textContent = '⏳ Устанавливаем... (1-2 мин)';
  result.textContent = '';
  try {
    const data = await api('POST', '/api/agent/install-playwright');
    result.style.color = data.status === 'ok' ? 'var(--success)' : 'var(--danger)';
    result.textContent = (data.status === 'ok' ? '✓ ' : '✗ ') + data.message;
  } catch (e) { result.style.color = 'var(--danger)'; result.textContent = '✗ ' + e.message; }
  finally { btn.disabled = false; btn.textContent = '⬇️ Установить браузер (playwright install chromium)'; }
});

document.getElementById('btn-open-browser').addEventListener('click', async () => {
  const btn = document.getElementById('btn-open-browser');
  const result = document.getElementById('browser-open-result');
  btn.disabled = true; btn.textContent = '⏳ Открываем...';
  result.textContent = '';
  try {
    const data = await api('POST', '/api/agent/open-browser');
    result.style.color = data.status === 'ok' ? 'var(--success)' : 'var(--danger)';
    result.textContent = (data.status === 'ok' ? '✓ ' : '✗ ') + data.message;
  } catch (e) { result.style.color = 'var(--danger)'; result.textContent = '✗ ' + e.message; }
  finally { btn.disabled = false; btn.textContent = '🌐 Открыть браузер'; }
});

// ── Map ───────────────────────────────────────────────────────────────────────

let _map = null, _drawingMode = false, _polygonPoints = [], _polyline = null, _polygon = null;

async function initMap() {
  try {
    const clients = await api('GET', '/api/listings/clients');
    _clientsCache = clients;
    const sel = document.getElementById('map-client-select');
    sel.innerHTML = '<option value="">— выберите клиента —</option>' +
      clients.map(c => `<option value="${c.id}" data-polygon="${c.area_polygon || ''}">${c.emoji || '🏠'} ${c.name}</option>`).join('');
    sel.onchange = () => {
      const opt = sel.options[sel.selectedIndex];
      if (opt.dataset.polygon) _loadExistingPolygon(opt.dataset.polygon);
    };
  } catch (_) {}

  if (_map) { _map.invalidateSize(); return; }

  _map = L.map('map-container', { zoomControl: true }).setView([51.1694, 71.4491], 11);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap', maxZoom: 19 }).addTo(_map);
  _map.on('click', _onMapClick);
  _map.on('dblclick', e => { e.originalEvent.preventDefault(); _finishPolygon(); });
}

function _onMapClick(e) {
  if (!_drawingMode) return;
  _polygonPoints.push([e.latlng.lat, e.latlng.lng]);
  _redrawPolyline();
}

function _redrawPolyline() {
  if (_polyline) _map.removeLayer(_polyline);
  if (_polygonPoints.length < 2) return;
  _polyline = L.polyline(_polygonPoints, { color: '#4f8ef7', weight: 2, dashArray: '6,4' }).addTo(_map);
}

function _finishPolygon() {
  if (!_drawingMode || _polygonPoints.length < 3) return;
  _drawingMode = false;
  document.getElementById('map-container').classList.remove('map-draw-active');
  document.getElementById('map-hint').style.display = 'none';
  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon  = null; }
  _polygon = L.polygon(_polygonPoints, { color: '#4f8ef7', fillColor: '#4f8ef7', fillOpacity: 0.15, weight: 2 }).addTo(_map);
  _map.fitBounds(_polygon.getBounds(), { padding: [20, 20] });
  const coordStr = _polygonPoints.map(p => `${p[0].toFixed(6)},${p[1].toFixed(6)}`).join(',');
  document.getElementById('map-polygon-info').textContent = `✓ Область: ${_polygonPoints.length} точек`;
  const btn = document.getElementById('btn-save-polygon');
  btn.disabled = false;
  btn.dataset.coords = coordStr;
}

function _loadExistingPolygon(coordStr) {
  if (!_map || !coordStr) return;
  const parts = coordStr.split(',').map(Number);
  _polygonPoints = [];
  for (let i = 0; i < parts.length - 1; i += 2) _polygonPoints.push([parts[i], parts[i+1]]);
  _drawingMode = true;
  _finishPolygon();
  document.getElementById('map-polygon-info').textContent = `↩ Загружена сохранённая область (${_polygonPoints.length} точек)`;
}

document.getElementById('btn-draw-polygon').addEventListener('click', () => {
  if (!_map) { showToast('Сначала откройте вкладку Карта', 'error'); return; }
  _drawingMode = true; _polygonPoints = [];
  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon  = null; }
  document.getElementById('map-container').classList.add('map-draw-active');
  document.getElementById('map-hint').style.display = 'flex';
  document.getElementById('btn-save-polygon').disabled = true;
  document.getElementById('map-polygon-info').textContent = '';
});

document.getElementById('btn-finish-polygon').addEventListener('click', _finishPolygon);

document.getElementById('btn-clear-polygon').addEventListener('click', () => {
  _drawingMode = false; _polygonPoints = [];
  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon  = null; }
  document.getElementById('map-hint').style.display = 'none';
  document.getElementById('map-container').classList.remove('map-draw-active');
  document.getElementById('btn-save-polygon').disabled = true;
  document.getElementById('map-polygon-info').textContent = '';
});

document.getElementById('btn-save-polygon').addEventListener('click', async () => {
  const clientId = document.getElementById('map-client-select').value;
  if (!clientId) { showToast('Выберите клиента', 'error'); return; }
  const coords = document.getElementById('btn-save-polygon').dataset.coords;
  if (!coords) { showToast('Сначала обведите область', 'error'); return; }
  try {
    await api('PATCH', `/api/listings/clients/${clientId}/polygon`, { area_polygon: coords });
    showToast('Область сохранена ✓');
    const opt = document.querySelector(`#map-client-select option[value="${clientId}"]`);
    if (opt) opt.dataset.polygon = coords;
  } catch (e) { showToast(e.message, 'error'); }
});

// ── Start ─────────────────────────────────────────────────────────────────────

checkOnboarding();
