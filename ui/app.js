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
    document.getElementById('stat-messages').textContent = s.messages;
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
        <td>${statusBadge(r.status)}</td>
      </tr>
    `).join('');
  } catch (_) {}
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
    name:       document.getElementById('c-name').value.trim(),
    district:   document.getElementById('c-district').value.trim() || null,
    budget_min: parseInt(document.getElementById('c-budget-min').value) || null,
    budget_max: parseInt(document.getElementById('c-budget-max').value) || null,
    area_min:   parseInt(document.getElementById('c-area-min').value)   || null,
    area_max:   parseInt(document.getElementById('c-area-max').value)   || null,
    rooms:      document.getElementById('c-rooms').value     || null,
    deal_type:  document.getElementById('c-deal-type').value,
  };
  if (!body.name) { showToast('Введите имя клиента', 'error'); return; }
  try {
    await api('POST', '/api/listings/clients', body);
    showToast('Клиент добавлен ✓');
    loadClients();
    loadStats();
    ['c-name','c-district','c-budget-min','c-budget-max','c-area-min','c-area-max'].forEach(id => {
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
    const { running } = await api('GET', '/api/agent/status');
    _agentRunning = running;
    const dot  = document.getElementById('agent-dot');
    const text = document.getElementById('agent-status-text');
    const btn  = document.getElementById('btn-toggle-agent');
    dot.classList.toggle('running', running);
    text.textContent = running ? 'Агент работает' : 'Агент остановлен';
    btn.textContent  = running ? 'Остановить агента' : 'Запустить агента';
    btn.style.background = running ? 'var(--danger)' : '';
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

// ── Настройки ─────────────────────────────────────────────────────────────────

document.getElementById('btn-update-token').addEventListener('click', async () => {
  const token = document.getElementById('settings-token').value.trim();
  if (!token) { showToast('Введите токен', 'error'); return; }
  try {
    await api('POST', '/api/auth/gemini-token', { token });
    showToast('Токен обновлён ✓');
    document.getElementById('settings-token').value = '';
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// ── Старт ─────────────────────────────────────────────────────────────────────

checkOnboarding();
