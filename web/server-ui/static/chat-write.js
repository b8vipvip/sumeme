(() => {
  const runtime = {
    agents: [],
    agentsLoaded: false,
    activeOperationId: null,
    sending: false,
    pollVersion: 0,
  };

  const terminalStatuses = new Set([
    'aborted',
    'cancelled',
    'canceled',
    'completed',
    'done',
    'error',
    'failed',
    'success',
  ]);
  const waitingStatuses = new Set([
    'human_approve_required',
    'human_input_required',
    'waiting_for_human',
    'waitingForHuman',
  ]);

  function collection(value, keys) {
    if (Array.isArray(value)) return value;
    for (const key of keys) {
      if (Array.isArray(value?.[key])) return value[key];
    }
    return [];
  }

  function statusName(value) {
    return String(
      value?.currentState?.status
      || value?.status
      || value?.state
      || '',
    );
  }

  function sleep(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  async function postTrpc(url, body) {
    const response = await fetch(url, {
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
      const error = new Error(
        response.headers.get('content-type')?.includes('text/html')
          ? 'LobeHub 写接口返回了网页而不是 JSON，请检查 /trpc 代理'
          : `无法解析 LobeHub 写接口响应 (${response.status})`,
      );
      error.status = response.status;
      throw error;
    }

    if (!response.ok) {
      let message = `LobeHub 写接口请求失败 (${response.status})`;
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

  async function trpcMutation(procedure, input = {}) {
    try {
      return await postTrpc(`/trpc/${procedure}`, { json: input });
    } catch (singleError) {
      if (![400, 404, 405].includes(singleError.status)) throw singleError;
      return postTrpc(`/trpc/${procedure}?batch=1`, { 0: { json: input } });
    }
  }

  function activeTopic() {
    return topics.find((topic) => topic.id === activeTopicId);
  }

  function topicAgentId(topic) {
    return topic?.agentId || topic?.assistantId || topic?.agent?.id || '';
  }

  function agentTitle(agent) {
    return String(agent?.title || agent?.name || agent?.slug || '未命名代理').trim();
  }

  function setRunStatus(text, kind = '') {
    const node = document.getElementById('chatRunStatus');
    if (!node) return;
    node.textContent = text;
    node.dataset.kind = kind;
  }

  function setSending(sending) {
    runtime.sending = sending;
    const textarea = document.getElementById('chatMessageInput');
    const button = document.getElementById('sendMessageButton');
    const newButton = document.getElementById('newConversationButton');
    const select = document.getElementById('chatAgentSelect');
    if (textarea) textarea.disabled = sending;
    if (button) {
      button.disabled = sending || !textarea?.value.trim();
      button.textContent = sending ? '执行中…' : '发送';
    }
    if (newButton) newButton.disabled = sending;
    if (select) select.disabled = sending || Boolean(activeTopicId && topicAgentId(activeTopic()));
  }

  function refreshSendButton() {
    const textarea = document.getElementById('chatMessageInput');
    const button = document.getElementById('sendMessageButton');
    if (button) button.disabled = runtime.sending || !textarea?.value.trim();
  }

  function renderAgentOptions() {
    const select = document.getElementById('chatAgentSelect');
    if (!select) return;
    const previous = select.value;
    select.replaceChildren();

    if (!runtime.agents.length) {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = runtime.agentsLoaded ? '没有可用代理' : '正在读取代理…';
      select.appendChild(option);
      select.disabled = true;
      return;
    }

    runtime.agents.forEach((agent) => {
      const option = document.createElement('option');
      option.value = agent.id;
      option.textContent = agentTitle(agent);
      select.appendChild(option);
    });

    const boundAgentId = topicAgentId(activeTopic());
    const requested = boundAgentId || previous;
    if (requested && runtime.agents.some((agent) => agent.id === requested)) {
      select.value = requested;
    } else {
      select.selectedIndex = 0;
    }
    select.disabled = runtime.sending || Boolean(activeTopicId && boundAgentId);
  }

  async function loadAgents({ force = false } = {}) {
    if (runtime.agentsLoaded && !force) {
      renderAgentOptions();
      return;
    }
    runtime.agentsLoaded = false;
    renderAgentOptions();
    try {
      const payload = await trpcQuery('agent.queryAgents', { limit: 100, offset: 0 });
      runtime.agents = collection(payload, ['items', 'agents', 'data'])
        .filter((agent) => agent?.id)
        .sort((left, right) => agentTitle(left).localeCompare(agentTitle(right), 'zh-CN'));
      runtime.agentsLoaded = true;
      renderAgentOptions();
      setRunStatus(runtime.agents.length ? 'LobeHub 原生代理运行时已连接' : '当前账户没有可用代理');
    } catch (error) {
      runtime.agents = [];
      runtime.agentsLoaded = false;
      renderAgentOptions();
      setRunStatus(`代理列表读取失败：${error.message}`, 'error');
    }
  }

  function updateComposerContext(topic) {
    renderAgentOptions();
    const hint = document.getElementById('chatComposerHint');
    if (!hint) return;
    const agentId = topicAgentId(topic);
    if (topic?.id) {
      hint.textContent = agentId
        ? '消息将由该会话绑定的 LobeHub 代理完整执行。'
        : '该旧会话未返回代理标识，请从右侧选择一个代理后发送。';
    } else {
      hint.textContent = '发送第一条消息时，LobeHub 会创建 Topic，并保存用户与助手消息。';
    }
  }

  async function refreshTranscript(topicId, { keepScroll = false } = {}) {
    if (!topicId) return [];
    const previousScroll = messageList.scrollTop;
    const transcript = await trpcQuery('topic.getTopicTranscript', {
      includeMessages: true,
      limit: 300,
      offset: 0,
      topicId,
    });
    const messages = transcriptCollection(transcript);
    renderMessages(messages);
    if (keepScroll) messageList.scrollTop = previousScroll;
    else messageList.scrollTop = messageList.scrollHeight;
    return messages;
  }

  function operationError(status) {
    const candidate = status?.currentState?.error || status?.error;
    if (!candidate) return '';
    if (typeof candidate === 'string') return candidate;
    return candidate.message || candidate.error?.message || JSON.stringify(candidate);
  }

  async function pollOperation(result) {
    const version = ++runtime.pollVersion;
    runtime.activeOperationId = result.operationId;
    let consecutiveStatusFailures = 0;

    for (let attempt = 0; attempt < 240; attempt += 1) {
      if (version !== runtime.pollVersion) return;
      let status = null;
      try {
        status = await trpcQuery('aiAgent.getOperationStatus', {
          historyLimit: 6,
          includeHistory: false,
          operationId: result.operationId,
        });
        consecutiveStatusFailures = 0;
      } catch (error) {
        consecutiveStatusFailures += 1;
        if (consecutiveStatusFailures >= 5) {
          setRunStatus(`执行状态暂时不可读：${error.message}`, 'warning');
        }
      }

      try {
        await refreshTranscript(result.topicId, { keepScroll: attempt > 0 });
      } catch {
        // The topic can be committed a fraction later than execAgent returns.
      }

      const currentStatus = statusName(status);
      if (waitingStatuses.has(currentStatus)) {
        setRunStatus('代理正在等待工具审批或人工输入；审批界面将在下一阶段接入。', 'warning');
      } else if (currentStatus) {
        setRunStatus(`LobeHub 代理状态：${currentStatus}`);
      } else {
        setRunStatus('LobeHub 代理正在执行…');
      }

      const failed = Boolean(status?.hasError) || ['error', 'failed'].includes(currentStatus);
      const completed = Boolean(status?.isCompleted) || terminalStatuses.has(currentStatus);
      if (failed) {
        throw new Error(operationError(status) || `代理执行失败：${currentStatus || 'unknown'}`);
      }
      if (completed) return;
      await sleep(1250);
    }

    setRunStatus('代理仍在后台执行，页面会保留本次会话，可稍后重新读取。', 'warning');
  }

  async function sendPrompt(event) {
    event.preventDefault();
    if (runtime.sending) return;

    const textarea = document.getElementById('chatMessageInput');
    const select = document.getElementById('chatAgentSelect');
    const prompt = textarea?.value.trim() || '';
    const topic = activeTopic();
    const agentId = topicAgentId(topic) || select?.value || '';

    if (!prompt) return;
    if (!agentId) {
      setRunStatus('请先选择一个 LobeHub 代理。', 'error');
      select?.focus();
      return;
    }

    const originalPrompt = textarea.value;
    setSending(true);
    setRunStatus('正在交给 LobeHub 原生代理运行时…');
    chatConnectionLabel.textContent = '正在执行代理';

    try {
      const input = {
        agentId,
        appContext: {
          scope: 'main',
          ...(activeTopicId ? { topicId: activeTopicId } : {}),
        },
        autoStart: true,
        prompt,
        trigger: 'chat',
      };
      const result = await trpcMutation('aiAgent.execAgent', input);
      if (!result?.success || !result.topicId || !result.operationId) {
        throw new Error(result?.error || result?.message || 'LobeHub 未返回有效的代理执行结果');
      }

      activeTopicId = result.topicId;
      runtime.activeOperationId = result.operationId;
      textarea.value = '';
      refreshSendButton();
      messageHeader.hidden = false;
      activeTopicTitle.textContent = topic?.title || prompt.slice(0, 80) || '新对话';
      activeTopicMeta.textContent = `${formatDate(result.createdAt || result.timestamp)} · ${String(result.topicId).slice(0, 12)}`;
      updateComposerContext({ ...(topic || {}), agentId, id: result.topicId });
      await refreshTranscript(result.topicId).catch(() => {});
      await pollOperation(result);

      setRunStatus('LobeHub 代理执行完成', 'success');
      chatConnectionLabel.textContent = 'LobeHub 原生代理已完成';
      topicsLoaded = false;
      await loadTopics({ force: true });
      showToast('消息已由 LobeHub 代理完成');
    } catch (error) {
      textarea.value = originalPrompt;
      refreshSendButton();
      setRunStatus(error.message, 'error');
      chatConnectionLabel.textContent = '代理执行异常';
      if (activeTopicId) await refreshTranscript(activeTopicId).catch(() => {});
    } finally {
      runtime.activeOperationId = null;
      setSending(false);
      textarea.focus();
    }
  }

  function startNewConversation() {
    if (runtime.sending) return;
    runtime.pollVersion += 1;
    runtime.activeOperationId = null;
    activeTopicId = null;
    transcriptLoadVersion += 1;
    renderTopics();
    messageHeader.hidden = false;
    activeTopicTitle.textContent = '新对话';
    activeTopicMeta.textContent = '选择代理并发送第一条消息';
    messageCountLabel.textContent = '0 条消息';
    renderMessageState({
      icon: '✦',
      title: '开始新的 LobeHub 对话',
      message: '消息会通过 LobeHub aiAgent.execAgent 完整执行，并写回原会话数据库。',
    });
    updateComposerContext(null);
    setRunStatus('准备创建新的 LobeHub Topic');
    document.getElementById('chatMessageInput')?.focus();
  }

  function installUi() {
    const badge = document.querySelector('.read-only-badge');
    if (badge) {
      badge.textContent = '第二阶段 · LobeHub 原生代理';
      badge.classList.add('runtime-badge');
    }

    const headingActions = document.querySelector('.chat-heading-actions');
    if (headingActions && !document.getElementById('newConversationButton')) {
      const newButton = document.createElement('button');
      newButton.className = 'button primary';
      newButton.id = 'newConversationButton';
      newButton.type = 'button';
      newButton.textContent = '＋ 新对话';
      newButton.addEventListener('click', startNewConversation);
      headingActions.insertBefore(newButton, document.getElementById('reloadTopicsButton'));
    }

    if (messageHeader && !document.getElementById('chatAgentSelect')) {
      const actions = document.createElement('div');
      actions.className = 'message-header-actions';
      const label = document.createElement('label');
      label.className = 'agent-select-field';
      const caption = document.createElement('span');
      caption.textContent = '代理';
      const select = document.createElement('select');
      select.id = 'chatAgentSelect';
      select.setAttribute('aria-label', '选择 LobeHub 代理');
      label.append(caption, select);
      actions.append(label, messageCountLabel);
      messageHeader.appendChild(actions);
    }

    const oldFooter = document.querySelector('.chat-readonly-footer');
    if (oldFooter) {
      const wrapper = document.createElement('div');
      wrapper.className = 'chat-composer-shell';
      wrapper.innerHTML = `
        <form class="chat-composer" id="chatComposer">
          <textarea id="chatMessageInput" rows="3" maxlength="30000" placeholder="发送消息给 LobeHub 代理；Enter 发送，Shift+Enter 换行"></textarea>
          <div class="chat-composer-actions">
            <div><strong id="chatRunStatus">正在连接 LobeHub 原生代理运行时…</strong><small id="chatComposerHint">读取当前会话代理…</small></div>
            <button class="button primary" id="sendMessageButton" type="submit" disabled>发送</button>
          </div>
        </form>
        <div class="chat-runtime-footer"><span>模型、系统提示、工具、记忆和消息持久化均由 LobeHub 服务端执行。</span><span id="chatRuntimeOperation">原生运行时</span></div>
      `;
      oldFooter.replaceWith(wrapper);

      const form = document.getElementById('chatComposer');
      const textarea = document.getElementById('chatMessageInput');
      form.addEventListener('submit', sendPrompt);
      textarea.addEventListener('input', refreshSendButton);
      textarea.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
          event.preventDefault();
          form.requestSubmit();
        }
      });
    }

    const originalSelectTopic = selectTopic;
    selectTopic = async (topic) => {
      await originalSelectTopic(topic);
      updateComposerContext(topic);
      setRunStatus('可以继续向此 LobeHub 会话发送消息');
    };

    const originalNavigate = navigate;
    navigate = (page) => {
      originalNavigate(page);
      if (page === 'chat') {
        loadAgents();
        updateComposerContext(activeTopic());
      }
    };

    const reloadButton = document.getElementById('reloadTopicsButton');
    reloadButton?.addEventListener('click', () => loadAgents({ force: true }));

    updateComposerContext(activeTopic());
    loadAgents();
  }

  installUi();
})();
