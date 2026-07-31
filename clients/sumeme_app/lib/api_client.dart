import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class SuMeMeApiException implements Exception {
  const SuMeMeApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class SuMeMeApiClient {
  SuMeMeApiClient({http.Client? client}) : _client = client ?? http.Client();

  final http.Client _client;

  Uri _root(String serverUrl) {
    final String normalized = serverUrl.trim().replaceFirst(RegExp(r'/+$'), '');
    final Uri uri = Uri.parse(normalized);
    if (!uri.hasScheme || uri.host.isEmpty) {
      throw const SuMeMeApiException('服务器地址格式不正确');
    }
    return uri;
  }

  Uri _gateway(String serverUrl, String path) {
    final Uri root = _root(serverUrl);
    final String clean = path.replaceFirst(RegExp(r'^/+'), '');
    return root.replace(path: '/api/gateway/$clean', query: null, fragment: null);
  }

  Map<String, String> _headers(String token) => <String, String>{
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        if (token.trim().isNotEmpty) 'Authorization': 'Bearer ${token.trim()}',
        'X-SuMeMe-Client': 'native-flutter',
      };

  Future<Map<String, dynamic>> health(String serverUrl) async {
    final Uri uri = _root(serverUrl).replace(path: '/sumeme-health');
    final http.Response response = await _client
        .get(uri, headers: const <String, String>{'Accept': 'application/json'})
        .timeout(const Duration(seconds: 15));
    return _decodeObject(response);
  }

  Future<List<String>> models({
    required String serverUrl,
    required String gatewayToken,
  }) async {
    final http.Response response = await _client
        .get(
          _gateway(serverUrl, 'v1/models'),
          headers: _headers(gatewayToken),
        )
        .timeout(const Duration(seconds: 20));
    final Map<String, dynamic> body = _decodeObject(response);
    final Object? raw = body['data'];
    if (raw is! List) return const <String>[];
    return raw
        .whereType<Map>()
        .map((Map item) => item['id']?.toString() ?? '')
        .where((String value) => value.isNotEmpty)
        .toList(growable: false);
  }

  Stream<String> streamChat({
    required String serverUrl,
    required String gatewayToken,
    required String accountId,
    required String vaultId,
    required String conversationId,
    required String model,
    required List<Map<String, String>> messages,
  }) async* {
    final http.Request request = http.Request(
      'POST',
      _gateway(serverUrl, 'v1/chat/completions'),
    );
    request.headers.addAll(_headers(gatewayToken));
    request.headers['X-SuMeMe-Conversation-ID'] = conversationId;
    request.body = jsonEncode(<String, Object>{
      'model': model,
      'stream': true,
      'user': accountId,
      'metadata': <String, String>{
        'vault_id': vaultId,
        'conversation_id': conversationId,
      },
      'messages': messages,
    });

    final http.StreamedResponse response =
        await _client.send(request).timeout(const Duration(seconds: 30));
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final String body = await response.stream.bytesToString();
      throw SuMeMeApiException(
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
        final Object? choices = decoded['choices'];
        if (choices is! List || choices.isEmpty) continue;
        final Object? first = choices.first;
        if (first is! Map) continue;
        final Object? delta = first['delta'];
        if (delta is! Map) continue;
        final Object? content = delta['content'];
        if (content is String && content.isNotEmpty) {
          yield content;
        }
      } on FormatException {
        continue;
      }
    }
  }

  Future<Map<String, dynamic>> searchMemory({
    required String serverUrl,
    required String adminToken,
    required String accountId,
    required String vaultId,
    required String query,
  }) async {
    final http.Response response = await _client
        .post(
          _gateway(serverUrl, 'api/memory/search'),
          headers: _headers(adminToken),
          body: jsonEncode(<String, Object>{
            'principal_type': 'account',
            'account_id': accountId,
            'vault_id': vaultId,
            'query': query,
          }),
        )
        .timeout(const Duration(seconds: 30));
    return _decodeObject(response);
  }

  Future<List<Map<String, dynamic>>> listVaults({
    required String serverUrl,
    required String adminToken,
    required String accountId,
  }) async {
    final http.Response response = await _client
        .post(
          _gateway(serverUrl, 'api/vaults/list'),
          headers: _headers(adminToken),
          body: jsonEncode(<String, Object>{
            'principal_type': 'account',
            'account_id': accountId,
          }),
        )
        .timeout(const Duration(seconds: 20));
    final Map<String, dynamic> body = _decodeObject(response);
    final Object? raw = body['vaults'];
    if (raw is! List) return const <Map<String, dynamic>>[];
    return raw
        .whereType<Map>()
        .map((Map value) => Map<String, dynamic>.from(value))
        .toList(growable: false);
  }

  Future<Map<String, dynamic>> updateVault({
    required String serverUrl,
    required String adminToken,
    required String accountId,
    required String vaultId,
    required String storageMode,
  }) async {
    final http.Response response = await _client
        .put(
          _gateway(serverUrl, 'api/vaults/policy'),
          headers: _headers(adminToken),
          body: jsonEncode(<String, Object>{
            'principal_type': 'account',
            'account_id': accountId,
            'vault_id': vaultId,
            'storage_mode': storageMode,
          }),
        )
        .timeout(const Duration(seconds: 20));
    return _decodeObject(response);
  }

  Future<List<Map<String, dynamic>>> listObjects({
    required String serverUrl,
    required String gatewayToken,
    required String accountId,
    required String vaultId,
  }) async {
    final http.Response response = await _client
        .post(
          _gateway(serverUrl, 'api/objects/list'),
          headers: _headers(gatewayToken),
          body: jsonEncode(<String, Object>{
            'user': accountId,
            'metadata': <String, String>{'vault_id': vaultId},
            'limit': 200,
          }),
        )
        .timeout(const Duration(seconds: 25));
    final Map<String, dynamic> body = _decodeObject(response);
    final Object? raw = body['objects'];
    if (raw is! List) return const <Map<String, dynamic>>[];
    return raw
        .whereType<Map>()
        .map((Map value) => Map<String, dynamic>.from(value))
        .toList(growable: false);
  }

  Map<String, dynamic> _decodeObject(http.Response response) {
    Object? decoded;
    try {
      decoded = jsonDecode(response.body);
    } on FormatException {
      decoded = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SuMeMeApiException(
        _safeError(response.body, '服务器请求失败'),
        statusCode: response.statusCode,
      );
    }
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) return Map<String, dynamic>.from(decoded);
    throw const SuMeMeApiException('服务器返回了无法识别的数据');
  }

  String _safeError(String body, String fallback) {
    try {
      final Object? decoded = jsonDecode(body);
      if (decoded is Map) {
        final Object? detail = decoded['detail'];
        if (detail != null) return detail.toString();
        final Object? error = decoded['error'];
        if (error is Map && error['message'] != null) {
          return error['message'].toString();
        }
      }
    } on FormatException {
      // Fall back to a bounded plain-text message.
    }
    final String normalized = body.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalized.isEmpty) return fallback;
    return normalized.length > 240 ? '${normalized.substring(0, 240)}…' : normalized;
  }

  void close() => _client.close();
}
