part of 'client_state.dart';

extension SuMeMeClientChatState on SuMeMeClientState {
  Future<void> sendMessage(String text) async {
    final String normalized = text.trim();
    if ((normalized.isEmpty && pendingAttachments.isEmpty) || sending) return;
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

    final List<ChatAttachment> attachments =
        List<ChatAttachment>.from(pendingAttachments);
    pendingAttachments.clear();
    final String attachmentSummary = attachments.isEmpty
        ? ''
        : attachments.map((ChatAttachment item) => item.name).join('、');
    final String displayText = normalized.isNotEmpty
        ? normalized
        : '请查看我上传的资料：$attachmentSummary';
    final ChatMessage userMessage = ChatMessage(
      id: _id(),
      role: 'user',
      text: displayText,
      createdAt: DateTime.now(),
      attachments: attachments,
    );
    final ChatMessage assistant = ChatMessage(
      id: _id(),
      role: 'assistant',
      text: '',
      createdAt: DateTime.now(),
      streaming: true,
    );
    timeline.addAll(<ChatMessage>[userMessage, assistant]);
    sending = true;
    errorMessage = null;
    notifyListeners();

    try {
      final List<ChatMessage> context = visibleTimeline
          .where((ChatMessage item) => item.id != assistant.id)
          .toList(growable: false);
      final int start = max(0, context.length - 80);
      final List<Map<String, Object?>> messages = context
          .sublist(start)
          .map((ChatMessage item) {
        String content = item.text;
        if (item.attachments.isNotEmpty) {
          final String names = item.attachments
              .map((ChatAttachment attachment) =>
                  '${attachment.name} [file_id=${attachment.id}]')
              .join('\n');
          content = '$content\n\n已上传资料：\n$names';
        }
        return <String, Object?>{'role': item.role, 'content': content};
      }).toList(growable: false);
      await for (final String chunk in _api.streamChat(
        cookie: sessionCookie,
        conversationId: conversationId,
        model: selectedModel,
        messages: messages,
        memoryEnabled: memoryEnabled,
        fileIds: attachments
            .map((ChatAttachment item) => item.id)
            .where((String id) => id.isNotEmpty)
            .toList(growable: false),
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
      await _persistTimeline();
      notifyListeners();
    }
  }

  Future<List<ChatMessage>> searchLocalHistory({
    String keyword = '',
    DateTime? start,
    DateTime? end,
  }) async {
    final String query = keyword.trim().toLowerCase();
    return timeline.where((ChatMessage message) {
      if (start != null && message.createdAt.isBefore(start)) return false;
      if (end != null && message.createdAt.isAfter(end)) return false;
      if (query.isEmpty) return true;
      return message.text.toLowerCase().contains(query) ||
          message.attachments.any(
            (ChatAttachment item) => item.name.toLowerCase().contains(query),
          );
    }).toList(growable: false);
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
}
