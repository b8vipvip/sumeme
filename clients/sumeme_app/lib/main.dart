import 'dart:io';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_windows/webview_flutter_windows.dart' as windows;

import 'bundled_lobehub_server.dart';

const String defaultAppUrl = 'https://sumeme.mv3.cn';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const SuMeMeApp());
}

class SuMeMeApp extends StatelessWidget {
  const SuMeMeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SuMeMe',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
        useMaterial3: true,
      ),
      home: const SuMeMeBrowser(),
    );
  }
}

class SuMeMeBrowser extends StatefulWidget {
  const SuMeMeBrowser({super.key});

  @override
  State<SuMeMeBrowser> createState() => _SuMeMeBrowserState();
}

class _SuMeMeBrowserState extends State<SuMeMeBrowser> {
  late final BundledLobeHubServer _server;
  Uri? _localOrigin;
  String? _error;

  @override
  void initState() {
    super.initState();
    _server = BundledLobeHubServer(remoteOrigin: Uri.parse(defaultAppUrl));
    _start();
  }

  Future<void> _start() async {
    try {
      final Uri origin = await _server.start();
      if (mounted) {
        setState(() => _localOrigin = origin);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    }
  }

  @override
  void dispose() {
    _server.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final String? error = _error;
    if (error != null) {
      return Scaffold(
        body: Center(
          child: _StartupError(message: error, onRetry: _start),
        ),
      );
    }

    final Uri? origin = _localOrigin;
    if (origin == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    if (Platform.isAndroid) {
      return _AndroidBrowser(localOrigin: origin);
    }
    if (Platform.isWindows) {
      return _WindowsBrowser(localOrigin: origin);
    }
    return const _UnsupportedPlatform();
  }
}

class _AndroidBrowser extends StatefulWidget {
  const _AndroidBrowser({required this.localOrigin});

  final Uri localOrigin;

  @override
  State<_AndroidBrowser> createState() => _AndroidBrowserState();
}

class _AndroidBrowserState extends State<_AndroidBrowser> {
  late final WebViewController _controller;
  int _progress = 0;
  String? _error;
  String _title = 'LobeHub';

  Uri get _home => widget.localOrigin;
  Uri get _controlPanel => widget.localOrigin.resolve('sumeme-control/');

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(Colors.transparent)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (int progress) {
            if (mounted) {
              setState(() => _progress = progress);
            }
          },
          onPageStarted: (String url) {
            if (mounted) {
              setState(() {
                _error = null;
                _title = Uri.tryParse(url)?.path.startsWith('/sumeme-control') == true
                    ? '服务控制台'
                    : 'LobeHub';
              });
            }
          },
          onWebResourceError: (WebResourceError error) {
            if (mounted && error.isForMainFrame == true) {
              setState(() => _error = error.description);
            }
          },
          onNavigationRequest: (NavigationRequest request) {
            final Uri? uri = Uri.tryParse(request.url);
            if (uri == null || (uri.scheme != 'https' && uri.scheme != 'http')) {
              return NavigationDecision.prevent;
            }
            return NavigationDecision.navigate;
          },
        ),
      )
      ..loadRequest(_home);
  }

  Future<void> _goBack() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _BrowserToolbar(
              title: _title,
              onBack: _goBack,
              onHome: () => _controller.loadRequest(_home),
              onControlPanel: () => _controller.loadRequest(_controlPanel),
              onRemote: () => _controller.loadRequest(Uri.parse(defaultAppUrl)),
              onReload: _controller.reload,
            ),
            if (_progress < 100) LinearProgressIndicator(value: _progress / 100),
            if (_error != null)
              _ErrorBanner(
                message: _error!,
                onRetry: () => _controller.loadRequest(_home),
              ),
            Expanded(child: WebViewWidget(controller: _controller)),
          ],
        ),
      ),
    );
  }
}

class _WindowsBrowser extends StatefulWidget {
  const _WindowsBrowser({required this.localOrigin});

  final Uri localOrigin;

  @override
  State<_WindowsBrowser> createState() => _WindowsBrowserState();
}

class _WindowsBrowserState extends State<_WindowsBrowser> {
  final windows.WebviewController _controller = windows.WebviewController();
  bool _ready = false;
  String? _error;
  String _title = 'LobeHub';

  Uri get _home => widget.localOrigin;
  Uri get _controlPanel => widget.localOrigin.resolve('sumeme-control/');

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      await _controller.initialize();
      await _controller.setPopupWindowPolicy(windows.WebviewPopupWindowPolicy.deny);
      await _controller.setDefaultContextMenusEnabled(true);
      await _controller.loadUrl(_home.toString());
      if (mounted) {
        setState(() {
          _ready = true;
          _error = null;
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    }
  }

  Future<void> _load(Uri uri, String title) async {
    try {
      await _controller.loadUrl(uri.toString());
      if (mounted) {
        setState(() {
          _title = title;
          _error = null;
        });
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() => _error = error.toString());
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Column(
          children: <Widget>[
            _BrowserToolbar(
              title: _title,
              onHome: () => _load(_home, 'LobeHub'),
              onControlPanel: () => _load(_controlPanel, '服务控制台'),
              onRemote: () => _load(Uri.parse(defaultAppUrl), '在线页面'),
              onReload: () => _load(
                _title == '服务控制台' ? _controlPanel : _home,
                _title,
              ),
            ),
            if (_error != null)
              _ErrorBanner(message: _error!, onRetry: _initialize),
            Expanded(
              child: _ready
                  ? windows.Webview(_controller)
                  : const Center(child: CircularProgressIndicator()),
            ),
          ],
        ),
      ),
    );
  }
}

class _BrowserToolbar extends StatelessWidget {
  const _BrowserToolbar({
    required this.title,
    this.onBack,
    required this.onHome,
    required this.onControlPanel,
    required this.onRemote,
    required this.onReload,
  });

  final String title;
  final Future<void> Function()? onBack;
  final Future<void> Function() onHome;
  final Future<void> Function() onControlPanel;
  final Future<void> Function() onRemote;
  final Future<void> Function() onReload;

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 1,
      child: SizedBox(
        height: 52,
        child: Row(
          children: <Widget>[
            if (onBack != null)
              IconButton(
                tooltip: '返回',
                onPressed: () => onBack!(),
                icon: const Icon(Icons.arrow_back),
              ),
            IconButton(
              tooltip: '内置 LobeHub',
              onPressed: () => onHome(),
              icon: const Icon(Icons.chat_bubble_outline),
            ),
            IconButton(
              tooltip: '服务控制台',
              onPressed: () => onControlPanel(),
              icon: const Icon(Icons.monitor_heart_outlined),
            ),
            Expanded(
              child: Text(
                'SuMeMe · $title',
                textAlign: TextAlign.center,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            IconButton(
              tooltip: '直接打开在线页面',
              onPressed: () => onRemote(),
              icon: const Icon(Icons.cloud_outlined),
            ),
            IconButton(
              tooltip: '刷新',
              onPressed: () => onReload(),
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
      ),
    );
  }
}

class _StartupError extends StatelessWidget {
  const _StartupError({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                const Icon(Icons.error_outline, size: 44),
                const SizedBox(height: 16),
                const Text(
                  '客户端内置服务启动失败',
                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 10),
                Text(message, textAlign: TextAlign.center),
                const SizedBox(height: 18),
                FilledButton(onPressed: () => onRetry(), child: const Text('重试')),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return MaterialBanner(
      content: Text('页面加载失败：$message'),
      actions: <Widget>[
        TextButton(onPressed: () => onRetry(), child: const Text('重新载入内置页面')),
      ],
    );
  }
}

class _UnsupportedPlatform extends StatelessWidget {
  const _UnsupportedPlatform();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: Text('当前构建仅支持 Android 和 Windows。')),
    );
  }
}
