import 'package:flutter/material.dart';

import 'client_state.dart';

class SuMeMeSettingsPage extends StatelessWidget {
  const SuMeMeSettingsPage({super.key, required this.state});

  final SuMeMeClientState state;

  Future<void> _confirmClear(BuildContext context) async {
    final bool? confirmed = await showDialog<bool>(
      context: context,
      builder: (BuildContext context) => AlertDialog(
        icon: const Icon(Icons.delete_sweep_outlined),
        title: const Text('清除当前可见聊天？'),
        content: Text(
          state.hideHistory
              ? '只清除“隐藏历史”开启后产生的当前聊天，之前被隐藏的记录仍会保留。'
              : '本机保存的完整单对话时间线将被清除。服务端长期记忆不会因此删除。',
        ),
        actions: <Widget>[
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
          FilledButton.tonal(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('确认清除'),
          ),
        ],
      ),
    );
    if (confirmed == true) await state.clearVisibleHistory();
  }

  @override
  Widget build(BuildContext context) {
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 860),
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 36),
          children: <Widget>[
            _Section(
              title: '账户',
              children: <Widget>[
                ListTile(
                  leading: CircleAvatar(
                    backgroundColor: colors.primaryContainer,
                    child: Text(
                      (state.user?['name']?.toString() ?? state.user?['email']?.toString() ?? 'S')
                          .characters
                          .first
                          .toUpperCase(),
                    ),
                  ),
                  title: Text(state.user?['name']?.toString() ?? 'SuMeMe 用户'),
                  subtitle: Text(state.user?['email']?.toString() ?? '—'),
                  trailing: OutlinedButton.icon(
                    onPressed: state.signOut,
                    icon: const Icon(Icons.logout_rounded),
                    label: const Text('退出'),
                  ),
                ),
                ListTile(
                  leading: Icon(
                    state.isConnected ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                  ),
                  title: const Text('SuMeMe 服务'),
                  subtitle: const Text('接口、模型和存储配置由服务端统一管理'),
                  trailing: Text(state.isConnected ? '已连接' : '异常'),
                  onTap: state.refreshConnection,
                ),
              ],
            ),
            _Section(
              title: '聊天与记忆',
              children: <Widget>[
                SwitchListTile(
                  secondary: const Icon(Icons.auto_awesome_rounded),
                  title: const Text('长期记忆'),
                  subtitle: const Text('发送消息时召回与你当前问题相关的长期记忆'),
                  value: state.memoryEnabled,
                  onChanged: state.setMemoryEnabled,
                ),
                SwitchListTile(
                  secondary: const Icon(Icons.visibility_off_outlined),
                  title: const Text('隐藏历史对话'),
                  subtitle: const Text('重启或重新登录后不显示旧聊天，也不把旧聊天加入当前上下文'),
                  value: state.hideHistory,
                  onChanged: state.setHideHistory,
                ),
                SwitchListTile(
                  secondary: const Icon(Icons.vertical_align_bottom_rounded),
                  title: const Text('回答时自动滚动'),
                  subtitle: const Text('生成回答时保持视图停留在最新内容'),
                  value: state.autoScroll,
                  onChanged: state.setAutoScroll,
                ),
                ListTile(
                  leading: const Icon(Icons.model_training_outlined),
                  title: const Text('默认模型'),
                  subtitle: Text(state.selectedModel.isEmpty ? '由服务端管理员配置' : state.selectedModel),
                  trailing: state.models.isEmpty
                      ? null
                      : DropdownButton<String>(
                          value: state.models.contains(state.selectedModel)
                              ? state.selectedModel
                              : state.models.first,
                          underline: const SizedBox.shrink(),
                          items: state.models
                              .map((String model) => DropdownMenuItem<String>(
                                    value: model,
                                    child: ConstrainedBox(
                                      constraints: const BoxConstraints(maxWidth: 210),
                                      child: Text(model, overflow: TextOverflow.ellipsis),
                                    ),
                                  ))
                              .toList(growable: false),
                          onChanged: (String? value) {
                            if (value != null) state.selectModel(value);
                          },
                        ),
                ),
              ],
            ),
            _Section(
              title: '外观',
              children: <Widget>[
                SwitchListTile(
                  secondary: const Icon(Icons.dark_mode_outlined),
                  title: const Text('深色模式'),
                  value: state.darkMode,
                  onChanged: state.setDarkMode,
                ),
                ListTile(
                  leading: const Icon(Icons.format_size_rounded),
                  title: const Text('文字大小'),
                  subtitle: Slider(
                    value: state.textScale,
                    min: .9,
                    max: 1.3,
                    divisions: 4,
                    label: '${(state.textScale * 100).round()}%',
                    onChanged: state.setTextScale,
                  ),
                  trailing: Text('${(state.textScale * 100).round()}%'),
                ),
              ],
            ),
            _Section(
              title: '数据与隐私',
              children: <Widget>[
                ListTile(
                  leading: const Icon(Icons.storage_outlined),
                  title: const Text('本机聊天记录'),
                  subtitle: Text(
                    state.hideHistory
                        ? '历史当前被隐藏，但仍安全保留在本机账户作用域中'
                        : '共保存 ${state.timeline.length} 条消息，可持续向上翻阅',
                  ),
                ),
                ListTile(
                  leading: Icon(Icons.delete_outline_rounded, color: colors.error),
                  title: Text('清除可见聊天', style: TextStyle(color: colors.error)),
                  subtitle: const Text('不会删除服务端长期记忆或资料库文件'),
                  onTap: () => _confirmClear(context),
                ),
              ],
            ),
            _Section(
              title: '关于与更新',
              children: <Widget>[
                ListTile(
                  leading: const Icon(Icons.apps_rounded),
                  title: const Text('当前版本'),
                  trailing: Text('${state.currentVersion}+${state.currentBuild}'),
                ),
                ListTile(
                  leading: const Icon(Icons.new_releases_outlined),
                  title: const Text('最新版本'),
                  subtitle: Text(state.updateStatus),
                  trailing: state.latestRelease?.available == true
                      ? Text(state.latestRelease!.version)
                      : null,
                ),
                if (state.latestRelease?.notes.isNotEmpty == true)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(56, 0, 20, 14),
                    child: Text(
                      state.latestRelease!.notes,
                      style: TextStyle(color: colors.onSurfaceVariant, height: 1.5),
                    ),
                  ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                  child: Row(
                    children: <Widget>[
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: state.checkingUpdate ? null : state.checkForUpdates,
                          icon: state.checkingUpdate
                              ? const SizedBox(
                                  width: 18,
                                  height: 18,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.refresh_rounded),
                          label: const Text('检查更新'),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: FilledButton.icon(
                          onPressed: state.latestRelease?.downloadUrl.isNotEmpty == true
                              ? state.openUpdateDownload
                              : null,
                          icon: const Icon(Icons.download_rounded),
                          label: Text(state.hasUpdate ? '手动更新' : '下载安装包'),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.children});

  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
              child: Text(
                title,
                style: TextStyle(
                  fontWeight: FontWeight.w800,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ),
            Card(
              elevation: 0,
              clipBehavior: Clip.antiAlias,
              child: Column(children: children),
            ),
          ],
        ),
      );
}
