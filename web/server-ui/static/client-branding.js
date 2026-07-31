(() => {
  'use strict';

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
    refreshHeading();
    applyRegistrationPolicy();
  });
})();
