import 'package:flutter/material.dart';

import 'app_state.dart';

const List<_NavItem> _navigation = <_NavItem>[
  _NavItem('首页', Icons.home_outlined, Icons.home_rounded),
  _NavItem('对话', Icons.forum_outlined, Icons.forum_rounded),
  _NavItem('记忆', Icons.auto_awesome_outlined, Icons.auto_awesome_rounded),
  _NavItem('资料库', Icons.folder_outlined, Icons.folder_rounded),
  _NavItem('Vault', Icons.inventory_2_outlined, Icons.inventory_2_rounded),
  _NavItem('同步', Icons.sync_outlined, Icons.sync_rounded),
  _NavItem('设置', Icons.settings_outlined, Icons.settings_rounded),
];

class _NavItem {
  const _NavItem(this.label, this.icon, this.selectedIcon);

  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

class SuMeMeRoot extends StatefulWidget {
  const SuMeMeRoot({super.key});

  @override
  State<SuMeMeRoot> createState() => _SuMeMeRootState();
}

class _SuMeMeRootState extends State<SuMeMeRoot> {
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
      cardTheme: CardTheme(
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
      builder: (BuildContext context, Widget? child) {
        return MaterialApp(
          title: 'SuMeMe',
          debugShowCheckedModeBanner: false,
          themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
          theme: _theme(Brightness.light),
          darkTheme: _theme(Brightness.dark),
          home: state.initialized
              ? _AdaptiveShell(state: state)
              : const _BootScreen(),
        );
      },
    );
  }
}

class _BootScreen extends StatelessWidget {
  const _BootScreen();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            _BrandMark(size: 72),
            SizedBox(height: 22),
            Text(
              'SuMeMe',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
            ),
            SizedBox(height: 8),
            Text('正在准备你的个人记忆空间…'),
            SizedBox(height: 24),
            SizedBox(width: 220, child: LinearProgressIndicator()),
          ],
        ),
      ),
    );
  }
}

class _AdaptiveShell extends StatelessWidget {
  const _AdaptiveShell({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        if (constraints.maxWidth >= 900) {
          return _DesktopShell(state: state);
        }
        return _MobileShell(state: state);
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
              padding: const EdgeInsets.fromLTRB(10, 18, 10, 26),
              child: extended
                  ? const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: <Widget>[
                        _BrandMark(size: 42),
                        SizedBox(width: 12),
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text(
                              'SuMeMe',
                              style: TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                            Text('个人记忆空间', style: TextStyle(fontSize: 11)),
                          ],
                        ),
                      ],
                    )
                  : const _BrandMark(size: 42),
            ),
            destinations: _navigation
                .map(
                  (_NavItem item) => NavigationRailDestination(
                    icon: Icon(item.icon),
                    selectedIcon: Icon(item.selectedIcon),
                    label: Text(item.label),
                  ),
                )
                .toList(growable: false),
          ),
          VerticalDivider(
            width: 1,
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
          Expanded(
            child: Column(
              children: <Widget>[
                _DesktopTopBar(state: state),
                if (state.errorMessage != null) _ErrorBanner(state: state),
                Expanded(child: _SelectedPage(state: state)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DesktopTopBar extends StatelessWidget {
  const _DesktopTopBar({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final int index = state.selectedIndex.clamp(0, _navigation.length - 1).toInt();
    return Container(
      height: 66,
      padding: const EdgeInsets.symmetric(horizontal: 24),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLowest,
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
              _navigation[index].label,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w700,
                  ),
            ),
          ),
          _ConnectionChip(state: state),
          const SizedBox(width: 8),
          IconButton(
            tooltip: '刷新服务连接',
            onPressed: state.connecting ? null : state.refreshConnection,
            icon: state.connecting
                ? const SizedBox.square(
                    dimension: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
    );
  }
}

class _MobileShell extends StatelessWidget {
  const _MobileShell({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final int selectedBottom = state.selectedIndex <= 3 ? state.selectedIndex : 4;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 6,
        title: Row(
          children: <Widget>[
            const _BrandMark(size: 34),
            const SizedBox(width: 10),
            Text(
              state.selectedIndex < _navigation.length
                  ? _navigation[state.selectedIndex].label
                  : '更多',
            ),
          ],
        ),
        actions: <Widget>[
          IconButton(
            tooltip: '刷新服务连接',
            onPressed: state.connecting ? null : state.refreshConnection,
            icon: Icon(
              state.isConnected
                  ? Icons.cloud_done_outlined
                  : Icons.cloud_off_outlined,
            ),
          ),
        ],
      ),
      drawer: _AppDrawer(state: state),
      body: Column(
        children: <Widget>[
          if (state.errorMessage != null) _ErrorBanner(state: state),
          Expanded(
            child: state.selectedIndex == 7
                ? _MorePage(state: state)
                : _SelectedPage(state: state),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedBottom,
        onDestinationSelected: (int index) {
          state.selectPage(index <= 3 ? index : 7);
        },
        destinations: const <NavigationDestination>[
          NavigationDestination(
            icon: Icon(Icons.home_outlined),
            selectedIcon: Icon(Icons.home_rounded),
            label: '首页',
          ),
          NavigationDestination(
            icon: Icon(Icons.forum_outlined),
            selectedIcon: Icon(Icons.forum_rounded),
            label: '对话',
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            selectedIcon: Icon(Icons.auto_awesome_rounded),
            label: '记忆',
          ),
          NavigationDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder_rounded),
            label: '资料',
          ),
          NavigationDestination(
            icon: Icon(Icons.grid_view_outlined),
            selectedIcon: Icon(Icons.grid_view_rounded),
            label: '更多',
          ),
        ],
      ),
    );
  }
}

class _AppDrawer extends StatelessWidget {
  const _AppDrawer({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return NavigationDrawer(
      selectedIndex:
          state.selectedIndex < _navigation.length ? state.selectedIndex : null,
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
                  Text(
                    'SuMeMe',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
                  ),
                  Text('个人记忆空间'),
                ],
              ),
            ],
          ),
        ),
        ..._navigation.map(
          (_NavItem item) => NavigationDrawerDestination(
            icon: Icon(item.icon),
            selectedIcon: Icon(item.selectedIcon),
            label: Text(item.label),
          ),
        ),
        const Padding(
          padding: EdgeInsets.fromLTRB(24, 18, 24, 8),
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

class _SelectedPage extends StatelessWidget {
  const _SelectedPage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final List<Widget> pages = <Widget>[
      _HomePage(state: state),
      _ChatPage(state: state),
      _MemoryPage(state: state),
      _LibraryPage(state: state),
      _VaultPage(state: state),
      _SyncPage(state: state),
      _SettingsPage(state: state),
    ];
    final int index = state.selectedIndex.clamp(0, pages.length - 1).toInt();
    return IndexedStack(index: index, children: pages);
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

class _PageHeading extends StatelessWidget {
  const _PageHeading({
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
              Text(
                title,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 8),
              Text(
                description,
                style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.5),
              ),
            ],
          ),
        ),
        if (actions.isNotEmpty)
          Wrap(spacing: 9, runSpacing: 9, children: actions),
      ],
    );
  }
}

class _HomePage extends StatelessWidget {
  const _HomePage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final Map<String, dynamic> health = state.health ?? const <String, dynamic>{};
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeading(
            eyebrow: 'PERSONAL MEMORY OS',
            title: _greeting(),
            description:
                '在一个地方对话、保存资料、检索记忆，并控制哪些内容留在本地或同步到云端。',
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
                childAspectRatio: columns == 1 ? 3.1 : 1.75,
                children: <Widget>[
                  _MetricCard(
                    icon: state.isConnected
                        ? Icons.cloud_done_outlined
                        : Icons.cloud_off_outlined,
                    label: '服务连接',
                    value: state.isConnected ? '在线' : '未连接',
                    detail: state.serverUrl,
                  ),
                  _MetricCard(
                    icon: Icons.auto_awesome_outlined,
                    label: '记忆引擎',
                    value: health['memory_provider']?.toString() ?? '--',
                    detail: state.memoryEnabled ? '允许长期记忆' : '长期记忆已暂停',
                  ),
                  _MetricCard(
                    icon: Icons.inventory_2_outlined,
                    label: '当前 Vault',
                    value: state.vaultId,
                    detail:
                        health['default_storage_mode']?.toString() ?? '策略未读取',
                  ),
                  _MetricCard(
                    icon: Icons.forum_outlined,
                    label: '本机会话',
                    value: '${state.conversations.length}',
                    detail: '索引保存在当前设备',
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 18),
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final Widget recent = _Panel(
                title: '最近对话',
                subtitle: '继续上次的思路',
                child: state.conversations.isEmpty
                    ? const _EmptyState(
                        icon: Icons.forum_outlined,
                        title: '还没有对话',
                        description:
                            '新建对话后，SuMeMe 会根据 Vault 策略整理长期记忆。',
                      )
                    : Column(
                        children: state.conversations.take(5).map(
                          (Conversation conversation) {
                            return ListTile(
                              contentPadding: EdgeInsets.zero,
                              leading: const CircleAvatar(
                                child: Icon(Icons.chat_bubble_outline, size: 18),
                              ),
                              title: Text(
                                conversation.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                              subtitle: Text(_relativeTime(conversation.updatedAt)),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () {
                                state.activateConversation(conversation.id);
                                state.selectPage(1);
                              },
                            );
                          },
                        ).toList(growable: false),
                      ),
              );
              final Widget capability = _Panel(
                title: '系统能力',
                subtitle: '来自当前服务器',
                child: Column(
                  children: <Widget>[
                    _CapabilityRow(
                      label: 'MemPalace 原文记忆',
                      enabled: health['mempalace_enabled'] == true,
                    ),
                    _CapabilityRow(
                      label: 'Letta 结构化记忆',
                      enabled: health['letta_enabled'] == true,
                    ),
                    _CapabilityRow(
                      label: '记忆检查点',
                      enabled: health['memory_checkpoint'] == true,
                    ),
                    _CapabilityRow(
                      label: '可信账户身份',
                      enabled: health['identity_enforcement'] !=
                          'legacy-client-asserted',
                    ),
                  ],
                ),
              );
              if (constraints.maxWidth >= 820) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(flex: 3, child: recent),
                    const SizedBox(width: 18),
                    Expanded(flex: 2, child: capability),
                  ],
                );
              }
              return Column(
                children: <Widget>[
                  recent,
                  const SizedBox(height: 18),
                  capability,
                ],
              );
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

class _ChatPage extends StatefulWidget {
  const _ChatPage({required this.state});

  final SuMeMeAppState state;

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

  Future<void> _send() async {
    final String text = composer.text;
    if (text.trim().isEmpty) return;
    composer.clear();
    await widget.state.sendMessage(text);
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool showConversationList = constraints.maxWidth >= 720;
        final bool showContext = constraints.maxWidth >= 1100;
        return Row(
          children: <Widget>[
            if (showConversationList) ...<Widget>[
              SizedBox(
                width: showContext ? 280 : 235,
                child: _ConversationList(state: widget.state),
              ),
              const VerticalDivider(width: 1),
            ],
            Expanded(
              child: Column(
                children: <Widget>[
                  _ChatToolbar(
                    state: widget.state,
                    compact: !showConversationList,
                  ),
                  const Divider(height: 1),
                  Expanded(child: _Messages(state: widget.state)),
                  _MessageComposer(
                    state: widget.state,
                    controller: composer,
                    onSend: _send,
                  ),
                ],
              ),
            ),
            if (showContext) ...<Widget>[
              const VerticalDivider(width: 1),
              SizedBox(width: 285, child: _ContextPanel(state: widget.state)),
            ],
          ],
        );
      },
    );
  }
}

class _ConversationList extends StatelessWidget {
  const _ConversationList({required this.state});

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
                      final Conversation conversation = state.conversations[index];
                      final bool selected =
                          conversation.id == state.activeConversationId;
                      return ListTile(
                        selected: selected,
                        selectedTileColor: Theme.of(context)
                            .colorScheme
                            .primaryContainer
                            .withValues(alpha: 0.65),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        leading: const Icon(Icons.chat_bubble_outline, size: 19),
                        title: Text(
                          conversation.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                        subtitle: Text(_relativeTime(conversation.updatedAt)),
                        trailing: PopupMenuButton<String>(
                          iconSize: 18,
                          onSelected: (String value) {
                            if (value == 'delete') {
                              state.deleteConversation(conversation.id);
                            }
                          },
                          itemBuilder: (BuildContext context) =>
                              const <PopupMenuEntry<String>>[
                            PopupMenuItem<String>(
                              value: 'delete',
                              child: Text('删除会话'),
                            ),
                          ],
                        ),
                        onTap: () =>
                            state.activateConversation(conversation.id),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}

class _ChatToolbar extends StatelessWidget {
  const _ChatToolbar({required this.state, required this.compact});

  final SuMeMeAppState state;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final Conversation? conversation = state.activeConversation;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Row(
        children: <Widget>[
          if (compact)
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
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                Text(
                  '${state.vaultId} · ${state.selectedModel.isEmpty ? '未选择模型' : state.selectedModel}',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: '对话信息',
            onPressed: () {},
            icon: const Icon(Icons.info_outline),
          ),
        ],
      ),
    );
  }
}

class _Messages extends StatelessWidget {
  const _Messages({required this.state});

  final SuMeMeAppState state;

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
                Text(
                  '从任何想法开始',
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                        fontWeight: FontWeight.w800,
                      ),
                ),
                const SizedBox(height: 10),
                Text(
                  'SuMeMe 会结合当前 Vault 中允许使用的历史记忆回答，也可以随时暂停长期记忆。',
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
                  ].map(
                    (String text) => ActionChip(
                      label: Text(text),
                      onPressed: () => state.sendMessage(text),
                    ),
                  ).toList(growable: false),
                ),
              ],
            ),
          ),
        ),
      );
    }
    return ListView.builder(
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
    final bool fromUser = message.role == 'user';
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Align(
      alignment: fromUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 760),
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: fromUser ? colors.primary : colors.surfaceContainerLow,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(18),
            topRight: const Radius.circular(18),
            bottomLeft: Radius.circular(fromUser ? 18 : 5),
            bottomRight: Radius.circular(fromUser ? 5 : 18),
          ),
          border: fromUser ? null : Border.all(color: colors.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            SelectableText(
              message.text.isEmpty && message.streaming
                  ? '正在思考…'
                  : message.text,
              style: TextStyle(
                color: fromUser ? colors.onPrimary : colors.onSurface,
                height: 1.55,
              ),
            ),
            if (message.streaming) ...<Widget>[
              const SizedBox(height: 9),
              SizedBox(
                width: 70,
                child: LinearProgressIndicator(
                  minHeight: 2,
                  color: fromUser ? colors.onPrimary : colors.primary,
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

class _MessageComposer extends StatelessWidget {
  const _MessageComposer({
    required this.state,
    required this.controller,
    required this.onSend,
  });

  final SuMeMeAppState state;
  final TextEditingController controller;
  final Future<void> Function() onSend;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 14),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerLowest,
        border: Border(
          top: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
        ),
      ),
      child: Column(
        children: <Widget>[
          Row(
            children: <Widget>[
              FilterChip(
                avatar: Icon(
                  state.memoryEnabled
                      ? Icons.auto_awesome
                      : Icons.auto_awesome_outlined,
                  size: 17,
                ),
                label: Text(
                  state.memoryEnabled ? '长期记忆开启' : '长期记忆暂停',
                ),
                selected: state.memoryEnabled,
                onSelected: state.setMemoryEnabled,
              ),
              const Spacer(),
              Flexible(
                child: Text(
                  '${state.vaultId} · ${state.selectedModel.isEmpty ? '未选择模型' : state.selectedModel}',
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: controller,
            minLines: 1,
            maxLines: 6,
            textInputAction: TextInputAction.newline,
            decoration: InputDecoration(
              hintText: '输入消息…',
              prefixIcon: IconButton(
                tooltip: '添加附件',
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('文件选择界面已预留，下一阶段接入上传和解析队列。'),
                    ),
                  );
                },
                icon: const Icon(Icons.attach_file),
              ),
              suffixIcon: Padding(
                padding: const EdgeInsets.all(6),
                child: FilledButton(
                  onPressed: state.sending ? null : onSend,
                  style: FilledButton.styleFrom(
                    minimumSize: const Size(46, 42),
                    padding: EdgeInsets.zero,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                  child: state.sending
                      ? const SizedBox.square(
                          dimension: 19,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_upward_rounded),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ContextPanel extends StatelessWidget {
  const _ContextPanel({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: Theme.of(context).colorScheme.surfaceContainerLowest,
      child: ListView(
        padding: const EdgeInsets.all(18),
        children: <Widget>[
          Text(
            '本轮上下文',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 16),
          _InfoRow(icon: Icons.inventory_2_outlined, label: 'Vault', value: state.vaultId),
          _InfoRow(
            icon: Icons.smart_toy_outlined,
            label: '模型',
            value: state.selectedModel.isEmpty ? '未选择' : state.selectedModel,
          ),
          _InfoRow(
            icon: Icons.auto_awesome_outlined,
            label: '长期记忆',
            value: state.memoryEnabled ? '允许' : '暂停',
          ),
          const SizedBox(height: 20),
          Text(
            '相关记忆',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 10),
          const _EmptyState(
            icon: Icons.travel_explore_outlined,
            title: '等待召回结果',
            description: '后续将在这里显示来源、时间与相关度。',
            compact: true,
          ),
        ],
      ),
    );
  }
}

class _MemoryPage extends StatefulWidget {
  const _MemoryPage({required this.state});

  final SuMeMeAppState state;

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
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeading(
            eyebrow: 'MEMORY EXPLORER',
            title: '检索你的长期记忆',
            description:
                '按自然语言搜索原始对话与结构化记忆。结果始终限制在当前账户和 Vault。',
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
                        ? const SizedBox.square(
                            dimension: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
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
              Chip(label: Text('全部')),
              Chip(label: Text('对话')),
              Chip(label: Text('人物')),
              Chip(label: Text('项目')),
              Chip(label: Text('事件')),
              Chip(label: Text('偏好')),
            ],
          ),
          const SizedBox(height: 16),
          if (widget.state.memoryResults.isEmpty)
            const Card(
              child: _EmptyState(
                icon: Icons.auto_awesome_outlined,
                title: '输入问题开始检索',
                description:
                    '当前接口返回经过作用域限制的记忆上下文；逐条来源、编辑、删除和时间线将在专用记忆 API 完成后启用。',
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
                            Expanded(
                              child: Text(
                                result.query,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ),
                            Chip(label: Text(result.storageMode)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        SelectableText(
                          result.context.isEmpty
                              ? '没有检索到可显示的记忆。'
                              : result.context,
                        ),
                        const SizedBox(height: 12),
                        Text(
                          '来源：${result.provider}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
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

class _LibraryPage extends StatelessWidget {
  const _LibraryPage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeading(
            eyebrow: 'KNOWLEDGE LIBRARY',
            title: '资料库',
            description:
                '集中管理文档、图片、音频和视频，并查看上传、解析、索引与同步状态。',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: () {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('原生文件选择将在附件摄取服务完成后启用。'),
                    ),
                  );
                },
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
              const Expanded(
                child: TextField(
                  decoration: InputDecoration(
                    hintText: '搜索文件名、内容或标签',
                    prefixIcon: Icon(Icons.search),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              IconButton.filledTonal(
                tooltip: '筛选',
                onPressed: () {},
                icon: const Icon(Icons.filter_list),
              ),
            ],
          ),
          const SizedBox(height: 16),
          if (state.libraryObjects.isEmpty)
            const Card(
              child: _EmptyState(
                icon: Icons.folder_open_outlined,
                title: '资料库还是空的',
                description:
                    '服务端已具备私有对象预签名上传、校验、下载和删除接口；原生导入与异步解析队列正在接入。',
              ),
            )
          else
            Card(
              child: Column(
                children: state.libraryObjects.map(
                  (Map<String, dynamic> object) {
                    return ListTile(
                      leading: const CircleAvatar(
                        child: Icon(Icons.insert_drive_file_outlined),
                      ),
                      title: Text(
                        object['original_name']?.toString() ?? '未命名文件',
                      ),
                      subtitle: Text(
                        '${_formatBytes(object['size_bytes'])} · ${object['state'] ?? 'unknown'}',
                      ),
                      trailing: const Icon(Icons.more_horiz),
                    );
                  },
                ).toList(growable: false),
              ),
            ),
        ],
      ),
    );
  }
}

class _VaultPage extends StatelessWidget {
  const _VaultPage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final List<Map<String, dynamic>> values = state.vaults;
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          _PageHeading(
            eyebrow: 'PRIVACY VAULTS',
            title: 'Vault 与存储策略',
            description:
                '每个 Vault 都有独立的账户边界与存储模式，所有策略由服务端再次验证。',
            actions: <Widget>[
              FilledButton.icon(
                onPressed: state.loadingVaults ? null : state.refreshVaults,
                icon: state.loadingVaults
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
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
              current: true,
            )
          else
            ...values.map(
              (Map<String, dynamic> vault) => Padding(
                padding: const EdgeInsets.only(bottom: 14),
                child: _VaultCard(
                  state: state,
                  vaultId: vault['vault_id']?.toString() ?? 'default',
                  mode: vault['storage_mode']?.toString() ?? 'cloud',
                  current: vault['vault_id']?.toString() == state.vaultId,
                ),
              ),
            ),
          const SizedBox(height: 16),
          const _Panel(
            title: '三种存储模式',
            subtitle: '服务端执行的隐私策略',
            child: Column(
              children: <Widget>[
                _PolicyRow(
                  icon: Icons.phone_android_outlined,
                  title: '仅本地',
                  description: '不从服务端召回，也不自动写入服务端记忆。',
                ),
                _PolicyRow(
                  icon: Icons.cloud_outlined,
                  title: '云端',
                  description: '服务端正常召回、写入记忆并保存允许的附件。',
                ),
                _PolicyRow(
                  icon: Icons.sync_lock_outlined,
                  title: '混合',
                  description: '允许召回，只接受显式脱敏的非原始派生内容。',
                ),
              ],
            ),
          ),
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
    required this.current,
  });

  final SuMeMeAppState state;
  final String vaultId;
  final String mode;
  final bool current;

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
                  backgroundColor:
                      Theme.of(context).colorScheme.primaryContainer,
                  child: const Icon(Icons.inventory_2_outlined),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        vaultId,
                        style: Theme.of(context).textTheme.titleLarge?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                      Text(_modeDescription(mode)),
                    ],
                  ),
                ),
                if (current) const Chip(label: Text('当前')),
                const SizedBox(width: 8),
                PopupMenuButton<String>(
                  initialValue: mode,
                  onSelected: (String value) =>
                      state.updateVaultMode(vaultId, value),
                  itemBuilder: (BuildContext context) =>
                      const <PopupMenuEntry<String>>[
                    PopupMenuItem<String>(
                      value: 'local-only',
                      child: Text('仅本地 local-only'),
                    ),
                    PopupMenuItem<String>(
                      value: 'cloud',
                      child: Text('云端 cloud'),
                    ),
                    PopupMenuItem<String>(
                      value: 'hybrid',
                      child: Text('混合 hybrid'),
                    ),
                  ],
                  child: Chip(label: Text(mode)),
                ),
              ],
            ),
            const SizedBox(height: 16),
            const LinearProgressIndicator(
              value: 0.18,
              minHeight: 8,
              borderRadius: BorderRadius.all(Radius.circular(99)),
            ),
            const SizedBox(height: 8),
            Row(
              children: <Widget>[
                Text(
                  '容量统计将在附件摄取完成后启用',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const Spacer(),
                TextButton(onPressed: () {}, child: const Text('查看内容')),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _modeDescription(String value) {
    switch (value) {
      case 'local-only':
        return '原始内容只留在设备，不调用服务端记忆';
      case 'hybrid':
        return '允许云端召回，只同步显式脱敏的派生内容';
      default:
        return '允许服务端召回与自动持久化';
    }
  }
}

class _SyncPage extends StatelessWidget {
  const _SyncPage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    final bool trusted =
        state.health?['identity_enforcement'] != 'legacy-client-asserted';
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeading(
            eyebrow: 'SYNC CENTER',
            title: '同步中心',
            description: '查看设备、同步任务、失败重试与未来的冲突解决记录。',
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
                    child: Icon(
                      trusted
                          ? Icons.verified_user_outlined
                          : Icons.gpp_maybe_outlined,
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          trusted ? '可信账户身份已启用' : '同步尚未开放',
                          style:
                              Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.w800,
                                  ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          trusted
                              ? '客户端可以按账户与 Vault 进行严格隔离同步。'
                              : '服务器仍处于 legacy-client-asserted 模式。完成可信登录与设备令牌后才开放私有同步。',
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
                  _MetricCard(
                    icon: Icons.devices_outlined,
                    label: '设备',
                    value: '1',
                    detail: '当前设备',
                  ),
                  _MetricCard(
                    icon: Icons.pending_actions_outlined,
                    label: '待同步',
                    value: '0',
                    detail: '任务队列',
                  ),
                  _MetricCard(
                    icon: Icons.warning_amber_outlined,
                    label: '冲突',
                    value: '0',
                    detail: '等待处理',
                  ),
                ],
              );
            },
          ),
          const SizedBox(height: 16),
          const Card(
            child: _EmptyState(
              icon: Icons.sync_disabled_outlined,
              title: '暂无同步任务',
              description:
                  '本地加密 Vault、增量同步、冲突合并与后台任务将在可信身份迁移后接入。',
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsPage extends StatefulWidget {
  const _SettingsPage({required this.state});

  final SuMeMeAppState state;

  @override
  State<_SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<_SettingsPage> {
  late final TextEditingController server;
  late final TextEditingController gateway;
  late final TextEditingController admin;
  late final TextEditingController account;
  late final TextEditingController vault;
  late final TextEditingController model;
  bool hideGateway = true;
  bool hideAdmin = true;
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
    if (!mounted) return;
    setState(() => saving = false);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('设置已保存并重新测试连接')),
    );
  }

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      maxWidth: 960,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeading(
            eyebrow: 'SETTINGS',
            title: '客户端设置',
            description:
                '客户端与服务端独立部署。这里保存的是客户端连接配置，不会修改服务器 .env。',
          ),
          const SizedBox(height: 18),
          _SettingsPanel(
            icon: Icons.dns_outlined,
            title: '服务器连接',
            description: 'API 通过服务器的 /api/gateway 入口访问。',
            child: Column(
              children: <Widget>[
                TextField(
                  controller: server,
                  decoration: const InputDecoration(
                    labelText: '服务器地址',
                    hintText: 'https://sumeme.mv3.cn',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: gateway,
                  obscureText: hideGateway,
                  decoration: InputDecoration(
                    labelText: '客户端 Gateway 凭据',
                    helperText: '用于模型、聊天与对象 API，保存在系统安全凭据存储中。',
                    suffixIcon: IconButton(
                      onPressed: () =>
                          setState(() => hideGateway = !hideGateway),
                      icon: Icon(
                        hideGateway
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: admin,
                  obscureText: hideAdmin,
                  decoration: InputDecoration(
                    labelText: '管理员凭据（可选）',
                    helperText: '用于 Vault 策略与记忆管理，同样保存在安全存储中。',
                    suffixIcon: IconButton(
                      onPressed: () => setState(() => hideAdmin = !hideAdmin),
                      icon: Icon(
                        hideAdmin
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 14),
          _SettingsPanel(
            icon: Icons.person_outline,
            title: '账户与 Vault',
            description: '当前字段兼容现有单用户部署；正式版将改为可信登录会话。',
            child: LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                final List<Widget> fields = <Widget>[
                  Expanded(
                    child: TextField(
                      controller: account,
                      decoration: const InputDecoration(labelText: '账户 ID'),
                    ),
                  ),
                  const SizedBox(width: 12, height: 12),
                  Expanded(
                    child: TextField(
                      controller: vault,
                      decoration: const InputDecoration(labelText: '默认 Vault'),
                    ),
                  ),
                ];
                if (constraints.maxWidth >= 600) return Row(children: fields);
                return Column(
                  children: <Widget>[
                    TextField(
                      controller: account,
                      decoration: const InputDecoration(labelText: '账户 ID'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: vault,
                      decoration: const InputDecoration(labelText: '默认 Vault'),
                    ),
                  ],
                );
              },
            ),
          ),
          const SizedBox(height: 14),
          _SettingsPanel(
            icon: Icons.smart_toy_outlined,
            title: '默认模型',
            description: '保存后会刷新服务器模型列表，也可以手动填写模型名称。',
            child: TextField(
              controller: model,
              decoration: const InputDecoration(labelText: '模型名称'),
            ),
          ),
          const SizedBox(height: 14),
          _SettingsPanel(
            icon: Icons.palette_outlined,
            title: '外观与隐私',
            description: '这些选项只保存在当前设备。',
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
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.save_outlined),
              label: const Text('保存并测试连接'),
            ),
          ),
          const SizedBox(height: 20),
          Text(
            'SuMeMe 原生客户端 0.3 · Android / Windows',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

class _MorePage extends StatelessWidget {
  const _MorePage({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return _PageScroll(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          const _PageHeading(
            eyebrow: 'MORE',
            title: '更多功能',
            description: '管理 Vault、同步、连接与隐私设置。',
          ),
          const SizedBox(height: 18),
          _MoreTile(
            icon: Icons.inventory_2_outlined,
            title: 'Vault',
            subtitle: '本地、云端和混合存储策略',
            onTap: () => state.selectPage(4),
          ),
          _MoreTile(
            icon: Icons.sync_outlined,
            title: '同步中心',
            subtitle: '任务、冲突和设备状态',
            onTap: () => state.selectPage(5),
          ),
          _MoreTile(
            icon: Icons.settings_outlined,
            title: '设置',
            subtitle: '服务器、账户、模型与隐私',
            onTap: () => state.selectPage(6),
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({
    required this.icon,
    required this.label,
    required this.value,
    required this.detail,
  });

  final IconData icon;
  final String label;
  final String value;
  final String detail;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(17),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: <Widget>[
            Container(
              padding: const EdgeInsets.all(9),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primaryContainer,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                icon,
                color: Theme.of(context).colorScheme.primary,
                size: 21,
              ),
            ),
            const SizedBox(height: 12),
            Text(label, style: Theme.of(context).textTheme.bodySmall),
            Text(
              value,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text(
              detail,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }
}

class _Panel extends StatelessWidget {
  const _Panel({
    required this.title,
    required this.subtitle,
    required this.child,
  });

  final String title;
  final String subtitle;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 14),
            child,
          ],
        ),
      ),
    );
  }
}

class _CapabilityRow extends StatelessWidget {
  const _CapabilityRow({required this.label, required this.enabled});

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
            color: enabled
                ? Theme.of(context).colorScheme.tertiary
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
          const SizedBox(width: 10),
          Expanded(child: Text(label)),
          Text(
            enabled ? '可用' : '未启用',
            style: Theme.of(context).textTheme.bodySmall,
          ),
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
        color: state.isConnected
            ? Theme.of(context).colorScheme.tertiary
            : Theme.of(context).colorScheme.error,
      ),
      label: Text(state.isConnected ? '服务在线' : '未连接'),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.state});

  final SuMeMeAppState state;

  @override
  Widget build(BuildContext context) {
    return MaterialBanner(
      backgroundColor: Theme.of(context).colorScheme.errorContainer,
      leading: const Icon(Icons.error_outline),
      content: Text(state.errorMessage ?? '未知错误'),
      actions: <Widget>[
        TextButton(onPressed: state.clearError, child: const Text('关闭')),
        TextButton(onPressed: () => state.selectPage(6), child: const Text('设置')),
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
              Icon(
                icon,
                size: compact ? 36 : 48,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
              SizedBox(height: compact ? 10 : 14),
              Text(
                title,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                description,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.5),
              ),
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
        borderRadius: BorderRadius.circular(size * 0.31),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            Color(0xFF8A7BFF),
            Color(0xFF6554E8),
            Color(0xFF3E2EBC),
          ],
        ),
        boxShadow: <BoxShadow>[
          BoxShadow(
            color: const Color(0xFF6554E8).withValues(alpha: 0.26),
            blurRadius: 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: Center(
        child: Text(
          'Su',
          style: TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w900,
            fontSize: size * 0.36,
          ),
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
  });

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
                Text(
                  value,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PolicyRow extends StatelessWidget {
  const _PolicyRow({
    required this.icon,
    required this.title,
    required this.description,
  });

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
            child: Text.rich(
              TextSpan(
                children: <InlineSpan>[
                  TextSpan(
                    text: '$title：',
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
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

class _SettingsPanel extends StatelessWidget {
  const _SettingsPanel({
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
                      Text(
                        title,
                        style:
                            Theme.of(context).textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.w800,
                                ),
                      ),
                      const SizedBox(height: 3),
                      Text(
                        description,
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
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
  const _MoreTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

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
          title: Text(
            title,
            style: const TextStyle(fontWeight: FontWeight.w700),
          ),
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
  if (bytes < 1024 * 1024) {
    return '${(bytes / 1024).toStringAsFixed(1)} KiB';
  }
  if (bytes < 1024 * 1024 * 1024) {
    return '${(bytes / 1024 / 1024).toStringAsFixed(1)} MiB';
  }
  return '${(bytes / 1024 / 1024 / 1024).toStringAsFixed(1)} GiB';
}
