(() => {
  const page = document.getElementById('page-files');
  if (!page) return;

  const nativeFetch = window.fetch.bind(window);
  const PAGE_SIZE = 50;
  const state = {
    busy: false,
    files: [],
    hasMore: false,
    loaded: false,
    offset: 0,
    query: '',
    sortType: 'desc',
    uploading: false,
  };

  function unwrapTrpc(payload) {
    const envelope = Array.isArray(payload) ? payload[0] : payload;
    const trpcError = envelope?.error?.json || envelope?.error;
    if (trpcError) {
      const error = new Error(
        trpcError.message || trpcError.data?.message || 'LobeHub 资料接口请求失败',
      );
      error.status = trpcError.data?.httpStatus;
      throw error;
    }
    const data = envelope?.result?.data;
    if (data && Object.prototype.hasOwnProperty.call(data, 'json')) return data.json;
    if (data !== undefined) return data;
    if (envelope && Object.prototype.hasOwnProperty.call(envelope, 'json')) return envelope.json;
    return envelope;
  }

  async function parseResponse(response, fallbackMessage) {
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      const error = new Error(`${fallbackMessage}：响应不是 JSON (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (!response.ok) {
      let message = `${fallbackMessage} (${response.status})`;
      try { unwrapTrpc(payload); } catch (error) { message = error.message || message; }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return unwrapTrpc(payload);
  }

  async function trpcQuery(procedure, input = {}) {
    const singleInput = encodeURIComponent(JSON.stringify({ json: input }));
    const singleUrl = `/trpc/${procedure}?input=${singleInput}`;
    try {
      const response = await nativeFetch(singleUrl, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      return await parseResponse(response, 'LobeHub 资料读取失败');
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      const batchInput = encodeURIComponent(JSON.stringify({ 0: { json: input } }));
      const response = await nativeFetch(`/trpc/${procedure}?batch=1&input=${batchInput}`, {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      return parseResponse(response, 'LobeHub 资料读取失败');
    }
  }

  async function postTrpc(url, body) {
    const response = await nativeFetch(url, {
      body: JSON.stringify(body),
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      method: 'POST',
    });
    return parseResponse(response, 'LobeHub 资料写入失败');
  }

  async function trpcMutation(procedure, input = {}) {
    try {
      return await postTrpc(`/trpc/${procedure}`, { json: input });
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      return postTrpc(`/trpc/${procedure}?batch=1`, { 0: { json: input } });
    }
  }

  function formatBytes(bytes) {
    const value = Number(bytes || 0);
    if (!Number.isFinite(value) || value <= 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
    const normalized = value / (1024 ** index);
    return `${normalized >= 10 || index === 0 ? normalized.toFixed(0) : normalized.toFixed(1)} ${units[index]}`;
  }

  function formatDate(value) {
    if (!value) return '时间未知';
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

  function mimeFromFile(file) {
    if (file.type) return file.type;
    const extension = file.name.split('.').pop()?.toLowerCase() || '';
    const types = {
      csv: 'text/csv',
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      gif: 'image/gif',
      jpeg: 'image/jpeg',
      jpg: 'image/jpeg',
      json: 'application/json',
      m4a: 'audio/mp4',
      md: 'text/markdown',
      mp3: 'audio/mpeg',
      mp4: 'video/mp4',
      pdf: 'application/pdf',
      png: 'image/png',
      pptx: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
      txt: 'text/plain',
      wav: 'audio/wav',
      webp: 'image/webp',
      xlsx: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    };
    return types[extension] || 'application/octet-stream';
  }

  function fileIcon(type) {
    const mime = String(type || '').toLowerCase();
    if (mime.startsWith('image/')) return '▧';
    if (mime.startsWith('audio/')) return '♫';
    if (mime.startsWith('video/')) return '▶';
    if (mime.includes('pdf')) return 'PDF';
    if (mime.includes('spreadsheet') || mime.includes('csv')) return '表';
    if (mime.includes('word') || mime.includes('text') || mime.includes('json')) return '文';
    return '▣';
  }

  function statusPresentation(file) {
    if (file.embeddingStatus === 'error' || file.chunkingStatus === 'error') {
      return { label: '解析失败', kind: 'error' };
    }
    if (file.finishEmbedding) return { label: '可检索', kind: 'success' };
    if (file.embeddingStatus || file.chunkingStatus) return { label: '处理中', kind: 'warning' };
    return { label: '已保存', kind: 'neutral' };
  }

  page.replaceChildren();
  const heading = document.createElement('div');
  heading.className = 'page-heading files-page-heading';
  const headingText = document.createElement('div');
  const eyebrow = document.createElement('span');
  eyebrow.className = 'eyebrow';
  eyebrow.textContent = 'FILES & OBJECTS';
  const title = document.createElement('h2');
  title.textContent = '资料与对象';
  const subtitle = document.createElement('p');
  subtitle.textContent = '直接管理当前 LobeHub 账户中的文件记录与 RustFS 对象，不建立第二套资料库。';
  headingText.append(eyebrow, title, subtitle);
  const headingActions = document.createElement('div');
  headingActions.className = 'files-heading-actions';
  const phaseBadge = document.createElement('span');
  phaseBadge.className = 'files-native-badge';
  phaseBadge.textContent = 'LobeHub 原生资料库';
  const reloadButton = document.createElement('button');
  reloadButton.className = 'button secondary';
  reloadButton.type = 'button';
  reloadButton.textContent = '重新读取';
  headingActions.append(phaseBadge, reloadButton);
  heading.append(headingText, headingActions);

  const panel = document.createElement('div');
  panel.className = 'panel files-manager-panel';

  const toolbar = document.createElement('div');
  toolbar.className = 'files-toolbar';
  const searchLabel = document.createElement('label');
  searchLabel.className = 'files-search';
  const searchIcon = document.createElement('span');
  searchIcon.textContent = '⌕';
  const searchInput = document.createElement('input');
  searchInput.type = 'search';
  searchInput.placeholder = '按文件名搜索';
  searchInput.autocomplete = 'off';
  searchLabel.append(searchIcon, searchInput);

  const sortSelect = document.createElement('select');
  sortSelect.className = 'files-sort';
  sortSelect.setAttribute('aria-label', '资料排序');
  const newest = document.createElement('option');
  newest.value = 'desc';
  newest.textContent = '最新上传';
  const oldest = document.createElement('option');
  oldest.value = 'asc';
  oldest.textContent = '最早上传';
  sortSelect.append(newest, oldest);

  const uploadButton = document.createElement('button');
  uploadButton.className = 'button primary';
  uploadButton.type = 'button';
  uploadButton.textContent = '＋ 上传资料';
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.multiple = true;
  fileInput.hidden = true;
  fileInput.setAttribute('aria-label', '上传资料到 LobeHub');
  toolbar.append(searchLabel, sortSelect, uploadButton, fileInput);

  const summary = document.createElement('div');
  summary.className = 'files-summary';
  const countCard = document.createElement('div');
  const countLabel = document.createElement('span');
  countLabel.textContent = '当前页';
  const countValue = document.createElement('strong');
  countValue.textContent = '—';
  countCard.append(countLabel, countValue);
  const sizeCard = document.createElement('div');
  const sizeLabel = document.createElement('span');
  sizeLabel.textContent = '当前页容量';
  const sizeValue = document.createElement('strong');
  sizeValue.textContent = '—';
  sizeCard.append(sizeLabel, sizeValue);
  const searchCard = document.createElement('div');
  const searchStatusLabel = document.createElement('span');
  searchStatusLabel.textContent = '可检索资料';
  const searchStatusValue = document.createElement('strong');
  searchStatusValue.textContent = '—';
  searchCard.append(searchStatusLabel, searchStatusValue);
  const pageCard = document.createElement('div');
  const pageLabel = document.createElement('span');
  pageLabel.textContent = '页码';
  const pageValue = document.createElement('strong');
  pageValue.textContent = '1';
  pageCard.append(pageLabel, pageValue);
  summary.append(countCard, sizeCard, searchCard, pageCard);

  const uploadQueue = document.createElement('div');
  uploadQueue.className = 'files-upload-queue';
  uploadQueue.hidden = true;

  const list = document.createElement('div');
  list.className = 'files-list';
  list.setAttribute('aria-live', 'polite');

  const pagination = document.createElement('div');
  pagination.className = 'files-pagination';
  const previousButton = document.createElement('button');
  previousButton.className = 'button secondary';
  previousButton.type = 'button';
  previousButton.textContent = '上一页';
  const rangeLabel = document.createElement('span');
  rangeLabel.textContent = '—';
  const nextButton = document.createElement('button');
  nextButton.className = 'button secondary';
  nextButton.type = 'button';
  nextButton.textContent = '下一页';
  pagination.append(previousButton, rangeLabel, nextButton);

  const detailDialog = document.createElement('dialog');
  detailDialog.className = 'files-detail-dialog';
  const detailClose = document.createElement('button');
  detailClose.className = 'files-dialog-close';
  detailClose.type = 'button';
  detailClose.textContent = '×';
  detailClose.setAttribute('aria-label', '关闭资料详情');
  const detailTitle = document.createElement('h3');
  detailTitle.textContent = '资料详情';
  const detailBody = document.createElement('dl');
  detailBody.className = 'files-detail-grid';
  detailDialog.append(detailClose, detailTitle, detailBody);

  panel.append(toolbar, summary, uploadQueue, list, pagination, detailDialog);
  page.append(heading, panel);

  function setBusy(busy) {
    state.busy = busy;
    reloadButton.disabled = busy || state.uploading;
    searchInput.disabled = busy || state.uploading;
    sortSelect.disabled = busy || state.uploading;
    uploadButton.disabled = busy || state.uploading;
    previousButton.disabled = busy || state.uploading || state.offset === 0;
    nextButton.disabled = busy || state.uploading || !state.hasMore;
  }

  function renderState(icon, headingTextValue, message) {
    list.replaceChildren();
    const node = document.createElement('div');
    node.className = 'files-empty-state';
    const symbol = document.createElement('span');
    symbol.textContent = icon;
    const headingNode = document.createElement('h3');
    headingNode.textContent = headingTextValue;
    const paragraph = document.createElement('p');
    paragraph.textContent = message;
    node.append(symbol, headingNode, paragraph);
    list.appendChild(node);
  }

  function updateSummary() {
    countValue.textContent = `${state.files.length} 个`;
    sizeValue.textContent = formatBytes(
      state.files.reduce((total, file) => total + Number(file.size || 0), 0),
    );
    searchStatusValue.textContent = `${state.files.filter((file) => file.finishEmbedding).length} 个`;
    pageValue.textContent = String(Math.floor(state.offset / PAGE_SIZE) + 1);
    const start = state.files.length ? state.offset + 1 : 0;
    const end = state.offset + state.files.length;
    rangeLabel.textContent = state.hasMore ? `${start}–${end}，后面还有资料` : `${start}–${end}`;
    previousButton.disabled = state.busy || state.uploading || state.offset === 0;
    nextButton.disabled = state.busy || state.uploading || !state.hasMore;
  }

  function createActionButton(label, className, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', handler);
    return button;
  }

  async function showDetails(file) {
    detailTitle.textContent = '正在读取…';
    detailBody.replaceChildren();
    if (typeof detailDialog.showModal === 'function') detailDialog.showModal();
    else detailDialog.setAttribute('open', '');
    try {
      const detail = await trpcQuery('file.findById', { id: file.id });
      detailTitle.textContent = detail?.name || file.name || '资料详情';
      const fields = [
        ['文件 ID', detail?.id],
        ['类型', detail?.fileType],
        ['大小', formatBytes(detail?.size)],
        ['来源', detail?.source || 'LobeHub'],
        ['创建时间', formatDate(detail?.createdAt)],
        ['更新时间', formatDate(detail?.updatedAt)],
        ['对象路径', detail?.metadata?.path || detail?.url],
        ['哈希', detail?.fileHash],
      ];
      fields.forEach(([label, value]) => {
        const term = document.createElement('dt');
        term.textContent = label;
        const description = document.createElement('dd');
        description.textContent = value == null || value === '' ? '—' : String(value);
        detailBody.append(term, description);
      });
    } catch (error) {
      detailTitle.textContent = '资料详情读取失败';
      const term = document.createElement('dt');
      term.textContent = '错误';
      const description = document.createElement('dd');
      description.textContent = error.message;
      detailBody.append(term, description);
    }
  }

  async function renameFile(file) {
    const currentName = String(file.name || '');
    const nextName = window.prompt('输入新的资料名称', currentName);
    if (nextName == null) return;
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === currentName) return;
    try {
      await trpcMutation('file.updateFile', { id: file.id, name: trimmed });
      showToast('资料名称已更新');
      await loadFiles();
    } catch (error) {
      showToast(`重命名失败：${error.message}`);
    }
  }

  async function deleteFile(file) {
    const confirmed = window.confirm(
      `确定删除“${file.name || '未命名资料'}”吗？\n\nLobeHub 会删除当前账户的文件记录；若底层对象没有被其他记录引用，也会从 RustFS 删除。`,
    );
    if (!confirmed) return;
    try {
      setBusy(true);
      await trpcMutation('file.removeFile', { id: file.id });
      showToast('资料已删除');
      if (state.files.length === 1 && state.offset > 0) state.offset -= PAGE_SIZE;
      await loadFiles();
    } catch (error) {
      showToast(`删除失败：${error.message}`);
    } finally {
      setBusy(false);
    }
  }

  function renderFiles() {
    updateSummary();
    if (!state.files.length) {
      renderState(
        state.query ? '⌕' : '▣',
        state.query ? '没有匹配资料' : '还没有资料',
        state.query ? '换一个文件名关键词后重新搜索。' : '点击“上传资料”把文件保存到 LobeHub 与 RustFS。',
      );
      return;
    }

    list.replaceChildren();
    state.files.forEach((file) => {
      const row = document.createElement('article');
      row.className = 'files-row';

      const icon = document.createElement('div');
      icon.className = 'files-icon';
      icon.textContent = fileIcon(file.fileType);

      const identity = document.createElement('div');
      identity.className = 'files-identity';
      const name = document.createElement('strong');
      name.textContent = file.name || '未命名资料';
      const meta = document.createElement('span');
      meta.textContent = `${file.fileType || '未知类型'} · ${formatBytes(file.size)} · ${formatDate(file.createdAt)}`;
      identity.append(name, meta);

      const status = statusPresentation(file);
      const statusNode = document.createElement('span');
      statusNode.className = `files-status ${status.kind}`;
      statusNode.textContent = status.label;

      const actions = document.createElement('div');
      actions.className = 'files-actions';
      if (file.url) {
        const open = document.createElement('a');
        open.className = 'files-action-link';
        open.href = file.url;
        open.target = '_blank';
        open.rel = 'noopener noreferrer';
        open.textContent = '打开';
        actions.appendChild(open);
      }
      actions.append(
        createActionButton('详情', 'files-action-button', () => showDetails(file)),
        createActionButton('重命名', 'files-action-button', () => renameFile(file)),
        createActionButton('删除', 'files-action-button danger', () => deleteFile(file)),
      );
      row.append(icon, identity, statusNode, actions);
      list.appendChild(row);
    });
  }

  async function loadFiles({ reset = false } = {}) {
    if (!window.session?.user && typeof session !== 'undefined' && !session?.user) return;
    if (state.busy) return;
    if (reset) state.offset = 0;
    state.query = searchInput.value.trim();
    state.sortType = sortSelect.value === 'asc' ? 'asc' : 'desc';
    setBusy(true);
    renderState('…', '正在读取资料', '正在通过当前登录会话读取 LobeHub 文件记录。');
    try {
      const payload = await trpcQuery('file.getFiles', {
        limit: PAGE_SIZE + 1,
        offset: state.offset,
        parentId: null,
        q: state.query || null,
        showFilesInKnowledgeBase: false,
        sorter: 'createdAt',
        sortType: state.sortType,
      });
      const rows = Array.isArray(payload)
        ? payload
        : Array.isArray(payload?.items) ? payload.items : [];
      state.hasMore = rows.length > PAGE_SIZE;
      state.files = rows.slice(0, PAGE_SIZE).filter((file) => file?.id);
      state.loaded = true;
      renderFiles();
    } catch (error) {
      state.files = [];
      state.hasMore = false;
      updateSummary();
      renderState('!', '无法读取资料', error.message);
    } finally {
      setBusy(false);
    }
  }

  async function hashFile(file) {
    if (!window.crypto?.subtle) throw new Error('当前浏览器不支持安全文件哈希');
    const digest = await window.crypto.subtle.digest('SHA-256', await file.arrayBuffer());
    return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
  }

  function createStorageMetadata(file) {
    const extension = (file.name.includes('.') ? file.name.split('.').pop() : 'bin')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '')
      .slice(0, 12) || 'bin';
    const date = Math.floor(Date.now() / 3_600_000).toString();
    const dirname = `files/${date}`;
    const identifier = window.crypto?.randomUUID?.()
      || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const filename = `${identifier}.${extension}`;
    return { date, dirname, filename, path: `${dirname}/${filename}` };
  }

  function uploadToSignedUrl(url, file, onProgress) {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open('PUT', url);
      request.setRequestHeader('Content-Type', mimeFromFile(file));
      request.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
        }
      });
      request.addEventListener('load', () => {
        if (request.status >= 200 && request.status < 300) {
          onProgress(100);
          resolve();
        } else reject(new Error(`对象存储上传失败 (${request.status})`));
      });
      request.addEventListener('error', () => reject(new Error('无法连接 LobeHub 对象存储')));
      request.addEventListener('abort', () => reject(new Error('资料上传已取消')));
      request.send(file);
    });
  }

  function renderUploadQueue(items) {
    uploadQueue.replaceChildren();
    uploadQueue.hidden = items.length === 0;
    items.forEach((item) => {
      const row = document.createElement('div');
      row.className = `files-upload-item ${item.status}`;
      const name = document.createElement('strong');
      name.textContent = item.file.name;
      const progress = document.createElement('span');
      progress.textContent = item.message || `${item.progress || 0}%`;
      const bar = document.createElement('i');
      bar.style.width = `${item.progress || 0}%`;
      row.append(name, progress, bar);
      uploadQueue.appendChild(row);
    });
  }

  async function uploadOne(item) {
    item.status = 'working';
    item.message = '计算 SHA-256';
    renderUploadQueue(item.queue);
    const hash = await hashFile(item.file);

    item.message = '检查 LobeHub 去重记录';
    renderUploadQueue(item.queue);
    const existing = await trpcMutation('file.checkFileHash', { hash });
    let metadata;
    let objectPath;

    if (existing?.isExist && (existing?.metadata?.path || existing?.url)) {
      metadata = existing.metadata && typeof existing.metadata === 'object'
        ? { ...existing.metadata }
        : {};
      objectPath = metadata.path || existing.url;
      metadata.path = objectPath;
      item.progress = 80;
      item.message = '复用已有对象';
      renderUploadQueue(item.queue);
    } else {
      metadata = createStorageMetadata(item.file);
      objectPath = metadata.path;
      item.message = '获取签名上传地址';
      renderUploadQueue(item.queue);
      const signed = await trpcMutation('upload.createS3PreSignedUrl', { pathname: objectPath });
      const signedUrl = typeof signed === 'string' ? signed : signed?.preSignUrl || signed?.url;
      if (!signedUrl) throw new Error('LobeHub 未返回签名上传地址');
      item.message = '上传到 RustFS';
      renderUploadQueue(item.queue);
      await uploadToSignedUrl(signedUrl, item.file, (progress) => {
        item.progress = progress;
        item.message = `上传 ${progress}%`;
        renderUploadQueue(item.queue);
      });
    }

    item.progress = Math.max(item.progress || 0, 95);
    item.message = '创建 LobeHub 文件记录';
    renderUploadQueue(item.queue);
    const record = await trpcMutation('file.createFile', {
      fileType: mimeFromFile(item.file),
      hash,
      metadata,
      name: item.file.name,
      size: item.file.size,
      source: 'sumeme-files',
      url: objectPath,
    });
    if (!record?.id) throw new Error('LobeHub 未返回文件记录 ID');
    item.progress = 100;
    item.status = 'success';
    item.message = '上传完成';
    renderUploadQueue(item.queue);
  }

  async function uploadFiles(files) {
    if (!files.length || state.uploading) return;
    state.uploading = true;
    setBusy(true);
    const queue = files.map((file) => ({
      file,
      message: '等待上传',
      progress: 0,
      queue: null,
      status: 'pending',
    }));
    queue.forEach((item) => { item.queue = queue; });
    renderUploadQueue(queue);
    let failures = 0;
    for (const item of queue) {
      try {
        await uploadOne(item);
      } catch (error) {
        failures += 1;
        item.status = 'error';
        item.message = error.message || '上传失败';
        renderUploadQueue(queue);
      }
    }
    state.uploading = false;
    setBusy(false);
    showToast(failures ? `${queue.length - failures} 个上传成功，${failures} 个失败` : `${queue.length} 个资料已上传`);
    await loadFiles({ reset: true });
    if (!failures) {
      window.setTimeout(() => {
        uploadQueue.hidden = true;
        uploadQueue.replaceChildren();
      }, 1800);
    }
  }

  let searchTimer = null;
  searchInput.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => loadFiles({ reset: true }), 350);
  });
  sortSelect.addEventListener('change', () => loadFiles({ reset: true }));
  reloadButton.addEventListener('click', () => loadFiles());
  uploadButton.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    const files = Array.from(fileInput.files || []);
    fileInput.value = '';
    uploadFiles(files);
  });
  previousButton.addEventListener('click', () => {
    state.offset = Math.max(0, state.offset - PAGE_SIZE);
    loadFiles();
  });
  nextButton.addEventListener('click', () => {
    if (!state.hasMore) return;
    state.offset += PAGE_SIZE;
    loadFiles();
  });
  detailClose.addEventListener('click', () => detailDialog.close?.());
  detailDialog.addEventListener('click', (event) => {
    if (event.target === detailDialog) detailDialog.close?.();
  });

  const originalNavigate = window.navigate || navigate;
  window.navigate = navigate = (targetPage) => {
    originalNavigate(targetPage);
    if (targetPage === 'files' && !state.loaded) loadFiles();
  };

  window.sumemeFilesManager = {
    load: () => loadFiles({ reset: true }),
  };

  if (location.hash === '#files') loadFiles();
})();
