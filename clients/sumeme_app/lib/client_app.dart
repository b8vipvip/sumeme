import 'package:flutter/material.dart';

import 'client_api.dart';
import 'client_state.dart';

const List<_Destination> _destinations = <_Destination>[
  _Destination('首页', Icons.home_outlined, Icons.home_rounded),
  _Destination('对话', Icons.forum_outlined, Icons.forum_rounded),
  _Destination('记忆', Icons.auto_awesome_outlined, Icons.auto_awesome_rounded),
  _Destination('资料', Icons.folder_outlined, Icons.folder_rounded),
  _Destination('Vault', Icons.inventory_2_outlined, Icons.inventory_2_rounded),
  _Destination('同步', Icons.sync_outlined, Icons.sync_rounded),
  _Destination('设置', Icons.settings_outlined, Icons.settings_rounded),
];

class _Destination {
  const _Destination(this.label, this.icon, this.selectedIcon);
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

class SuMeMeClientApp extends StatefulWidget {
  const SuMeMeClientApp({super.key});

  @override
  State<SuMeMeClientApp> createState() => _SuMeMeClientAppState();
}

class _SuMeMeClientAppState extends State<SuMeMeClientApp> {
  late final SuMeMeClientState state;

  @override
  void initState() {
    super.initState();
    state = SuMeMeClientState()..initialize();
  }

  @override
  void dispose() {
    state.dispose();
    super.dispose();
  }

  ThemeData _theme(Brightness brightness) {
    final ColorScheme colors = ColorScheme.fromSeed(
      seedColor: const Color(0xFF6558E8),
      brightness: brightness,
      surface: brightness == Brightness.light
          ? const Color(0xFFF7F7FC)
          : const Color(0xFF111218),
    );
    return ThemeData(
      colorScheme: colors,
      useMaterial3: true,
      scaffoldBackgroundColor: colors.surface,
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: colors.outlineVariant),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: colors.surfaceContainerLowest,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (BuildContext context, Widget? child) => MaterialApp(
        title: 'SuMeMe',
        debugShowCheckedModeBanner: false,
        themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
        theme: _theme(Brightness.light),
        darkTheme: _theme(Brightness.dark),
        home: !state.initialized
            ? const _BootScreen()
            : state.loggedIn
                ? _AdaptiveShell(state: state)
                : _LoginScreen(state: state),
      ),
    );
  }
}

class _BootScreen extends StatelessWidget {
  const _BootScreen();

  @override
  Widget build(BuildContext context) => const Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              _Brand(size: 72),
              SizedBox(height: 20),
              Text(
                'SuMeMe',
                style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
              ),
              SizedBox(height: 20),
              SizedBox(width: 220, child: LinearProgressIndicator()),
            ],
          ),
        ),
      );
}

class _LoginScreen extends StatefulWidget {
  const _LoginScreen({required this.state});
  final SuMeMeClientState state;

  @override
  State<_LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<_LoginScreen> {
  final TextEditingController name = TextEditingController();
  final TextEditingController email = TextEditingController();
  final TextEditingController password = TextEditingController();
  bool signup = false;
  bool obscure = true;

  @override
  void dispose() {
    name.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final bool ok = signup
        ? await widget.state.signUp(name.text, email.text, password.text)
        : await widget.state.signIn(email.text, password.text);
    if (!mounted || !ok) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(signup ? '账户创建成功' : '登录成功')),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: <Widget>[
                      const Center(child: _Brand(size: 66)),
                      const SizedBox(height: 18),
                      Text(
                        signup ? '创建 SuMeMe 账户' : '登录 SuMeMe',
                        textAlign: TextAlign.center,
                        style: Theme.of(context)
                            .textTheme
                            .headlineSmall
                            ?.copyWith(fontWeight: FontWeight.w800),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        '客户端只保存安全登录会话。API、模型和云存储由服务器统一配置。',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                      const SizedBox(height: 22),
                      if (signup) ...<Widget>[
                        TextField(
                          controller: name,
                          decoration: const InputDecoration(labelText: '昵称'),
                        ),
                        const SizedBox(height: 12),
                      ],
                      TextField(
                        controller: email,
                        keyboardType: TextInputType.emailAddress,
                        decoration: const InputDecoration(labelText: '邮箱'),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: password,
                        obscureText: obscure,
                        onSubmitted: (_) => _submit(),
                        decoration: InputDecoration(
                          labelText: '密码',
                          suffixIcon: IconButton(
                            onPressed: () =>
                                setState(() => obscure = !obscure),
                            icon: Icon(
                              obscure
                                  ? Icons.visibility_outlined
                                  : Icons.visibility_off_outlined,
                            ),
                          ),
                        ),
                      ),
                      if (widget.state.errorMessage != null) ...<Widget>[
                        const SizedBox(height: 12),
                        Text(
                          widget.state.errorMessage!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ],
                      const SizedBox(height: 18),
                      FilledButton(
                        onPressed:
                            widget.state.authenticating ? null : _submit,
                        child: widget.state.authenticating
                            ? const SizedBox.square(
                                dimension: 20,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : Text(signup ? '创建并登录' : '登录'),
                      ),
                      const SizedBox(height: 8),
                      if (widget.state.registrationEnabled || signup)
                        TextButton(
                          onPressed: () =>
                              setState(() => signup = !signup),
                          child: Text(
                            signup ? '已有账户？返回登录' : '没有账户？创建账户',
                          ),
                        ),
                      const Divider(height: 28),
                      Text(
                        SuMeMeClientApi.serverUrl,
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      );
}

class _AdaptiveShell extends StatelessWidget {
  const _AdaptiveShell({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) =>
            constraints.maxWidth >= 900
                ? _DesktopShell(state: state)
                : _MobileShell(state: state),
      );
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Row(
          children: <Widget>[
            NavigationRail(
              extended: MediaQuery.sizeOf(context).width >= 1180,
              minExtendedWidth: 220,
              selectedIndex: state.selectedIndex,
              onDestinationSelected: state.selectPage,
              leading: const Padding(
                padding: EdgeInsets.fromLTRB(10, 18, 10, 24),
                child: _Brand(size: 44),
              ),
              destinations: _destinations
                  .map(
                    (_Destination item) => NavigationRailDestination(
                      icon: Icon(item.icon),
                      selectedIcon: Icon(item.selectedIcon),
                      label: Text(item.label),
                    ),
                  )
                  .toList(growable: false),
            ),
            const VerticalDivider(width: 1),
            Expanded(
              child: Column(
                children: <Widget>[
                  _TopBar(state: state),
                  if (state.errorMessage != null) _ErrorBanner(state: state),
                  Expanded(child: _PageHost(state: state)),
                ],
              ),
            ),
          ],
        ),
      );
}

class _MobileShell extends StatelessWidget {
  const _MobileShell({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) {
    final int bottomIndex = state.selectedIndex <= 3 ? state.selectedIndex : 4;
    return Scaffold(
      appBar: AppBar(
        title: Text(_destinations[state.selectedIndex].label),
        actions: <Widget>[
          IconButton(
            onPressed: state.refreshConnection,
            icon: Icon(
              state.isConnected ? Icons.cloud_done : Icons.cloud_off,
            ),
          ),
        ],
      ),
      drawer: NavigationDrawer(
        selectedIndex: state.selectedIndex,
        onDestinationSelected: (int value) {
          Navigator.of(context).pop();
          state.selectPage(value);
        },
        children: <Widget>[
          const Padding(
            padding: EdgeInsets.all(24),
            child: Row(
              children: <Widget>[
                _Brand(size: 44),
                SizedBox(width: 12),
                Text(
                  'SuMeMe',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
          ..._destinations.map(
            (_Destination item) => NavigationDrawerDestination(
              icon: Icon(item.icon),
              selectedIcon: Icon(item.selectedIcon),
              label: Text(item.label),
            ),
          ),
        ],
      ),
      body: Column(
        children: <Widget>[
          if (state.errorMessage != null) _ErrorBanner(state: state),
          Expanded(child: _PageHost(state: state)),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: bottomIndex,
        onDestinationSelected: (int value) =>
            state.selectPage(value <= 3 ? value : 6),
        destinations: const <NavigationDestination>[
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            label: '首页',
          ),
          NavigationDestination(
            icon: Icon(Icons.forum_outlined),
            label: '对话',
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            label: '记忆',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            label: '资料',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            label: '设置',
          ),
        ],
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => Container(
        height: 66,
        padding: const EdgeInsets.symmetric(horizontal: 24),
        decoration: BoxDecoration(
          border: Border(
            bottom: BorderSide(
              color: Theme.of(context).colorScheme.outlineVariant,
            ),
          ),
        ),
        child: Row(
          children: <Widget>[
            Expanded(
              child: Text(
                _destinations[state.selectedIndex].label,
                style: Theme.of(context)
                    .textTheme
                    .titleLarge
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
            ),
            Chip(label: Text(state.isConnected ? '服务在线' : '连接异常')),
            const SizedBox(width: 8),
            IconButton(
              onPressed: state.refreshConnection,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
      );
}

class _PageHost extends StatelessWidget {
  const _PageHost({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => IndexedStack(
        index: state.selectedIndex,
        children: <Widget>[
          _HomePage(state: state),
          _ChatPage(state: state),
          _MemoryPage(state: state),
          const _PlaceholderPage(
            icon: Icons.folder_outlined,
            title: '资料库',
            description: '资料上传与管理继续使用服务器统一存储策略。',
          ),
          const _PlaceholderPage(
            icon: Icons.inventory_2_outlined,
            title: 'Vault',
            description: 'Vault 模式由服务端管理员配置，客户端只展示当前可用策略。',
          ),
          const _PlaceholderPage(
            icon: Icons.sync_outlined,
            title: '同步中心',
            description: '设备与同步任务将在可信设备令牌阶段接入。',
          ),
          _SettingsPage(state: state),
        ],
      );
}

class _HomePage extends StatelessWidget {
  const _HomePage({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => _PageScroll(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '个人记忆空间',
              style: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text('对话、保存资料并检索长期记忆。服务接口与密钥由服务器统一管理。'),
            const SizedBox(height: 22),
            Wrap(
              spacing: 14,
              runSpacing: 14,
              children: <Widget>[
                _Metric(
                  icon: Icons.cloud_done_outlined,
                  label: '服务',
                  value: state.isConnected ? '在线' : '异常',
                ),
                _Metric(
                  icon: Icons.person_outline,
                  label: '账户',
                  value: state.user?['email']?.toString() ?? '已登录',
                ),
                _Metric(
                  icon: Icons.smart_toy_outlined,
                  label: '模型',
                  value:
                      state.selectedModel.isEmpty ? '待配置' : state.selectedModel,
                ),
                _Metric(
                  icon: Icons.system_update_outlined,
                  label: '版本',
                  value: state.currentVersion,
                ),
              ],
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: () {
                state.createConversation();
                state.selectPage(1);
              },
              icon: const Icon(Icons.add_comment_outlined),
              label: const Text('开始对话'),
            ),
          ],
        ),
      );
}

class _ChatPage extends StatefulWidget {
  const _ChatPage({required this.state});
  final SuMeMeClientState state;

  @override
  State<_ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends State<_ChatPage> {
  final TextEditingController composer = TextEditingController();

  @override
  void dispose() {
    composer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final Conversation? conversation = widget.state.activeConversation;
    return Column(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: <Widget>[
              FilledButton.icon(
                onPressed: widget.state.createConversation,
                icon: const Icon(Icons.add),
                label: const Text('新对话'),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: DropdownButtonFormField<String>(
                  value: widget.state.models.contains(widget.state.selectedModel)
                      ? widget.state.selectedModel
                      : null,
                  decoration: const InputDecoration(
                    labelText: '模型（由服务端提供）',
                    isDense: true,
                  ),
                  items: widget.state.models
                      .map(
                        (String value) => DropdownMenuItem<String>(
                          value: value,
                          child: Text(value),
                        ),
                      )
                      .toList(),
                  onChanged: (String? value) {
                    if (value != null) widget.state.selectModel(value);
                  },
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: conversation == null || conversation.messages.isEmpty
              ? const _Empty(
                  icon: Icons.forum_outlined,
                  title: '从任何想法开始',
                  description: '消息由服务器统一选择接口和模型，并按当前账户调用长期记忆。',
                )
              : ListView.builder(
                  padding: const EdgeInsets.all(18),
                  itemCount: conversation.messages.length,
                  itemBuilder: (BuildContext context, int index) {
                    final ChatMessage message = conversation.messages[index];
                    final bool user = message.role == 'user';
                    return Align(
                      alignment:
                          user ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        constraints: const BoxConstraints(maxWidth: 760),
                        margin: const EdgeInsets.only(bottom: 12),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: user
                              ? Theme.of(context).colorScheme.primaryContainer
                              : Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Text(
                          message.streaming && message.text.isEmpty
                              ? '正在思考…'
                              : message.text,
                        ),
                      ),
                    );
                  },
                ),
        ),
        Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: <Widget>[
              Expanded(
                child: TextField(
                  controller: composer,
                  minLines: 1,
                  maxLines: 6,
                  decoration: const InputDecoration(hintText: '输入消息…'),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filled(
                onPressed: widget.state.sending
                    ? null
                    : () {
                        final String text = composer.text;
                        composer.clear();
                        widget.state.sendMessage(text);
                      },
                icon: widget.state.sending
                    ? const SizedBox.square(
                        dimension: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.send_rounded),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _MemoryPage extends StatefulWidget {
  const _MemoryPage({required this.state});
  final SuMeMeClientState state;

  @override
  State<_MemoryPage> createState() => _MemoryPageState();
}

class _MemoryPageState extends State<_MemoryPage> {
  final TextEditingController query = TextEditingController();

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => _PageScroll(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '搜索长期记忆',
              style: Theme.of(context)
                  .textTheme
                  .headlineSmall
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 14),
            Row(
              children: <Widget>[
                Expanded(
                  child: TextField(
                    controller: query,
                    decoration: const InputDecoration(
                      hintText: '例如：我上次决定使用哪个模型？',
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton.icon(
                  onPressed: () => widget.state.searchMemory(query.text),
                  icon: const Icon(Icons.search),
                  label: const Text('搜索'),
                ),
              ],
            ),
            const SizedBox(height: 18),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: SelectableText(
                  widget.state.memoryResult.isEmpty
                      ? '搜索结果将在这里显示。'
                      : widget.state.memoryResult,
                ),
              ),
            ),
          ],
        ),
      );
}

class _SettingsPage extends StatelessWidget {
  const _SettingsPage({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => _PageScroll(
        maxWidth: 900,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              '设置',
              style: Theme.of(context)
                  .textTheme
                  .headlineMedium
                  ?.copyWith(fontWeight: FontWeight.w800),
            ),
            const SizedBox(height: 8),
            const Text(
              '客户端不再配置 API Key、中转站、管理员 Token 或服务器模式。相关配置统一位于服务端 /admin。',
            ),
            const SizedBox(height: 18),
            _SettingsCard(
              title: '账户',
              icon: Icons.person_outline,
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text(state.user?['email']?.toString() ?? '已登录'),
                subtitle: Text(state.user?['name']?.toString() ?? 'SuMeMe 用户'),
                trailing: TextButton(
                  onPressed: state.signOut,
                  child: const Text('退出登录'),
                ),
              ),
            ),
            const SizedBox(height: 14),
            _SettingsCard(
              title: '外观与记忆',
              icon: Icons.palette_outlined,
              child: Column(
                children: <Widget>[
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('深色模式'),
                    value: state.darkMode,
                    onChanged: state.setDarkMode,
                  ),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    title: const Text('默认启用长期记忆'),
                    value: state.memoryEnabled,
                    onChanged: state.setMemoryEnabled,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 14),
            _SettingsCard(
              title: '关于与更新',
              icon: Icons.info_outline,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  _KeyValue(
                    label: '当前版本',
                    value: '${state.currentVersion}+${state.currentBuild}',
                  ),
                  _KeyValue(
                    label: '最新版本',
                    value: state.latestRelease?.available == true
                        ? state.latestRelease!.version
                        : '尚未发布',
                  ),
                  _KeyValue(
                    label: '更新通道',
                    value: state.latestRelease?.channel ?? 'stable',
                  ),
                  const _KeyValue(
                    label: '服务地址',
                    value: SuMeMeClientApi.serverUrl,
                  ),
                  const SizedBox(height: 10),
                  Text(state.updateStatus),
                  if ((state.latestRelease?.notes ?? '').isNotEmpty) ...<Widget>[
                    const SizedBox(height: 8),
                    Text(
                      state.latestRelease!.notes,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                  const SizedBox(height: 14),
                  Wrap(
                    spacing: 10,
                    runSpacing: 10,
                    children: <Widget>[
                      OutlinedButton.icon(
                        onPressed: state.checkingUpdate
                            ? null
                            : state.checkForUpdates,
                        icon: state.checkingUpdate
                            ? const SizedBox.square(
                                dimension: 17,
                                child:
                                    CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.refresh),
                        label: const Text('检查更新'),
                      ),
                      FilledButton.icon(
                        onPressed:
                            state.latestRelease?.downloadUrl.isNotEmpty == true
                                ? state.openUpdateDownload
                                : null,
                        icon: const Icon(Icons.download_outlined),
                        label: Text(
                          state.hasUpdate ? '手动更新' : '重新下载安装包',
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      );
}

class _PlaceholderPage extends StatelessWidget {
  const _PlaceholderPage({
    required this.icon,
    required this.title,
    required this.description,
  });
  final IconData icon;
  final String title;
  final String description;

  @override
  Widget build(BuildContext context) => _PageScroll(
        child: _Empty(icon: icon, title: title, description: description),
      );
}

class _PageScroll extends StatelessWidget {
  const _PageScroll({required this.child, this.maxWidth = 1200});
  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) => SingleChildScrollView(
        padding: const EdgeInsets.all(22),
        child: Center(
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth),
            child: child,
          ),
        ),
      );
}

class _SettingsCard extends StatelessWidget {
  const _SettingsCard({
    required this.title,
    required this.icon,
    required this.child,
  });
  final String title;
  final IconData icon;
  final Widget child;

  @override
  Widget build(BuildContext context) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Row(
                children: <Widget>[
                  Icon(icon),
                  const SizedBox(width: 10),
                  Text(
                    title,
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                ],
              ),
              const SizedBox(height: 14),
              child,
            ],
          ),
        ),
      );
}

class _KeyValue extends StatelessWidget {
  const _KeyValue({required this.label, required this.value});
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SizedBox(
              width: 110,
              child: Text(label, style: Theme.of(context).textTheme.bodySmall),
            ),
            Expanded(child: SelectableText(value)),
          ],
        ),
      );
}

class _Metric extends StatelessWidget {
  const _Metric({required this.icon, required this.label, required this.value});
  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: 230,
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Icon(icon),
                const SizedBox(height: 14),
                Text(label),
                const SizedBox(height: 4),
                Text(
                  value,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context)
                      .textTheme
                      .titleMedium
                      ?.copyWith(fontWeight: FontWeight.w800),
                ),
              ],
            ),
          ),
        ),
      );
}

class _Empty extends StatelessWidget {
  const _Empty({
    required this.icon,
    required this.title,
    required this.description,
  });
  final IconData icon;
  final String title;
  final String description;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(
                icon,
                size: 64,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 16),
              Text(
                title,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(description, textAlign: TextAlign.center),
            ],
          ),
        ),
      );
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.state});
  final SuMeMeClientState state;

  @override
  Widget build(BuildContext context) => MaterialBanner(
        content: Text(state.errorMessage ?? ''),
        actions: <Widget>[
          TextButton(onPressed: state.clearError, child: const Text('关闭')),
        ],
      );
}

class _Brand extends StatelessWidget {
  const _Brand({required this.size});
  final double size;

  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: <Color>[Color(0xFF6558E8), Color(0xFF8B5CF6)],
          ),
          borderRadius: BorderRadius.circular(size * 0.28),
        ),
        child: Text(
          'Su',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w900,
            fontSize: size * 0.38,
          ),
        ),
      );
}
