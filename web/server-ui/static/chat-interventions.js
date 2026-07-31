(() => {
  const composerShell = document.querySelector('.chat-composer-shell');
  const messageListNode = document.getElementById('messageList');
  if (!composerShell || !messageListNode) return;

  const chainedFetch = window.fetch.bind(window);
  const terminalStatuses = new Set([
    'aborted',
    'cancelled',
    'canceled',
    'completed',
    'done',
    'error',
    'failed',
    'interrupted',
    'success',
  ]);
  const waitingStatuses = new Set([
    'human_approve_required',
    'human_input_required',
    'waiting_for_human',
    'waitingForHuman',
  ]);

  const state = {
    active: null,
    busy: false,
    monitorVersion: 0,
    pending: [],
    transcript: [],
  };

  const panel = document.createElement('section');
  panel.className = 'intervention-panel';
  panel.id = 'chatInterventionPanel';
  panel.hidden = true;

  const panelHeader = document.createElement('header');
  panelHeader.className = 'intervention-panel-header';
  const panelHeading = document.createElement('div');
  const eyebrow = document.createElement('span');
  eyebrow.className = 'intervention-eyebrow';
  eyebrow.textContent = 'HUMAN IN THE LOOP';
  const title = document.createElement('h3');
  title.textContent = '需要你的确认';
  const description = document.createElement('p');
  description.textContent = 'LobeHub 已暂停代理执行，等待明确批准、拒绝或人工输入。';
  panelHeading.append(eyebrow, title, description);
  const counter = document.createElement('span');
  counter.className = 'intervention-counter';
  counter.textContent = '0 项';
  panelHeader.append(panelHeading, counter);

  const panelBody = document.createElement('div');
  panelBody.className = 'intervention-list';
  panel.append(panelHeader, panelBody);
  composerShell.parentElement.insertBefore(panel, composerShell);

  function setRunStatus(text, kind = '') {
    const node = document.getElementById('chatRunStatus');
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
  }

  function sleep(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  function unwrapTrpc(payload) {
    const envelope = Array.isArray(payload) ? payload[0] : payload;
    const trpcError = envelope?.error?.json || envelope?.error;
    if (trpcError) {
      const message = trpcError.message || trpcError.data?.message || 'LobeHub 人工干预接口失败';
      const error = new Error(message);
      error.status = trpcError.data?.httpStatus;
      throw error;
    }
    const data = envelope?.result?.data;
    if (data && Object.prototype.hasOwnProperty.call(data, 'json')) return data.json;
    if (data !== undefined) return data;
    return envelope;
  }

  async function readResponse(response, fallback) {
    const text = await response.text();
    let payload;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      const error = new Error(`${fallback} (${response.status})`);
      error.status = response.status;
      throw error;
    }
    if (!response.ok) {
      try {
        unwrapTrpc(payload);
      } catch (error) {
        error.status ||= response.status;
        throw error;
      }
      const error = new Error(`${fallback} (${response.status})`);
      error.status = response.status;
      throw error;
    }
    return unwrapTrpc(payload);
  }

  async function queryUrl(url) {
    const response = await chainedFetch(url, {
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
    return readResponse(response, '无法读取 LobeHub 人工干预状态');
  }

  async function trpcQuery(procedure, input = {}) {
    const single = encodeURIComponent(JSON.stringify({ json: input }));
    try {
      return await queryUrl(`/trpc/${procedure}?input=${single}`);
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      const batch = encodeURIComponent(JSON.stringify({ 0: { json: input } }));
      return queryUrl(`/trpc/${procedure}?batch=1&input=${batch}`);
    }
  }

  async function postUrl(url, body) {
    const response = await chainedFetch(url, {
      body: JSON.stringify(body),
      credentials: 'include',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
      },
      method: 'POST',
    });
    return readResponse(response, '无法提交 LobeHub 人工干预');
  }

  async function trpcMutation(procedure, input = {}) {
    try {
      return await postUrl(`/trpc/${procedure}`, { json: input });
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      return postUrl(`/trpc/${procedure}?batch=1`, { 0: { json: input } });
    }
  }

  function collection(value, keys) {
    if (Array.isArray(value)) return value;
    for (const key of keys) {
      if (Array.isArray(value?.[key])) return value[key];
    }
    return [];
  }

  function parseExecInput(body) {
    try {
      const value = JSON.parse(body || '{}');
      return value?.json || value?.[0]?.json || {};
    } catch {
      return {};
    }
  }

  function statusName(value) {
    return String(value?.currentState?.status || value?.status || value?.state || '');
  }

  function operationContext(status, fallback = {}) {
    const current = status?.currentState || {};
    const metadata = current.metadata || status?.metadata || {};
    return {
      agentId: metadata.agentId || fallback.agentId || '',
      operationId: fallback.operationId || status?.operationId || current.operationId || '',
      topicId: metadata.topicId || fallback.topicId || '',
    };
  }

  function messagePlugin(message) {
    return message?.plugin || message?.pluginState?.plugin || message?.metadata?.plugin || {};
  }

  function callId(call) {
    return String(call?.id || call?.toolCallId || call?.tool_call_id || '');
  }

  function callName(call) {
    const identifier = call?.identifier || call?.pluginIdentifier || call?.type || 'tool';
    const apiName = call?.apiName || call?.name || call?.function?.name || 'call';
    return `${identifier} · ${apiName}`;
  }

  function callArguments(call) {
    const candidate = call?.arguments ?? call?.function?.arguments ?? call?.args ?? {};
    if (typeof candidate === 'string') {
      try { return JSON.stringify(JSON.parse(candidate), null, 2); } catch { return candidate; }
    }
    try { return JSON.stringify(candidate, null, 2); } catch { return String(candidate); }
  }

  function findToolMessageId(call) {
    if (call?.toolMessageId || call?.messageId) return call.toolMessageId || call.messageId;
    const targetCallId = callId(call);
    const message = state.transcript.find((item) => {
      if (item?.role !== 'tool') return false;
      const plugin = messagePlugin(item);
      return String(plugin.toolCallId || item.toolCallId || '') === targetCallId;
    });
    return message?.id || '';
  }

  function createButton(label, className, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = className;
    button.textContent = label;
    button.addEventListener('click', handler);
    return button;
  }

  function setBusy(busy) {
    state.busy = busy;
    panel.querySelectorAll('button, input, textarea, select').forEach((node) => {
      node.disabled = busy;
    });
    panel.classList.toggle('busy', busy);
  }

  function humanText(value, fallback) {
    if (typeof value === 'string') return value;
    if (!value || typeof value !== 'object') return fallback;
    return value.prompt || value.question || value.message || value.description || value.title || fallback;
  }

  function humanOptions(value) {
    if (!value || typeof value !== 'object') return [];
    const options = value.options || value.choices || value.items || value.selections;
    if (!Array.isArray(options)) return [];
    return options.map((option, index) => {
      if (typeof option === 'string' || typeof option === 'number') {
        return { label: String(option), value: option };
      }
      return {
        label: String(option?.label || option?.title || option?.name || option?.value || `选项 ${index + 1}`),
        value: option?.value ?? option?.id ?? option?.label ?? option,
      };
    });
  }

  async function submitIntervention(pending, payload, buttonLabel) {
    if (state.busy) return;
    setBusy(true);
    setRunStatus(`${buttonLabel}，正在恢复 LobeHub 代理…`);
    try {
      const result = await trpcMutation('aiAgent.processHumanIntervention', {
        operationId: pending.operationId,
        stepIndex: Number.isFinite(pending.stepCount) ? pending.stepCount : 0,
        ...payload,
      });
      if (!result?.success) throw new Error(result?.message || 'LobeHub 未确认人工干预结果');
      setRunStatus('人工决定已提交，LobeHub 代理继续执行', 'success');
      panel.hidden = true;
      state.pending = [];
      renderPending();
      state.monitorVersion += 1;
      monitorOperation({ ...state.active, operationId: pending.operationId });
    } catch (error) {
      setRunStatus(error.message, 'error');
    } finally {
      setBusy(false);
    }
  }

  function renderToolCall(pending, call, index) {
    const card = document.createElement('article');
    card.className = 'intervention-card tool-approval';

    const header = document.createElement('div');
    header.className = 'intervention-card-header';
    const heading = document.createElement('div');
    const kind = document.createElement('span');
    kind.className = 'intervention-kind';
    kind.textContent = `工具调用 ${index + 1}`;
    const name = document.createElement('h4');
    name.textContent = callName(call);
    heading.append(kind, name);
    const callIdentifier = document.createElement('code');
    callIdentifier.textContent = callId(call) || 'tool-call';
    header.append(heading, callIdentifier);

    const argumentsBlock = document.createElement('pre');
    argumentsBlock.className = 'intervention-arguments';
    argumentsBlock.textContent = callArguments(call);

    const reason = document.createElement('textarea');
    reason.className = 'intervention-reason';
    reason.rows = 2;
    reason.placeholder = '拒绝原因（可选）';

    const actions = document.createElement('div');
    actions.className = 'intervention-actions';
    const toolMessageId = findToolMessageId(call);
    const approve = createButton('批准执行', 'button primary intervention-approve', () => {
      submitIntervention(pending, {
        action: 'approve',
        data: { approvedToolCall: call },
        toolMessageId,
      }, '已批准工具调用');
    });
    approve.disabled = !toolMessageId;
    approve.title = toolMessageId ? '明确允许 LobeHub 执行此工具' : '未找到对应的 LobeHub 工具消息，暂不能批准';

    const rejectContinue = createButton('拒绝并让 AI 继续', 'button secondary', () => {
      submitIntervention(pending, {
        action: 'reject_continue',
        reason: reason.value.trim() || undefined,
        toolMessageId,
      }, '已拒绝工具调用');
    });
    rejectContinue.disabled = !toolMessageId;

    const reject = createButton('拒绝并停止', 'button danger-outline', () => {
      submitIntervention(pending, {
        action: 'reject',
        reason: reason.value.trim() || undefined,
        toolMessageId,
      }, '已拒绝工具调用');
    });
    reject.disabled = !toolMessageId;
    actions.append(approve, rejectContinue, reject);

    card.append(header, argumentsBlock);
    if (!toolMessageId) {
      const warning = document.createElement('p');
      warning.className = 'intervention-warning';
      warning.textContent = '尚未从消息记录中定位到对应工具消息。请等待片刻或刷新会话，系统不会在缺少关联 ID 时自动批准。';
      card.appendChild(warning);
    }
    card.append(reason, actions);
    return card;
  }

  function renderHumanPrompt(pending) {
    const card = document.createElement('article');
    card.className = 'intervention-card human-prompt';
    const kind = document.createElement('span');
    kind.className = 'intervention-kind';
    kind.textContent = '人工输入';
    const heading = document.createElement('h4');
    heading.textContent = humanText(pending.pendingHumanPrompt, 'LobeHub 代理需要你的补充信息');
    const input = document.createElement('textarea');
    input.className = 'intervention-input';
    input.rows = 3;
    input.placeholder = '输入回复后继续代理执行';
    const actions = document.createElement('div');
    actions.className = 'intervention-actions';
    const submit = createButton('提交并继续', 'button primary', () => {
      const value = input.value.trim();
      if (!value) {
        input.focus();
        setRunStatus('请输入内容后再继续', 'error');
        return;
      }
      submitIntervention(pending, { action: 'input', data: { input: value } }, '已提交人工输入');
    });
    actions.appendChild(submit);
    card.append(kind, heading, input, actions);
    return card;
  }

  function renderHumanSelect(pending) {
    const card = document.createElement('article');
    card.className = 'intervention-card human-select';
    const kind = document.createElement('span');
    kind.className = 'intervention-kind';
    kind.textContent = '人工选择';
    const heading = document.createElement('h4');
    heading.textContent = humanText(pending.pendingHumanSelect, '请选择一个选项');
    const options = humanOptions(pending.pendingHumanSelect);
    let control;
    if (options.length) {
      control = document.createElement('select');
      control.className = 'intervention-select';
      options.forEach((option, index) => {
        const node = document.createElement('option');
        node.value = String(index);
        node.textContent = option.label;
        control.appendChild(node);
      });
      control.dataset.mode = 'options';
      control._sumemeOptions = options;
    } else {
      control = document.createElement('input');
      control.className = 'intervention-input';
      control.type = 'text';
      control.placeholder = '输入选择值';
      control.dataset.mode = 'text';
    }
    const actions = document.createElement('div');
    actions.className = 'intervention-actions';
    const submit = createButton('确认选择', 'button primary', () => {
      let selection;
      if (control.dataset.mode === 'options') {
        selection = control._sumemeOptions?.[Number(control.value)]?.value;
      } else {
        selection = control.value.trim();
      }
      if (selection === undefined || selection === null || selection === '') {
        control.focus();
        setRunStatus('请选择或输入一个值', 'error');
        return;
      }
      submitIntervention(pending, { action: 'select', data: { selection } }, '已提交人工选择');
    });
    actions.appendChild(submit);
    card.append(kind, heading, control, actions);
    return card;
  }

  function renderPending() {
    panelBody.replaceChildren();
    const count = state.pending.reduce((total, pending) => {
      if (pending.type === 'tool_approval') return total + Math.max(1, collection(pending.pendingToolsCalling, []).length);
      return total + 1;
    }, 0);
    counter.textContent = `${count} 项`;
    panel.hidden = count === 0;
    if (!count) return;

    state.pending.forEach((pending) => {
      if (pending.type === 'tool_approval') {
        const calls = collection(pending.pendingToolsCalling, []);
        if (calls.length) calls.forEach((call, index) => panelBody.appendChild(renderToolCall(pending, call, index)));
        else {
          const unavailable = document.createElement('article');
          unavailable.className = 'intervention-card';
          unavailable.textContent = 'LobeHub 报告需要工具审批，但没有返回工具调用详情。系统不会自动批准。';
          panelBody.appendChild(unavailable);
        }
      } else if (pending.type === 'human_prompt') {
        panelBody.appendChild(renderHumanPrompt(pending));
      } else if (pending.type === 'human_select') {
        panelBody.appendChild(renderHumanSelect(pending));
      }
    });
  }

  async function loadTranscript(topicId) {
    if (!topicId) return [];
    const transcript = await trpcQuery('topic.getTopicTranscript', {
      includeMessages: true,
      limit: 300,
      offset: 0,
      topicId,
    });
    return collection(transcript, ['items', 'messages', 'data']);
  }

  async function loadPending(operationId, topicId) {
    const [pendingResult, transcript] = await Promise.all([
      trpcQuery('aiAgent.getPendingInterventions', { operationId }),
      loadTranscript(topicId).catch(() => []),
    ]);
    state.transcript = transcript;
    state.pending = collection(pendingResult, ['pendingInterventions']).filter(
      (item) => item?.operationId === operationId,
    );
    renderPending();
    return state.pending;
  }

  async function monitorOperation(context) {
    if (!context?.operationId) return;
    const version = ++state.monitorVersion;
    state.active = { ...(state.active || {}), ...context };

    for (let attempt = 0; attempt < 360; attempt += 1) {
      if (version !== state.monitorVersion) return;
      try {
        const status = await trpcQuery('aiAgent.getOperationStatus', {
          historyLimit: 4,
          includeHistory: false,
          operationId: context.operationId,
        });
        if (version !== state.monitorVersion) return;
        state.active = operationContext(status, state.active);
        const name = statusName(status);

        if (waitingStatuses.has(name)) {
          const pending = await loadPending(context.operationId, state.active.topicId);
          if (pending.length) {
            setRunStatus('LobeHub 代理已暂停，等待你的明确决定', 'warning');
          }
        } else if (terminalStatuses.has(name) || status?.isCompleted || status?.hasError) {
          state.pending = [];
          renderPending();
          return;
        } else if (!state.busy && !state.pending.length) {
          panel.hidden = true;
        }
      } catch {
        // The existing chat runtime owns the primary error display. This monitor
        // is intentionally best-effort so it never blocks ordinary chat.
      }
      await sleep(1500);
    }
  }

  async function recoverPendingForCurrentUser() {
    try {
      const response = await chainedFetch('/api/auth/get-session', { credentials: 'include' });
      if (!response.ok) return;
      const session = await response.json();
      const userId = session?.user?.id;
      if (!userId) return;
      const result = await trpcQuery('aiAgent.getPendingInterventions', { userId });
      const pending = collection(result, ['pendingInterventions']);
      if (!pending.length) return;
      const newest = [...pending].sort((left, right) => String(right.lastModified).localeCompare(String(left.lastModified)))[0];
      const status = await trpcQuery('aiAgent.getOperationStatus', {
        historyLimit: 4,
        includeHistory: false,
        operationId: newest.operationId,
      });
      monitorOperation(operationContext(status, { operationId: newest.operationId }));
    } catch {
      // A stale/expired operation should not affect page startup.
    }
  }

  window.fetch = async (input, init = {}) => {
    const requestUrl = typeof input === 'string' ? input : input?.url || '';
    let parsed;
    try { parsed = new URL(requestUrl, window.location.origin); } catch { parsed = null; }
    const isExecution = parsed?.pathname === '/trpc/aiAgent.execAgent'
      && String(init.method || 'GET').toUpperCase() === 'POST';

    const response = await chainedFetch(input, init);
    if (!isExecution || !response.ok) return response;

    try {
      const result = unwrapTrpc(await response.clone().json());
      if (result?.success && result?.operationId) {
        const request = parseExecInput(init.body);
        monitorOperation({
          agentId: result.agentId || request.agentId || '',
          operationId: result.operationId,
          topicId: result.topicId || request.appContext?.topicId || '',
        });
      }
    } catch {
      // Preserve the original response for the main chat runtime.
    }
    return response;
  };

  recoverPendingForCurrentUser();
})();
