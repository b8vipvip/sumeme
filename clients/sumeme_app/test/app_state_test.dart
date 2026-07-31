import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/app_state.dart';

void main() {
  test('chat messages round-trip through local persistence JSON', () {
    final ChatMessage original = ChatMessage(
      id: 'message-1',
      role: 'user',
      text: '记住这条信息',
      createdAt: DateTime.utc(2026, 7, 31, 8),
    );

    final ChatMessage restored = ChatMessage.fromJson(original.toJson());

    expect(restored.id, original.id);
    expect(restored.role, original.role);
    expect(restored.text, original.text);
    expect(restored.createdAt, original.createdAt);
  });

  test('conversation persistence keeps messages and metadata', () {
    final Conversation original = Conversation(
      id: 'conversation-1',
      title: '原生客户端设计',
      updatedAt: DateTime.utc(2026, 7, 31, 9),
      messages: <ChatMessage>[
        ChatMessage(
          id: 'message-1',
          role: 'assistant',
          text: '已切换到原生 Flutter UI。',
          createdAt: DateTime.utc(2026, 7, 31, 9),
        ),
      ],
    );

    final Conversation restored = Conversation.fromJson(original.toJson());

    expect(restored.id, original.id);
    expect(restored.title, original.title);
    expect(restored.updatedAt, original.updatedAt);
    expect(restored.messages, hasLength(1));
    expect(restored.messages.single.text, contains('原生 Flutter UI'));
  });
}
