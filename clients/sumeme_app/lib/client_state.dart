import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'client_api.dart';

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.role,
    required this.text,
    required this.createdAt,
    this.streaming = false,
  });

  final String id;
  final String role;
  String text;
  final DateTime createdAt;
  bool streaming;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'role': role,
        'text': text,
        'created_at': createdAt.toIso8601String(),
      };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id']?.toString() ?? '',
        role: json['role']?.toString() ?? 'user',
        text: json['text']?.toString() ?? '',
        createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ??
            DateTime.now(),
      );
}

class Conversation {
  Conversation({
    required this.id,
    required this.title,
    required this.updatedAt,
    List<ChatMessage>? messages,
  }) : messages = messages ?? <ChatMessage>[];

  final String id;
  String title;
  DateTime updatedAt;
  final List<ChatMessage> messages;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'title': title,
        'updated_at': updatedAt.toIso8601String(),
        'messages': messages.map((ChatMessage item) => item.toJson()).toList(),
      };

  factory Conversation.fromJson(Map<String, dynamic> json) => Conversation(
        id: json['id']?.toString() ?? '',
        title: json['title']?.toString() ?? '新对话',
        updatedAt: DateTime.tryParse(json['updated_at']?.toString() ?? '') ??
            DateTime.now(),
        messages: (json['messages'] as List<Object?>? ?? const <Object?>[])
            .whereType<Map<Object?, Object?>>()
            .map((Map<Object?, Object?> item) =>
                ChatMessage.fromJson(Map<String, dynamic>.from(item)))
            .toList(),
      );
}

class SuMeMeClientState extends ChangeNotifier {
  SuMeMeClientState({SuMeMeClientApi? api}) : _api = api ?? SuMeMeClientApi();

  static const FlutterSecureStorage _secure = FlutterSecureStorage();
  static const String _sessionKey = 'sumeme.session.cookie.v2';
  static const String _conversationKey = 'sumeme.conversations.v2';

  final SuMeMeClientApi _api;
  final Random _random = Random.secure();

  bool initialized = false;
  bool connecting = false;
  bool authenticating = false;
  bool sending = false;
  bool checkingUpdate = false;
  bool darkMode = false;
  bool memoryEnabled = true;
  int selectedIndex = 0;
  String? errorMessage;

  String sessionCookie = '';
  Map<String, dynamic>? user;
  Map<String, dynamic>? health;
  Map<String, dynamic>? serverConfig;
  List<String> models = <String>[];
  String selectedModel = '';
  List<Conversation> conversations = <Conversation>[];
  String? activeConversationId;
  String currentVersion = '0.0.0';
  int currentBuild = 0;
  ReleaseInfo? latestRelease;
  String updateStatus = '尚未检查更新';
  String memoryResult = '';

  bool get loggedIn => user != null && sessionCookie.isNotEmpty;
  bool get isConnected => health?['status'] == 'ok';
  bool get registrationEnabled =>
      serverConfig?['registration_enabled'] != false;
  String get platformName => Platform.isAndroid ? 'android' : 'windows';
  bool get hasUpdate =>
      latestRelease != null &&
      latestRelease!.available &&
      compareVersions(latestRelease!.version, currentVersion) > 0;

  Conversation? get activeConversation {
    for (final Conversation item in conversations) {
      if (item.id == activeConversationId) return item;
    }
    return null;
  }

  Future<void> initialize() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    darkMode = prefs.getBool('dark_mode') ?? false;
    memoryEnabled = prefs.getBool('memory_enabled') ?? true;
    selectedModel = prefs.getString('selected_model') ?? '';
    sessionCookie = await _secure.read(key: _sessionKey) ?? '';
    final PackageInfo package = await PackageInfo.fromPlatform();
    currentVersion = package.version;
    currentBuild = int.tryParse(package.buildNumber) ?? 0;
    _restoreConversations(prefs.getString(_conversationKey));
    initialized = true;
    notifyListeners();
    await refreshConnection(silent: true);
    if (sessionCookie.isNotEmpty) await restoreSession();
    await checkForUpdates(silent: true);
  }

  void _restoreConversations(String? raw) {
    if (raw == null || raw.isEmpty) return;
    try {
      final Object? decoded = jsonDecode(raw);
      if (decoded is List<Object?>) {
        conversations = decoded
            .whereType<Map<Object?, Object?>>()
            .map((Map<Object?, Object?> item) =>
                Conversation.fromJson(Map<String, dynamic>.from(item)))
            .where((Conversation item) => item.id.isNotEmpty)
            .toList();
      }
    } on FormatException {
      conversations = <Conversation>[];
    }
    conversations.sort(
      (Conversation a, Conversation b) => b.updatedAt.compareTo(a.updatedAt),
    );
    if (conversations.isNotEmpty) activeConversationId = conversations.first.id;
  }

  Future<void> refreshConnection({bool silent = false}) async {
    if (connecting) return;
    connecting = true;
    if (!silent) errorMessage = null;
    notifyListeners();
    try {
      final List<Object> values = await Future.wait<Object>(<Future<Object>>[
        _api.health(),
        _api.config(),
      ]);
      health = values[0] as Map<String, dynamic>;
      serverConfig = values[1] as Map<String, dynamic>;
    } on Object catch (error) {
      health = null;
      if (!silent) errorMessage = error.toString();
    } finally {
      connecting = false;
      notifyListeners();
    }
  }

  Future<void> restoreSession() async {
    try {
      final Map<String, dynamic> value = await _api.session(sessionCookie);
      user = value['user'] is Map<Object?, Object?>
          ? Map<String, dynamic>.from(
              value['user'] as Map<Object?, Object?>,
            )
          : null;
      if (user != null) await refreshModels();
    } on Object {
      await _clearSession();
    }
    notifyListeners();
  }

  Future<bool> signIn(String email, String password) async {
    authenticating = true;
    errorMessage = null;
    notifyListeners();
    try {
      final AuthResult result =
          await _api.signIn(email: email, password: password);
      if (result.cookie.isEmpty) {
        throw const SuMeMeClientException('服务器未返回登录会话');
      }
      sessionCookie = result.cookie;
      await _secure.write(key: _sessionKey, value: sessionCookie);
      await restoreSession();
      return loggedIn;
    } on Object catch (error) {
      errorMessage = error.toString();
      return false;
    } finally {
      authenticating = false;
      notifyListeners();
    }
  }

  Future<bool> signUp(String name, String email, String password) async {
    authenticating = true;
    errorMessage = null;
    notifyListeners();
    try {
      final AuthResult result = await _api.signUp(
        name: name,
        email: email,
        password: password,
      );
      if (result.cookie.isEmpty) {
        throw const SuMeMeClientException('账户已创建，但服务器未返回登录会话');
      }
      sessionCookie = result.cookie;
      await _secure.write(key: _sessionKey, value: sessionCookie);
      await restoreSession();
      return loggedIn;
    } on Object catch (error) {
      errorMessage = error.toString();
      return false;
    } finally {
      authenticating = false;
      notifyListeners();
    }
  }

  Future<void> signOut() async {
    try {
      if (sessionCookie.isNotEmpty) await _api.signOut(sessionCookie);
    } on Object {
      // Local sign-out must still complete if the server session already expired.
    }
    await _clearSession();
    notifyListeners();
  }

  Future<void> _clearSession() async {
    sessionCookie = '';
    user = null;
    models = <String>[];
    selectedModel = '';
    await _secure.delete(key: _sessionKey);
  }

  Future<void> refreshModels() async {
    if (!loggedIn) return;
    try {
      models = await _api.models(sessionCookie);
      final String serverDefault =
          serverConfig?['default_model']?.toString() ?? '';
      if (selectedModel.isEmpty || !models.contains(selectedModel)) {
        selectedModel = models.contains(serverDefault)
            ? serverDefault
            : (models.isEmpty ? serverDefault : models.first);
      }
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setString('selected_model', selectedModel);
    } on Object catch (error) {
      errorMessage = error.toString();
    }
    notifyListeners();
  }

  void selectPage(int index) {
    selectedIndex = index;
    notifyListeners();
  }

  void selectModel(String value) {
    selectedModel = value;
    SharedPreferences.getInstance().then(
      (SharedPreferences prefs) => prefs.setString('selected_model', value),
    );
    notifyListeners();
  }

  Future<void> setDarkMode(bool value) async {
    darkMode = value;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('dark_mode', value);
    notifyListeners();
  }

  Future<void> setMemoryEnabled(bool value) async {
    memoryEnabled = value;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('memory_enabled', value);
    notifyListeners();
  }

  Conversation createConversation() {
    final Conversation conversation = Conversation(
      id: _id(),
      title: '新对话',
      updatedAt: DateTime.now(),
    );
    conversations.insert(0, conversation);
    activeConversationId = conversation.id;
    _persistConversations();
    notifyListeners();
    return conversation;
  }

  void activateConversation(String id) {
    activeConversationId = id;
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    final String normalized = text.trim();
    if (normalized.isEmpty || sending) return;
    if (!loggedIn) {
      errorMessage = '请先登录 SuMeMe 账户';
      notifyListeners();
      return;
    }
    if (selectedModel.isEmpty) {
      errorMessage = '服务端尚未配置可用模型，请联系管理员在 /admin 设置';
      notifyListeners();
      return;
    }
    final Conversation conversation = activeConversation ?? createConversation();
    final ChatMessage userMessage = ChatMessage(
      id: _id(),
      role: 'user',
      text: normalized,
      createdAt: DateTime.now(),
    );
    final ChatMessage assistant = ChatMessage(
      id: _id(),
      role: 'assistant',
      text: '',
      createdAt: DateTime.now(),
      streaming: true,
    );
    conversation.messages.addAll(<ChatMessage>[userMessage, assistant]);
    if (conversation.title == '新对话') {
      conversation.title = normalized.length > 24
          ? '${normalized.substring(0, 24)}…'
          : normalized;
    }
    sending = true;
    errorMessage = null;
    notifyListeners();
    try {
      final List<Map<String, String>> messages = conversation.messages
          .where((ChatMessage item) => item.id != assistant.id)
          .map(
            (ChatMessage item) => <String, String>{
              'role': item.role,
              'content': item.text,
            },
          )
          .toList(growable: false);
      await for (final String chunk in _api.streamChat(
        cookie: sessionCookie,
        conversationId: conversation.id,
        model: selectedModel,
        messages: messages,
        memoryEnabled: memoryEnabled,
      )) {
        assistant.text += chunk;
        notifyListeners();
      }
      if (assistant.text.trim().isEmpty) {
        assistant.text = '服务器没有返回可显示的文本。';
      }
    } on Object catch (error) {
      assistant.text = '请求失败：$error';
      errorMessage = error.toString();
    } finally {
      assistant.streaming = false;
      sending = false;
      conversation.updatedAt = DateTime.now();
      conversations.sort(
        (Conversation a, Conversation b) => b.updatedAt.compareTo(a.updatedAt),
      );
      await _persistConversations();
      notifyListeners();
    }
  }

  Future<void> searchMemory(String query) async {
    final String normalized = query.trim();
    if (!loggedIn || normalized.isEmpty) return;
    try {
      final Map<String, dynamic> result = await _api.searchMemory(
        cookie: sessionCookie,
        query: normalized,
      );
      memoryResult = result['context']?.toString() ?? '没有找到相关记忆。';
    } on Object catch (error) {
      errorMessage = error.toString();
    }
    notifyListeners();
  }

  Future<void> checkForUpdates({bool silent = false}) async {
    if (checkingUpdate) return;
    checkingUpdate = true;
    if (!silent) updateStatus = '正在检查更新…';
    notifyListeners();
    try {
      latestRelease = await _api.release(platform: platformName);
      if (latestRelease?.available != true) {
        updateStatus = '服务器尚未发布此平台版本';
      } else if (hasUpdate) {
        updateStatus = '发现新版本 ${latestRelease!.version}';
      } else {
        updateStatus = '当前已是最新版本';
      }
    } on Object catch (error) {
      updateStatus = '检查失败：$error';
      if (!silent) errorMessage = error.toString();
    } finally {
      checkingUpdate = false;
      notifyListeners();
    }
  }

  Future<bool> openUpdateDownload() async {
    final String url = latestRelease?.downloadUrl ?? '';
    if (url.isEmpty) {
      errorMessage = '当前版本没有可用下载地址';
      notifyListeners();
      return false;
    }
    final bool opened = await launchUrl(
      Uri.parse(url),
      mode: LaunchMode.externalApplication,
    );
    if (!opened) {
      errorMessage = '无法打开更新下载地址';
      notifyListeners();
    }
    return opened;
  }

  void clearError() {
    errorMessage = null;
    notifyListeners();
  }

  String _id() {
    final int now = DateTime.now().microsecondsSinceEpoch;
    final int salt = _random.nextInt(1 << 32);
    return '${now.toRadixString(16)}${salt.toRadixString(16).padLeft(8, '0')}';
  }

  Future<void> _persistConversations() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _conversationKey,
      jsonEncode(
        conversations.map((Conversation item) => item.toJson()).toList(),
      ),
    );
  }

  @override
  void dispose() {
    _api.close();
    super.dispose();
  }
}

int compareVersions(String left, String right) {
  List<int> parse(String value) => value
      .split('+')
      .first
      .split('-')
      .first
      .split('.')
      .map((String item) => int.tryParse(item) ?? 0)
      .toList();
  final List<int> a = parse(left);
  final List<int> b = parse(right);
  final int length = max(a.length, b.length);
  for (int index = 0; index < length; index += 1) {
    final int av = index < a.length ? a[index] : 0;
    final int bv = index < b.length ? b[index] : 0;
    if (av != bv) return av.compareTo(bv);
  }
  return 0;
}
