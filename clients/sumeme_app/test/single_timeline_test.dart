import 'package:flutter_test/flutter_test.dart';
import 'package:sumeme_app/client_api.dart';
import 'package:sumeme_app/client_models.dart';
import 'package:sumeme_app/client_state.dart';

void main() {
  test('single timeline messages preserve attachments', () {
    final ChatMessage message = ChatMessage(
      id: 'm1',
      role: 'user',
      text: '分析这份资料',
      createdAt: DateTime.utc(2026, 8, 1, 8, 30),
      attachments: const <ChatAttachment>[
        ChatAttachment(
          id: 'file-1',
          name: 'report.pdf',
          fileType: 'application/pdf',
          size: 2048,
        ),
      ],
    );

    final ChatMessage restored = ChatMessage.fromJson(message.toJson());
    expect(restored.id, 'm1');
    expect(restored.attachments, hasLength(1));
    expect(restored.attachments.single.name, 'report.pdf');
  });

  test('semantic version comparison recognizes 0.5 update', () {
    expect(compareVersions('0.5.0', '0.4.0'), greaterThan(0));
    expect(compareVersions('0.5.0+12', '0.5.0+1'), 0);
    expect(compareVersions('0.4.9', '0.5.0'), lessThan(0));
  });
}
