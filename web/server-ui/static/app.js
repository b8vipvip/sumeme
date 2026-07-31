const authView = document.getElementById('authView');
const appView = document.getElementById('appView');
const authError = document.getElementById('authError');
const authTitle = document.getElementById('authTitle');
const authDescription = document.getElementById('authDescription');
const authSubmit = document.getElementById('authSubmit');
const authModeButton = document.getElementById('authModeButton');
const loginForm = document.getElementById('loginForm');
const toast = document.getElementById('toast');
let signupMode = false;
let session = null;

const pageMeta = {
  overview: ['总览', 'LobeHub 后端与 SuMeMe 记忆服务运行状态'],
  chat: ['对话', '保留 LobeHub 会话能力，替换表现层'],
  memories: ['记忆', '搜索与管理长期记忆'],
  files: ['资料与对象', '附件和私有对象存储'],
  vaults: ['Vault', '存储策略与作用域'],
  models: ['模型', '远程模型与供应商'],
  operations: ['运维', '健康状态与部署信息'],
  settings: ['设置', '账户和服务连接信息'],
};

function showToast(message) {
  toast.textContent = message;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

async function jsonFetch(url, options = {}) {
  const response = await fetch(url, { credentials: 'include', ...options });
  const text = await response.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = { message: text }; }
  if (!response.ok) {
    const message = data?.message || data?.error || data?.detail || `请求失败 (${response.status})`;
    throw new Error(typeof message === 'string' ? message : JSON.stringify(message));
  }
  return data;
}

async function readSession() {
  try {
    const value = await jsonFetch('/api/auth/get-session');
    session = value?.session ? value : null;
  } catch {
    session = null;
  }
  renderAuthState();
}

function renderAuthState() {
  const loggedIn = Boolean(session?.session && session?.user);
  authView.hidden = loggedIn;
  appView.hidden = !loggedIn;
  if (!loggedIn) return;
  const email = session.user.email || session.user.name || '已登录用户';
  document.getElementById('accountLabel').textContent = email;
  document.getElementById('settingsEmail').textContent = session.user.email || '—';
  document.getElementById('settingsUserId').textContent = session.user.id || '—';
  navigate(location.hash.slice(1) || 'overview');
  loadHealth();
}

function setAuthMode(signup) {
  signupMode = signup;
  document.querySelectorAll('.signup-only').forEach((node) => { node.hidden = !signup; });
  authTitle.textContent = signup ? '创建 SuMeMe 账户' : '登录 SuMeMe';
  authDescription.textContent = signup
    ? '账户仍创建在 LobeHub 的认证与数据库系统中，SuMeMe 只提供新的前端。'
    : '使用 LobeHub 账户系统登录，账户、会话和附件数据仍由原后端管理。';
  authSubmit.textContent = signup ? '创建并登录' : '登录';
  authModeButton.textContent = signup ? '已有账户？返回登录' : '没有账户？创建账户';
  document.getElementById('passwordInput').autocomplete = signup ? 'new-password' : 'current-password';
  authError.hidden = true;
}

authModeButton.addEventListener('click', () => setAuthMode(!signupMode));
loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  authError.hidden = true;
  authSubmit.disabled = true;
  authSubmit.textContent = signupMode ? '创建中…' : '登录中…';
  const email = document.getElementById('emailInput').value.trim();
  const password = document.getElementById('passwordInput').value;
  const name = document.getElementById('nameInput').value.trim() || email.split('@')[0];
  try {
    await jsonFetch(signupMode ? '/api/auth/sign-up/email' : '/api/auth/sign-in/email', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(signupMode ? { email, password, name } : { email, password }),
    });
    await readSession();
    showToast(signupMode ? '账户创建成功' : '登录成功');
  } catch (error) {
    authError.querySelector('span').textContent = error.message;
    authError.hidden = false;
  } finally {
    authSubmit.disabled = false;
    authSubmit.textContent = signupMode ? '创建并登录' : '登录';
  }
});

document.getElementById('logoutButton').addEventListener('click', async () => {
  try { await jsonFetch('/api/auth/sign-out', { method: 'POST' }); } catch {}
  session = null;
  renderAuthState();
  showToast('已退出登录');
});

function navigate(page) {
  if (!pageMeta[page]) page = 'overview';
  document.querySelectorAll('.page').forEach((node) => node.classList.toggle('active', node.id === `page-${page}`));
  document.querySelectorAll('.nav-item').forEach((node) => node.classList.toggle('active', node.dataset.page === page));
  document.getElementById('pageTitle').textContent = pageMeta[page][0];
  document.getElementById('pageSubtitle').textContent = pageMeta[page][1];
  if (location.hash !== `#${page}`) history.replaceState(null, '', `#${page}`);
  document.body.classList.remove('sidebar-open');
}

document.querySelectorAll('[data-page]').forEach((node) => node.addEventListener('click', (event) => {
  event.preventDefault();
  navigate(node.dataset.page);
}));
document.querySelectorAll('[data-jump]').forEach((node) => node.addEventListener('click', (event) => {
  event.preventDefault();
  navigate(node.dataset.jump);
}));
window.addEventListener('hashchange', () => navigate(location.hash.slice(1) || 'overview'));
document.getElementById('menuButton').addEventListener('click', () => document.body.classList.toggle('sidebar-open'));

async function loadHealth() {
  const gatewayStatus = document.getElementById('gatewayStatus');
  const heroStatus = document.getElementById('heroStatus');
  try {
    const data = await jsonFetch('/sumeme-health');
    document.getElementById('healthJson').textContent = JSON.stringify(data, null, 2);
    gatewayStatus.textContent = data.status === 'ok' ? '正常' : String(data.status || '未知');
    document.getElementById('gatewayDetail').textContent = data.identity_enforcement || 'memory-gateway';
    document.getElementById('vaultMode').textContent = data.default_storage_mode || '—';
    document.getElementById('vaultModeDetail').textContent = data.default_storage_mode || '—';
    document.getElementById('scopeMode').textContent = data.identity_enforcement || '—';
    document.getElementById('providerName').textContent = data.memory_provider || '—';
    document.getElementById('serverLabel').textContent = '服务在线';
    document.getElementById('serverDot').classList.add('good');
    heroStatus.textContent = '系统可用';
    heroStatus.classList.add('good');
  } catch (error) {
    document.getElementById('healthJson').textContent = error.message;
    gatewayStatus.textContent = '连接失败';
    document.getElementById('serverLabel').textContent = '服务异常';
    document.getElementById('serverDot').classList.remove('good');
    heroStatus.textContent = '需要检查';
    heroStatus.classList.remove('good');
  }
}

document.getElementById('refreshButton').addEventListener('click', async () => {
  await Promise.all([readSession(), loadHealth()]);
  showToast('状态已刷新');
});

readSession();
