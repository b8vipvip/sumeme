part of 'client_state.dart';

extension SuMeMeClientLibraryState on SuMeMeClientState {
  Future<void> uploadFiles(List<UploadFileData> files) async {
    if (!loggedIn || uploading || files.isEmpty) return;
    uploading = true;
    errorMessage = null;
    notifyListeners();
    try {
      for (final UploadFileData file in files) {
        final LibraryItem item = await _api.uploadFile(
          cookie: sessionCookie,
          file: file,
          onProgress: (double progress, String stage) {
            uploadProgress[file.name] = UploadProgress(
              name: file.name,
              progress: progress,
              stage: stage,
            );
            notifyListeners();
          },
        );
        pendingAttachments.add(ChatAttachment.fromLibraryItem(item));
      }
      await refreshLibrary(silent: true);
    } on Object catch (error) {
      errorMessage = error.toString();
    } finally {
      uploading = false;
      Future<void>.delayed(const Duration(seconds: 2), () {
        uploadProgress.clear();
        notifyListeners();
      });
      notifyListeners();
    }
  }

  void removePendingAttachment(String id) {
    pendingAttachments.removeWhere((ChatAttachment item) => item.id == id);
    notifyListeners();
  }

  Future<void> refreshLibrary({bool silent = false}) async {
    if (!loggedIn || loadingLibrary) return;
    loadingLibrary = true;
    if (!silent) errorMessage = null;
    notifyListeners();
    try {
      libraryItems = await _api.listFiles(cookie: sessionCookie, limit: 500);
      libraryItems.sort((LibraryItem a, LibraryItem b) =>
          b.createdAt.compareTo(a.createdAt));
    } on Object catch (error) {
      if (!silent) errorMessage = error.toString();
    } finally {
      loadingLibrary = false;
      notifyListeners();
    }
  }

  void setLibraryQuery(String value) {
    libraryQuery = value;
    notifyListeners();
  }

  Future<void> renameLibraryItem(LibraryItem item, String name) async {
    final String normalized = name.trim();
    if (normalized.isEmpty) return;
    try {
      await _api.renameFile(
        cookie: sessionCookie,
        id: item.id,
        name: normalized,
      );
      await refreshLibrary(silent: true);
    } on Object catch (error) {
      errorMessage = error.toString();
      notifyListeners();
    }
  }

  Future<void> deleteLibraryItem(LibraryItem item) async {
    try {
      await _api.deleteFile(cookie: sessionCookie, id: item.id);
      libraryItems.removeWhere((LibraryItem value) => value.id == item.id);
      notifyListeners();
    } on Object catch (error) {
      errorMessage = error.toString();
      notifyListeners();
    }
  }
}
