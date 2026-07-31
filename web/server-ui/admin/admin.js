(() => {
  'use strict';

  const authView = document.getElementById('adminAuth');
  const appView = document.getElementById('adminApp');
  const authForm = document.getElementById('adminAuthForm');
  const authTitle = document.getElementById('authTitle');
  const authDescription = document.getElementById('authDescription');
  const authError = document.getElementById('authError');
  const authSubmit = document.getElementById('authSubmit');
  const toast = document.getElementById('adminToast');
  let bootstrapMode = false;
  let settings = {};
  let toastTimer = null;

  async function jsonFetch(url, options = {}) {
    const response = await fetch(url, {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
    const text = await response.text();
    let payload = null;
    try { payload = text ? JSON.parse(text) : null; } catch { payload = null; }
    if (!response.ok) {
      const detail = payload?.detail || payload?.error?.message || text || `请求失败 (${response.status})`;
      const error = new Error(String(detail));
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }

  function setAuthMode(initialized) {
    bootstrapMode = !initialized;
    authTitle.textContent = bootstrapMode ? '创建初始管理员' : '管理后台登录';
    authDescription.textContent = bootstrapMode
      ? '首次启用需要创建独立管理员账户。此账户不等同于普通 LobeHub 用户。'
      : '登录独立服务端控制面。普通用户账户不能进入这里。';
    authSubmit.textContent = bootstrapMode ? '创建管理员并登录' : '登录';
    document.getElementById('displayNameField').hidden = !bootstrapMode;
    document.getElementById('confirmPasswordField').hidden = !bootstrapMode;
    document.getElementById('adminPassword').autocomplete = bootstrapMode ? 'new-password' : 'current-password';
    document.getElementById('authNote').textContent = bootstrapMode
      ? '密码至少 12 位。系统不会生成或公开默认管理员密码。'
      : '管理员会话使用 Secure、HttpOnly、SameSite=Strict Cookie。';
  }

  function showAuth() {
    authView.hidden = false;
    appView.hidden = true;
  }

  function showApp(admin) {
    authView.hidden = true;
    appView.hidden = false;
    document.getElementById('adminIdentity').textContent = admin?.email || '管理员';
  }

  async function initialize() {
    try {
      const status = await jsonFetch('/api/admin/bootstrap/status');
      setAuthMode(Boolean(status.initialized));
      if (status.initialized) {
        try {
          const session = await jsonFetch('/api/admin/session');
          showApp(session.admin);
          await loadAll();
          return;
        } catch {}
      }
      showAuth();
    } catch (error) {
      setAuthMode(true);
      authError.textContent = error.message;
      authError.hidden = false;
      showAuth();
    }
  }

  authForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    authError.hidden = true;
    authSubmit.disabled = true;
    const email = document.getElementById('adminEmail').value.trim();
    const password = document.getElementById('adminPassword').value;
    try {
      let payload;
      if (bootstrapMode) {
        const confirm = document.getElementById('adminPasswordConfirm').value;
        if (password !== confirm) throw new Error('两次输入的密码不一致');
        payload = await jsonFetch('/api/admin/bootstrap', {
          method: 'POST',
          body: JSON.stringify({
            email,
            password,
            display_name: document.getElementById('adminDisplayName').value.trim(),
          }),
        });
      } else {
        payload = await jsonFetch('/api/admin/login', {
          method: 'POST',
          body: JSON.stringify({ email, password }),
        });
      }
      showApp(payload.admin);
      authForm.reset();
      await loadAll();
      showToast(bootstrapMode ? '初始管理员已创建' : '登录成功');
    } catch (error) {
      authError.textContent = error.message;
      authError.hidden = false;
    } finally {
      authSubmit.disabled = false;
    }
  });

  document.getElementById('adminLogout').addEventListener('click', async () => {
    try { await jsonFetch('/api/admin/logout', { method: 'POST' }); } catch {}
    try {
      const status = await jsonFetch('/api/admin/bootstrap/status');
      setAuthMode(Boolean(status.initialized));
    } catch {}
    showAuth();
  });

  const pageMeta = {
    overview: ['系统总览', '服务端控制面与运行状态'],
    api: ['API 与模型', 'OpenAI 兼容接口与默认模型'],
    users: ['用户管理', 'LobeHub 用户、角色与封禁状态'],
    storage: ['云存储', 'RustFS / S3 与 Bucket 配置'],
    modules: ['模块与模式', '记忆、对象、身份和存储策略'],
    releases: ['客户端版本', 'Android 与 Windows 更新信息'],
    audit: ['审计记录', '管理员操作与配置变更'],
  };

  function navigate(page) {
    if (!pageMeta[page]) page = 'overview';
    document.querySelectorAll('[data-page-view]').forEach((node) => {
      node.classList.toggle('active', node.dataset.pageView === page);
    });
    document.querySelectorAll('.nav-item').forEach((node) => {
      node.classList.toggle('active', node.dataset.page === page);
    });
    document.getElementById('pageTitle').textContent = pageMeta[page][0];
    document.getElementById('pageSubtitle').textContent = pageMeta[page][1];
    history.replaceState(null, '', `/admin/#${page}`);
    if (page === 'users') loadUsers();
    if (page === 'audit') loadAudit();
    if (page === 'releases') loadReleases();
  }

  document.querySelectorAll('.nav-item').forEach((node) => {
    node.addEventListener('click', () => navigate(node.dataset.page));
  });

  function fieldByName(form, name) {
    return form.querySelector(`[name="${CSS.escape(name)}"]`);
  }

  function populateForm(form, keys) {
    keys.forEach((key) => {
      const input = fieldByName(form, key);
      if (!input) return;
      const value = settings[key];
      if (input.type === 'checkbox') input.checked = Boolean(value);
      else if (value && typeof value === 'object' && Object.hasOwn(value, 'configured')) input.value = '';
      else input.value = value ?? '';
    });
  }

  function collectForm(form) {
    const values = {};
    new FormData(form).forEach((value, key) => { values[key] = String(value); });
    form.querySelectorAll('input[type="checkbox"][name]').forEach((input) => {
      values[input.name] = input.checked;
    });
    form.querySelectorAll('input[type="password"][name]').forEach((input) => {
      if (!input.value.trim()) delete values[input.name];
    });
    return values;
  }

  async function loadSettings() {
    const payload = await jsonFetch('/api/admin/settings');
    settings = payload.values || {};
    populateForm(document.getElementById('apiForm'), [
      'api.relay_base_url', 'api.relay_api_key', 'api.chat_model',
      'api.memory_model', 'api.embedding_model', 'api.model_list',
    ]);
    populateForm(document.getElementById('storageForm'), [
      'storage.endpoint', 'storage.bucket', 'storage.private_bucket',
      'storage.region', 'storage.path_style', 'storage.access_key', 'storage.secret_key',
    ]);
    populateForm(document.getElementById('modulesForm'), [
      'modules.mempalace_enabled', 'modules.letta_enabled',
      'modules.object_api_enabled', 'modules.searxng_enabled',
      'modules.public_registration_enabled', 'modes.memory_provider',
      'modes.default_storage_mode', 'modes.identity_mode', 'modes.release_channel',
    ]);
    const secretState = (key) => settings[key]?.configured ? '已配置，留空表示保持不变' : '未配置';
    document.getElementById('apiKeyState').textContent = secretState('api.relay_api_key');
    document.getElementById('storageAccessState').textContent = secretState('storage.access_key');
    document.getElementById('storageSecretState').textContent = secretState('storage.secret_key');
    document.getElementById('metricChannel').textContent = settings['modes.release_channel'] || 'stable';
  }

  async function saveSettings(form, label) {
    const response = await jsonFetch('/api/admin/settings', {
      method: 'PUT',
      body: JSON.stringify({ values: collectForm(form) }),
    });
    await loadSettings();
    showToast(`${label}已保存${response.restart_required ? '；部分配置需重新部署' : ''}`);
  }

  ['apiForm', 'storageForm', 'modulesForm'].forEach((id) => {
    document.getElementById(id).addEventListener('submit', async (event) => {
      event.preventDefault();
      const button = event.currentTarget.querySelector('button[type="submit"]');
      button.disabled = true;
      try { await saveSettings(event.currentTarget, '配置'); }
      catch (error) { showToast(`保存失败：${error.message}`); }
      finally { button.disabled = false; }
    });
  });

  async function loadSystem() {
    const payload = await jsonFetch('/api/admin/system');
    const components = payload.components || {};
    document.getElementById('systemStatus').textContent = payload.status === 'ok' ? '系统可用' : '需要检查';
    document.getElementById('systemStatus').classList.toggle('good', payload.status === 'ok');
    document.getElementById('metricMemory').textContent = components.memory_provider || '—';
    document.getElementById('metricDatabase').textContent = components.lobe_database_configured ? '已连接' : '未配置';
    document.getElementById('metricObjects').textContent = components.objects_enabled ? '已启用' : '未启用';
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN');
  }

  async function updateUser(user, change) {
    const response = await jsonFetch(`/api/admin/users/${encodeURIComponent(user.id)}`, {
      method: 'PATCH',
      body: JSON.stringify(change),
    });
    showToast(`用户 ${response.user.email || response.user.id} 已更新`);
    await loadUsers();
  }

  async function loadUsers() {
    const table = document.getElementById('userTable');
    table.innerHTML = '<tr><td colspan="6">正在读取…</td></tr>';
    try {
      const query = encodeURIComponent(document.getElementById('userSearch').value.trim());
      const payload = await jsonFetch(`/api/admin/users?search=${query}`);
      if (!payload.available) {
        table.innerHTML = '<tr><td colspan="6">LobeHub 用户数据库尚未连接。</td></tr>';
        return;
      }
      table.replaceChildren();
      (payload.users || []).forEach((user) => {
        const row = document.createElement('tr');
        const identity = document.createElement('td');
        identity.className = 'user-main';
        const primary = document.createElement('b');
        primary.textContent = user.email || user.username || user.id;
        const secondary = document.createElement('small');
        secondary.textContent = user.full_name || user.id;
        identity.append(primary, secondary);
        const role = document.createElement('td'); role.textContent = user.role || 'user';
        const status = document.createElement('td');
        const badge = document.createElement('span');
        badge.className = `badge ${user.banned ? 'bad' : 'good'}`;
        badge.textContent = user.banned ? '已封禁' : '正常'; status.appendChild(badge);
        const sessions = document.createElement('td'); sessions.textContent = String(user.active_sessions ?? 0);
        const active = document.createElement('td'); active.textContent = formatDate(user.last_active_at);
        const actions = document.createElement('td'); actions.className = 'table-actions';
        const roleButton = document.createElement('button');
        roleButton.textContent = user.role === 'admin' ? '设为用户' : '设为管理员';
        roleButton.addEventListener('click', () => updateUser(user, { role: user.role === 'admin' ? 'user' : 'admin' }));
        const banButton = document.createElement('button');
        banButton.textContent = user.banned ? '解除封禁' : '封禁';
        banButton.addEventListener('click', async () => {
          if (!user.banned && !confirm(`确认封禁 ${user.email || user.id} 并注销其活动会话？`)) return;
          await updateUser(user, { banned: !user.banned, ban_reason: user.banned ? '' : '管理员操作' });
        });
        actions.append(roleButton, banButton);
        row.append(identity, role, status, sessions, active, actions);
        table.appendChild(row);
      });
      if (!table.children.length) table.innerHTML = '<tr><td colspan="6">没有匹配的用户。</td></tr>';
    } catch (error) {
      table.innerHTML = `<tr><td colspan="6">读取失败：${String(error.message).replaceAll('<', '&lt;')}</td></tr>`;
    }
  }

  document.getElementById('reloadUsers').addEventListener('click', loadUsers);
  document.getElementById('userSearch').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); loadUsers(); }
  });

  async function loadReleases() {
    const payload = await jsonFetch('/api/admin/releases');
    document.querySelectorAll('.release-form').forEach((form) => {
      const platform = form.dataset.platform;
      const channel = form.elements.channel.value;
      const release = (payload.releases || []).find((item) => item.platform === platform && item.channel === channel);
      ['latest_version', 'minimum_version', 'download_url', 'notes'].forEach((key) => {
        form.elements[key].value = release?.[key] || '';
      });
    });
  }

  document.querySelectorAll('.release-form').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const payload = Object.fromEntries(new FormData(form).entries());
      try {
        await jsonFetch('/api/admin/releases', { method: 'PUT', body: JSON.stringify(payload) });
        showToast(`${payload.platform} 版本信息已保存`);
      } catch (error) { showToast(`保存失败：${error.message}`); }
    });
    form.elements.channel.addEventListener('change', loadReleases);
  });

  async function loadAudit() {
    const table = document.getElementById('auditTable');
    try {
      const payload = await jsonFetch('/api/admin/audit');
      table.replaceChildren();
      (payload.events || []).forEach((event) => {
        const row = document.createElement('tr');
        [formatDate(event.created_at), event.admin_email || 'system', event.action, event.target, JSON.stringify(event.detail || {})].forEach((value) => {
          const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell);
        });
        table.appendChild(row);
      });
      if (!table.children.length) table.innerHTML = '<tr><td colspan="5">暂无审计记录。</td></tr>';
    } catch (error) { table.innerHTML = `<tr><td colspan="5">读取失败：${error.message}</td></tr>`; }
  }

  async function loadAll() {
    try { await Promise.all([loadSystem(), loadSettings(), loadReleases()]); }
    catch (error) {
      if (error.status === 401) { showAuth(); return; }
      showToast(`刷新失败：${error.message}`);
    }
  }

  document.getElementById('refreshAdmin').addEventListener('click', loadAll);
  initialize();
})();
