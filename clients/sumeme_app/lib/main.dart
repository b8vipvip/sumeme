import 'package:flutter/material.dart';

import 'app_state.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SuMeMeBootstrap());
}

class SuMeMeBootstrap extends StatefulWidget {
  const SuMeMeBootstrap({super.key});

  @override
  State<SuMeMeBootstrap> createState() => _SuMeMeBootstrapState();
}

class _SuMeMeBootstrapState extends State<SuMeMeBootstrap> {
  late final SuMeMeAppState state;

  @override
  void initState() {
    super.initState();
    state = SuMeMeAppState()..initialize();
  }

  @override
  void dispose() {
    state.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (BuildContext context, Widget? child) {
        return MaterialApp(
          title: 'SuMeMe',
          debugShowCheckedModeBanner: false,
          themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
          theme: _theme(Brightness.light),
          darkTheme: _theme(Brightness.dark),
          home: state.initialized
              ? SuMeMeShell(state: state)
              : const _StartupScreen(),
        );
      },
    );
  }

  ThemeData _theme(Brightness brightness) {
    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF6657E8),
      brightness: brightness,
      surface: brightness == Brightness.light
          ? const Color(0xFFF8F8FC)
          : const Color(0xFF111218),
    );
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      scaffoldBackgroundColor: scheme.surface,
      visualDensity: VisualDensity.standard,
      cardTheme: CardThemeData(
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: .65)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surfaceContainerLowest,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: scheme.surfaceContainerLowest,
        indicatorColor: scheme.primaryContainer,
      ),
    );
  }
}

class _StartupScreen extends StatelessWidget {
  const _StartupScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const _BrandMark(size: 72),
            const SizedBox(height: 20),
            Text('SuMeMe', style: Theme.of(context).textTheme.headlineMedium),
            const SizedBox(height: 8),
            const Text('正在准备你的个人记忆空间…'),
            const SizedBox(height: 24),
            const SizedBox(
              width: 220,
              child: LinearProgressIndicator(borderRadius: BorderRadius.all(Radius.circular(99))),
            ),
          ],
        ),
      ),
    );
  }
}

class _Destination {
  const _Destination(this.label, this.icon, this.selectedIcon);

  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

const List<_Destination> _destinations = <_Destination>[
  _Destination('首页', Icons.home_outlined, Icons.home_rounded),
  _Destination('对话', Icons.forum_outlined, Icons.forum_rounded),
  _Destination('记忆', Icons.auto_awesome_outlined, Icons.auto_awesome_rounded),
  _Destination('资料库', Icons.folder_outlined, Icons.folder_rounded),
  _Destination('Vault', Icons.inventory_2_outlined, Icons.inventory_2_rounded),
  _Destination('同步', Icons.sync_outlined, Icons.sync_rounded),
  _Destination('设置', Icons.settings_outlined, Icons.settings_rounded),
];

class SuMeMeShell extends StatelessWidget {
  const SuMeMeShell({super.key, required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool desktop = constraints.maxWidth >= 900;
        return desktop ? _DesktopShell(state: state) : _MobileShell(state: state);
      },
    );
  }
}

class _DesktopShell extends StatelessWidget {
  const _DesktopShell({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final bool extended = MediaQuery.sizeOf(context).width >= 1180;
    return Scaffold(
      body: Row(
        children: <Widget>[
          NavigationRail(
            extended: extended,
            minExtendedWidth: 220,
            selectedIndex: state.selectedIndex,
            onDestinationSelected: state.selectPage,
            leading: Padding(
              padding: const EdgeInsets.fromLTRB(8, 16, 8, 22),
              child: extended
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        _BrandMark(size: 42),
                        SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('SuMeMe', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
                            Text('个人记忆空间', style: TextStyle(fontSize: 11)),
                          ],
                        ),
                      ],
                    )
                  : const _BrandMark(size: 42),
            ),
            trailing: Expanded(
              child: Align(
                alignment: Alignment.bottomCenter,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 18),
                  child: extended
                      ? _ConnectionChip(state: state)
                      : Icon(
                          state.isConnected ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                          color: state.isConnected
                              ? Theme.of(context).colorScheme.tertiary
                              : Theme.of(context).colorScheme.error,
                        ),
                ),
              ),
            ),
            destinations: _destinations
                .map(
                  (_Destination item) => NavigationRailDestination(
                    icon: Icon(item.icon),
                    selectedIcon: Icon(item.selectedIcon),
                    label: Text(item.label),
                  ),
                )
                .toList(),
          ),
          VerticalDivider(width: 1, color: Theme.of(context).colorScheme.outlineVariant),
          Expanded(
            child: Column(
              children: <Widget>[
                _TopBar(state: state),
                if (state.errorMessage != null) _ErrorStrip(state: state),
                Expanded(child: _PageBody(state: state)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MobileShell extends StatelessWidget {
  const _MobileShell({required this.state});

  final SuMeMeAppState state;

  int get _bottomIndex {
    if (state.selectedIndex <= 3) return state.selectedIndex;
    return 4;
  }

  int _pageForBottom(int value) => value <= 3 ? value : 7;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 4,
        title: Row(
          children: <Widget>[
            const _BrandMark(size: 34),
            const SizedBox(width: 10),
            Text(_mobileTitle(state.selectedIndex)),
          ],
        ),
        actions: <Widget>[
          IconButton(
            tooltip: '刷新连接',
            onPressed: state.connecting ? null : state.refreshConnection,
            icon: state.connecting
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Icon(state.isConnected ? Icons.cloud_done_outlined : Icons.cloud_off_outlined),
          ),
        ],
      ),
      drawer: _MobileDrawer(state: state),
      body: Column(
        children: <Widget>[
          if (state.errorMessage != null) _ErrorStrip(state: state),
          Expanded(
            child: state.selectedIndex == 7
                ? _MoreScreen(state: state)
                : _PageBody(state: state),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _bottomIndex,
        onDestinationSelected: (int index) => state.selectPage(_pageForBottom(index)),
        destinations: const <NavigationDestination>[
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home), label: '首页'),
          NavigationDestination(icon: Icon(Icons.forum_outlined), selectedIcon: Icon(Icons.forum), label: '对话'),
          NavigationDestination(icon: Icon(Icons.auto_awesome_outlined), selectedIcon: Icon(Icons.auto_awesome), label: '记忆'),
          NavigationDestination(icon: Icon(Icons.folder_outlined), selectedIcon: Icon(Icons.folder), label: '资料'),
          NavigationDestination(icon: Icon(Icons.grid_view_outlined), selectedIcon: Icon(Icons.grid_view), label: '更多'),
        ],
      ),
    );
  }

  String _mobileTitle(int index) {
    if (index >= 0 && index < _destinations.length) return _destinations[index].label;
    return '更多';
  }
}

class _MobileDrawer extends StatelessWidget {
  const _MobileDrawer({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return NavigationDrawer(
      selectedIndex: state.selectedIndex < _destinations.length ? state.selectedIndex : null,
      onDestinationSelected: (int index) {
        Navigator.of(context).pop();
        state.selectPage(index);
      },
      children: <Widget>[
        const Padding(
          padding: EdgeInsets.fromLTRB(24, 26, 24, 18),
          child: Row(
            children: <Widget>[
              _BrandMark(size: 46),
              SizedBox(width: 13),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('SuMeMe', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
                  Text('个人记忆空间'),
                ],
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
        const Padding(
          padding: EdgeInsets.fromLTRB(24, 20, 24, 8),
          child: Divider(),
        ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: _ConnectionChip(state: state),
        ),
      ],
    );
  }
}

class _TopBar extends StatelessWidget {
  const _TopBar({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 66,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLowest,
        border: Border(bottom: BorderSide(color: Theme.of(context).colorScheme.outlineVariant)),
      ),
      child: Row(
        children: <Widget>[
          Expanded(
            child: Text(
              _destinations[state.selectedIndex.clamp(0, _destinations.length - 1)].label,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w750),
            ),
          ),
          _ConnectionChip(state: state),
          const SizedBox(width: 8),
          IconButton(
            tooltip: '刷新连接',
            onPressed: state.connecting ? null : state.refreshConnection,
            icon: state.connecting
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
          IconButton(
            tooltip: '设置',
            onPressed: () => state.selectPage(6),
            icon: const Icon(Icons.tune_rounded),
          ),
        ],
      ),
    );
  }
}

class _PageBody extends StatelessWidget {
  const _PageBody({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = <Widget>[
      _DashboardScreen(state: state),
      _ChatScreen(state: state),
      _MemoryScreen(state: state),
      _LibraryScreen(state: state),
      _VaultScreen(state: state),
      _SyncScreen(state: state),
      _SettingsScreen(state: state),
    ];
    final int index = state.selectedIndex.clamp(0, pages.length - 1);
    return IndexedStack(index: index, children: pages);
  }
}

class _DashboardScreen extends StatelessWidget {
  const _DashboardScreen({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final Map<String, dynamic> health = state.health ?? const <String, dynamic>{};
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeader(
            eyebrow: 'PERSONAL MEMORY OS',
            title: _greeting(),
            description: '在一个地方对话、保存资料、检索记忆，并控制哪些内容留在本地或同步到云端。',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: () {
                  state.createConversation();
                  state.selectPage(1);
                },
                icon: const Icon(Icons.add_comment_outlined),
                label: const Text('开始对话'),
              ),
              OutlinedButton.icon(
                onPressed: () => state.selectPage(2),
                icon: const Icon(Icons.search),
                label: const Text('搜索记忆'),
              ),
            ],
          ),
          const SizedBox(height: 22),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final int columns = constraints.maxWidth >= 1050
                  ? 4
                  : constraints.maxWidth >= 600
                      ? 2
                      : 1;
              return GridView.count(
                crossAxisCount: columns,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 14,
                crossAxisSpacing: 14,
                childAspectRatio: columns == 1 ? 3.2 : 1.85,
                children: <Widget>[
                  _MetricCard(
                    icon: state.isConnected ? Icons.cloud_done_outlined : Icons.cloud_off_outlined,
                    label: '服务连接',
                    value: state.isConnected ? '在线' : '未连接',
                    detail: state.serverUrl,
                    tone: state.isConnected ? _Tone.good : _Tone.bad,
                  ),
                  _MetricCard(
                    icon: Icons.auto_awesome_outlined,
                    label: '记忆引擎',
                    value: health['memory_provider']?.toString() ?? '--',
                    detail: state.memoryEnabled ? '本轮允许召回与写入' : '当前已暂停长期记忆',
                    tone: state.memoryEnabled ? _Tone.primary : _Tone.warning,
                  ),
                  _MetricCard(
                    icon: Icons.inventory_2_outlined,
                    label: '当前 Vault',
                    value: state.vaultId,
                    detail: health['default_storage_mode']?.toString() ?? '策略未读取',
                    tone: _Tone.primary,
                  ),
                  _MetricCard(
                    icon: Icons.forum_outlined,
                    label: '本机会话',
                    value: '${state.conversations.length}',
                    detail: '会话索引保存在当前设备',
                    tone: _Tone.neutral,
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final bool row = constraints.maxWidth >= 820;
              final Widget recent = _SectionCard(
                title: '最近对话',
                subtitle: '继续上次的思路',
                trailing: TextButton(onPressed: () => state.selectPage(1), child: const Text('查看全部')),
                child: state.conversations.isEmpty
                    ? const _EmptyState(
                        icon: Icons.forum_outlined,
                        title: '还没有对话',
                        description: '新建对话后，SuMeMe 会在允许的 Vault 策略下整理长期记忆。',
                      )
                    : Column(
                        children: state.conversations.take(5).map((Conversation item) {
                          return ListTile(
                            contentPadding: EdgeInsets.zero,
                            leading: const CircleAvatar(child: Icon(Icons.chat_bubble_outline, size: 18)),
                            title: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                            subtitle: Text(_relativeTime(item.updatedAt)),
                            trailing: const Icon(Icons.chevron_right),
                            onTap: () {
                              state.activateConversation(item.id);
                              state.selectPage(1);
                            },
                          );
                        }).toList(),
                      ),
              );
              final Widget system = _SectionCard(
                title: '系统能力',
                subtitle: '当前服务器报告',
                child: Column(
                  children: <Widget>[
                    _CapabilityRow('MemPalace 原文记忆', health['mempalace_enabled'] == true),
                    _CapabilityRow('Letta 结构化记忆', health['letta_enabled'] == true),
                    _CapabilityRow('记忆检查点', health['memory_checkpoint'] == true),
                    _CapabilityRow('可信账户身份', health['identity_enforcement'] != 'legacy-client-asserted'),
                  ],
                ),
              );
              if (row) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(flex: 3, child: recent),
                    const SizedBox(width: 18),
                    Expanded(flex: 2, child: system),
                  ],
                );
              }
              return Column(children: <Widget>[recent, const SizedBox(height: 18), system]);
            },
          ),
        ],
      ),
    );
  }

  String _greeting() {
    final int hour = DateTime.now().hour;
    if (hour < 6) return '夜深了，记下此刻的想法';
    if (hour < 12) return '早上好，今天想记住什么？';
    if (hour < 18) return '下午好，继续整理你的世界';
    return '晚上好，回顾今天的重要片段';
  }
}

class _ChatScreen extends StatefulWidget {
  const _ChatScreen({required this.state});

  final SuMeMeAppState state;

  @override
  State<_ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<_ChatScreen> {
  final TextEditingController composer = TextEditingController();
  final ScrollController scroll = ScrollController();

  @override
  void dispose() {
    composer.dispose();
    scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final String value = composer.text;
    if (value.trim().isEmpty) return;
    composer.clear();
    await widget.state.sendMessage(value);
    if (scroll.hasClients) {
      await scroll.animateTo(
        scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 250),
        curve: Curves.easeOut,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool wide = constraints.maxWidth >= 1060;
        final bool medium = constraints.maxWidth >= 720;
        return Row(
          children: <Widget>[
            if (medium) ...<Widget>[
              SizedBox(width: wide ? 280 : 235, child: _ConversationSidebar(state: widget.state)),
              const VerticalDivider(width: 1),
            ],
            Expanded(
              child: Column(
                children: <Widget>[
                  _ChatHeader(state: widget.state, showConversationButton: !medium),
                  const Divider(height: 1),
                  Expanded(child: _MessageList(state: widget.state, controller: scroll)),
                  _Composer(
                    state: widget.state,
                    controller: composer,
                    onSend: _send,
                  ),
                ],
              ),
            ),
            if (wide) ...<Widget>[
              const VerticalDivider(width: 1),
              SizedBox(width: 285, child: _ContextSidebar(state: widget.state)),
            ],
          ],
        );
      },
    );
  }
}

class _ConversationSidebar extends StatelessWidget {
  const _ConversationSidebar({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      child: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(14),
            child: SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                onPressed: state.createConversation,
                icon: const Icon(Icons.add),
                label: const Text('新对话'),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14),
            child: TextField(
              decoration: const InputDecoration(
                hintText: '搜索本机会话',
                prefixIcon: Icon(Icons.search, size: 20),
                isDense: true,
              ),
            ),
          ),
          const SizedBox(height: 10),
          Expanded(
            child: state.conversations.isEmpty
                ? const Center(child: Text('暂无会话'))
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    itemCount: state.conversations.length,
                    itemBuilder: (BuildContext context, int index) {
                      final Conversation item = state.conversations[index];
                      final bool selected = item.id == state.activeConversationId;
                      return ListTile(
                        selected: selected,
                        selectedTileColor: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: .65),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        leading: const Icon(Icons.chat_bubble_outline, size: 19),
                        title: Text(item.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                        subtitle: Text(_relativeTime(item.updatedAt)),
                        trailing: PopupMenuButton<String>(
                          iconSize: 18,
                          onSelected: (String value) {
                            if (value == 'delete') state.deleteConversation(item.id);
                          },
                          itemBuilder: (BuildContext context) => const <PopupMenuEntry<String>>[
                            PopupMenuItem(value: 'delete', child: Text('删除会话')),
                          ],
                        ),
                        onTap: () => state.activateConversation(item.id),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _ChatHeader extends StatelessWidget {
  const _ChatHeader({required this.state, required this.showConversationButton});

  final SuMeMeAppState state;
  final bool showConversationButton;

  @override
  Widget build(BuildContext context) {
    final Conversation? conversation = state.activeConversation;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: <Widget>[
          if (showConversationButton)
            IconButton(
              tooltip: '新对话',
              onPressed: state.createConversation,
              icon: const Icon(Icons.add_comment_outlined),
            ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  conversation?.title ?? '新对话',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700),
                ),
                Text(
                  '${state.vaultId} · ${state.selectedModel.isEmpty ? '未选择模型' : state.selectedModel}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          if (state.models.isNotEmpty)
            DropdownButtonHideUnderline(
              child: DropdownButton<String>(
                value: state.models.contains(state.selectedModel) ? state.selectedModel : state.models.first,
                items: state.models
                    .map((String model) => DropdownMenuItem<String>(value: model, child: Text(model)))
                    .toList(),
                onChanged: (String? value) {
                  if (value != null) state.selectedModel = value;
                  state.notifyListeners();
                },
              ),
            ),
        ],
      ),
    );
  }
}

class _MessageList extends StatelessWidget {
  const _MessageList({required this.state, required this.controller});

  final SuMeMeAppState state;
  final ScrollController controller;

  @override
  Widget build(BuildContext context) {
    final Conversation? conversation = state.activeConversation;
    if (conversation == null || conversation.messages.isEmpty) {
      return Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 620),
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const _BrandMark(size: 70),
                const SizedBox(height: 20),
                Text('从任何想法开始', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
                const SizedBox(height: 10),
                Text(
                  'SuMeMe 会结合当前 Vault 中允许使用的历史记忆回答，也可以暂时关闭长期记忆。',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.bodyLarge,
                ),
                const SizedBox(height: 24),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: <String>[
                    '总结我最近在做的项目',
                    '帮我回忆上次的决定',
                    '整理今天上传的资料',
                  ].map((String text) {
                    return ActionChip(
                      label: Text(text),
                      onPressed: () => state.sendMessage(text),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return ListView.builder(
      controller: controller,
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 28),
      itemCount: conversation.messages.length,
      itemBuilder: (BuildContext context, int index) {
        return _MessageBubble(message: conversation.messages[index]);
      },
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    final bool user = message.role == 'user';
    final ColorScheme scheme = Theme.of(context).colorScheme;
    return Align(
      alignment: user ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 760),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: user ? scheme.primary : scheme.surfaceContainerLow,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(user ? 18 : 5),
            bottomRight: Radius.circular(user ? 5 : 18),
          ),
          border: user ? null : Border.all(color: scheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SelectableText(
              message.text.isEmpty && message.streaming ? '正在思考…' : message.text,
              style: TextStyle(
                color: user ? scheme.onPrimary : scheme.onSurface,
                height: 1.55,
              ),
            ),
            if (message.streaming) ...<Widget>[
              const SizedBox(height: 9),
              SizedBox(
                width: 70,
                child: LinearProgressIndicator(
                  minHeight: 2,
                  color: user ? scheme.onPrimary : scheme.primary,
                  backgroundColor: Colors.transparent,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _Composer extends StatelessWidget {
  const _Composer({required this.state, required this.controller, required this.onSend});

  final SuMeMeAppState state;
  final TextEditingController controller;
  final Future<void> Function() onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLowest,
        border: Border(top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant)),
      ),
      child: Column(
        children: <Widget>[
          Row(
            children: <Widget>[
              FilterChip(
                avatar: Icon(state.memoryEnabled ? Icons.auto_awesome : Icons.auto_awesome_outlined, size: 17),
                label: Text(state.memoryEnabled ? '长期记忆开启' : '长期记忆暂停'),
                selected: state.memoryEnabled,
                onSelected: state.setMemoryEnabled,
              ),
              const Spacer(),
              Text('${state.vaultId} · ${state.selectedModel.isEmpty ? '未选择模型' : state.selectedModel}', style: Theme.of(context).textTheme.bodySmall),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: controller,
            minLines: 1,
            maxLines: 6,
            textInputAction: TextInputAction.newline,
            decoration: InputDecoration(
              hintText: '输入消息，Enter 换行…',
              prefixIcon: IconButton(
                tooltip: '添加附件（摄取接口开发中）',
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('原生附件选择界面已预留，下一阶段接入分片上传和解析队列。')),
                ),
                icon: const Icon(Icons.attach_file),
              ),
              suffixIcon: Padding(
                padding: const EdgeInsets.all(6),
                child: FilledButton(
                  onPressed: state.sending ? null : onSend,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(46, 42),
                    padding: EdgeInsets.zero,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: state.sending
                      ? const SizedBox.square(dimension: 19, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.arrow_upward_rounded),
                ),
              ),
            ),
            onSubmitted: (_) => onSend(),
          ),
        ],
      ),
    );
  }
}

class _ContextSidebar extends StatelessWidget {
  const _ContextSidebar({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      child: ListView(
        padding: const EdgeInsets.all(18),
        children: <Widget>[
          Text('本轮上下文', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w750)),
          const SizedBox(height: 16),
          _InfoTile(icon: Icons.inventory_2_outlined, label: 'Vault', value: state.vaultId),
          _InfoTile(icon: Icons.smart_toy_outlined, label: '模型', value: state.selectedModel.isEmpty ? '未选择' : state.selectedModel),
          _InfoTile(icon: Icons.auto_awesome_outlined, label: '长期记忆', value: state.memoryEnabled ? '允许' : '暂停'),
          const SizedBox(height: 18),
          Text('相关记忆', style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          const _EmptyState(
            icon: Icons.travel_explore_outlined,
            title: '等待召回结果',
            description: '服务端完成记忆检索后，这里将显示来源、时间与相关度。',
            compact: true,
          ),
        ],
      ),
    );
  }
}

class _MemoryScreen extends StatefulWidget {
  const _MemoryScreen({required this.state});

  final SuMeMeAppState state;

  @override
  State<_MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends State<_MemoryScreen> {
  final TextEditingController query = TextEditingController();

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeader(
            eyebrow: 'MEMORY EXPLORER',
            title: '检索你的长期记忆',
            description: '按自然语言搜索原始对话与结构化记忆。结果始终限制在当前账户和 Vault。',
          ),
          const SizedBox(height: 20),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: <Widget>[
                  Expanded(
                    child: TextField(
                      controller: query,
                      decoration: const InputDecoration(
                        hintText: '例如：我上次为什么决定使用 Flutter？',
                        prefixIcon: Icon(Icons.search),
                      ),
                      onSubmitted: widget.state.searchMemory,
                    ),
                  ),
                  const SizedBox(width: 10),
                  FilledButton.icon(
                    onPressed: widget.state.loadingMemories
                        ? null
                        : () => widget.state.searchMemory(query.text),
                    icon: widget.state.loadingMemories
                        ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                        : const Icon(Icons.manage_search),
                    label: const Text('搜索'),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: const <Widget>[
              FilterChip(label: Text('全部'), selected: true, onSelected: null),
              FilterChip(label: Text('对话'), selected: false, onSelected: null),
              FilterChip(label: Text('人物'), selected: false, onSelected: null),
              FilterChip(label: Text('项目'), selected: false, onSelected: null),
              FilterChip(label: Text('事件'), selected: false, onSelected: null),
              FilterChip(label: Text('偏好'), selected: false, onSelected: null),
            ],
          ),
          const SizedBox(height: 16),
          if (widget.state.memoryResults.isEmpty)
            const Card(
              child: _EmptyState(
                icon: Icons.auto_awesome_outlined,
                title: '输入问题开始检索',
                description: '当前服务端接口返回经过作用域限制的记忆上下文。后续将加入逐条来源、编辑、删除和时间线。',
              ),
            )
          else
            ...widget.state.memoryResults.map(
              (MemoryResult result) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Card(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Row(
                          children: <Widget>[
                            const Icon(Icons.auto_awesome, size: 20),
                            const SizedBox(width: 8),
                            Expanded(child: Text(result.query, style: const TextStyle(fontWeight: FontWeight.w700))),
                            Chip(label: Text(result.storageMode)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SelectableText(result.context.isEmpty ? '没有检索到可显示的记忆。' : result.context),
                        const SizedBox(height: 12),
                        Text('来源：${result.provider}', style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _LibraryScreen extends StatelessWidget {
  const _LibraryScreen({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeader(
            eyebrow: 'KNOWLEDGE LIBRARY',
            title: '资料库',
            description: '集中管理文档、图片、音频和视频，并查看上传、解析、索引及同步状态。',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: () => ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('文件选择与上传协议将在 attachment-worker 阶段接入。')),
                ),
                icon: const Icon(Icons.upload_file_outlined),
                label: const Text('导入资料'),
              ),
              OutlinedButton.icon(
                onPressed: state.loadingLibrary ? null : state.refreshLibrary,
                icon: const Icon(Icons.refresh),
                label: const Text('刷新'),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Row(
            children: <Widget>[
              Expanded(
                child: TextField(
                  decoration: const InputDecoration(
                    hintText: '搜索文件名、内容或标签',
                    prefixIcon: Icon(Icons.search),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(tooltip: '筛选', onPressed: () {}, icon: const Icon(Icons.filter_list)),
              const SizedBox(width: 6),
              IconButton.filledTonal(tooltip: '排序', onPressed: () {}, icon: const Icon(Icons.sort)),
            ],
          ),
          const SizedBox(height: 16),
          if (state.libraryObjects.isEmpty)
            const Card(
              child: _EmptyState(
                icon: Icons.folder_open_outlined,
                title: '资料库还是空的',
                description: '服务端已经具备私有对象预签名上传、校验、下载和删除接口；原生导入与解析队列正在接入。',
              ),
            )
          else
            Card(
              child: Column(
                children: state.libraryObjects.map((Map<String, dynamic> item) {
                  return ListTile(
                    leading: _FileAvatar(contentType: item['content_type']?.toString() ?? ''),
                    title: Text(item['original_name']?.toString() ?? '未命名文件'),
                    subtitle: Text('${_formatBytes(item['size_bytes'])} · ${item['state'] ?? 'unknown'}'),
                    trailing: PopupMenuButton<String>(
                      itemBuilder: (BuildContext context) => const <PopupMenuEntry<String>>[
                        PopupMenuItem(value: 'download', child: Text('下载')),
                        PopupMenuItem(value: 'details', child: Text('查看详情')),
                        PopupMenuItem(value: 'delete', child: Text('删除')),
                      ],
                    ),
                  );
                }).toList(),
              ),
            ),
        ],
      ),
    );
  }
}

class _VaultScreen extends StatelessWidget {
  const _VaultScreen({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final List<Map<String, dynamic>> values = state.vaults;
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeader(
            eyebrow: 'PRIVACY VAULTS',
            title: 'Vault 与存储策略',
            description: '每个 Vault 都有独立的账户边界和存储模式。切换策略不会绕过服务端授权。',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: state.loadingVaults ? null : state.refreshVaults,
                icon: state.loadingVaults
                    ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.refresh),
                label: const Text('读取策略'),
              ),
            ],
          ),
          const SizedBox(height: 18),
          if (values.isEmpty)
            _VaultCard(
              state: state,
              vaultId: state.vaultId,
              mode: state.health?['default_storage_mode']?.toString() ?? 'cloud',
              isCurrent: true,
            )
          else
            ...values.map(
              (Map<String, dynamic> item) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _VaultCard(
                  state: state,
                  vaultId: item['vault_id']?.toString() ?? 'default',
                  mode: item['storage_mode']?.toString() ?? 'cloud',
                  isCurrent: item['vault_id']?.toString() == state.vaultId,
                ),
              ),
            ),
          const SizedBox(height: 14),
          const _PolicyExplanation(),
        ],
      ),
    );
  }
}

class _VaultCard extends StatelessWidget {
  const _VaultCard({
    required this.state,
    required this.vaultId,
    required this.mode,
    required this.isCurrent,
  });

  final SuMeMeAppState state;
  final String vaultId;
  final String mode;
  final bool isCurrent;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: <Widget>[
            Row(
              children: <Widget>[
                CircleAvatar(
                  radius: 25,
                  backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                  child: const Icon(Icons.inventory_2_outlined),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Row(
                        children: <Widget>[
                          Flexible(child: Text(vaultId, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800))),
                          if (isCurrent) ...<Widget>[
                            const SizedBox(width: 8),
                            const Chip(label: Text('当前')),
                          ],
                        ],
                      ),
                      Text(_modeDescription(mode)),
                    ],
                  ),
                ),
                PopupMenuButton<String>(
                  initialValue: mode,
                  onSelected: (String value) => state.updateVaultMode(vaultId, value),
                  itemBuilder: (BuildContext context) => const <PopupMenuEntry<String>>[
                    PopupMenuItem(value: 'local-only', child: Text('仅本地 local-only')),
                    PopupMenuItem(value: 'cloud', child: Text('云端 cloud')),
                    PopupMenuItem(value: 'hybrid', child: Text('混合 hybrid')),
                  ],
                  child: Chip(
                    avatar: Icon(_modeIcon(mode), size: 18),
                    label: Text(mode),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const LinearProgressIndicator(value: .18, minHeight: 8, borderRadius: BorderRadius.all(Radius.circular(99))),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Text('容量统计将在附件摄取完成后启用', style: Theme.of(context).textTheme.bodySmall),
                const Spacer(),
                TextButton(onPressed: () {}, child: const Text('查看内容')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String _modeDescription(String mode) {
    switch (mode) {
      case 'local-only':
        return '原始内容只保存在设备，本轮聊天不调用云端记忆';
      case 'hybrid':
        return '允许云端召回，只同步显式脱敏的派生内容';
      default:
        return '允许服务端召回和自动持久化';
    }
  }

  static IconData _modeIcon(String mode) {
    switch (mode) {
      case 'local-only':
        return Icons.phone_android_outlined;
      case 'hybrid':
        return Icons.sync_lock_outlined;
      default:
        return Icons.cloud_outlined;
    }
  }
}

class _PolicyExplanation extends StatelessWidget {
  const _PolicyExplanation();

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('三种存储模式', style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 14),
            const _PolicyRow(Icons.phone_android_outlined, '仅本地', '不从服务端召回，也不自动写入服务端记忆。'),
            const _PolicyRow(Icons.cloud_outlined, '云端', '服务端正常召回、写入记忆并保存允许的附件。'),
            const _PolicyRow(Icons.sync_lock_outlined, '混合', '允许召回，只接受显式脱敏且非原始的云端派生内容。'),
          ],
        ),
      ),
    );
  }
}

class _SyncScreen extends StatelessWidget {
  const _SyncScreen({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final bool trusted = state.health?['identity_enforcement'] != 'legacy-client-asserted';
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeader(
            eyebrow: 'SYNC CENTER',
            title: '同步中心',
            description: '查看设备、同步任务、失败重试和未来的冲突解决记录。',
          ),
          const SizedBox(height: 18),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: <Widget>[
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: trusted
                        ? Theme.of(context).colorScheme.tertiaryContainer
                        : Theme.of(context).colorScheme.errorContainer,
                    child: Icon(trusted ? Icons.verified_user_outlined : Icons.gpp_maybe_outlined),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          trusted ? '可信账户身份已启用' : '同步尚未开放',
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          trusted
                              ? '客户端可以按账户与 Vault 进行严格隔离同步。'
                              : '服务器仍处于 legacy-client-asserted 身份模式。完成可信登录和设备令牌后，才会开放私有同步。',
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final int columns = constraints.maxWidth > 760 ? 3 : 1;
              return GridView.count(
                crossAxisCount: columns,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                mainAxisSpacing: 14,
                crossAxisSpacing: 14,
                childAspectRatio: columns == 1 ? 3.4 : 1.35,
                children: const <Widget>[
                  _SyncCard(icon: Icons.devices_outlined, title: '设备', value: '1', detail: '当前设备'),
                  _SyncCard(icon: Icons.pending_actions_outlined, title: '待同步', value: '0', detail: '任务队列'),
                  _SyncCard(icon: Icons.warning_amber_outlined, title: '冲突', value: '0', detail: '等待处理'),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          const Card(
            child: _EmptyState(
              icon: Icons.sync_disabled_outlined,
              title: '暂无同步任务',
              description: '本地加密 Vault、增量同步、冲突合并和后台任务将在可信身份迁移之后接入。',
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsScreen extends StatefulWidget {
  const _SettingsScreen({required this.state});

  final SuMeMeAppState state;

  @override
  State<_SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<_SettingsScreen> {
  late final TextEditingController server;
  late final TextEditingController gateway;
  late final TextEditingController admin;
  late final TextEditingController account;
  late final TextEditingController vault;
  late final TextEditingController model;
  bool obscureGateway = true;
  bool obscureAdmin = true;
  bool saving = false;

  @override
  void initState() {
    super.initState();
    server = TextEditingController(text: widget.state.serverUrl);
    gateway = TextEditingController(text: widget.state.gatewayToken);
    admin = TextEditingController(text: widget.state.adminToken);
    account = TextEditingController(text: widget.state.accountId);
    vault = TextEditingController(text: widget.state.vaultId);
    model = TextEditingController(text: widget.state.selectedModel);
  }

  @override
  void dispose() {
    server.dispose();
    gateway.dispose();
    admin.dispose();
    account.dispose();
    vault.dispose();
    model.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    setState(() => saving = true);
    await widget.state.saveSettings(
      nextServerUrl: server.text,
      nextGatewayToken: gateway.text,
      nextAdminToken: admin.text,
      nextAccountId: account.text,
      nextVaultId: vault.text,
      nextModel: model.text,
    );
    if (mounted) {
      setState(() => saving = false);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('设置已保存')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      maxWidth: 960,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeader(
            eyebrow: 'SETTINGS',
            title: '客户端设置',
            description: '客户端与服务端独立部署。这里保存的是客户端连接配置，不会修改服务器 .env。',
          ),
          const SizedBox(height: 18),
          _SettingsSection(
            icon: Icons.dns_outlined,
            title: '服务器连接',
            description: '默认连接你的 SuMeMe 域名。API 统一经过 /api/gateway。',
            child: Column(
              children: <Widget>[
                TextField(
                  controller: server,
                  decoration: const InputDecoration(labelText: '服务器地址', hintText: 'https://sumeme.mv3.cn'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: gateway,
                  obscureText: obscureGateway,
                  decoration: InputDecoration(
                    labelText: '客户端 Gateway 凭据',
                    helperText: '用于模型、聊天和对象 API；保存在系统安全凭据存储中。',
                    suffixIcon: IconButton(
                      onPressed: () => setState(() => obscureGateway = !obscureGateway),
                      icon: Icon(obscureGateway ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: admin,
                  obscureText: obscureAdmin,
                  decoration: InputDecoration(
                    labelText: '管理员凭据（可选）',
                    helperText: '仅用于 Vault 策略和记忆管理；同样保存在系统安全凭据存储中。',
                    suffixIcon: IconButton(
                      onPressed: () => setState(() => obscureAdmin = !obscureAdmin),
                      icon: Icon(obscureAdmin ? Icons.visibility_outlined : Icons.visibility_off_outlined),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SettingsSection(
            icon: Icons.person_outline,
            title: '账户与 Vault',
            description: '当前字段用于兼容现有单用户部署；正式版会改为可信登录会话。',
            child: Row(
              children: <Widget>[
                Expanded(child: TextField(controller: account, decoration: const InputDecoration(labelText: '账户 ID'))),
                const SizedBox(width: 12),
                Expanded(child: TextField(controller: vault, decoration: const InputDecoration(labelText: '默认 Vault'))),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SettingsSection(
            icon: Icons.smart_toy_outlined,
            title: '模型',
            description: '保存后会刷新服务器模型列表。也可以手动填写模型名称。',
            child: TextField(controller: model, decoration: const InputDecoration(labelText: '默认模型')),
          ),
          const SizedBox(height: 14),
          _SettingsSection(
            icon: Icons.palette_outlined,
            title: '外观与隐私',
            description: '界面设置只保存在当前设备。',
            child: Column(
              children: <Widget>[
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('深色模式'),
                  value: widget.state.darkMode,
                  onChanged: widget.state.setDarkMode,
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('默认启用长期记忆'),
                  subtitle: const Text('每个对话仍可单独暂停'),
                  value: widget.state.memoryEnabled,
                  onChanged: widget.state.setMemoryEnabled,
                ),
              ],
            ),
          ),
          const SizedBox(height: 20),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton.icon(
              onPressed: saving ? null : _save,
              icon: saving
                  ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.save_outlined),
              label: const Text('保存并测试连接'),
            ),
          ),
          const SizedBox(height: 20),
          Text('SuMeMe 原生客户端 0.3 · Android / Windows', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _MoreScreen extends StatelessWidget {
  const _MoreScreen({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeader(
            eyebrow: 'MORE',
            title: '更多功能',
            description: '管理 Vault、同步、连接和隐私设置。',
          ),
          const SizedBox(height: 18),
          _MoreTile(icon: Icons.inventory_2_outlined, title: 'Vault', subtitle: '本地、云端和混合存储策略', onTap: () => state.selectPage(4)),
          _MoreTile(icon: Icons.sync_outlined, title: '同步中心', subtitle: '任务、冲突和设备状态', onTap: () => state.selectPage(5)),
          _MoreTile(icon: Icons.settings_outlined, title: '设置', subtitle: '服务器、账户、模型与隐私', onTap: () => state.selectPage(6)),
        ],
      ),
    );
  }
}

class _PageScroll extends StatelessWidget {
  const _PageScroll({required this.child, this.maxWidth = 1280});

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(22),
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: child,
        ),
      ),
    );
  }
}

class _PageHeader extends StatelessWidget {
  const _PageHeader({
    required this.eyebrow,
    required this.title,
    required this.description,
    this.actions = const <Widget>[],
  });

  final String eyebrow;
  final String title;
  final String description;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 18,
      runSpacing: 14,
      alignment: WrapAlignment.spaceBetween,
      crossAxisAlignment: WrapCrossAlignment.end,
      children: <Widget>[
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(
                eyebrow,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.primary,
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.5,
                ),
              ),
              const SizedBox(height: 7),
              Text(title, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w850, letterSpacing: -.8)),
              const SizedBox(height: 8),
              Text(description, style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.55)),
            ],
          ),
        ),
        if (actions.isNotEmpty) Wrap(spacing: 9, runSpacing: 9, children: actions),
      ],
    );
  }
}

enum _Tone { primary, good, warning, bad, neutral }

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.detail,
    required this.tone,
  });

  final IconData icon;
  final String label;
  final String value;
  final String detail;
  final _Tone tone;

  @override
  Widget build(BuildContext context) {
    final ColorScheme scheme = Theme.of(context).colorScheme;
    final (Color, Color) colors = switch (tone) {
      _Tone.good => (scheme.tertiary, scheme.tertiaryContainer),
      _Tone.warning => (const Color(0xFF9A5B00), const Color(0xFFFFE6B8)),
      _Tone.bad => (scheme.error, scheme.errorContainer),
      _Tone.neutral => (scheme.onSurfaceVariant, scheme.surfaceContainerHighest),
      _ => (scheme.primary, scheme.primaryContainer),
    };
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Row(
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.all(9),
                  decoration: BoxDecoration(color: colors.$2, borderRadius: BorderRadius.circular(12)),
                  child: Icon(icon, color: colors.$1, size: 21),
                ),
                const Spacer(),
                Icon(Icons.north_east, size: 16, color: scheme.onSurfaceVariant),
              ],
            ),
            const SizedBox(height: 12),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            Text(value, maxLines: 1, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w850)),
            Text(detail, maxLines: 2, overflow: TextOverflow.ellipsis, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.subtitle, required this.child, this.trailing});

  final String title;
  final String subtitle;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
                if (trailing != null) trailing!,
              ],
            ),
            const SizedBox(height: 14),
            child,
          ],
        ),
      ),
    );
  }
}

class _CapabilityRow extends StatelessWidget {
  const _CapabilityRow(this.label, this.enabled);

  final String label;
  final bool enabled;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: <Widget>[
          Icon(
            enabled ? Icons.check_circle_outline : Icons.radio_button_unchecked,
            size: 20,
            color: enabled ? Theme.of(context).colorScheme.tertiary : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(label)),
          Text(enabled ? '可用' : '未启用', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

class _ConnectionChip extends StatelessWidget {
  const _ConnectionChip({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: Icon(
        state.isConnected ? Icons.circle : Icons.error_outline,
        size: 13,
        color: state.isConnected ? Theme.of(context).colorScheme.tertiary : Theme.of(context).colorScheme.error,
      ),
      label: Text(state.isConnected ? '服务在线' : '未连接'),
    );
  }
}

class _ErrorStrip extends StatelessWidget {
  const _ErrorStrip({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return MaterialBanner(
      backgroundColor: Theme.of(context).colorScheme.errorContainer,
      content: Text(state.errorMessage ?? '未知错误'),
      leading: const Icon(Icons.error_outline),
      actions: <Widget>[
        TextButton(onPressed: state.clearError, child: const Text('关闭')),
        TextButton(onPressed: () => state.selectPage(6), child: const Text('打开设置')),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({
    required this.icon,
    required this.title,
    required this.description,
    this.compact = false,
  });

  final IconData icon;
  final String title;
  final String description;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.all(compact ? 12 : 34),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Icon(icon, size: compact ? 36 : 48, color: Theme.of(context).colorScheme.onSurfaceVariant),
              SizedBox(height: compact ? 10 : 14),
              Text(title, textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w750)),
              const SizedBox(height: 6),
              Text(description, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.5)),
            ],
          ),
        ),
      ),
    );
  }
}

class _BrandMark extends StatelessWidget {
  const _BrandMark({required this.size});

  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * .31),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[Color(0xFF8A7BFF), Color(0xFF6554E8), Color(0xFF3E2EBC)],
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(color: const Color(0xFF6554E8).withValues(alpha: .26), blurRadius: 18, offset: const Offset(0, 8)),
        ],
      ),
      child: Center(
        child: Text(
          'Su',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: size * .36, letterSpacing: -1),
        ),
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({required this.icon, required this.label, required this.value});

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 11),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, size: 19),
          const SizedBox(width: 9),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(label, style: Theme.of(context).textTheme.bodySmall),
                Text(value, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w650)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _FileAvatar extends StatelessWidget {
  const _FileAvatar({required this.contentType});

  final String contentType;

  @override
  Widget build(BuildContext context) {
    IconData icon = Icons.insert_drive_file_outlined;
    if (contentType.startsWith('image/')) icon = Icons.image_outlined;
    if (contentType.startsWith('audio/')) icon = Icons.audio_file_outlined;
    if (contentType.startsWith('video/')) icon = Icons.video_file_outlined;
    if (contentType == 'application/pdf') icon = Icons.picture_as_pdf_outlined;
    return CircleAvatar(child: Icon(icon, size: 20));
  }
}

class _PolicyRow extends StatelessWidget {
  const _PolicyRow(this.icon, this.title, this.description);

  final IconData icon;
  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, size: 21),
          const SizedBox(width: 10),
          Expanded(
            child: RichText(
              text: TextSpan(
                style: DefaultTextStyle.of(context).style,
                children: <InlineSpan>[
                  TextSpan(text: '$title：', style: const TextStyle(fontWeight: FontWeight.w750)),
                  TextSpan(text: description),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SyncCard extends StatelessWidget {
  const _SyncCard({required this.icon, required this.title, required this.value, required this.detail});

  final IconData icon;
  final String title;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Icon(icon),
            Text(value, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w850)),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            Text(detail, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
      ),
    );
  }
}

class _SettingsSection extends StatelessWidget {
  const _SettingsSection({
    required this.icon,
    required this.title,
    required this.description,
    required this.child,
  });

  final IconData icon;
  final String title;
  final String description;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Icon(icon),
                const SizedBox(width: 11),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(title, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w800)),
                      const SizedBox(height: 3),
                      Text(description, style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 18),
            child,
          ],
        ),
      ),
    );
  }
}

class _MoreTile extends StatelessWidget {
  const _MoreTile({required this.icon, required this.title, required this.subtitle, required this.onTap});

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 10),
          leading: CircleAvatar(child: Icon(icon)),
          title: Text(title, style: const TextStyle(fontWeight: FontWeight.w750)),
          subtitle: Text(subtitle),
          trailing: const Icon(Icons.chevron_right),
          onTap: onTap,
        ),
      ),
    );
  }
}

String _relativeTime(DateTime value) {
  final Duration difference = DateTime.now().difference(value);
  if (difference.inMinutes < 1) return '刚刚';
  if (difference.inHours < 1) return '${difference.inMinutes} 分钟前';
  if (difference.inDays < 1) return '${difference.inHours} 小时前';
  if (difference.inDays < 7) return '${difference.inDays} 天前';
  return '${value.year}/${value.month}/${value.day}';
}

String _formatBytes(Object? value) {
  final int bytes = int.tryParse(value?.toString() ?? '') ?? 0;
  if (bytes < 1024) return '$bytes B';
  if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KiB';
  if (bytes < 1024 * 1024 * 1024) return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MiB';
  return '${(bytes / 1024 / 1024 / 1024).toStringAsFixed(1)} GiB';
}
