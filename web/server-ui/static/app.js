const authView = document.getElementById('authView');
const appView = document.getElementById('appView');
const authError = document.getElementById('authError');
const authTitle = document.getElementById('authTitle');
const authDescription = document.getElementById('authDescription');
const authSubmit = document.getElementById('authSubmit');
const authModeButton = document.getElementById('authModeButton');
const loginForm = document.getElementById('loginForm');
const toast = document.getElementById('toast');
const topicList = document.getElementById('topicList');
const topicSearchInput = document.getElementById('topicSearchInput');
const topicCountLabel = document.getElementById('topicCountLabel');
const messageList = document.getElementById('messageList');
const messageHeader = document.getElementById('messageHeader');
const activeTopicTitle = document.getElementById('activeTopicTitle');
const activeTopicMeta = document.getElementById('activeTopicMeta');
const messageCountLabel = document.getElementById('messageCountLabel');
const chatConnectionLabel = document.getElementById('chatConnectionLabel');

let signupMode = false;
let session = null;
let topics = [];
let topicsLoaded = false;
let activeTopicId = null;
let topicLoadVersion = 0;
let transcriptLoadVersion = 0;

const pageMeta = {
  overview: ['总览', 'LobeHub 后端与 SuMeMe 记忆服务运行状态'],
  chat: ['对话', '浏览 LobeHub 中现有的会话主题和消息记录'],
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

function unwrapTrpcEnvelope(payload) {
  const envelope = Array.isArray(payload) ? payload[0] : payload;
  const trpcError = envelope?.error?.json || envelope?.error;
  if (trpcError) {
    const message = trpcError.message || trpcError.data?.message || 'LobeHub tRPC 请求失败';
    const error = new Error(message);
    error.trpcCode = trpcError.data?.code || trpcError.code;
    throw error;
  }

  const data = envelope?.result?.data;
  if (data && Object.prototype.hasOwnProperty.call(data, 'json')) return data.json;
  if (data !== undefined) return data;
  if (envelope && Object.prototype.hasOwnProperty.call(envelope, 'json')) return envelope.json;
  return envelope;
}

async function fetchTrpcUrl(url) {
  const response = await fetch(url, {
    credentials: 'include',
    headers: { Accept: 'application/json' },
  });
  const text = await response.text();
  let payload;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    const error = new Error(response.headers.get('content-type')?.includes('text/html')
      ? 'LobeHub 接口返回了网页而不是 JSON，请检查 /trpc 代理'
      : `无法解析 LobeHub 接口响应 (${response.status})`);
    error.status = response.status;
    throw error;
  }

  if (!response.ok) {
    let message = `LobeHub 接口请求失败 (${response.status})`;
    try {
      unwrapTrpcEnvelope(payload);
    } catch (error) {
      message = error.message || message;
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return unwrapTrpcEnvelope(payload);
}

async function trpcQuery(procedure, input = {}) {
  const singleInput = encodeURIComponent(JSON.stringify({ json: input }));
  const singleUrl = `/trpc/${procedure}?input=${singleInput}`;

  try {
    return await fetchTrpcUrl(singleUrl);
  } catch (singleError) {
    if (![400, 404, 405].includes(singleError.status)) throw singleError;

    const batchInput = encodeURIComponent(JSON.stringify({ 0: { json: input } }));
    const batchUrl = `/trpc/${procedure}?batch=1&input=${batchInput}`;
    return fetchTrpcUrl(batchUrl);
  }
}

function formatDate(value) {
  if (!value) return '时间未知';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function contentToText(content) {
  if (typeof content === 'string') return content;
  if (content == null) return '';
  if (Array.isArray(content)) {
    return content
      .map((item) => {
        if (typeof item === 'string') return item;
        if (typeof item?.text === 'string') return item.text;
        if (typeof item?.content === 'string') return item.content;
        return '';
      })
      .filter(Boolean)
      .join('\n');
  }
  if (typeof content.text === 'string') return content.text;
  if (typeof content.content === 'string') return content.content;
  try { return JSON.stringify(content, null, 2); } catch { return String(content); }
}

function topicCollection(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.topics)) return value.topics;
  if (Array.isArray(value?.data)) return value.data;
  return [];
}

function transcriptCollection(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.messages)) return value.messages;
  if (Array.isArray(value?.data)) return value.data;
  return [];
}

function topicPreview(topic) {
  const lastMessage = topic.lastMessage || topic.latestMessage || topic.message;
  const content = contentToText(lastMessage?.content ?? lastMessage ?? topic.lastMessageContent);
  return content.trim().replace(/\s+/g, ' ').slice(0, 90) || '暂无消息预览';
}

function topicTitle(topic) {
  return String(topic.title || topic.name || '未命名会话').trim() || '未命名会话';
}

function topicUpdatedAt(topic) {
  return topic.updatedAt || topic.lastMessage?.createdAt || topic.createdAt;
}

function renderConversationState({ icon = '', title = '', message = '', loading = false } = {}) {
  topicList.replaceChildren();
  const state = document.createElement('div');
  state.className = 'conversation-state';
  if (loading) {
    const spinner = document.createElement('span');
    spinner.className = 'loading-spinner';
    state.appendChild(spinner);
  } else if (icon) {
    const iconNode = document.createElement('span');
    iconNode.className = 'state-icon';
    iconNode.textContent = icon;
    state.appendChild(iconNode);
  }
  if (title) {
    const heading = document.createElement('h3');
    heading.textContent = title;
    state.appendChild(heading);
  }
  const paragraph = document.createElement('p');
  paragraph.textContent = message;
  state.appendChild(paragraph);
  topicList.appendChild(state);
}

function renderMessageState({ icon = '', title = '', message = '', loading = false } = {}) {
  messageList.replaceChildren();
  const state = document.createElement('div');
  state.className = 'conversation-state message-placeholder';
  if (loading) {
    const spinner = document.createElement('span');
    spinner.className = 'loading-spinner';
    state.appendChild(spinner);
  } else if (icon) {
    const iconNode = document.createElement('span');
    iconNode.textContent = icon;
    state.appendChild(iconNode);
  }
  if (title) {
    const heading = document.createElement('h3');
    heading.textContent = title;
    state.appendChild(heading);
  }
  const paragraph = document.createElement('p');
  paragraph.textContent = message;
  state.appendChild(paragraph);
  messageList.appendChild(state);
}

function filteredTopics() {
  const keyword = topicSearchInput.value.trim().toLocaleLowerCase('zh-CN');
  if (!keyword) return topics;
  return topics.filter((topic) => `${topicTitle(topic)} ${topicPreview(topic)}`.toLocaleLowerCase('zh-CN').includes(keyword));
}

function renderTopics() {
  const visibleTopics = filteredTopics();
  topicCountLabel.textContent = topicSearchInput.value.trim()
    ? `${visibleTopics.length} / ${topics.length} 条会话`
    : `${topics.length} 条会话`;

  if (!topics.length) {
    renderConversationState({ icon: '○', title: '还没有会话', message: '当前 LobeHub 账户中没有可显示的会话主题。' });
    return;
  }
  if (!visibleTopics.length) {
    renderConversationState({ icon: '⌕', title: '没有匹配结果', message: '换一个关键词搜索会话标题或最近内容。' });
    return;
  }

  topicList.replaceChildren();
  visibleTopics.forEach((topic) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'conversation-item';
    item.classList.toggle('active', topic.id === activeTopicId);
    item.dataset.topicId = topic.id;
    item.setAttribute('role', 'listitem');

    const top = document.createElement('span');
    top.className = 'conversation-item-top';
    const title = document.createElement('strong');
    title.textContent = topicTitle(topic);
    const time = document.createElement('time');
    time.textContent = formatDate(topicUpdatedAt(topic));
    top.append(title, time);

    const preview = document.createElement('span');
    preview.className = 'conversation-preview';
    preview.textContent = topicPreview(topic);

    const meta = document.createElement('span');
    meta.className = 'conversation-item-meta';
    if (topic.favorite) {
      const favorite = document.createElement('span');
      favorite.textContent = '★ 收藏';
      meta.appendChild(favorite);
    }
    const identifier = document.createElement('span');
    identifier.textContent = String(topic.id || '').slice(0, 8);
    meta.appendChild(identifier);

    item.append(top, preview, meta);
    item.addEventListener('click', () => selectTopic(topic));
    topicList.appendChild(item);
  });
}

function attachmentList(message) {
  const candidates = [message.files, message.fileList, message.attachments, message.images];
  return candidates.find(Array.isArray) || [];
}

function rolePresentation(role) {
  if (role === 'user') return { label: '你', className: 'user' };
  if (role === 'assistant') return { label: 'AI', className: 'assistant' };
  if (role === 'system') return { label: '系统', className: 'system' };
  if (role === 'tool' || role === 'function') return { label: '工具', className: 'tool' };
  return { label: role || '消息', className: 'other' };
}

function renderMessages(messages) {
  messageCountLabel.textContent = `${messages.length} 条消息`;
  if (!messages.length) {
    renderMessageState({ icon: '○', title: '没有消息', message: '该会话主题存在，但还没有可显示的消息记录。' });
    return;
  }

  messageList.replaceChildren();
  messages.forEach((message) => {
    const role = rolePresentation(message.role);
    const article = document.createElement('article');
    article.className = `message-row ${role.className}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role.label.slice(0, 2);

    const body = document.createElement('div');
    body.className = 'message-body';
    const header = document.createElement('div');
    header.className = 'message-meta';
    const author = document.createElement('strong');
    author.textContent = role.label;
    const time = document.createElement('time');
    time.textContent = formatDate(message.createdAt || message.updatedAt);
    header.append(author, time);

    const content = document.createElement('div');
    content.className = 'message-content';
    content.textContent = contentToText(message.content).trim() || '[无文本内容]';
    body.append(header, content);

    const files = attachmentList(message);
    if (files.length) {
      const fileRow = document.createElement('div');
      fileRow.className = 'message-files';
      files.forEach((file) => {
        const chip = document.createElement(file?.url ? 'a' : 'span');
        chip.className = 'message-file-chip';
        chip.textContent = `▣ ${file?.name || file?.fileName || file?.id || '附件'}`;
        if (file?.url) {
          chip.href = file.url;
          chip.target = '_blank';
          chip.rel = 'noopener noreferrer';
        }
        fileRow.appendChild(chip);
      });
      body.appendChild(fileRow);
    }

    article.append(avatar, body);
    messageList.appendChild(article);
  });
  messageList.scrollTop = 0;
}

async function selectTopic(topic) {
  if (!topic?.id) return;
  activeTopicId = topic.id;
  renderTopics();
  messageHeader.hidden = false;
  activeTopicTitle.textContent = topicTitle(topic);
  activeTopicMeta.textContent = `${formatDate(topicUpdatedAt(topic))} · ${String(topic.id).slice(0, 12)}`;
  messageCountLabel.textContent = '读取中…';
  renderMessageState({ loading: true, message: '正在读取 LobeHub 消息记录…' });

  const loadVersion = ++transcriptLoadVersion;
  try {
    const transcript = await trpcQuery('topic.getTopicTranscript', {
      includeMessages: true,
      limit: 200,
      offset: 0,
      topicId: topic.id,
    });
    if (loadVersion !== transcriptLoadVersion) return;
    renderMessages(transcriptCollection(transcript));
    chatConnectionLabel.textContent = 'LobeHub 消息已连接';
  } catch (error) {
    if (loadVersion !== transcriptLoadVersion) return;
    messageCountLabel.textContent = '读取失败';
    renderMessageState({ icon: '!', title: '无法读取消息', message: error.message });
    chatConnectionLabel.textContent = '消息接口异常';
  }
}

async function loadTopics({ force = false } = {}) {
  if (!session?.user) return;
  if (topicsLoaded && !force) return;

  const loadVersion = ++topicLoadVersion;
  topicsLoaded = false;
  topicCountLabel.textContent = '正在读取…';
  chatConnectionLabel.textContent = '正在连接 LobeHub';
  renderConversationState({ loading: true, message: '正在读取 LobeHub 会话…' });

  try {
    const payload = await trpcQuery('topic.queryTopics', {
      pageSize: 200,
      withLastMessage: true,
    });
    if (loadVersion !== topicLoadVersion) return;

    topics = topicCollection(payload)
      .filter((topic) => topic && topic.id)
      .sort((left, right) => new Date(topicUpdatedAt(right) || 0) - new Date(topicUpdatedAt(left) || 0));
    topicsLoaded = true;
    document.getElementById('lobeStatus').textContent = '已连接';
    chatConnectionLabel.textContent = 'LobeHub 会话已连接';
    renderTopics();

    const previous = topics.find((topic) => topic.id === activeTopicId);
    if (previous) {
      await selectTopic(previous);
    } else if (topics[0]) {
      await selectTopic(topics[0]);
    } else {
      activeTopicId = null;
      messageHeader.hidden = true;
      renderMessageState({ icon: '💬', title: '还没有会话', message: '创建会话与发送消息将在下一阶段接入。' });
    }
  } catch (error) {
    if (loadVersion !== topicLoadVersion) return;
    topics = [];
    topicsLoaded = false;
    document.getElementById('lobeStatus').textContent = '接口异常';
    chatConnectionLabel.textContent = 'LobeHub 会话接口异常';
    topicCountLabel.textContent = '读取失败';
    renderConversationState({ icon: '!', title: '无法读取会话', message: error.message });
  }
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
  if (!loggedIn) {
    topics = [];
    topicsLoaded = false;
    activeTopicId = null;
    return;
  }
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
  topics = [];
  topicsLoaded = false;
  activeTopicId = null;
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
  if (page === 'chat') loadTopics();
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

topicSearchInput.addEventListener('input', renderTopics);
document.getElementById('reloadTopicsButton').addEventListener('click', async () => {
  await loadTopics({ force: true });
  if (topicsLoaded) showToast('LobeHub 会话已刷新');
});

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
  await readSession();
  await loadHealth();
  if (location.hash === '#chat') await loadTopics({ force: true });
  showToast('状态已刷新');
});

readSession();
