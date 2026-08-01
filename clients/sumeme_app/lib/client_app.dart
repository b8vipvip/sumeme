import 'package:flutter/material.dart';

import 'auth_page.dart';
import 'chat_page.dart';
import 'client_state.dart';
import 'history_search_dialog.dart';
import 'library_page.dart';
import 'settings_page.dart';

class SuMeMeClientApp extends StatefulWidget {
  const SuMeMeClientApp({super.key});

  @override
  State<SuMeMeClientApp> createState() => _SuMeMeClientAppState();
}

class _SuMeMeClientAppState extends State<SuMeMeClientApp> {
  late final SuMeMeClientState state;
  String? _shownError;

  @override
  void initState() {
    super.initState();
    state = SuMeMeClientState()..addListener(_changed);
    state.initialize();
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    state
      ..removeListener(_changed)
      ..dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ThemeData light = _theme(Brightness.light);
    final ThemeData dark = _theme(Brightness.dark);
    return MaterialApp(
      title: 'SuMeMe',
      debugShowCheckedModeBanner: false,
      theme: light,
      darkTheme: dark,
      themeMode: state.darkMode ? ThemeMode.dark : ThemeMode.light,
      builder: (BuildContext context, Widget? child) {
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(
            textScaler: TextScaler.linear(state.textScale),
          ),
          child: child ?? const SizedBox.shrink(),
        );
      },
      home: _home(),
    );
  }

  Widget _home() {
    if (!state.initialized) return const _SplashPage();
    if (!state.loggedIn) return SuMeMeAuthPage(state: state);
    return Builder(
      builder: (BuildContext context) {
        if (state.errorMessage != null && state.errorMessage != _shownError) {
          _shownError = state.errorMessage;
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!context.mounted || _shownError == null) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(_shownError!),
                action: SnackBarAction(
                  label: '知道了',
                  onPressed: state.clearError,
                ),
              ),
            );
          });
        }
        return _ClientShell(state: state);
      },
    );
  }

  ThemeData _theme(Brightness brightness) {
    final ColorScheme scheme = ColorScheme.fromSeed(
      seedColor: const Color(0xFF5B5CE2),
      brightness: brightness,
      primary: brightness == Brightness.light
          ? const Color(0xFF5757D9)
          : const Color(0xFFBFC2FF),
      surface: brightness == Brightness.light
          ? const Color(0xFFFFFFFF)
          : const Color(0xFF17171B),
    );
    final bool light = brightness == Brightness.light;
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor:
          light ? const Color(0xFFF7F7FA) : const Color(0xFF101014),
      fontFamilyFallback: const <String>[
        'Microsoft YaHei UI',
        'PingFang SC',
        'Noto Sans CJK SC',
      ],
      appBarTheme: AppBarTheme(
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        backgroundColor:
            light ? const Color(0xFFF7F7FA) : const Color(0xFF101014),
        surfaceTintColor: Colors.transparent,
        titleTextStyle: TextStyle(
          color: scheme.onSurface,
          fontSize: 18,
          fontWeight: FontWeight.w800,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: light ? const Color(0xFFF1F1F6) : const Color(0xFF24242A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: scheme.primary, width: 1.4),
        ),
      ),
      cardTheme: CardThemeData(
        color: scheme.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18),
          side: BorderSide(color: scheme.outlineVariant.withValues(alpha: .7)),
        ),
      ),
      dividerTheme: DividerThemeData(color: scheme.outlineVariant),
    );
  }
}

class _ClientShell extends StatefulWidget {
  const _ClientShell({required this.state});

  final SuMeMeClientState state;

  @override
  State<_ClientShell> createState() => _ClientShellState();
}

class _ClientShellState extends State<_ClientShell> {
  final GlobalKey<ScaffoldState> _scaffold = GlobalKey<ScaffoldState>();

  String get _title => switch (widget.state.currentSection) {
        'library' => '资料库',
        'settings' => '设置',
        _ => 'SuMeMe',
      };

  Widget get _body => switch (widget.state.currentSection) {
        'library' => SuMeMeLibraryPage(state: widget.state),
        'settings' => SuMeMeSettingsPage(state: widget.state),
        _ => SuMeMeChatPage(state: widget.state),
      };

  void _openSection(String section) {
    widget.state.setSection(section);
    Navigator.maybePop(context);
  }

  @override
  Widget build(BuildContext context) {
    final bool chat = widget.state.currentSection == 'chat';
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Scaffold(
      key: _scaffold,
      drawer: NavigationDrawer(
        selectedIndex: switch (widget.state.currentSection) {
          'library' => 1,
          'settings' => 2,
          _ => 0,
        },
        onDestinationSelected: (int index) => _openSection(
          switch (index) {
            1 => 'library',
            2 => 'settings',
            _ => 'chat',
          },
        ),
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 28, 20, 20),
            child: Row(
              children: <Widget>[
                Container(
                  width: 48,
                  height: 48,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: <Color>[colors.primary, colors.tertiary],
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Text(
                    'Su',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 19,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      const Text(
                        'SuMeMe',
                        style: TextStyle(fontSize: 19, fontWeight: FontWeight.w800),
                      ),
                      Text(
                        widget.state.user?['name']?.toString() ??
                            widget.state.user?['email']?.toString() ??
                            '个人记忆助手',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: colors.onSurfaceVariant, fontSize: 12),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          const Divider(indent: 18, endIndent: 18),
          const NavigationDrawerDestination(
            icon: Icon(Icons.chat_bubble_outline_rounded),
            selectedIcon: Icon(Icons.chat_bubble_rounded),
            label: Text('对话'),
          ),
          const NavigationDrawerDestination(
            icon: Icon(Icons.folder_outlined),
            selectedIcon: Icon(Icons.folder_rounded),
            label: Text('资料库'),
          ),
          const NavigationDrawerDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings_rounded),
            label: Text('设置'),
          ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.all(18),
            child: Container(
              padding: const EdgeInsets.all(13),
              decoration: BoxDecoration(
                color: colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: <Widget>[
                  Icon(
                    widget.state.isConnected
                        ? Icons.cloud_done_outlined
                        : Icons.cloud_off_outlined,
                    size: 18,
                    color: widget.state.isConnected ? colors.primary : colors.error,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.state.isConnected ? '服务在线' : '服务异常',
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                  Text('v${widget.state.currentVersion}', style: const TextStyle(fontSize: 11)),
                ],
              ),
            ),
          ),
        ],
      ),
      appBar: AppBar(
        leading: IconButton(
          tooltip: '导航菜单',
          onPressed: () => _scaffold.currentState?.openDrawer(),
          icon: const Icon(Icons.menu_rounded),
        ),
        title: chat
            ? Row(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  const Text('SuMeMe'),
                  const SizedBox(width: 8),
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: widget.state.isConnected ? const Color(0xFF21A366) : colors.error,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              )
            : Text(_title),
        actions: <Widget>[
          if (chat)
            PopupMenuButton<String>(
              tooltip: '对话选项',
              icon: const Icon(Icons.add_rounded),
              onSelected: (String value) {
                if (value == 'search') {
                  showHistorySearchDialog(context, widget.state);
                } else if (value == 'hide') {
                  widget.state.setHideHistory(!widget.state.hideHistory);
                } else if (value == 'bottom') {
                  // Rebuilding the chat page causes its auto-scroll policy to
                  // move to the newest message without exposing a global key.
                  widget.state.setSection('chat');
                }
              },
              itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
                const PopupMenuItem<String>(
                  value: 'search',
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(Icons.manage_search_rounded),
                    title: Text('查找记忆记录'),
                    subtitle: Text('按关键词和时间搜索'),
                  ),
                ),
                PopupMenuItem<String>(
                  value: 'hide',
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(
                      widget.state.hideHistory
                          ? Icons.visibility_rounded
                          : Icons.visibility_off_outlined,
                    ),
                    title: Text(widget.state.hideHistory ? '显示历史对话' : '隐藏历史对话'),
                    subtitle: Text(widget.state.hideHistory
                        ? '恢复完整时间线'
                        : '下次启动不显示旧聊天'),
                    trailing: Switch(
                      value: widget.state.hideHistory,
                      onChanged: null,
                    ),
                  ),
                ),
              ],
            ),
          if (!chat && widget.state.currentSection == 'library')
            IconButton(
              tooltip: '刷新资料库',
              onPressed: widget.state.loadingLibrary ? null : widget.state.refreshLibrary,
              icon: const Icon(Icons.refresh_rounded),
            ),
          const SizedBox(width: 6),
        ],
      ),
      body: _body,
    );
  }
}

class _SplashPage extends StatelessWidget {
  const _SplashPage();

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Container(
                width: 68,
                height: 68,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: const Color(0xFF5757D9),
                  borderRadius: BorderRadius.circular(23),
                ),
                child: const Text(
                  'Su',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 25,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              const SizedBox(height: 22),
              const SizedBox(
                width: 28,
                height: 28,
                child: CircularProgressIndicator(strokeWidth: 2.4),
              ),
              const SizedBox(height: 14),
              const Text('正在连接 SuMeMe…'),
            ],
          ),
        ),
      );
}
