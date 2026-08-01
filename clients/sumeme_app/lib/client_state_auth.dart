// ignore_for_file: invalid_use_of_protected_member, invalid_use_of_visible_for_testing_member

part of 'client_state.dart';

extension SuMeMeClientAuthState on SuMeMeClientState {
  Future<void> restoreSession() async {
    try {
      final Map<String, dynamic> value = await _api.session(sessionCookie);
      user = value['user'] is Map<Object?, Object?>
          ? Map<String, dynamic>.from(value['user']! as Map<Object?, Object?>)
          : null;
      if (user != null) {
        await _restoreTimeline(accountId);
        await refreshModels();
      }
    } on Object {
      await _clearSession();
      await _restoreTimeline('anonymous');
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
      await SuMeMeClientState._secure.write(
        key: SuMeMeClientState._sessionKey,
        value: sessionCookie,
      );
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
      await SuMeMeClientState._secure.write(
        key: SuMeMeClientState._sessionKey,
        value: sessionCookie,
      );
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
    final String previousId = accountId;
    await _persistTimeline(id: previousId);
    try {
      if (sessionCookie.isNotEmpty) await _api.signOut(sessionCookie);
    } on Object {
      // Local sign-out must still complete if the server session expired.
    }
    await _clearSession();
    timeline.clear();
    pendingAttachments.clear();
    libraryItems = <LibraryItem>[];
    currentSection = 'chat';
    notifyListeners();
  }

  Future<void> _clearSession() async {
    sessionCookie = '';
    user = null;
    models = <String>[];
    selectedModel = '';
    await SuMeMeClientState._secure.delete(key: SuMeMeClientState._sessionKey);
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
}
