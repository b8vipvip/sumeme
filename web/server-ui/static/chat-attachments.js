(() => {
  const composer = document.getElementById('chatComposer');
  const textarea = document.getElementById('chatMessageInput');
  const badge = document.querySelector('.read-only-badge');
  if (!composer || !textarea) return;

  const nativeFetch = window.fetch.bind(window);
  const state = {
    intercepting: false,
    items: [],
  };

  function setRunStatus(text, kind = '') {
    const node = document.getElementById('chatRunStatus');
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
  }

  function unwrapTrpc(payload) {
    const envelope = Array.isArray(payload) ? payload[0] : payload;
    const error = envelope?.error?.json || envelope?.error;
    if (error) {
      throw new Error(error.message || error.data?.message || 'LobeHub 文件接口请求失败');
    }
    const data = envelope?.result?.data;
    if (data && Object.prototype.hasOwnProperty.call(data, 'json')) return data.json;
    if (data !== undefined) return data;
    return envelope;
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
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      const error = new Error(`无法解析 LobeHub 文件接口响应 (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (!response.ok) {
      let message = `LobeHub 文件接口请求失败 (${response.status})`;
      try { unwrapTrpc(payload); } catch (error) { message = error.message || message; }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return unwrapTrpc(payload);
  }

  async function trpcMutation(procedure, input) {
    try {
      return await postTrpc(`/trpc/${procedure}`, { json: input });
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      return postTrpc(`/trpc/${procedure}?batch=1`, { 0: { json: input } });
    }
  }

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes < 1) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / (1024 ** index);
    return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
  }

  function mimeFromFile(file) {
    if (file.type) return file.type;
    const extension = file.name.split('.').pop()?.toLowerCase() || '';
    const types = {
      csv: 'text/csv',
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
      docx: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    };
    return types[extension] || 'application/octet-stream';
  }

  async function hashFile(file) {
    if (!window.crypto?.subtle) throw new Error('当前浏览器不支持安全文件哈希');
    const buffer = await file.arrayBuffer();
    const digest = await window.crypto.subtle.digest('SHA-256', buffer);
    return Array.from(new Uint8Array(digest), (value) => value.toString(16).padStart(2, '0')).join('');
  }

  function createStorageMetadata(file) {
    const extension = (file.name.includes('.') ? file.name.split('.').pop() : 'bin')
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '')
      .slice(0, 12) || 'bin';
    const date = (Date.now() / 1000 / 60 / 60).toFixed(0);
    const dirname = `files/${date}`;
    const identifier = window.crypto?.randomUUID?.()
      || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const filename = `${identifier}.${extension}`;
    return {
      date,
      dirname,
      filename,
      path: `${dirname}/${filename}`,
    };
  }

  function uploadToSignedUrl(url, file, onProgress) {
    return new Promise((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open('PUT', url);
      request.setRequestHeader('Content-Type', mimeFromFile(file));
      request.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
      });
      request.addEventListener('load', () => {
        if (request.status >= 200 && request.status < 300) {
          onProgress(100);
          resolve();
        } else {
          reject(new Error(`对象存储上传失败 (${request.status})`));
        }
      });
      request.addEventListener('error', () => reject(new Error('无法连接 LobeHub 对象存储')));
      request.addEventListener('abort', () => reject(new Error('附件上传已取消')));
      request.send(file);
    });
  }

  function itemKey(file) {
    return `${file.name}:${file.size}:${file.lastModified}`;
  }

  function statusLabel(item) {
    if (item.status === 'hashing') return '计算哈希';
    if (item.status === 'checking') return '检查去重';
    if (item.status === 'signing') return '准备上传';
    if (item.status === 'uploading') return `上传 ${item.progress || 0}%`;
    if (item.status === 'recording') return '写入 LobeHub';
    if (item.status === 'ready') return '已就绪';
    if (item.status === 'error') return item.error || '上传失败';
    return '等待发送';
  }

  const toolbar = document.createElement('div');
  toolbar.className = 'chat-attachment-toolbar';
  const attachButton = document.createElement('button');
  attachButton.className = 'attachment-button';
  attachButton.type = 'button';
  attachButton.textContent = '📎 添加附件';
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.multiple = true;
  fileInput.hidden = true;
  fileInput.setAttribute('aria-label', '选择要发送给 LobeHub 代理的附件');
  const note = document.createElement('span');
  note.textContent = '发送时上传到 LobeHub / RustFS，并作为 fileIds 交给原生代理';
  toolbar.append(attachButton, fileInput, note);

  const list = document.createElement('div');
  list.className = 'chat-attachment-list';
  list.hidden = true;
  composer.insertBefore(toolbar, textarea);
  composer.insertBefore(list, textarea);

  function renderItems() {
    list.replaceChildren();
    list.hidden = state.items.length === 0;
    state.items.forEach((item) => {
      const row = document.createElement('div');
      row.className = `chat-attachment-item ${item.status}`;

      const icon = document.createElement('span');
      icon.className = 'attachment-icon';
      icon.textContent = mimeFromFile(item.file).startsWith('image/') ? '▧' : '▣';

      const details = document.createElement('span');
      details.className = 'attachment-details';
      const name = document.createElement('strong');
      name.textContent = item.file.name;
      const meta = document.createElement('small');
      meta.textContent = `${formatBytes(item.file.size)} · ${statusLabel(item)}`;
      details.append(name, meta);

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'attachment-remove';
      remove.textContent = '×';
      remove.title = '从本次消息中移除';
      remove.disabled = state.intercepting || ['hashing', 'checking', 'signing', 'uploading', 'recording'].includes(item.status);
      remove.addEventListener('click', () => {
        state.items = state.items.filter((candidate) => candidate.key !== item.key);
        renderItems();
      });

      row.append(icon, details, remove);
      if (item.status === 'uploading') {
        const progress = document.createElement('span');
        progress.className = 'attachment-progress';
        progress.style.width = `${item.progress || 0}%`;
        row.appendChild(progress);
      }
      list.appendChild(row);
    });
  }

  function setBusy(busy) {
    state.intercepting = busy;
    attachButton.disabled = busy;
    fileInput.disabled = busy;
    renderItems();
  }

  async function uploadItem(item) {
    if (item.fileId) return item.fileId;
    try {
      item.status = 'hashing';
      item.error = '';
      renderItems();
      const hash = await hashFile(item.file);

      item.status = 'checking';
      renderItems();
      const existing = await trpcMutation('file.checkFileHash', { hash });
      let metadata;
      let objectPath;

      if (existing?.isExist && (existing?.metadata?.path || existing?.url)) {
        metadata = existing.metadata && typeof existing.metadata === 'object'
          ? { ...existing.metadata }
          : {};
        objectPath = metadata.path || existing.url;
        metadata.path = objectPath;
      } else {
        metadata = createStorageMetadata(item.file);
        objectPath = metadata.path;
        item.status = 'signing';
        renderItems();
        const signed = await trpcMutation('upload.createS3PreSignedUrl', { pathname: objectPath });
        const signedUrl = typeof signed === 'string' ? signed : signed?.preSignUrl || signed?.url;
        if (!signedUrl) throw new Error('LobeHub 未返回签名上传地址');

        item.status = 'uploading';
        item.progress = 0;
        renderItems();
        await uploadToSignedUrl(signedUrl, item.file, (progress) => {
          item.progress = progress;
          renderItems();
        });
      }

      item.status = 'recording';
      renderItems();
      const record = await trpcMutation('file.createFile', {
        fileType: mimeFromFile(item.file),
        hash,
        metadata,
        name: item.file.name,
        size: item.file.size,
        source: 'sumeme-chat',
        url: objectPath,
      });
      if (!record?.id) throw new Error('LobeHub 未返回文件记录 ID');

      item.fileId = record.id;
      item.status = 'ready';
      item.progress = 100;
      renderItems();
      return item.fileId;
    } catch (error) {
      item.status = 'error';
      item.error = error.message || '附件上传失败';
      renderItems();
      throw error;
    }
  }

  async function prepareAttachments() {
    if (!state.items.length) return [];
    setBusy(true);
    setRunStatus(`正在上传 ${state.items.length} 个附件到 LobeHub…`);
    const fileIds = [];
    try {
      for (let index = 0; index < state.items.length; index += 1) {
        setRunStatus(`正在处理附件 ${index + 1}/${state.items.length}：${state.items[index].file.name}`);
        fileIds.push(await uploadItem(state.items[index]));
      }
      setRunStatus('附件已写入 LobeHub，正在启动原生代理…');
      return fileIds;
    } finally {
      setBusy(false);
    }
  }

  function injectFileIds(body, fileIds) {
    const value = JSON.parse(body || '{}');
    if (value?.json) {
      value.json.fileIds = [...new Set([...(value.json.fileIds || []), ...fileIds])];
      return JSON.stringify(value);
    }
    if (value?.[0]?.json) {
      value[0].json.fileIds = [...new Set([...(value[0].json.fileIds || []), ...fileIds])];
      return JSON.stringify(value);
    }
    throw new Error('无法识别 LobeHub 代理请求格式');
  }

  function clearAfterAccepted() {
    state.items = [];
    fileInput.value = '';
    renderItems();
  }

  attachButton.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', () => {
    const known = new Set(state.items.map((item) => item.key));
    for (const file of Array.from(fileInput.files || [])) {
      const key = itemKey(file);
      if (known.has(key)) continue;
      known.add(key);
      state.items.push({ error: '', file, fileId: '', key, progress: 0, status: 'pending' });
    }
    fileInput.value = '';
    renderItems();
    textarea.focus();
  });

  document.getElementById('newConversationButton')?.addEventListener('click', () => {
    if (!state.intercepting) clearAfterAccepted();
  });

  window.fetch = async (input, init = {}) => {
    const requestUrl = typeof input === 'string' ? input : input?.url || '';
    let parsedUrl;
    try { parsedUrl = new URL(requestUrl, window.location.origin); } catch { parsedUrl = null; }
    const isAgentExecution = parsedUrl?.pathname === '/trpc/aiAgent.execAgent'
      && String(init.method || 'GET').toUpperCase() === 'POST';

    if (!isAgentExecution || !state.items.length) return nativeFetch(input, init);
    if (state.intercepting) throw new Error('附件仍在上传，请稍候');

    const fileIds = await prepareAttachments();
    const response = await nativeFetch(input, {
      ...init,
      body: injectFileIds(init.body, fileIds),
    });

    if (response.ok) {
      try {
        const result = unwrapTrpc(await response.clone().json());
        if (result?.success) clearAfterAccepted();
      } catch {
        // The main runtime owns response validation and error presentation.
      }
    }
    return response;
  };

  if (badge) badge.textContent = '第三阶段 · 原生代理与附件';
  renderItems();
})();
