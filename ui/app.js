/**
 * Nestify — фронтенд логика
 * Простой SPA без фреймворков.
 */

const API = '';  // FastAPI на том же домене

// ── Утилиты ─────────────────────────────────────────────────────────────────

async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
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
  ['screen-token', 'screen-dashboard'].forEach(s => {
    document.getElementById(s).classList.toggle('hidden', s !== id);
  });
}

function showPage(name) {
  document.querySelectorAll('[id^="page-"]').forEach(p => p.classList.add('hidden'));
  const page = document.getElementById(`page-${name}`);
  if (page) page.classList.remove('hidden');
  document.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.page === name);
  });
}

function fmt(n) {
  if (!n) return '—';
  return Number(n).toLocaleString('ru-RU');
}

// ── Онбординг: только токен ───────────────────────────────────────────────────

async function checkOnboarding() {
  try {
    const { has_token } = await api('GET', '/api/auth/gemini-token/status');
    if (has_token) {
      showScreen('screen-dashboard');
      initDashboard();
    } else {
      showScreen('screen-token');
    }
  } catch (e) {
    showScreen('screen-token');
  }
}

document.getElementById('btn-save-token').addEventListener('click', async () => {
  const token = document.getElementById('gemini-token-input').value.trim();
  if (!token) { showToast('Введите токен', 'error'); return; }
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен сохранён ✓');
    showScreen('screen-dashboard');
    initDashboard();
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Дашборд ──────────────────────────────────────────────────────────────────

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
  await loadStats();
  await loadOverviewListings();
  await loadAgentLog();
  await updateAgentStatus();
  // Автообновление каждые 15 секунд пока открыт дашборд
  setInterval(async () => {
    await loadStats();
    await loadOverviewListings();
    await loadAgentLog();
    await updateAgentStatus();
  }, 15_000);
}

// Статистика
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

// Последние объявления на главном экране
async function loadOverviewListings() {
  try {
    const rows = await api('GET', '/api/listings/?limit=10');
    const tbody = document.getElementById('overview-listings-body');
    if (!rows.length) return;
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><a href="${r.url || '#'}" target="_blank" style="color:var(--accent);text-decoration:none;">
          ${r.title || r.krisha_id || '—'}
        </a></td>
        <td>${r.client_id || '—'}</td>
        <td>${fmt(r.price)} ₸</td>
        <td>${r.area ? r.area + ' м²' : '—'}</td>
        <td>${scoreCell(r.ai_score)}</td>
        <td>${statusBadge(r.status)}</td>
      </tr>
    `).join('');
  } catch (_) {}
}

function scoreCell(score) {
  if (score === null || score === undefined) return '<span style="color:var(--text-muted)">—</span>';
  const color = score >= 7 ? 'var(--success)' : score >= 5 ? 'var(--warning)' : 'var(--danger)';
  return `<span style="font-weight:600;color:${color}">${score}/10</span>`;
}

function statusBadge(status) {
  const map = {
    new:      ['badge-info',    'Новое'],
    approved: ['badge-success', 'Одобрено'],
    rejected: ['badge-danger',  'Отклонено'],
    messaged: ['badge-warning', 'Написали'],
  };
  const [cls, label] = map[status] || ['badge-info', status || '—'];
  return `<span class="badge ${cls}">${label}</span>`;
}

// ── Клиенты ──────────────────────────────────────────────────────────────────

async function loadClients() {
  try {
    const rows = await api('GET', '/api/listings/clients');
    const tbody = document.getElementById('clients-body');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);padding:32px;">Нет клиентов</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.name}</td>
        <td>${r.district || '—'}</td>
        <td>${r.budget_min ? fmt(r.budget_min) + ' – ' + fmt(r.budget_max) + ' ₸' : '—'}</td>
        <td>${r.deal_type === 'rent' ? 'Аренда' : 'Покупка'}</td>
        <td>
          <button class="btn btn-ghost" style="padding:4px 10px;font-size:12px;"
            onclick="deleteClient(${r.id})">Удалить</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    showToast(e.message, 'error');
  }
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
  } catch (e) {
    showToast(e.message, 'error');
  }
});

async function deleteClient(id) {
  try {
    await api('DELETE', `/api/listings/clients/${id}`);
    showToast('Клиент удалён');
    loadClients();
    loadStats();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Объявления ────────────────────────────────────────────────────────────────

async function loadListings() {
  try {
    const rows = await api('GET', '/api/listings/');
    const tbody = document.getElementById('listings-body');
    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-muted);padding:32px;">Нет объявлений</td></tr>';
      return;
    }
    tbody.innerHTML = rows.map(r => `
      <tr>
        <td><a href="${r.url || '#'}" target="_blank" style="color:var(--accent);text-decoration:none;">
          ${r.title || r.krisha_id || '—'}
        </a></td>
        <td>${fmt(r.price)} ₸</td>
        <td>${r.area ? r.area + ' м²' : '—'}</td>
        <td>${r.district || '—'}</td>
        <td>${r.ai_score !== null ? r.ai_score + '/10' : '—'}</td>
        <td>${statusBadge(r.status)}</td>
      </tr>
    `).join('');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// Лог агента
async function loadAgentLog() {
  try {
    const rows = await api('GET', '/api/agent/log?limit=20');
    const tbody = document.getElementById('agent-log-body');
    if (!rows.length) return;
    const actionLabel = { search: '🔍 Поиск', analyze: '🤖 Анализ', search_error: '❌ Ошибка', send_message: '💬 Сообщение' };
    tbody.innerHTML = rows.map(r => {
      const time = new Date(r.created_at + 'Z').toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      return `<tr>
        <td style="color:var(--text-muted);white-space:nowrap;">${time}</td>
        <td>${actionLabel[r.action] || r.action}</td>
        <td style="color:var(--text-muted);">${r.details || ''}</td>
      </tr>`;
    }).join('');
  } catch (_) {}
}

// ── Агент ─────────────────────────────────────────────────────────────────────

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
    btn.style.background = running ? 'var(--danger)' : '';

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
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Сообщения ─────────────────────────────────────────────────────────────────

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
        <td>${r.client_name || '—'}</td>
        <td><a href="${r.url || '#'}" target="_blank" style="color:var(--accent);text-decoration:none;">${r.title || r.krisha_id || '—'}</a></td>
        <td style="max-width:300px;color:var(--text-muted);">${r.text || ''}</td>
        <td><span class="badge badge-success">Отправлено</span></td>
      </tr>`;
    }).join('');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// ── Настройки ─────────────────────────────────────────────────────────────────

async function loadSettingsPage() {
  try {
    const { has_token, masked } = await api('GET', '/api/auth/gemini-token/status');
    const el = document.getElementById('settings-token-status');
    if (has_token && masked) {
      el.textContent = masked;
      el.style.color = 'var(--success)';
    } else {
      el.textContent = 'не задан';
      el.style.color = 'var(--danger)';
    }
  } catch (_) {}
}

document.getElementById('btn-update-token').addEventListener('click', async () => {
  const token = document.getElementById('settings-token').value.trim();
  if (!token) { showToast('Введите токен', 'error'); return; }
  const btn = document.getElementById('btn-update-token');
  btn.disabled = true;
  btn.textContent = 'Сохраняем...';
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен сохранён ✓');
    document.getElementById('settings-token').value = '';
    await loadSettingsPage();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить токен';
  }
});

document.getElementById('btn-install-playwright').addEventListener('click', async () => {
  const btn = document.getElementById('btn-install-playwright');
  const result = document.getElementById('browser-open-result');
  btn.disabled = true;
  btn.textContent = '⏳ Устанавливаем браузер... (может занять 1-2 минуты)';
  result.textContent = '';
  try {
    const data = await api('POST', '/api/agent/install-playwright');
    if (data.status === 'ok') {
      result.style.color = 'var(--success)';
      result.textContent = '✓ ' + data.message + '\nТеперь нажмите "Открыть браузер".';
    } else {
      result.style.color = 'var(--danger)';
      result.textContent = '✗ ' + data.message + (data.output ? '\n\n' + data.output.slice(-300) : '');
    }
  } catch (e) {
    result.style.color = 'var(--danger)';
    result.textContent = '✗ ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = '⬇️ Установить браузер (playwright install chromium)';
  }
});

document.getElementById('btn-open-browser').addEventListener('click', async () => {
  const btn = document.getElementById('btn-open-browser');
  const result = document.getElementById('browser-open-result');
  btn.disabled = true;
  btn.textContent = '⏳ Открываем браузер...';
  result.textContent = '';
  try {
    const data = await api('POST', '/api/agent/open-browser');
    if (data.status === 'ok') {
      result.style.color = 'var(--success)';
      result.textContent = '✓ Браузер открыт. Если нужно — войдите в Krisha.kz вручную.';
    } else {
      result.style.color = 'var(--danger)';
      result.textContent = '✗ ' + (data.message || 'Ошибка');
    }
  } catch (e) {
    result.style.color = 'var(--danger)';
    result.textContent = '✗ ' + e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = '🌐 Открыть браузер';
  }
});

// ── Карта ─────────────────────────────────────────────────────────────────────

let _map = null;
let _drawingMode = false;
let _polygonPoints = [];   // [[lat, lon], ...]
let _polyline = null;      // линия в процессе рисования
let _polygon = null;       // готовый полигон

async function initMap() {
  // Заполняем список клиентов
  try {
    const clients = await api('GET', '/api/listings/clients');
    const sel = document.getElementById('map-client-select');
    sel.innerHTML = '<option value="">— выберите клиента —</option>' +
      clients.map(c => `<option value="${c.id}" data-polygon="${c.area_polygon || ''}">${c.name}</option>`).join('');

    // Если у выбранного клиента уже есть полигон — показываем его
    sel.addEventListener('change', () => {
      const opt = sel.options[sel.selectedIndex];
      const poly = opt.dataset.polygon;
      if (poly) _loadExistingPolygon(poly);
    });
  } catch (_) {}

  // Инициализируем карту один раз
  if (_map) {
    _map.invalidateSize();
    return;
  }

  _map = L.map('map-container', { zoomControl: true }).setView([51.1694, 71.4491], 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap',
    maxZoom: 19,
  }).addTo(_map);

  _map.on('click', _onMapClick);
  _map.on('dblclick', _finishPolygon);
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

function _finishPolygon(e) {
  if (!_drawingMode || _polygonPoints.length < 3) return;

  // Останавливаем рисование
  _drawingMode = false;
  document.getElementById('map-container').classList.remove('map-draw-active');
  document.getElementById('map-hint').style.display = 'none';

  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon = null; }

  _polygon = L.polygon(_polygonPoints, {
    color: '#4f8ef7',
    fillColor: '#4f8ef7',
    fillOpacity: 0.15,
    weight: 2,
  }).addTo(_map);

  _map.fitBounds(_polygon.getBounds(), { padding: [20, 20] });

  const coordStr = _polygonPoints.map(p => `${p[0].toFixed(6)},${p[1].toFixed(6)}`).join(',');
  document.getElementById('map-polygon-info').textContent =
    `✓ Область обведена: ${_polygonPoints.length} точек`;
  document.getElementById('btn-save-polygon').disabled = false;
  document.getElementById('btn-save-polygon').dataset.coords = coordStr;
}

function _loadExistingPolygon(coordStr) {
  if (!_map || !coordStr) return;
  const parts = coordStr.split(',').map(Number);
  if (parts.length < 4) return;
  _polygonPoints = [];
  for (let i = 0; i < parts.length - 1; i += 2) {
    _polygonPoints.push([parts[i], parts[i + 1]]);
  }
  _finishPolygon({});
  document.getElementById('map-polygon-info').textContent =
    `↩ Загружена сохранённая область (${_polygonPoints.length} точек)`;
}

document.getElementById('btn-draw-polygon').addEventListener('click', () => {
  if (!_map) { showToast('Сначала откройте карту', 'error'); return; }
  _drawingMode = true;
  _polygonPoints = [];
  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon = null; }
  document.getElementById('map-container').classList.add('map-draw-active');
  document.getElementById('map-hint').style.display = 'block';
  document.getElementById('btn-save-polygon').disabled = true;
  document.getElementById('map-polygon-info').textContent = '';
});

document.getElementById('btn-finish-polygon').addEventListener('click', () => {
  _finishPolygon({});
});

document.getElementById('btn-clear-polygon').addEventListener('click', () => {
  _drawingMode = false;
  _polygonPoints = [];
  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon = null; }
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
    showToast('Область сохранена для клиента ✓');
    // Обновляем data-polygon в select
    const opt = document.querySelector(`#map-client-select option[value="${clientId}"]`);
    if (opt) opt.dataset.polygon = coords;
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Старт ─────────────────────────────────────────────────────────────────────

checkOnboarding();
