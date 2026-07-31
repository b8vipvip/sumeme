import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class SuMeMeClientException implements Exception {
  const SuMeMeClientException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class SuMeMeClientApi {
  SuMeMeClientApi({http.Client? client}) : _client = client ?? http.Client();

  static const String serverUrl = 'https://sumeme.mv3.cn';
  final http.Client _client;

  Uri _uri(String path, [Map<String, String>? query]) => Uri.parse(serverUrl)
      .replace(path: path, queryParameters: query, fragment: null);

  Map<String, String> _headers({String cookie = '', bool json = false}) =>
      <String, String>{
        'Accept': 'application/json',
        if (json) 'Content-Type': 'application/json',
        if (cookie.isNotEmpty) 'Cookie': cookie,
        'X-SuMeMe-Client': 'native-flutter',
      };

  Future<Map<String, dynamic>> config() async {
    final http.Response response = await _client
        .get(_uri('/api/client/config'), headers: _headers())
        .timeout(const Duration(seconds: 15));
    return _decodeObject(response);
  }

  Future<Map<String, dynamic>> health() async {
    final http.Response response = await _client
        .get(_uri('/sumeme-health'), headers: _headers())
        .timeout(const Duration(seconds: 15));
    return _decodeObject(response);
  }

  Future<AuthResult> signIn({required String email, required String password}) async {
    final http.Response response = await _client
        .post(
          _uri('/api/auth/sign-in/email'),
          headers: _headers(json: true),
          body: jsonEncode(<String, String>{
            'email': email.trim(),
            'password': password,
          }),
        )
        .timeout(const Duration(seconds: 30));
    return AuthResult(body: _decodeObject(response), cookie: _sessionCookie(response));
  }

  Future<AuthResult> signUp({
    required String name,
    required String email,
    required String password,
  }) async {
    final http.Response response = await _client
        .post(
          _uri('/api/client/auth/sign-up/email'),
          headers: _headers(json: true),
          body: jsonEncode(<String, String>{
            'name': name.trim(),
            'email': email.trim(),
            'password': password,
          }),
        )
        .timeout(const Duration(seconds: 30));
    return AuthResult(body: _decodeObject(response), cookie: _sessionCookie(response));
  }

  Future<Map<String, dynamic>> session(String cookie) async {
    final http.Response response = await _client
        .get(_uri('/api/client/session'), headers: _headers(cookie: cookie))
        .timeout(const Duration(seconds: 15));
    return _decodeObject(response);
  }

  Future<void> signOut(String cookie) async {
    final http.Response response = await _client
        .post(
          _uri('/api/auth/sign-out'),
          headers: _headers(cookie: cookie, json: true),
          body: '{}',
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SuMeMeClientException(
        _safeError(response.body, '退出登录失败'),
        statusCode: response.statusCode,
      );
    }
  }

  Future<List<String>> models(String cookie) async {
    final http.Response response = await _client
        .get(_uri('/api/client/models'), headers: _headers(cookie: cookie))
        .timeout(const Duration(seconds: 20));
    final Map<String, dynamic> body = _decodeObject(response);
    final Object? raw = body['data'];
    if (raw is! List<Object?>) return const <String>[];
    return raw
        .whereType<Map<Object?, Object?>>()
        .map((Map<Object?, Object?> item) => item['id']?.toString() ?? '')
        .where((String value) => value.isNotEmpty)
        .toList(growable: false);
  }

  Stream<String> streamChat({
    required String cookie,
    required String conversationId,
    required String model,
    required List<Map<String, String>> messages,
    required bool memoryEnabled,
  }) async* {
    final http.Request request = http.Request(
      'POST',
      _uri('/api/client/chat/completions'),
    );
    request.headers.addAll(_headers(cookie: cookie, json: true));
    request.body = jsonEncode(<String, Object>{
      'conversation_id': conversationId,
      'memory_enabled': memoryEnabled,
      'messages': messages,
      'model': model,
      'stream': true,
      'vault_id': 'default',
    });
    final http.StreamedResponse response =
        await _client.send(request).timeout(const Duration(seconds: 30));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final String body = await response.stream.bytesToString();
      throw SuMeMeClientException(
        _safeError(body, '聊天请求失败'),
        statusCode: response.statusCode,
      );
    }
    await for (final String line in response.stream
        .transform(utf8.decoder)
        .transform(const LineSplitter())) {
      final String value = line.trim();
      if (!value.startsWith('data:')) continue;
      final String payload = value.substring(5).trim();
      if (payload.isEmpty || payload == '[DONE]') continue;
      try {
        final Object? decoded = jsonDecode(payload);
        if (decoded is! Map<String, dynamic>) continue;
        final Object? error = decoded['error'];
        if (error is Map<Object?, Object?> && error['message'] != null) {
          throw SuMeMeClientException(error['message'].toString());
        }
        final Object? choices = decoded['choices'];
        if (choices is! List<Object?> || choices.isEmpty) continue;
        final Object? first = choices.first;
        if (first is! Map<Object?, Object?>) continue;
        final Object? delta = first['delta'];
        if (delta is! Map<Object?, Object?>) continue;
        final Object? content = delta['content'];
        if (content is String && content.isNotEmpty) yield content;
      } on FormatException {
        continue;
      }
    }
  }

  Future<Map<String, dynamic>> searchMemory({
    required String cookie,
    required String query,
  }) async {
    final http.Response response = await _client
        .post(
          _uri('/api/gateway/api/ui/memory/search'),
          headers: _headers(cookie: cookie, json: true),
          body: jsonEncode(<String, String>{
            'query': query.trim(),
            'vault_id': 'default',
          }),
        )
        .timeout(const Duration(seconds: 45));
    return _decodeObject(response);
  }

  Future<ReleaseInfo> release({
    required String platform,
    String channel = 'stable',
  }) async {
    final http.Response response = await _client
        .get(
          _uri('/api/client/releases/$platform', <String, String>{
            'channel': channel,
          }),
          headers: _headers(),
        )
        .timeout(const Duration(seconds: 15));
    return ReleaseInfo.fromJson(_decodeObject(response));
  }

  String _sessionCookie(http.Response response) {
    final String raw = response.headers['set-cookie'] ?? '';
    if (raw.isEmpty) return '';
    final RegExp match = RegExp(
      r'(?:^|,\s*)((?:__Secure-)?better-auth\.session_token=[^;,]+)',
      caseSensitive: false,
    );
    final RegExpMatch? result = match.firstMatch(raw);
    if (result != null) return result.group(1) ?? '';
    return raw.split(';').first.trim();
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    Object? decoded;
    try {
      decoded = response.body.isEmpty ? <String, dynamic>{} : jsonDecode(response.body);
    } on FormatException {
      decoded = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SuMeMeClientException(
        _safeError(response.body, '服务器请求失败'),
        statusCode: response.statusCode,
      );
    }
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map<Object?, Object?>) return Map<String, dynamic>.from(decoded);
    throw const SuMeMeClientException('服务器返回了无法识别的数据');
  }

  String _safeError(String body, String fallback) {
    try {
      final Object? decoded = jsonDecode(body);
      if (decoded is Map<Object?, Object?>) {
        final Object? detail = decoded['detail'];
        if (detail != null) return detail.toString();
        final Object? message = decoded['message'];
        if (message != null) return message.toString();
        final Object? error = decoded['error'];
        if (error is Map<Object?, Object?> && error['message'] != null) {
          return error['message'].toString();
        }
      }
    } on FormatException {
      // Use a bounded plain-text fallback below.
    }
    final String normalized = body.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalized.isEmpty) return fallback;
    return normalized.length > 240 ? '${normalized.substring(0, 240)}…' : normalized;
  }

  void close() => _client.close();
}

class AuthResult {
  const AuthResult({required this.body, required this.cookie});

  final Map<String, dynamic> body;
  final String cookie;
}

class ReleaseInfo {
  const ReleaseInfo({
    required this.available,
    required this.platform,
    required this.channel,
    this.version = '',
    this.buildNumber = 0,
    this.downloadUrl = '',
    this.notes = '',
    this.publishedAt = '',
    this.mandatory = false,
  });

  final bool available;
  final String platform;
  final String channel;
  final String version;
  final int buildNumber;
  final String downloadUrl;
  final String notes;
  final String publishedAt;
  final bool mandatory;

  factory ReleaseInfo.fromJson(Map<String, dynamic> json) => ReleaseInfo(
        available: json['available'] == true,
        platform: json['platform']?.toString() ?? '',
        channel: json['channel']?.toString() ?? 'stable',
        version: json['version']?.toString() ?? '',
        buildNumber: int.tryParse(json['build_number']?.toString() ?? '') ?? 0,
        downloadUrl: json['download_url']?.toString() ?? '',
        notes: json['notes']?.toString() ?? '',
        publishedAt: json['published_at']?.toString() ?? '',
        mandatory: json['mandatory'] == true,
      );
}
