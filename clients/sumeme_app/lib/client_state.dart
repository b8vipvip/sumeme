import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import 'client_api.dart';
import 'client_models.dart';

part 'client_state_auth.dart';
part 'client_state_chat.dart';
part 'client_state_library.dart';

class SuMeMeClientState extends ChangeNotifier {
  SuMeMeClientState({SuMeMeClientApi? api}) : _api = api ?? SuMeMeClientApi();

  static const FlutterSecureStorage _secure = FlutterSecureStorage();
  static const String _sessionKey = 'sumeme.session.cookie.v2';
  static const String _legacyConversationKey = 'sumeme.conversations.v2';
  static const String _timelineKey = 'sumeme.single_timeline.v1';
  static const String _hideHistoryKey = 'sumeme.hide_history.v1';
  static const String _historyCutoffKey = 'sumeme.history_cutoff.v1';

  final SuMeMeClientApi _api;
  final Random _random = Random.secure();

  bool initialized = false;
  bool connecting = false;
  bool authenticating = false;
  bool sending = false;
  bool checkingUpdate = false;
  bool darkMode = false;
  bool memoryEnabled = true;
  bool hideHistory = false;
  bool autoScroll = true;
  bool loadingLibrary = false;
  bool uploading = false;
  int visibleMessageLimit = 80;
  double textScale = 1;
  String? errorMessage;
  String currentSection = 'chat';

  String sessionCookie = '';
  Map<String, dynamic>? user;
  Map<String, dynamic>? health;
  Map<String, dynamic>? serverConfig;
  List<String> models = <String>[];
  String selectedModel = '';
  final List<ChatMessage> timeline = <ChatMessage>[];
  DateTime? historyCutoff;
  final List<ChatAttachment> pendingAttachments = <ChatAttachment>[];
  final Map<String, UploadProgress> uploadProgress = <String, UploadProgress>{};
  List<LibraryItem> libraryItems = <LibraryItem>[];
  String libraryQuery = '';
  String currentVersion = '0.0.0';
  int currentBuild = 0;
  ReleaseInfo? latestRelease;
  String updateStatus = '尚未检查更新';
  String memoryResult = '';

  bool get loggedIn => user != null && sessionCookie.isNotEmpty;
  bool get isConnected => health?['status'] == 'ok';
  bool get registrationEnabled => serverConfig?['registration_enabled'] != false;
  String get platformName => Platform.isAndroid ? 'android' : 'windows';
  bool get hasUpdate => latestRelease != null &&
      latestRelease!.available &&
      compareVersions(latestRelease!.version, currentVersion) > 0;
  String get accountId => user?['id']?.toString() ?? 'anonymous';
  String get conversationId => 'sumeme-single-$accountId';

  List<ChatMessage> get visibleTimeline {
    final DateTime? cutoff = hideHistory ? historyCutoff : null;
    if (cutoff == null) return List<ChatMessage>.unmodifiable(timeline);
    return timeline
        .where((ChatMessage message) => !message.createdAt.isBefore(cutoff))
        .toList(growable: false);
  }

  List<ChatMessage> get displayedMessages {
    final List<ChatMessage> source = visibleTimeline;
    if (source.length <= visibleMessageLimit) return source;
    return source.sublist(source.length - visibleMessageLimit);
  }

  bool get canLoadOlder => visibleTimeline.length > visibleMessageLimit;

  List<LibraryItem> get filteredLibraryItems {
    final String query = libraryQuery.trim().toLowerCase();
    if (query.isEmpty) return List<LibraryItem>.unmodifiable(libraryItems);
    return libraryItems
        .where((LibraryItem item) =>
            item.name.toLowerCase().contains(query) ||
            item.fileType.toLowerCase().contains(query))
        .toList(growable: false);
  }

  Future<void> initialize() async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    darkMode = prefs.getBool('dark_mode') ?? false;
    memoryEnabled = prefs.getBool('memory_enabled') ?? true;
    autoScroll = prefs.getBool('auto_scroll') ?? true;
    textScale = prefs.getDouble('text_scale') ?? 1;
    selectedModel = prefs.getString('selected_model') ?? '';
    sessionCookie = await _secure.read(key: _sessionKey) ?? '';
    final PackageInfo package = await PackageInfo.fromPlatform();
    currentVersion = package.version;
    currentBuild = int.tryParse(package.buildNumber) ?? 0;
    initialized = true;
    notifyListeners();
    await refreshConnection(silent: true);
    if (sessionCookie.isNotEmpty) {
      await restoreSession();
    } else {
      await _restoreTimeline('anonymous');
    }
    await checkForUpdates(silent: true);
  }

  String _scopedKey(String base, String id) => '$base.$id';

  Future<void> _restoreTimeline(String id) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    timeline.clear();
    final String? raw = prefs.getString(_scopedKey(_timelineKey, id));
    if (raw != null && raw.isNotEmpty) {
      try {
        final Object? decoded = jsonDecode(raw);
        if (decoded is List<Object?>) {
          timeline.addAll(decoded
              .whereType<Map<Object?, Object?>>()
              .map((Map<Object?, Object?> item) => ChatMessage.fromJson(
                    Map<String, dynamic>.from(item),
                  ))
              .where((ChatMessage item) => item.id.isNotEmpty));
        }
      } on FormatException {
        timeline.clear();
      }
    } else {
      await _migrateLegacyConversations(prefs, id);
    }
    timeline.sort((ChatMessage a, ChatMessage b) =>
        a.createdAt.compareTo(b.createdAt));
    hideHistory = prefs.getBool(_scopedKey(_hideHistoryKey, id)) ?? false;
    historyCutoff = DateTime.tryParse(
      prefs.getString(_scopedKey(_historyCutoffKey, id)) ?? '',
    );
    if (hideHistory && historyCutoff == null) historyCutoff = DateTime.now();
    visibleMessageLimit = 80;
    notifyListeners();
  }

  Future<void> _migrateLegacyConversations(
    SharedPreferences prefs,
    String id,
  ) async {
    final String? legacy = prefs.getString(_legacyConversationKey);
    if (legacy == null || legacy.isEmpty) return;
    try {
      final Object? decoded = jsonDecode(legacy);
      if (decoded is! List<Object?>) return;
      for (final Object? rawConversation in decoded) {
        if (rawConversation is! Map<Object?, Object?>) continue;
        final Object? rawMessages = rawConversation['messages'];
        if (rawMessages is! List<Object?>) continue;
        timeline.addAll(rawMessages
            .whereType<Map<Object?, Object?>>()
            .map((Map<Object?, Object?> item) => ChatMessage.fromJson(
                  Map<String, dynamic>.from(item),
                )));
      }
      timeline.sort((ChatMessage a, ChatMessage b) =>
          a.createdAt.compareTo(b.createdAt));
      await _persistTimeline(id: id);
    } on FormatException {
      return;
    }
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

  void setSection(String section) {
    currentSection = section;
    notifyListeners();
    if (section == 'library' && loggedIn && libraryItems.isEmpty) {
      refreshLibrary();
    }
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

  Future<void> setAutoScroll(bool value) async {
    autoScroll = value;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool('auto_scroll', value);
    notifyListeners();
  }

  Future<void> setTextScale(double value) async {
    textScale = value.clamp(0.9, 1.3);
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('text_scale', textScale);
    notifyListeners();
  }

  Future<void> setHideHistory(bool value) async {
    hideHistory = value;
    historyCutoff = value ? DateTime.now() : null;
    visibleMessageLimit = 80;
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_scopedKey(_hideHistoryKey, accountId), value);
    if (historyCutoff == null) {
      await prefs.remove(_scopedKey(_historyCutoffKey, accountId));
    } else {
      await prefs.setString(
        _scopedKey(_historyCutoffKey, accountId),
        historyCutoff!.toIso8601String(),
      );
    }
    notifyListeners();
  }

  void loadOlderMessages() {
    if (!canLoadOlder) return;
    visibleMessageLimit = min(visibleTimeline.length, visibleMessageLimit + 100);
    notifyListeners();
  }

  Future<void> clearVisibleHistory() async {
    if (hideHistory && historyCutoff != null) {
      timeline.removeWhere(
        (ChatMessage message) => !message.createdAt.isBefore(historyCutoff!),
      );
    } else {
      timeline.clear();
    }
    await _persistTimeline();
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

  Future<void> _persistTimeline({String? id}) async {
    final SharedPreferences prefs = await SharedPreferences.getInstance();
    await prefs.setString(
      _scopedKey(_timelineKey, id ?? accountId),
      jsonEncode(timeline.map((ChatMessage item) => item.toJson()).toList()),
    );
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
      .map((String part) => int.tryParse(part) ?? 0)
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
