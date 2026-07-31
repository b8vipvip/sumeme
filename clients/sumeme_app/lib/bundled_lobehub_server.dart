import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';

class BundledLobeHubServer {
  BundledLobeHubServer({required this.remoteOrigin});

  final Uri remoteOrigin;
  final HttpClient _upstreamClient = HttpClient()..autoUncompress = true;
  HttpServer? _server;

  Uri get origin {
    final HttpServer? server = _server;
    if (server == null) {
      throw StateError('Bundled LobeHub server has not started');
    }
    return Uri.parse('http://127.0.0.1:${server.port}/');
  }

  Future<Uri> start() async {
    if (_server != null) {
      return origin;
    }
    final HttpServer server = await HttpServer.bind(
      InternetAddress.loopbackIPv4,
      0,
      shared: false,
    );
    _server = server;
    server.listen(_handleRequest, onError: (_) {});
    return origin;
  }

  Future<void> close() async {
    final HttpServer? server = _server;
    _server = null;
    await server?.close(force: true);
    _upstreamClient.close(force: true);
  }

  Future<void> _handleRequest(HttpRequest request) async {
    try {
      final String path = request.uri.path;
      if (path == '/__sumeme/client-info') {
        await _writeJson(request.response, <String, Object?>{
          'mode': 'bundled-client',
          'remote_origin': remoteOrigin.origin,
          'ui': 'lobehub-v2.2.11',
          'control_panel': '/sumeme-control/',
        });
        return;
      }

      if (path == '/sumeme-control' || path == '/sumeme-control/') {
        await _serveAsset(
          request.response,
          'assets/control-panel/index.html',
          contentType: ContentType.html,
        );
        return;
      }

      if (path.startsWith('/sumeme-control/')) {
        final String relative = path.substring('/sumeme-control/'.length);
        if (await _tryServeAsset(
          request.response,
          'assets/control-panel/$relative',
        )) {
          return;
        }
      }

      if (path.startsWith('/_spa/') || path.startsWith('/_spa-auth/')) {
        if (await _tryServeAsset(request.response, 'assets/lobehub$path')) {
          return;
        }
        await _notFound(request.response, 'Bundled LobeHub asset is missing: $path');
        return;
      }

      if (_mustProxy(path)) {
        await _proxy(request);
        return;
      }

      // Root-level files emitted by Vite (icons, service worker and metadata) are
      // looked up in the bundled desktop build before the request is considered
      // a client-side application route.
      if (path != '/' && _looksLikeFile(path)) {
        final String relative = path.substring(1);
        if (await _tryServeAsset(
          request.response,
          'assets/lobehub/_spa/$relative',
        )) {
          return;
        }
        await _proxy(request);
        return;
      }

      final String template = _isAuthRoute(path)
          ? 'assets/lobehub/auth.html'
          : 'assets/lobehub/desktop.html';
      await _serveAsset(
        request.response,
        template,
        contentType: ContentType.html,
      );
    } on Object catch (error) {
      // The upstream response may already have started before a socket error.
      // Best-effort rendering avoids a second exception masking the original.
      try {
        request.response.statusCode = HttpStatus.internalServerError;
        request.response.headers.contentType = ContentType.html;
        request.response.write(_errorDocument(error.toString()));
        await request.response.close();
      } on Object {
        // Ignore a secondary write/close failure on an already committed response.
      }
    }
  }

  bool _mustProxy(String path) {
    const List<String> prefixes = <String>[
      '/api',
      '/trpc',
      '/webapi',
      '/oidc',
      '/oauth',
      '/f',
      '/webhooks',
      '/.well-known',
      '/sumeme-health',
    ];
    return prefixes.any(
      (String prefix) => path == prefix || path.startsWith('$prefix/'),
    );
  }

  bool _isAuthRoute(String path) {
    const List<String> routes = <String>[
      '/signin',
      '/signup',
      '/auth-error',
      '/verify-email',
      '/reset-password',
    ];
    return routes.any(
      (String route) => path == route || path.startsWith('$route/'),
    );
  }

  bool _looksLikeFile(String path) {
    final String last = path.split('/').last;
    return last.contains('.') && !last.endsWith('.');
  }

  Future<void> _proxy(HttpRequest downstream) async {
    final Uri upstreamUri = remoteOrigin.replace(
      path: downstream.uri.path,
      query: downstream.uri.hasQuery ? downstream.uri.query : null,
    );
    final HttpClientRequest upstream =
        await _upstreamClient.openUrl(downstream.method, upstreamUri);
    upstream.followRedirects = false;

    const Set<String> skippedRequestHeaders = <String>{
      'host',
      'connection',
      'content-length',
      'transfer-encoding',
      'accept-encoding',
      'origin',
      'referer',
    };
    downstream.headers.forEach((String name, List<String> values) {
      if (skippedRequestHeaders.contains(name.toLowerCase())) {
        return;
      }
      for (final String value in values) {
        upstream.headers.add(name, value);
      }
    });

    if (downstream.headers.value('origin') != null) {
      upstream.headers.set('origin', remoteOrigin.origin);
    }
    final String? referer = downstream.headers.value('referer');
    if (referer != null) {
      upstream.headers.set('referer', _rewriteRequestUrl(referer));
    }
    upstream.headers.set('x-sumeme-client', 'bundled-lobehub');
    await upstream.addStream(downstream);

    final HttpClientResponse source = await upstream.close();
    downstream.response.statusCode = source.statusCode;

    const Set<String> skippedResponseHeaders = <String>{
      'connection',
      'content-length',
      'transfer-encoding',
      'content-encoding',
      'location',
      'set-cookie',
    };
    source.headers.forEach((String name, List<String> values) {
      if (skippedResponseHeaders.contains(name.toLowerCase())) {
        return;
      }
      for (final String value in values) {
        downstream.response.headers.add(name, value);
      }
    });

    for (final Cookie cookie in source.cookies) {
      cookie.domain = null;
      cookie.secure = false;
      if (cookie.sameSite == SameSite.none) {
        cookie.sameSite = SameSite.lax;
      }
      downstream.response.cookies.add(cookie);
    }

    final String? location = source.headers.value(HttpHeaders.locationHeader);
    if (location != null) {
      downstream.response.headers.set(
        HttpHeaders.locationHeader,
        _rewriteLocation(location),
      );
    }

    await downstream.response.addStream(source);
    await downstream.response.close();
  }

  String _rewriteRequestUrl(String rawUrl) {
    final Uri? value = Uri.tryParse(rawUrl);
    if (value == null || !value.hasScheme || value.origin != origin.origin) {
      return rawUrl;
    }
    return remoteOrigin.replace(
      path: value.path,
      query: value.hasQuery ? value.query : null,
      fragment: value.hasFragment ? value.fragment : null,
    ).toString();
  }

  String _rewriteLocation(String rawLocation) {
    final Uri? location = Uri.tryParse(rawLocation);
    if (location == null) {
      return rawLocation;
    }

    if (location.hasScheme && location.origin == remoteOrigin.origin) {
      final StringBuffer relative = StringBuffer(
        location.path.isEmpty ? '/' : location.path,
      );
      if (location.hasQuery) {
        relative.write('?${location.query}');
      }
      if (location.hasFragment) {
        relative.write('#${location.fragment}');
      }
      return origin.resolve(relative.toString()).toString();
    }

    if (!location.hasScheme && rawLocation.startsWith('/')) {
      return origin.resolve(rawLocation).toString();
    }
    return rawLocation;
  }

  Future<bool> _tryServeAsset(HttpResponse response, String key) async {
    if (key.contains('..')) {
      return false;
    }
    try {
      final ByteData data = await rootBundle.load(key);
      final Uint8List bytes = data.buffer.asUint8List(
        data.offsetInBytes,
        data.lengthInBytes,
      );
      response.statusCode = HttpStatus.ok;
      response.headers.contentType = _contentType(key);
      response.headers.set(
        HttpHeaders.cacheControlHeader,
        'public, max-age=31536000, immutable',
      );
      response.add(bytes);
      await response.close();
      return true;
    } on Object {
      return false;
    }
  }

  Future<void> _serveAsset(
    HttpResponse response,
    String key, {
    ContentType? contentType,
  }) async {
    try {
      final ByteData data = await rootBundle.load(key);
      response.statusCode = HttpStatus.ok;
      response.headers.contentType = contentType ?? _contentType(key);
      response.headers.set(HttpHeaders.cacheControlHeader, 'no-cache');
      response.add(
        data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes),
      );
      await response.close();
    } on Object {
      response.statusCode = HttpStatus.serviceUnavailable;
      response.headers.contentType = ContentType.html;
      response.write(_errorDocument(
        '客户端没有找到内置 LobeHub UI。请安装包含 bundled-web-ui 的新版本。',
      ));
      await response.close();
    }
  }

  Future<void> _notFound(HttpResponse response, String message) async {
    response.statusCode = HttpStatus.notFound;
    response.headers.contentType = ContentType.html;
    response.write(_errorDocument(message));
    await response.close();
  }

  Future<void> _writeJson(HttpResponse response, Object value) async {
    response.statusCode = HttpStatus.ok;
    response.headers.contentType = ContentType.json;
    response.write(jsonEncode(value));
    await response.close();
  }

  ContentType _contentType(String path) {
    final String lower = path.toLowerCase();
    if (lower.endsWith('.html')) return ContentType.html;
    if (lower.endsWith('.js') || lower.endsWith('.mjs')) {
      return ContentType('application', 'javascript', charset: 'utf-8');
    }
    if (lower.endsWith('.css')) {
      return ContentType('text', 'css', charset: 'utf-8');
    }
    if (lower.endsWith('.json') || lower.endsWith('.map')) {
      return ContentType.json;
    }
    if (lower.endsWith('.svg')) return ContentType('image', 'svg+xml');
    if (lower.endsWith('.png')) return ContentType('image', 'png');
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
      return ContentType('image', 'jpeg');
    }
    if (lower.endsWith('.webp')) return ContentType('image', 'webp');
    if (lower.endsWith('.ico')) return ContentType('image', 'x-icon');
    if (lower.endsWith('.woff2')) return ContentType('font', 'woff2');
    if (lower.endsWith('.wasm')) return ContentType('application', 'wasm');
    return ContentType.binary;
  }

  String _errorDocument(String message) => '''
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SuMeMe 客户端</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f5f6fa;color:#1f2430;font-family:system-ui,"Microsoft YaHei",sans-serif}
main{max-width:620px;margin:24px;padding:36px;border:1px solid #e5e7ef;border-radius:20px;background:white;box-shadow:0 18px 50px #1e243015}
h1{margin:0 0 12px;font-size:26px}p{line-height:1.7;color:#697184}a{display:inline-block;margin-top:12px;padding:10px 14px;border-radius:11px;background:#6750e8;color:white;text-decoration:none}
</style></head><body><main><h1>SuMeMe 页面暂不可用</h1><p>${htmlEscape.convert(message)}</p><a href="/sumeme-control/">打开服务控制台</a></main></body></html>
''';
}
