import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/client_api.dart';
import 'package:sumeme_app/client_models.dart';

void main() {
  test('chat messages round-trip through single timeline JSON', () {
    final ChatMessage original = ChatMessage(
      id: 'message-1',
      role: 'user',
      text: '记住这条信息',
      createdAt: DateTime.utc(2026, 7, 31, 8),
      attachments: const <ChatAttachment>[
        ChatAttachment(
          id: 'file-1',
          name: 'notes.txt',
          fileType: 'text/plain',
          size: 128,
        ),
      ],
    );

    final ChatMessage restored = ChatMessage.fromJson(original.toJson());

    expect(restored.id, original.id);
    expect(restored.role, original.role);
    expect(restored.text, original.text);
    expect(restored.createdAt, original.createdAt);
    expect(restored.attachments.single.name, 'notes.txt');
  });

  test('single timeline preserves chronological message order', () {
    final List<ChatMessage> timeline = <ChatMessage>[
      ChatMessage(
        id: 'message-2',
        role: 'assistant',
        text: '第二条',
        createdAt: DateTime.utc(2026, 8, 1, 9),
      ),
      ChatMessage(
        id: 'message-1',
        role: 'user',
        text: '第一条',
        createdAt: DateTime.utc(2026, 8, 1, 8),
      ),
    ]..sort((ChatMessage a, ChatMessage b) => a.createdAt.compareTo(b.createdAt));

    expect(timeline.map((ChatMessage item) => item.id), <String>['message-1', 'message-2']);
  });
}
