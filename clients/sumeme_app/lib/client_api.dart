import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:http/http.dart' as http;

class SuMeMeClientException implements Exception {
  const SuMeMeClientException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class UploadFileData {
  const UploadFileData({
    required this.name,
    required this.bytes,
    required this.mimeType,
  });

  final String name;
  final Uint8List bytes;
  final String mimeType;
  int get size => bytes.length;
}

class LibraryItem {
  const LibraryItem({
    required this.id,
    required this.name,
    required this.fileType,
    required this.size,
    required this.createdAt,
    required this.updatedAt,
    required this.url,
    required this.hash,
    required this.searchable,
    required this.metadata,
  });

  final String id;
  final String name;
  final String fileType;
  final int size;
  final DateTime createdAt;
  final DateTime updatedAt;
  final String url;
  final String hash;
  final bool searchable;
  final Map<String, dynamic> metadata;

  factory LibraryItem.fromJson(Map<String, dynamic> json) {
    DateTime date(Object? value) =>
        DateTime.tryParse(value?.toString() ?? '') ?? DateTime.fromMillisecondsSinceEpoch(0);
    final Object? rawMetadata = json['metadata'];
    return LibraryItem(
      id: json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '未命名资料',
      fileType: json['fileType']?.toString() ??
          json['file_type']?.toString() ??
          'application/octet-stream',
      size: int.tryParse(json['size']?.toString() ?? '') ?? 0,
      createdAt: date(json['createdAt'] ?? json['created_at']),
      updatedAt: date(json['updatedAt'] ?? json['updated_at']),
      url: json['url']?.toString() ?? '',
      hash: json['fileHash']?.toString() ?? json['hash']?.toString() ?? '',
      searchable: json['finishEmbedding'] == true ||
          json['embeddingStatus']?.toString() == 'success',
      metadata: rawMetadata is Map<Object?, Object?>
          ? Map<String, dynamic>.from(rawMetadata)
          : <String, dynamic>{},
    );
  }
}

class ChatAttachment {
  const ChatAttachment({
    required this.id,
    required this.name,
    required this.fileType,
    required this.size,
    this.url = '',
  });

  final String id;
  final String name;
  final String fileType;
  final int size;
  final String url;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'name': name,
        'file_type': fileType,
        'size': size,
        'url': url,
      };

  factory ChatAttachment.fromJson(Map<String, dynamic> json) => ChatAttachment(
        id: json['id']?.toString() ?? '',
        name: json['name']?.toString() ?? '附件',
        fileType: json['file_type']?.toString() ?? 'application/octet-stream',
        size: int.tryParse(json['size']?.toString() ?? '') ?? 0,
        url: json['url']?.toString() ?? '',
      );

  factory ChatAttachment.fromLibraryItem(LibraryItem item) => ChatAttachment(
        id: item.id,
        name: item.name,
        fileType: item.fileType,
        size: item.size,
        url: item.url,
      );
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
    required List<Map<String, Object?>> messages,
    required bool memoryEnabled,
    List<String> fileIds = const <String>[],
  }) async* {
    final http.Request request = http.Request(
      'POST',
      _uri('/api/client/chat/completions'),
    );
    request.headers.addAll(_headers(cookie: cookie, json: true));
    request.body = jsonEncode(<String, Object>{
      'conversation_id': conversationId,
      'file_ids': fileIds,
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

  Future<List<LibraryItem>> listFiles({
    required String cookie,
    String query = '',
    int limit = 500,
    int offset = 0,
  }) async {
    final Object? payload = await _trpcQuery(
      cookie: cookie,
      procedure: 'file.getFiles',
      input: <String, Object?>{
        'limit': limit,
        'offset': offset,
        'parentId': null,
        'q': query.trim().isEmpty ? null : query.trim(),
        'showFilesInKnowledgeBase': false,
        'sortType': 'desc',
      },
    );
    final List<Object?> rows = switch (payload) {
      List<Object?> value => value,
      Map<Object?, Object?> value when value['items'] is List<Object?> =>
        value['items']! as List<Object?>,
      Map<Object?, Object?> value when value['data'] is List<Object?> =>
        value['data']! as List<Object?>,
      _ => const <Object?>[],
    };
    return rows
        .whereType<Map<Object?, Object?>>()
        .map((Map<Object?, Object?> row) =>
            LibraryItem.fromJson(Map<String, dynamic>.from(row)))
        .where((LibraryItem item) => item.id.isNotEmpty)
        .toList(growable: false);
  }

  Future<LibraryItem> fileDetails({
    required String cookie,
    required String id,
  }) async {
    final Object? payload = await _trpcQuery(
      cookie: cookie,
      procedure: 'file.findById',
      input: <String, Object?>{'id': id},
    );
    if (payload is! Map<Object?, Object?>) {
      throw const SuMeMeClientException('服务器未返回资料详情');
    }
    return LibraryItem.fromJson(Map<String, dynamic>.from(payload));
  }

  Future<void> renameFile({
    required String cookie,
    required String id,
    required String name,
  }) async {
    await _trpcMutation(
      cookie: cookie,
      procedure: 'file.updateFile',
      input: <String, Object?>{'id': id, 'name': name.trim()},
    );
  }

  Future<void> deleteFile({required String cookie, required String id}) async {
    await _trpcMutation(
      cookie: cookie,
      procedure: 'file.removeFile',
      input: <String, Object?>{'id': id},
    );
  }

  Future<LibraryItem> uploadFile({
    required String cookie,
    required UploadFileData file,
    void Function(double progress, String stage)? onProgress,
  }) async {
    onProgress?.call(0.05, '计算文件哈希');
    final String hash = sha256.convert(file.bytes).toString();
    onProgress?.call(0.15, '检查重复资料');
    final Object? existing = await _trpcMutation(
      cookie: cookie,
      procedure: 'file.checkFileHash',
      input: <String, Object?>{'hash': hash},
    );

    Map<String, dynamic> metadata;
    String objectPath;
    if (existing is Map<Object?, Object?> &&
        existing['isExist'] == true &&
        (existing['metadata'] is Map<Object?, Object?> || existing['url'] != null)) {
      metadata = existing['metadata'] is Map<Object?, Object?>
          ? Map<String, dynamic>.from(existing['metadata']! as Map<Object?, Object?>)
          : <String, dynamic>{};
      objectPath = metadata['path']?.toString() ?? existing['url']?.toString() ?? '';
    } else {
      metadata = _storageMetadata(file.name);
      objectPath = metadata['path']!.toString();
      onProgress?.call(0.28, '获取云存储上传地址');
      final Object? signed = await _trpcMutation(
        cookie: cookie,
        procedure: 'upload.createS3PreSignedUrl',
        input: <String, Object?>{'pathname': objectPath},
      );
      final String signedUrl = signed is String
          ? signed
          : signed is Map<Object?, Object?>
              ? signed['preSignUrl']?.toString() ?? signed['url']?.toString() ?? ''
              : '';
      if (signedUrl.isEmpty) {
        throw const SuMeMeClientException('服务器未返回云存储上传地址');
      }
      onProgress?.call(0.42, '上传到云存储');
      final http.Response upload = await _client
          .put(
            Uri.parse(signedUrl),
            headers: <String, String>{'Content-Type': file.mimeType},
            body: file.bytes,
          )
          .timeout(const Duration(minutes: 10));
      if (upload.statusCode < 200 || upload.statusCode >= 300) {
        throw SuMeMeClientException(
          '云存储上传失败 (${upload.statusCode})',
          statusCode: upload.statusCode,
        );
      }
    }

    onProgress?.call(0.88, '创建资料记录');
    final Object? record = await _trpcMutation(
      cookie: cookie,
      procedure: 'file.createFile',
      input: <String, Object?>{
        'fileType': file.mimeType,
        'hash': hash,
        'metadata': metadata,
        'name': file.name,
        'size': file.size,
        'source': 'sumeme-native-client',
        'url': objectPath,
      },
    );
    if (record is! Map<Object?, Object?> || record['id'] == null) {
      throw const SuMeMeClientException('服务器未返回资料记录 ID');
    }
    onProgress?.call(1, '上传完成');
    return LibraryItem.fromJson(Map<String, dynamic>.from(record));
  }

  Map<String, dynamic> _storageMetadata(String originalName) {
    String extension = 'bin';
    final int dot = originalName.lastIndexOf('.');
    if (dot >= 0 && dot + 1 < originalName.length) {
      extension = originalName
          .substring(dot + 1)
          .toLowerCase()
          .replaceAll(RegExp('[^a-z0-9]'), '');
      if (extension.isEmpty) extension = 'bin';
      if (extension.length > 12) extension = extension.substring(0, 12);
    }
    final String date = (DateTime.now().millisecondsSinceEpoch ~/ 3600000).toString();
    final String dirname = 'files/$date';
    final String identifier =
        '${DateTime.now().microsecondsSinceEpoch.toRadixString(16)}-${sha1.convert(utf8.encode(originalName)).toString().substring(0, 12)}';
    final String filename = '$identifier.$extension';
    return <String, dynamic>{
      'date': date,
      'dirname': dirname,
      'filename': filename,
      'path': '$dirname/$filename',
    };
  }

  Future<Object?> _trpcQuery({
    required String cookie,
    required String procedure,
    required Map<String, Object?> input,
  }) async {
    final String encoded = Uri.encodeQueryComponent(jsonEncode(<String, Object?>{'json': input}));
    http.Response response = await _client
        .get(
          _uri('/trpc/$procedure', <String, String>{'input': jsonEncode(<String, Object?>{'json': input})}),
          headers: _headers(cookie: cookie),
        )
        .timeout(const Duration(seconds: 45));
    if (response.statusCode == 400 || response.statusCode == 404 || response.statusCode == 405) {
      final Map<String, Object?> batch = <String, Object?>{
        '0': <String, Object?>{'json': input},
      };
      response = await _client
          .get(
            _uri('/trpc/$procedure', <String, String>{
              'batch': '1',
              'input': jsonEncode(batch),
            }),
            headers: _headers(cookie: cookie),
          )
          .timeout(const Duration(seconds: 45));
    }
    // Keep the encoded value referenced so static analysis catches accidental
    // changes to the tRPC input shape while Uri handles percent encoding.
    assert(encoded.isNotEmpty);
    return _decodeTrpc(response);
  }

  Future<Object?> _trpcMutation({
    required String cookie,
    required String procedure,
    required Map<String, Object?> input,
  }) async {
    http.Response response = await _client
        .post(
          _uri('/trpc/$procedure'),
          headers: _headers(cookie: cookie, json: true),
          body: jsonEncode(<String, Object?>{'json': input}),
        )
        .timeout(const Duration(minutes: 2));
    if (response.statusCode == 400 || response.statusCode == 404 || response.statusCode == 405) {
      response = await _client
          .post(
            _uri('/trpc/$procedure', <String, String>{'batch': '1'}),
            headers: _headers(cookie: cookie, json: true),
            body: jsonEncode(<String, Object?>{
              '0': <String, Object?>{'json': input},
            }),
          )
          .timeout(const Duration(minutes: 2));
    }
    return _decodeTrpc(response);
  }

  Object? _decodeTrpc(http.Response response) {
    Object? decoded;
    try {
      decoded = response.body.isEmpty ? null : jsonDecode(response.body);
    } on FormatException {
      decoded = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw SuMeMeClientException(
        _safeError(response.body, '资料接口请求失败'),
        statusCode: response.statusCode,
      );
    }
    Object? envelope = decoded;
    if (envelope is List<Object?> && envelope.isNotEmpty) envelope = envelope.first;
    if (envelope is Map<Object?, Object?>) {
      final Object? error = envelope['error'];
      if (error is Map<Object?, Object?>) {
        final Object? json = error['json'];
        final String message = json is Map<Object?, Object?>
            ? json['message']?.toString() ?? '资料接口请求失败'
            : error['message']?.toString() ?? '资料接口请求失败';
        throw SuMeMeClientException(message);
      }
      final Object? result = envelope['result'];
      if (result is Map<Object?, Object?>) {
        final Object? data = result['data'];
        if (data is Map<Object?, Object?> && data.containsKey('json')) return data['json'];
        if (data != null) return data;
      }
      if (envelope.containsKey('json')) return envelope['json'];
    }
    return envelope;
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
