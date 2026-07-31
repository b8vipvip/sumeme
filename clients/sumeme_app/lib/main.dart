import 'dart:io';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_windows/webview_flutter_windows.dart' as windows;

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

class SuMeMeBrowser extends StatelessWidget {
  const SuMeMeBrowser({super.key});

  @override
  Widget build(BuildContext context) {
    if (Platform.isAndroid) {
      return const _AndroidBrowser();
    }
    if (Platform.isWindows) {
      return const _WindowsBrowser();
    }
    return const _UnsupportedPlatform();
  }
}

class _AndroidBrowser extends StatefulWidget {
  const _AndroidBrowser();

  @override
  State<_AndroidBrowser> createState() => _AndroidBrowserState();
}

class _AndroidBrowserState extends State<_AndroidBrowser> {
  late final WebViewController _controller;
  int _progress = 0;
  String? _error;

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
          onPageStarted: (_) {
            if (mounted) {
              setState(() => _error = null);
            }
          },
          onWebResourceError: (WebResourceError error) {
            if (mounted) {
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
      ..loadRequest(Uri.parse(defaultAppUrl));
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
              onBack: _goBack,
              onHome: () => _controller.loadRequest(Uri.parse(defaultAppUrl)),
              onReload: _controller.reload,
            ),
            if (_progress < 100) LinearProgressIndicator(value: _progress / 100),
            if (_error != null)
              _ErrorBanner(
                message: _error!,
                onRetry: () => _controller.loadRequest(Uri.parse(defaultAppUrl)),
              ),
            Expanded(child: WebViewWidget(controller: _controller)),
          ],
        ),
      ),
    );
  }
}

class _WindowsBrowser extends StatefulWidget {
  const _WindowsBrowser();

  @override
  State<_WindowsBrowser> createState() => _WindowsBrowserState();
}

class _WindowsBrowserState extends State<_WindowsBrowser> {
  final windows.WebviewController _controller = windows.WebviewController();
  bool _ready = false;
  String? _error;

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
      await _controller.loadUrl(defaultAppUrl);
      if (mounted) {
        setState(() => _ready = true);
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
              onHome: () => _controller.loadUrl(defaultAppUrl),
              onReload: () => _controller.loadUrl(defaultAppUrl),
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
    this.onBack,
    required this.onHome,
    required this.onReload,
  });

  final Future<void> Function()? onBack;
  final Future<void> Function() onHome;
  final Future<void> Function() onReload;

  @override
  Widget build(BuildContext context) {
    return Material(
      elevation: 1,
      child: SizedBox(
        height: 48,
        child: Row(
          children: <Widget>[
            if (onBack != null)
              IconButton(
                tooltip: '返回',
                onPressed: () => onBack!(),
                icon: const Icon(Icons.arrow_back),
              ),
            IconButton(
              tooltip: '首页',
              onPressed: () => onHome(),
              icon: const Icon(Icons.home_outlined),
            ),
            const Expanded(
              child: Text(
                'SuMeMe',
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w600),
              ),
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

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message, required this.onRetry});

  final String message;
  final Future<void> Function() onRetry;

  @override
  Widget build(BuildContext context) {
    return MaterialBanner(
      content: Text('页面加载失败：$message'),
      actions: <Widget>[
        TextButton(onPressed: () => onRetry(), child: const Text('重试')),
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
