import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'api_client.dart';

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
            .map(
              (Map<Object?, Object?> item) => ChatMessage.fromJson(
                Map<String, dynamic>.from(item),
              ),
            )
            .toList(),
      );
}

class MemoryResult {
  const MemoryResult({
    required this.query,
    required this.context,
    required this.provider,
    required this.storageMode,
  });

  final String query;
  final String context;
  final String provider;
  final String storageMode;
}

class SuMeMeAppState extends ChangeNotifier {
  SuMeMeAppState({SuMeMeApiClient? api}) : _api = api ?? SuMeMeApiClient();

  static const String defaultServerUrl = 'https://sumeme.mv3.cn';
  static const FlutterSecureStorage _secure = FlutterSecureStorage();
  static const String _conversationKey = 'sumeme.conversations.v1';

  final SuMeMeApiClient _api;
  final Random _random = Random.secure();

  bool initialized = false;
  bool connecting = false;
  bool sending = false;
  bool loadingMemories = false;
  bool loadingLibrary = false;
  bool loadingVaults = false;
  int selectedIndex = 0;
  String? errorMessage;

  String serverUrl = defaultServerUrl;
  String gatewayToken = '';
  String adminToken = '';
  String accountId = 'personal';
  String vaultId = 'default';
  String selectedModel = '';
  bool memoryEnabled = true;
  bool darkMode = false;

  Map<String, dynamic>? health;
  List<String> models = <String>[];
  List<Conversation> conversations = <Conversation>[];
  String? activeConversationId;
  List<MemoryResult> memoryResults = <MemoryResult>[];
  List<Map<String, dynamic>> libraryObjects = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> vaults = <Map<String, dynamic>>[];

  bool get isConnected => health?['status'] == 'ok';

  Conversation? get activeConversation {
    final String? id = activeConversationId;
    if (id == null) return null;
    for (final Conversation item in conversations) {
      if (item.id == id) return item;
    }
    return null;
  }

  Future<void> initialize() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    serverUrl = prefs.getString('server_url') ?? defaultServerUrl;
    accountId = prefs.getString('account_id') ?? 'personal';
    vaultId = prefs.getString('vault_id') ?? 'default';
    selectedModel = prefs.getString('selected_model') ?? '';
    memoryEnabled = prefs.getBool('memory_enabled') ?? true;
    darkMode = prefs.getBool('dark_mode') ?? false;
    gatewayToken = await _secure.read(key: 'gateway_token') ?? '';
    adminToken = await _secure.read(key: 'admin_token') ?? '';

    final String? encoded = prefs.getString(_conversationKey);
    if (encoded != null && encoded.isNotEmpty) {
      try {
        final Object? decoded = jsonDecode(encoded);
        if (decoded is List<Object?>) {
          conversations = decoded
              .whereType<Map<Object?, Object?>>()
              .map(
                (Map<Object?, Object?> item) => Conversation.fromJson(
                  Map<String, dynamic>.from(item),
                ),
              )
              .where((Conversation item) => item.id.isNotEmpty)
              .toList();
        }
      } on FormatException {
        conversations = <Conversation>[];
      }
    }
    conversations.sort(
      (Conversation a, Conversation b) => b.updatedAt.compareTo(a.updatedAt),
    );
    if (conversations.isNotEmpty) {
      activeConversationId = conversations.first.id;
    }
    initialized = true;
    notifyListeners();
    await refreshConnection(silent: true);
  }

  void selectPage(int index) {
    selectedIndex = index;
    notifyListeners();
  }

  void clearError() {
    errorMessage = null;
    notifyListeners();
  }

  Future<void> refreshConnection({bool silent = false}) async {
    if (connecting) return;
    connecting = true;
    if (!silent) errorMessage = null;
    notifyListeners();
    try {
      health = await _api.health(serverUrl);
      if (gatewayToken.isNotEmpty) {
        try {
          models = await _api.models(
            serverUrl: serverUrl,
            gatewayToken: gatewayToken,
          );
          if (selectedModel.isEmpty && models.isNotEmpty) {
            selectedModel = models.first;
          }
        } on SuMeMeApiException catch (error) {
          if (!silent) errorMessage = error.message;
        }
      }
    } on Object catch (error) {
      health = null;
      if (!silent) errorMessage = error.toString();
    } finally {
      connecting = false;
      notifyListeners();
    }
  }

  Future<void> saveSettings({
    required String nextServerUrl,
    required String nextGatewayToken,
    required String nextAdminToken,
    required String nextAccountId,
    required String nextVaultId,
    required String nextModel,
  }) async {
    serverUrl = nextServerUrl.trim().replaceFirst(RegExp(r'/+$'), '');
    gatewayToken = nextGatewayToken.trim();
    adminToken = nextAdminToken.trim();
    accountId = nextAccountId.trim().isEmpty ? 'personal' : nextAccountId.trim();
    vaultId = nextVaultId.trim().isEmpty ? 'default' : nextVaultId.trim();
    selectedModel = nextModel.trim();

    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString('server_url', serverUrl);
    await prefs.setString('account_id', accountId);
    await prefs.setString('vault_id', vaultId);
    await prefs.setString('selected_model', selectedModel);
    await _secure.write(key: 'gateway_token', value: gatewayToken);
    await _secure.write(key: 'admin_token', value: adminToken);
    await refreshConnection();
  }

  Future<void> setMemoryEnabled(bool value) async {
    memoryEnabled = value;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('memory_enabled', value);
    notifyListeners();
  }

  Future<void> setDarkMode(bool value) async {
    darkMode = value;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('dark_mode', value);
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

  Future<void> deleteConversation(String id) async {
    conversations.removeWhere((Conversation item) => item.id == id);
    if (activeConversationId == id) {
      activeConversationId = conversations.isEmpty ? null : conversations.first.id;
    }
    await _persistConversations();
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    final String normalized = text.trim();
    if (normalized.isEmpty || sending) return;
    if (gatewayToken.isEmpty) {
      errorMessage = '请先在设置中填写客户端 Gateway 凭据';
      selectedIndex = 6;
      notifyListeners();
      return;
    }
    if (selectedModel.isEmpty) {
      errorMessage = '没有可用模型，请在设置中填写模型名称或刷新模型列表';
      notifyListeners();
      return;
    }

    final Conversation conversation = activeConversation ?? createConversation();
    final ChatMessage user = ChatMessage(
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
    conversation.messages.addAll(<ChatMessage>[user, assistant]);
    if (conversation.title == '新对话') {
      conversation.title = normalized.length > 24
          ? '${normalized.substring(0, 24)}…'
          : normalized;
    }
    conversation.updatedAt = DateTime.now();
    sending = true;
    errorMessage = null;
    notifyListeners();

    try {
      final List<Map<String, String>> requestMessages = conversation.messages
          .where((ChatMessage item) => item.id != assistant.id)
          .map(
            (ChatMessage item) => <String, String>{
              'role': item.role,
              'content': item.text,
            },
          )
          .toList();
      if (!memoryEnabled) {
        requestMessages.insert(0, const <String, String>{
          'role': 'system',
          'content': '本轮不要使用或写入长期记忆。',
        });
      }
      await for (final String chunk in _api.streamChat(
        serverUrl: serverUrl,
        gatewayToken: gatewayToken,
        accountId: accountId,
        vaultId: vaultId,
        conversationId: conversation.id,
        model: selectedModel,
        messages: requestMessages,
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
    if (normalized.isEmpty || loadingMemories) return;
    if (adminToken.isEmpty) {
      errorMessage = '记忆检索需要管理员凭据；请在设置中填写';
      notifyListeners();
      return;
    }
    loadingMemories = true;
    errorMessage = null;
    notifyListeners();
    try {
      final Map<String, dynamic> result = await _api.searchMemory(
        serverUrl: serverUrl,
        adminToken: adminToken,
        accountId: accountId,
        vaultId: vaultId,
        query: normalized,
      );
      memoryResults.insert(
        0,
        MemoryResult(
          query: normalized,
          context: result['context']?.toString() ?? '',
          provider: result['provider']?.toString() ?? 'unknown',
          storageMode: result['storage_mode']?.toString() ?? 'unknown',
        ),
      );
    } on Object catch (error) {
      errorMessage = error.toString();
    } finally {
      loadingMemories = false;
      notifyListeners();
    }
  }

  Future<void> refreshLibrary() async {
    if (loadingLibrary) return;
    loadingLibrary = true;
    errorMessage = null;
    notifyListeners();
    try {
      libraryObjects = await _api.listObjects(
        serverUrl: serverUrl,
        gatewayToken: gatewayToken,
        accountId: accountId,
        vaultId: vaultId,
      );
    } on Object catch (error) {
      errorMessage = error.toString();
    } finally {
      loadingLibrary = false;
      notifyListeners();
    }
  }

  Future<void> refreshVaults() async {
    if (loadingVaults) return;
    loadingVaults = true;
    errorMessage = null;
    notifyListeners();
    try {
      vaults = await _api.listVaults(
        serverUrl: serverUrl,
        adminToken: adminToken,
        accountId: accountId,
      );
    } on Object catch (error) {
      errorMessage = error.toString();
    } finally {
      loadingVaults = false;
      notifyListeners();
    }
  }

  Future<void> updateVaultMode(String targetVault, String mode) async {
    if (adminToken.isEmpty) {
      errorMessage = '修改 Vault 策略需要管理员凭据';
      notifyListeners();
      return;
    }
    try {
      await _api.updateVault(
        serverUrl: serverUrl,
        adminToken: adminToken,
        accountId: accountId,
        vaultId: targetVault,
        storageMode: mode,
      );
      vaultId = targetVault;
      final SharedPreferences prefs = await SharedPreferences.getInstance();
      await prefs.setString('vault_id', vaultId);
      await refreshVaults();
    } on Object catch (error) {
      errorMessage = error.toString();
      notifyListeners();
    }
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
