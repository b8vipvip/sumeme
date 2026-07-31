(() => {
  'use strict';

  function installAdminBootstrapProtection() {
    const nativeFetch = window.fetch.bind(window);
    const form = document.getElementById('adminAuthForm');
    const displayField = document.getElementById('displayNameField');
    if (!form || !displayField) return;

    const label = document.createElement('label');
    label.id = 'bootstrapTokenField';
    label.hidden = displayField.hidden;
    const caption = document.createElement('span');
    caption.textContent = '一次性初始化密钥';
    const input = document.createElement('input');
    input.id = 'adminBootstrapToken';
    input.type = 'password';
    input.autocomplete = 'off';
    input.placeholder = '服务器 GATEWAY_ADMIN_TOKEN 或 SUMEME_ADMIN_BOOTSTRAP_TOKEN';
    const help = document.createElement('small');
    help.textContent = '只在创建首个管理员时校验，之后日常登录不再需要。';
    label.append(caption, input, help);
    form.insertBefore(label, displayField);

    const syncVisibility = () => {
      label.hidden = displayField.hidden;
      input.required = !displayField.hidden;
      if (displayField.hidden) input.value = '';
    };
    new MutationObserver(syncVisibility).observe(displayField, {
      attributes: true,
      attributeFilter: ['hidden'],
    });
    syncVisibility();

    window.fetch = (resource, options = {}) => {
      let url;
      try {
        url = new URL(typeof resource === 'string' ? resource : resource.url, location.origin);
      } catch {
        return nativeFetch(resource, options);
      }
      if (
        url.pathname === '/api/admin/bootstrap'
        && String(options.method || 'GET').toUpperCase() === 'POST'
      ) {
        const headers = new Headers(options.headers || {});
        headers.set('X-SuMeMe-Bootstrap-Token', input.value);
        return nativeFetch(resource, { ...options, headers });
      }
      return nativeFetch(resource, options);
    };
  }

  if (location.pathname.startsWith('/admin')) {
    window.addEventListener('DOMContentLoaded', installAdminBootstrapProtection);
    return;
  }

  const clientMeta = {
    overview: ['首页', '对话、资料与长期记忆'],
    chat: ['对话', '使用当前账户的代理、工具与附件'],
    memories: ['记忆', '浏览、搜索与管理长期记忆'],
    files: ['资料与对象', '当前账户的附件与私有对象'],
    vaults: ['Vault', '查看当前存储策略'],
    models: ['模型选择', '可用模型由服务器统一提供'],
    operations: ['关于', 'Web 客户端和服务状态'],
    settings: ['偏好设置', '账户、外观与客户端偏好'],
  };

  function refreshHeading() {
    const page = location.hash.slice(1) || 'overview';
    const meta = clientMeta[page] || clientMeta.overview;
    const title = document.getElementById('pageTitle');
    const subtitle = document.getElementById('pageSubtitle');
    if (title) title.textContent = meta[0];
    if (subtitle) subtitle.textContent = meta[1];
  }

  function applyClientBranding() {
    document.title = 'SuMeMe · Web 客户端';
    const brandDetail = document.querySelector('.brand small');
    if (brandDetail) brandDetail.textContent = '个人记忆 Web 客户端';
    const navLabels = {
      overview: '首页',
      chat: '对话',
      memories: '记忆',
      files: '资料与对象',
      vaults: 'Vault',
      models: '模型选择',
      operations: '关于',
      settings: '偏好设置',
    };
    document.querySelectorAll('.nav-item[data-page]').forEach((node) => {
      const label = navLabels[node.dataset.page];
      const icon = node.querySelector('span');
      if (label && icon) {
        node.replaceChildren(icon, document.createTextNode(label));
      }
    });
    const authDescription = document.getElementById('authDescription');
    if (authDescription) {
      authDescription.textContent = '登录后使用对话、长期记忆、资料与 Vault。API、模型和存储配置由管理员在 /admin 统一维护。';
    }
  }

  async function applyRegistrationPolicy() {
    try {
      const response = await fetch('/api/client/config', {
        credentials: 'include',
        headers: { Accept: 'application/json' },
      });
      if (!response.ok) return;
      const config = await response.json();
      const switcher = document.getElementById('authModeButton');
      if (switcher && config.registration_enabled === false) switcher.hidden = true;
    } catch {
      // Authentication remains usable when the public configuration check fails.
    }
  }

  window.addEventListener('hashchange', refreshHeading);
  window.addEventListener('DOMContentLoaded', () => {
    applyClientBranding();
    refreshHeading();
    applyRegistrationPolicy();
  });
})();
