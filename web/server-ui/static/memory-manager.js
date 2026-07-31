(() => {
  const page = document.getElementById('page-memories');
  if (!page) return;

  const API_BASE = '/api/gateway/api/ui/memory';
  const PAGE_SIZE = 40;
  const state = {
    busy: false,
    hasMore: false,
    items: [],
    loaded: false,
    offset: 0,
    query: '',
    role: '',
    stats: null,
  };

  async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
      ...options,
    });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = { detail: text }; }
    if (!response.ok) {
      const detail = data?.detail || data?.message || `请求失败 (${response.status})`;
      const error = new Error(humanError(detail));
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function humanError(value) {
    const code = typeof value === 'string' ? value : JSON.stringify(value);
    const messages = {
      cross_origin_request_rejected: '请求来源校验失败，请刷新页面后重试',
      lobehub_auth_invalid_response: 'LobeHub 登录服务返回了无效响应',
      lobehub_auth_unavailable: '暂时无法验证 LobeHub 登录状态',
      lobehub_session_required: '登录状态已失效，请重新登录',
      memory_not_found: '这条记忆不存在或不属于当前账户',
      memory_text_required: '请输入要保存的记忆内容',
      query_required: '请输入搜索内容',
      vault_local_only: '当前 Vault 为仅本地模式，服务端不能搜索或写入云端记忆',
      vault_sanitized_cloud_write_required: '混合模式要求先确认内容已经清理敏感信息',
    };
    return messages[code] || code;
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const normalized = value / (1024 ** index);
    return `${normalized >= 10 || index === 0 ? normalized.toFixed(0) : normalized.toFixed(1)} ${units[index]}`;
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  }

  function roleLabel(role) {
    if (role === 'user') return '用户原文';
    if (role === 'assistant') return 'AI 回复';
    return role || '记忆';
  }

  page.replaceChildren();

  const heading = document.createElement('div');
  heading.className = 'page-heading memory-page-heading';
  const headingCopy = document.createElement('div');
  const eyebrow = document.createElement('span');
  eyebrow.className = 'eyebrow';
  eyebrow.textContent = 'LONG-TERM MEMORY';
  const headingTitle = document.createElement('h2');
  headingTitle.textContent = '记忆';
  const headingDescription = document.createElement('p');
  headingDescription.textContent = '浏览 MemPalace 原文片段、执行语义召回，并在当前 LobeHub 账户作用域内显式管理长期记忆。';
  headingCopy.append(eyebrow, headingTitle, headingDescription);
  const headingActions = document.createElement('div');
  headingActions.className = 'memory-heading-actions';
  const scopeBadge = document.createElement('span');
  scopeBadge.className = 'memory-scope-badge';
  scopeBadge.textContent = '正在确认账户作用域';
  const reloadButton = document.createElement('button');
  reloadButton.className = 'button secondary';
  reloadButton.type = 'button';
  reloadButton.textContent = '重新读取';
  headingActions.append(scopeBadge, reloadButton);
  heading.append(headingCopy, headingActions);

  const statsGrid = document.createElement('div');
  statsGrid.className = 'memory-stats-grid';
  const statDefinitions = [
    ['记忆片段', 'memoryStatTotal'],
    ['会话来源', 'memoryStatConversations'],
    ['原文容量', 'memoryStatBytes'],
    ['最近写入', 'memoryStatLatest'],
  ];
  const statNodes = {};
  statDefinitions.forEach(([label, key]) => {
    const card = document.createElement('article');
    card.className = 'memory-stat-card';
    const caption = document.createElement('span');
    caption.textContent = label;
    const value = document.createElement('strong');
    value.textContent = '—';
    card.append(caption, value);
    statsGrid.appendChild(card);
    statNodes[key] = value;
  });

  const tabs = document.createElement('div');
  tabs.className = 'memory-tabs';
  const browseTab = document.createElement('button');
  browseTab.type = 'button';
  browseTab.className = 'active';
  browseTab.textContent = '浏览记忆';
  const searchTab = document.createElement('button');
  searchTab.type = 'button';
  searchTab.textContent = '语义搜索';
  const rememberTab = document.createElement('button');
  rememberTab.type = 'button';
  rememberTab.textContent = '手动写入';
  tabs.append(browseTab, searchTab, rememberTab);

  const panel = document.createElement('div');
  panel.className = 'panel memory-manager-panel';

  const browseView = document.createElement('section');
  browseView.className = 'memory-view active';
  const browseToolbar = document.createElement('div');
  browseToolbar.className = 'memory-toolbar';
  const filterLabel = document.createElement('label');
  filterLabel.className = 'memory-filter';
  const filterIcon = document.createElement('span');
  filterIcon.textContent = '⌕';
  const filterInput = document.createElement('input');
  filterInput.type = 'search';
  filterInput.placeholder = '搜索原文内容或来源';
  filterInput.autocomplete = 'off';
  filterLabel.append(filterIcon, filterInput);
  const roleSelect = document.createElement('select');
  roleSelect.setAttribute('aria-label', '按记忆角色筛选');
  [
    ['', '全部角色'],
    ['user', '用户原文'],
    ['assistant', 'AI 回复'],
  ].forEach(([value, label]) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = label;
    roleSelect.appendChild(option);
  });
  browseToolbar.append(filterLabel, roleSelect);
  const memoryList = document.createElement('div');
  memoryList.className = 'memory-list';
  memoryList.setAttribute('aria-live', 'polite');
  const pagination = document.createElement('div');
  pagination.className = 'memory-pagination';
  const previousButton = document.createElement('button');
  previousButton.className = 'button secondary';
  previousButton.type = 'button';
  previousButton.textContent = '上一页';
  const pageLabel = document.createElement('span');
  pageLabel.textContent = '—';
  const nextButton = document.createElement('button');
  nextButton.className = 'button secondary';
  nextButton.type = 'button';
  nextButton.textContent = '下一页';
  pagination.append(previousButton, pageLabel, nextButton);
  browseView.append(browseToolbar, memoryList, pagination);

  const searchView = document.createElement('section');
  searchView.className = 'memory-view';
  const searchForm = document.createElement('form');
  searchForm.className = 'memory-search-form';
  const semanticInput = document.createElement('textarea');
  semanticInput.rows = 3;
  semanticInput.maxLength = 12000;
  semanticInput.placeholder = '输入自然语言问题，例如：我之前对个人记忆系统有哪些要求？';
  const semanticButton = document.createElement('button');
  semanticButton.className = 'button primary';
  semanticButton.type = 'submit';
  semanticButton.textContent = '搜索长期记忆';
  searchForm.append(semanticInput, semanticButton);
  const searchStatus = document.createElement('p');
  searchStatus.className = 'memory-inline-status';
  searchStatus.textContent = '搜索会同时调用 MemPalace 原文向量召回和当前 Provider 的组合记忆上下文。';
  const semanticResults = document.createElement('div');
  semanticResults.className = 'memory-semantic-results';
  searchView.append(searchForm, searchStatus, semanticResults);

  const rememberView = document.createElement('section');
  rememberView.className = 'memory-view';
  const rememberForm = document.createElement('form');
  rememberForm.className = 'memory-remember-form';
  const rememberTextLabel = document.createElement('label');
  const rememberTextCaption = document.createElement('span');
  rememberTextCaption.textContent = '要保存的记忆内容';
  const rememberText = document.createElement('textarea');
  rememberText.rows = 7;
  rememberText.maxLength = 100000;
  rememberText.required = true;
  rememberText.placeholder = '例如：我开发项目时偏好先完成可验证的最小功能，再逐步上线。';
  rememberTextLabel.append(rememberTextCaption, rememberText);
  const rememberMeta = document.createElement('div');
  rememberMeta.className = 'memory-remember-meta';
  const conversationLabel = document.createElement('label');
  const conversationCaption = document.createElement('span');
  conversationCaption.textContent = '来源标识（可选）';
  const conversationInput = document.createElement('input');
  conversationInput.maxLength = 512;
  conversationInput.placeholder = 'manual-note 或项目名称';
  conversationLabel.append(conversationCaption, conversationInput);
  const assistantLabel = document.createElement('label');
  const assistantCaption = document.createElement('span');
  assistantCaption.textContent = '配套 AI 内容（可选）';
  const assistantInput = document.createElement('input');
  assistantInput.maxLength = 100000;
  assistantInput.placeholder = '需要一并保存的回复或结论';
  assistantLabel.append(assistantCaption, assistantInput);
  rememberMeta.append(conversationLabel, assistantLabel);
  const sanitizeLabel = document.createElement('label');
  sanitizeLabel.className = 'memory-sanitize-check';
  const sanitizeInput = document.createElement('input');
  sanitizeInput.type = 'checkbox';
  const sanitizeText = document.createElement('span');
  sanitizeText.textContent = '我确认内容已按当前 Vault 策略清理敏感信息（混合模式写入时必需）';
  sanitizeLabel.append(sanitizeInput, sanitizeText);
  const rememberActions = document.createElement('div');
  rememberActions.className = 'memory-remember-actions';
  const rememberStatus = document.createElement('span');
  rememberStatus.textContent = '内容会写入当前账户的 default Vault。';
  const rememberButton = document.createElement('button');
  rememberButton.className = 'button primary';
  rememberButton.type = 'submit';
  rememberButton.textContent = '保存到长期记忆';
  rememberActions.append(rememberStatus, rememberButton);
  rememberForm.append(rememberTextLabel, rememberMeta, sanitizeLabel, rememberActions);
  rememberView.appendChild(rememberForm);

  const detailDialog = document.createElement('dialog');
  detailDialog.className = 'memory-detail-dialog';
  const detailClose = document.createElement('button');
  detailClose.className = 'memory-dialog-close';
  detailClose.type = 'button';
  detailClose.textContent = '×';
  detailClose.setAttribute('aria-label', '关闭记忆详情');
  const detailTitle = document.createElement('h3');
  detailTitle.textContent = '记忆详情';
  const detailMeta = document.createElement('dl');
  detailMeta.className = 'memory-detail-meta';
  const detailContent = document.createElement('pre');
  detailContent.className = 'memory-detail-content';
  detailDialog.append(detailClose, detailTitle, detailMeta, detailContent);

  panel.append(tabs, browseView, searchView, rememberView, detailDialog);
  page.append(heading, statsGrid, panel);

  function setBusy(busy) {
    state.busy = busy;
    reloadButton.disabled = busy;
    filterInput.disabled = busy;
    roleSelect.disabled = busy;
    previousButton.disabled = busy || state.offset === 0;
    nextButton.disabled = busy || !state.hasMore;
  }

  function switchView(target) {
    const entries = [
      [browseTab, browseView, 'browse'],
      [searchTab, searchView, 'search'],
      [rememberTab, rememberView, 'remember'],
    ];
    entries.forEach(([button, view, name]) => {
      const active = name === target;
      button.classList.toggle('active', active);
      view.classList.toggle('active', active);
    });
  }

  function renderMemoryState(icon, title, message) {
    memoryList.replaceChildren();
    const node = document.createElement('div');
    node.className = 'memory-empty-state';
    const symbol = document.createElement('span');
    symbol.textContent = icon;
    const headingNode = document.createElement('h3');
    headingNode.textContent = title;
    const paragraph = document.createElement('p');
    paragraph.textContent = message;
    node.append(symbol, headingNode, paragraph);
    memoryList.appendChild(node);
  }

  function updateStats() {
    const stats = state.stats || {};
    statNodes.memoryStatTotal.textContent = stats.total == null ? '—' : `${stats.total} 条`;
    statNodes.memoryStatConversations.textContent = stats.conversations == null ? '—' : `${stats.conversations} 个`;
    statNodes.memoryStatBytes.textContent = stats.bytes == null ? '—' : formatBytes(stats.bytes);
    statNodes.memoryStatLatest.textContent = formatDate(stats.latest_at);
  }

  function updatePagination(total) {
    const start = state.items.length ? state.offset + 1 : 0;
    const end = state.offset + state.items.length;
    pageLabel.textContent = `${start}–${end} / ${Number(total || 0)}`;
    previousButton.disabled = state.busy || state.offset === 0;
    nextButton.disabled = state.busy || !state.hasMore;
  }

  function createAction(label, className, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', handler);
    return button;
  }

  async function showDetail(item) {
    detailTitle.textContent = '正在读取…';
    detailMeta.replaceChildren();
    detailContent.textContent = '';
    if (typeof detailDialog.showModal === 'function') detailDialog.showModal();
    else detailDialog.setAttribute('open', '');
    try {
      const data = await apiFetch(`/item/${encodeURIComponent(item.drawer_id)}`);
      const detail = data.item;
      detailTitle.textContent = roleLabel(detail.role);
      [
        ['记忆 ID', detail.drawer_id],
        ['角色', roleLabel(detail.role)],
        ['会话来源', detail.conversation_id],
        ['来源', detail.source],
        ['创建时间', formatDate(detail.created_at)],
        ['内容哈希', detail.content_hash],
      ].forEach(([label, value]) => {
        const term = document.createElement('dt');
        term.textContent = label;
        const description = document.createElement('dd');
        description.textContent = value || '—';
        detailMeta.append(term, description);
      });
      detailContent.textContent = JSON.stringify(detail.content, null, 2);
    } catch (error) {
      detailTitle.textContent = '读取失败';
      detailContent.textContent = error.message;
    }
  }

  async function deleteMemory(item) {
    const preview = String(item.preview || '').replace(/\s+/g, ' ').slice(0, 90);
    const confirmed = window.confirm(
      `确定删除这条长期记忆吗？\n\n${preview}\n\n系统会同时删除 MemPalace 原文记录和对应的 Qdrant 向量点。`,
    );
    if (!confirmed) return;
    try {
      setBusy(true);
      await apiFetch('/delete', {
        body: JSON.stringify({ drawer_id: item.drawer_id, vault_id: 'default' }),
        method: 'POST',
      });
      showToast('记忆已删除');
      if (state.items.length === 1 && state.offset > 0) state.offset -= PAGE_SIZE;
      await Promise.all([loadStats(), loadMemories()]);
    } catch (error) {
      showToast(`删除失败：${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  function renderMemories(total) {
    updatePagination(total);
    if (!state.items.length) {
      renderMemoryState(
        state.query || state.role ? '⌕' : '✦',
        state.query || state.role ? '没有匹配记忆' : '还没有长期记忆',
        state.query || state.role
          ? '调整关键词或角色筛选后重试。'
          : '正常对话和手动写入的内容会在这里形成账户隔离的记忆片段。',
      );
      return;
    }

    memoryList.replaceChildren();
    state.items.forEach((item) => {
      const row = document.createElement('article');
      row.className = `memory-row ${item.role || 'other'}`;
      const role = document.createElement('span');
      role.className = 'memory-role';
      role.textContent = roleLabel(item.role);
      const body = document.createElement('div');
      body.className = 'memory-row-body';
      const preview = document.createElement('p');
      preview.textContent = item.preview || '[无可显示文本]';
      const meta = document.createElement('span');
      meta.textContent = `${formatDate(item.created_at)} · ${item.conversation_id || '未知会话'} · ${item.drawer_id.slice(0, 10)}`;
      body.append(preview, meta);
      const actions = document.createElement('div');
      actions.className = 'memory-row-actions';
      actions.append(
        createAction('详情', 'memory-action', () => showDetail(item)),
        createAction('删除', 'memory-action danger', () => deleteMemory(item)),
      );
      row.append(role, body, actions);
      memoryList.appendChild(row);
    });
  }

  async function loadStats() {
    try {
      const data = await apiFetch('/stats');
      state.stats = data.stats || {};
      scopeBadge.textContent = `${data.scope || '当前账户'} · ${data.storage_mode || '未知模式'} · ${data.provider || 'memory'}`;
      updateStats();
    } catch (error) {
      scopeBadge.textContent = `账户作用域读取失败：${error.message}`;
      state.stats = null;
      updateStats();
    }
  }

  async function loadMemories({ reset = false } = {}) {
    if (state.busy) return;
    if (reset) state.offset = 0;
    state.query = filterInput.value.trim();
    state.role = roleSelect.value;
    setBusy(true);
    renderMemoryState('…', '正在读取长期记忆', '正在验证 LobeHub 会话并读取当前账户的 default Vault。');
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(state.offset),
      vault_id: 'default',
    });
    if (state.query) params.set('q', state.query);
    if (state.role) params.set('role', state.role);
    try {
      const data = await apiFetch(`/list?${params.toString()}`);
      state.items = Array.isArray(data.items) ? data.items : [];
      state.hasMore = Boolean(data.has_more);
      state.loaded = true;
      scopeBadge.textContent = `${data.scope || '当前账户'} · ${data.storage_mode || '未知模式'} · ${data.provider || 'memory'}`;
      renderMemories(data.total);
    } catch (error) {
      state.items = [];
      state.hasMore = false;
      updatePagination(0);
      renderMemoryState('!', '无法读取长期记忆', error.message);
    } finally {
      setBusy(false);
    }
  }

  function renderSemanticResults(data) {
    semanticResults.replaceChildren();
    const raw = Array.isArray(data.raw_results) ? data.raw_results : [];
    const summary = document.createElement('div');
    summary.className = 'memory-search-summary';
    const summaryTitle = document.createElement('strong');
    summaryTitle.textContent = `召回 ${raw.length} 条 MemPalace 原文片段`;
    const summaryMeta = document.createElement('span');
    summaryMeta.textContent = `${data.scope || '当前账户'} · ${data.storage_mode || '未知模式'} · ${data.provider || 'memory'}`;
    summary.append(summaryTitle, summaryMeta);
    semanticResults.appendChild(summary);

    if (raw.length) {
      const rawList = document.createElement('div');
      rawList.className = 'memory-search-hits';
      raw.forEach((item, index) => {
        const hit = document.createElement('article');
        const header = document.createElement('div');
        const title = document.createElement('strong');
        title.textContent = `#${index + 1} ${item.wing || 'scope'} / ${item.room || 'memory'}`;
        const score = document.createElement('span');
        score.textContent = `相似度 ${Number(item.similarity || 0).toFixed(4)}`;
        header.append(title, score);
        const text = document.createElement('p');
        text.textContent = item.text || '';
        hit.append(header, text);
        rawList.appendChild(hit);
      });
      semanticResults.appendChild(rawList);
    }

    const contextSection = document.createElement('section');
    contextSection.className = 'memory-context-section';
    const contextTitle = document.createElement('h3');
    contextTitle.textContent = '注入模型前的组合记忆上下文';
    const context = document.createElement('pre');
    context.textContent = data.context || '[没有召回到可用记忆]';
    contextSection.append(contextTitle, context);
    semanticResults.appendChild(contextSection);
  }

  async function runSemanticSearch(event) {
    event.preventDefault();
    const query = semanticInput.value.trim();
    if (!query) return;
    semanticButton.disabled = true;
    semanticButton.textContent = '搜索中…';
    searchStatus.textContent = '正在调用当前账户作用域下的 MemPalace 与组合 Provider…';
    semanticResults.replaceChildren();
    try {
      const data = await apiFetch('/search', {
        body: JSON.stringify({ query, vault_id: 'default' }),
        method: 'POST',
      });
      renderSemanticResults(data);
      searchStatus.textContent = '搜索完成。结果只来自当前 LobeHub 账户的 default Vault。';
    } catch (error) {
      searchStatus.textContent = `搜索失败：${error.message}`;
    } finally {
      semanticButton.disabled = false;
      semanticButton.textContent = '搜索长期记忆';
    }
  }

  async function rememberMemory(event) {
    event.preventDefault();
    const text = rememberText.value.trim();
    if (!text) return;
    rememberButton.disabled = true;
    rememberButton.textContent = '写入中…';
    rememberStatus.textContent = '正在写入 MemPalace，并按当前配置同步结构化记忆…';
    try {
      const data = await apiFetch('/remember', {
        body: JSON.stringify({
          assistant_text: assistantInput.value.trim(),
          conversation_id: conversationInput.value.trim(),
          sanitized_for_cloud: sanitizeInput.checked,
          text,
          vault_id: 'default',
        }),
        method: 'POST',
      });
      const success = Boolean(data.write?.success);
      rememberStatus.textContent = success
        ? `写入成功，来源 ${data.conversation_id}`
        : `部分组件未完成：${(data.write?.error_codes || []).join(', ') || '未知原因'}`;
      if (success) {
        rememberText.value = '';
        assistantInput.value = '';
        conversationInput.value = '';
        sanitizeInput.checked = false;
        showToast('长期记忆已保存');
        await Promise.all([loadStats(), loadMemories({ reset: true })]);
      }
    } catch (error) {
      rememberStatus.textContent = `写入失败：${error.message}`;
    } finally {
      rememberButton.disabled = false;
      rememberButton.textContent = '保存到长期记忆';
    }
  }

  let filterTimer = null;
  filterInput.addEventListener('input', () => {
    window.clearTimeout(filterTimer);
    filterTimer = window.setTimeout(() => loadMemories({ reset: true }), 350);
  });
  roleSelect.addEventListener('change', () => loadMemories({ reset: true }));
  previousButton.addEventListener('click', () => {
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    loadMemories();
  });
  nextButton.addEventListener('click', () => {
    if (!state.hasMore) return;
    state.offset += PAGE_SIZE;
    loadMemories();
  });
  reloadButton.addEventListener('click', () => Promise.all([loadStats(), loadMemories()]));
  browseTab.addEventListener('click', () => switchView('browse'));
  searchTab.addEventListener('click', () => switchView('search'));
  rememberTab.addEventListener('click', () => switchView('remember'));
  searchForm.addEventListener('submit', runSemanticSearch);
  rememberForm.addEventListener('submit', rememberMemory);
  detailClose.addEventListener('click', () => detailDialog.close?.());
  detailDialog.addEventListener('click', (event) => {
    if (event.target === detailDialog) detailDialog.close?.();
  });

  const originalNavigate = window.navigate || navigate;
  window.navigate = navigate = (targetPage) => {
    originalNavigate(targetPage);
    if (targetPage === 'memories' && !state.loaded) {
      Promise.all([loadStats(), loadMemories()]);
    }
  };

  window.sumemeMemoryManager = {
    load: () => Promise.all([loadStats(), loadMemories({ reset: true })]),
  };

  if (location.hash === '#memories') Promise.all([loadStats(), loadMemories()]);
})();
