/**
 * Nestify — фронтенд логика
 * SPA без фреймворков. Glass + Neomorphism UI.
 */

const API = '';

// ── Утилиты ──────────────────────────────────────────────────────────────────

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
  el._t = setTimeout(() => el.classList.remove('show'), 3200);
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

function fmtPrice(n) {
  if (!n) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace('.0', '') + ' млн ₸';
  return fmt(n) + ' ₸';
}

// ── Онбординг ─────────────────────────────────────────────────────────────────

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
  const btn = document.getElementById('btn-save-token');
  btn.disabled = true;
  btn.textContent = 'Сохраняем...';
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен сохранён ✓');
    showScreen('screen-dashboard');
    initDashboard();
  } catch (e) {
    showToast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = 'Открыть дашборд →';
  }
});

// ── Дашборд ───────────────────────────────────────────────────────────────────

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

// ── Статистика ─────────────────────────────────────────────────────────────────

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

// ── Рендер строки объявления ───────────────────────────────────────────────────

function scorePill(score) {
  if (score === null || score === undefined || score === 0) {
    return `<span class="score-pill none">—</span>`;
  }
  const cls = score >= 7 ? 'high' : score >= 5 ? 'mid' : 'low';
  return `<span class="score-pill ${cls}">${score}/10</span>`;
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

// Пытается извлечь площадь из заголовка если в базе не записана
function guessArea(r) {
  if (r.area && r.area > 5) return r.area + ' м²';
  if (r.title) {
    const m = r.title.match(/([\d]+[,.]?\d*)\s*м²/);
    if (m) return parseFloat(m[1].replace(',', '.')) + ' м²';
    const m2 = r.title.match(/(\d+)\s*кв/i);
    if (m2) return m2[1] + ' м²';
  }
  return '—';
}

function renderListingRow(r) {
  const clientHtml = r.client_name
    ? `<span class="client-chip">
         <span class="client-avatar">${r.client_emoji || '🏠'}</span>
         ${r.client_name}
       </span>`
    : `<span style="color:var(--text-muted);font-size:12px;">—</span>`;

  const metaParts = [];
  const area = guessArea(r);
  if (area !== '—') metaParts.push(area);
  if (r.district) metaParts.push(r.district);

  const div = document.createElement('div');
  div.className = 'listing-row';
  div.innerHTML = `
    <div>
      <a href="${r.url || '#'}" target="_blank" class="listing-title"
         title="${(r.title || '').replace(/"/g, '&quot;')}">
        ${r.title || r.krisha_id || '—'}
      </a>
      ${metaParts.length ? `<div class="listing-meta">${metaParts.join(' · ')}</div>` : ''}
    </div>
    <div>${clientHtml}</div>
    <div class="listing-price">${fmtPrice(r.price)}</div>
    <div>${scorePill(r.ai_score)}</div>
    <div>${statusBadge(r.status)}</div>
  `;
  return div;
}

// ── Обзор — последние объявления ──────────────────────────────────────────────

async function loadOverviewListings() {
  try {
    const rows = await api('GET', '/api/listings/?limit=10');
    const grid = document.getElementById('overview-listings-grid');
    const empty = document.getElementById('overview-empty');

    // Убираем старые строки (кроме header и empty)
    grid.querySelectorAll('.listing-row:not(.header)').forEach(el => el.remove());
    if (empty) empty.remove();

    if (!rows.length) {
      const emptyEl = document.createElement('div');
      emptyEl.id = 'overview-empty';
      emptyEl.className = 'empty-state';
      emptyEl.innerHTML = '<div class="empty-icon">🏘️</div>Нет данных. Добавьте клиента и запустите агента.';
      grid.appendChild(emptyEl);
      return;
    }

    rows.forEach(r => grid.appendChild(renderListingRow(r)));
  } catch (_) {}
}

// ── Лог агента ────────────────────────────────────────────────────────────────

async function loadAgentLog() {
  try {
    const rows = await api('GET', '/api/agent/log?limit=20');
    const tbody = document.getElementById('agent-log-body');
    if (!rows.length) return;
    const actionLabel = {
      search:       '🔍 Поиск',
      analyze:      '🤖 Анализ',
      search_error: '❌ Ошибка',
      send_message: '💬 Сообщение',
    };
    tbody.innerHTML = rows.map(r => {
      const time = new Date(r.created_at + 'Z').toLocaleTimeString('ru-RU', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      });
      return `<tr>
        <td style="color:var(--text-muted);white-space:nowrap;font-size:12px;">${time}</td>
        <td>${actionLabel[r.action] || r.action}</td>
        <td style="color:var(--text-muted);font-size:12px;">${r.details || ''}</td>
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
    btn.style.background = running
      ? 'linear-gradient(135deg, var(--danger), #d44)'
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
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Эмодзи пикер ──────────────────────────────────────────────────────────────

const EMOJIS = [
  '🏠','🏡','🏢','🏗️','🏘️','🏙️',
  '🏛️','🏟️','🏰','🏯','🗼','🗽',
  '👨','👩','👦','👧','👴','👵',
  '💼','📋','📊','💰','💎','🔑',
  '⭐','🌟','✨','🎯','🚀','💡',
  '🌆','🌇','🌃','🌉','🌁','🗺️',
];

let _selectedEmoji = '🏠';

function initEmojiPicker() {
  const picker = document.getElementById('emoji-picker');
  const preview = document.getElementById('emoji-preview');
  const hiddenInput = document.getElementById('c-emoji');

  picker.innerHTML = EMOJIS.map(e =>
    `<div class="emoji-option${e === _selectedEmoji ? ' selected' : ''}"
          data-emoji="${e}" title="${e}">${e}</div>`
  ).join('');

  picker.querySelectorAll('.emoji-option').forEach(opt => {
    opt.addEventListener('click', () => {
      _selectedEmoji = opt.dataset.emoji;
      preview.textContent = _selectedEmoji;
      hiddenInput.value = _selectedEmoji;
      picker.querySelectorAll('.emoji-option').forEach(o =>
        o.classList.toggle('selected', o.dataset.emoji === _selectedEmoji)
      );
      picker.classList.add('hidden');
    });
  });

  preview.addEventListener('click', () => {
    picker.classList.toggle('hidden');
  });

  // Закрываем пикер при клике вне него
  document.addEventListener('click', (e) => {
    if (!picker.contains(e.target) && e.target !== preview) {
      picker.classList.add('hidden');
    }
  });
}

// ── Клиенты ───────────────────────────────────────────────────────────────────

async function loadClients() {
  try {
    const rows = await api('GET', '/api/listings/clients');
    const grid = document.getElementById('clients-grid');

    if (!rows.length) {
      grid.innerHTML = `
        <div class="empty-state glass-panel" style="grid-column:1/-1;padding:40px;">
          <div class="empty-icon">👥</div>
          Нет клиентов. Добавьте первого клиента выше.
        </div>`;
      return;
    }

    grid.innerHTML = rows.map(r => {
      const tags = [];
      if (r.budget_min || r.budget_max) {
        const from = r.budget_min ? fmtPrice(r.budget_min) : '';
        const to   = r.budget_max ? fmtPrice(r.budget_max) : '';
        tags.push(`💰 ${from}${from && to ? ' – ' : ''}${to}`);
      }
      if (r.area_min || r.area_max) {
        const from = r.area_min ? r.area_min + ' м²' : '';
        const to   = r.area_max ? r.area_max + ' м²' : '';
        tags.push(`📐 ${from}${from && to ? ' – ' : ''}${to}`);
      }
      if (r.rooms) tags.push(`🚪 ${r.rooms} комн.`);
      if (r.district) tags.push(`📍 ${r.district}`);

      const hasMap = !!r.area_polygon;
      const hasMsg = !!r.message_template;

      return `
        <div class="client-card" onclick="openClientModal(${r.id})">
          <div class="client-card-header">
            <div class="client-card-avatar">${r.emoji || '🏠'}</div>
            <div>
              <div class="client-card-name">${r.name}</div>
              <div class="client-card-type">${r.deal_type === 'rent' ? 'Аренда' : 'Покупка'}${hasMap ? ' · 🗺️' : ''}${hasMsg ? ' · 💬' : ''}</div>
            </div>
          </div>
          ${tags.length ? `<div class="client-card-params">${tags.map(t => `<span class="param-tag">${t}</span>`).join('')}</div>` : ''}
          <div class="client-card-actions">
            <span style="font-size:11px;color:var(--text-muted);flex:1;">Нажмите для подробностей</span>
            <button class="btn btn-danger btn-sm"
                    onclick="event.stopPropagation();deleteClient(${r.id})"
                    style="padding:4px 10px;font-size:11px;">
              Удалить
            </button>
          </div>
        </div>`;
    }).join('');
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
    emoji:            document.getElementById('c-emoji').value || '🏠',
  };
  if (!body.name) { showToast('Введите имя клиента', 'error'); return; }
  try {
    await api('POST', '/api/listings/clients', body);
    showToast('Клиент добавлен ✓');
    loadClients();
    loadStats();
    // Сброс формы
    ['c-name','c-district','c-budget-min','c-budget-max','c-area-min','c-area-max','c-message-template'].forEach(id => {
      document.getElementById(id).value = '';
    });
    document.getElementById('c-rooms').value = '';
    _selectedEmoji = '🏠';
    document.getElementById('emoji-preview').textContent = '🏠';
    document.getElementById('c-emoji').value = '🏠';
    document.querySelectorAll('.emoji-option').forEach(o =>
      o.classList.toggle('selected', o.dataset.emoji === '🏠')
    );
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

// ── Модал: детали клиента ─────────────────────────────────────────────────────

let _modalMap = null;

async function openClientModal(clientId) {
  try {
    const clients = await api('GET', '/api/listings/clients');
    const r = clients.find(c => c.id === clientId);
    if (!r) return;

    document.getElementById('modal-avatar').textContent = r.emoji || '🏠';
    document.getElementById('modal-name').textContent = r.name;
    document.getElementById('modal-deal-type').textContent =
      r.deal_type === 'rent' ? 'Аренда' : 'Покупка';

    // Параметры
    const params = [];
    if (r.budget_min) params.push(['Бюджет от', fmtPrice(r.budget_min)]);
    if (r.budget_max) params.push(['Бюджет до', fmtPrice(r.budget_max)]);
    if (r.area_min)   params.push(['Площадь от', r.area_min + ' м²']);
    if (r.area_max)   params.push(['Площадь до', r.area_max + ' м²']);
    if (r.rooms)      params.push(['Комнат', r.rooms]);
    if (r.district)   params.push(['Район', r.district]);

    document.getElementById('modal-params').innerHTML = params.length
      ? params.map(([l, v]) => `
          <div class="modal-param">
            <div class="param-label">${l}</div>
            <div class="param-value">${v}</div>
          </div>`).join('')
      : '<div style="color:var(--text-muted);font-size:13px;grid-column:1/-1;">Параметры не заданы</div>';

    // Шаблон сообщения
    const templateSection = document.getElementById('modal-template-section');
    if (r.message_template) {
      document.getElementById('modal-template').textContent = r.message_template;
      document.getElementById('modal-template').className = 'modal-message-box';
      templateSection.classList.remove('hidden');
    } else {
      templateSection.classList.add('hidden');
    }

    // Карта
    const mapSection = document.getElementById('modal-map-section');
    if (r.area_polygon) {
      mapSection.classList.remove('hidden');
      document.getElementById('client-modal-overlay').classList.remove('hidden');
      // Инициализируем мини-карту после открытия модала
      setTimeout(() => initModalMap(r.area_polygon), 100);
    } else {
      mapSection.classList.add('hidden');
      document.getElementById('client-modal-overlay').classList.remove('hidden');
    }
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function initModalMap(polygonStr) {
  const container = document.getElementById('modal-map');

  // Уничтожаем предыдущую карту
  if (_modalMap) {
    _modalMap.remove();
    _modalMap = null;
  }

  _modalMap = L.map(container, { zoomControl: true, scrollWheelZoom: false })
    .setView([51.1694, 71.4491], 11);

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OSM',
    maxZoom: 19,
  }).addTo(_modalMap);

  const parts = polygonStr.split(',').map(Number);
  if (parts.length >= 4) {
    const points = [];
    for (let i = 0; i < parts.length - 1; i += 2) {
      points.push([parts[i], parts[i + 1]]);
    }
    const poly = L.polygon(points, {
      color: '#4f8ef7',
      fillColor: '#4f8ef7',
      fillOpacity: 0.15,
      weight: 2,
    }).addTo(_modalMap);
    _modalMap.fitBounds(poly.getBounds(), { padding: [16, 16] });
  }
}

document.getElementById('btn-modal-close').addEventListener('click', () => {
  document.getElementById('client-modal-overlay').classList.add('hidden');
});

document.getElementById('client-modal-overlay').addEventListener('click', (e) => {
  if (e.target === document.getElementById('client-modal-overlay')) {
    document.getElementById('client-modal-overlay').classList.add('hidden');
  }
});

// ── Объявления ────────────────────────────────────────────────────────────────

async function loadListings() {
  try {
    const rows = await api('GET', '/api/listings/');
    const grid = document.getElementById('listings-grid');

    grid.querySelectorAll('.listing-row:not(.header)').forEach(el => el.remove());
    const emptyEl = document.getElementById('listings-empty');
    if (emptyEl) emptyEl.remove();

    if (!rows.length) {
      const empty = document.createElement('div');
      empty.id = 'listings-empty';
      empty.className = 'empty-state';
      empty.innerHTML = '<div class="empty-icon">🏡</div>Нет объявлений';
      grid.appendChild(empty);
      return;
    }

    rows.forEach(r => grid.appendChild(renderListingRow(r)));
  } catch (e) {
    showToast(e.message, 'error');
  }
}

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
      const time = new Date(r.sent_at + 'Z').toLocaleString('ru-RU', {
        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit',
      });
      return `<tr>
        <td style="color:var(--text-muted);white-space:nowrap;font-size:12px;">${time}</td>
        <td>${r.client_name || '—'}</td>
        <td><a href="${r.url || '#'}" target="_blank" style="color:var(--accent);text-decoration:none;font-size:13px;">${r.title || r.krisha_id || '—'}</a></td>
        <td style="max-width:280px;color:var(--text-muted);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.text || ''}</td>
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
  btn.textContent = '⏳ Устанавливаем... (1-2 минуты)';
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
  btn.textContent = '⏳ Открываем...';
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
let _polygonPoints = [];
let _polyline = null;
let _polygon = null;

async function initMap() {
  try {
    const clients = await api('GET', '/api/listings/clients');
    const sel = document.getElementById('map-client-select');
    sel.innerHTML = '<option value="">— выберите клиента —</option>' +
      clients.map(c =>
        `<option value="${c.id}" data-polygon="${c.area_polygon || ''}">${c.emoji || '🏠'} ${c.name}</option>`
      ).join('');

    sel.onchange = () => {
      const opt = sel.options[sel.selectedIndex];
      const poly = opt.dataset.polygon;
      if (poly) _loadExistingPolygon(poly);
    };
  } catch (_) {}

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
  document.getElementById('map-polygon-info').textContent = `✓ Область: ${_polygonPoints.length} точек`;
  document.getElementById('btn-save-polygon').disabled = false;
  document.getElementById('btn-save-polygon').dataset.coords = coordStr;
}

function _loadExistingPolygon(coordStr) {
  if (!_map || !coordStr) return;
  const parts = coordStr.split(',').map(Number);
  if (parts.length < 4) return;

  if (_polyline) { _map.removeLayer(_polyline); _polyline = null; }
  if (_polygon)  { _map.removeLayer(_polygon);  _polygon = null; }

  const points = [];
  for (let i = 0; i < parts.length - 1; i += 2) {
    points.push([parts[i], parts[i + 1]]);
  }
  _polygonPoints = points;

  _polygon = L.polygon(points, {
    color: '#4f8ef7',
    fillColor: '#4f8ef7',
    fillOpacity: 0.15,
    weight: 2,
  }).addTo(_map);
  _map.fitBounds(_polygon.getBounds(), { padding: [20, 20] });

  const coordStr2 = points.map(p => `${p[0].toFixed(6)},${p[1].toFixed(6)}`).join(',');
  document.getElementById('btn-save-polygon').disabled = false;
  document.getElementById('btn-save-polygon').dataset.coords = coordStr2;
  document.getElementById('map-polygon-info').textContent =
    `↩ Загружена сохранённая область (${points.length} точек)`;
}

document.getElementById('btn-draw-polygon').addEventListener('click', () => {
  if (!_map) { showToast('Перейдите на вкладку Карта', 'error'); return; }
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
    showToast('Область сохранена ✓');
    const opt = document.querySelector(`#map-client-select option[value="${clientId}"]`);
    if (opt) opt.dataset.polygon = coords;
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Старт ─────────────────────────────────────────────────────────────────────

checkOnboarding();
