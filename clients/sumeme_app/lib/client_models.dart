import 'package:flutter/foundation.dart';

import 'client_api.dart';

class ChatMessage {
  ChatMessage({
    required this.id,
    required this.role,
    required this.text,
    required this.createdAt,
    List<ChatAttachment>? attachments,
    this.streaming = false,
  }) : attachments = attachments ?? <ChatAttachment>[];

  final String id;
  final String role;
  String text;
  final DateTime createdAt;
  final List<ChatAttachment> attachments;
  bool streaming;

  Map<String, Object?> toJson() => <String, Object?>{
        'id': id,
        'role': role,
        'text': text,
        'created_at': createdAt.toIso8601String(),
        'attachments': attachments
            .map((ChatAttachment item) => item.toJson())
            .toList(growable: false),
      };

  factory ChatMessage.fromJson(Map<String, dynamic> json) => ChatMessage(
        id: json['id']?.toString() ?? '',
        role: json['role']?.toString() ?? 'user',
        text: json['text']?.toString() ?? '',
        createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ??
            DateTime.now(),
        attachments:
            (json['attachments'] as List<Object?>? ?? const <Object?>[])
                .whereType<Map<Object?, Object?>>()
                .map((Map<Object?, Object?> item) => ChatAttachment.fromJson(
                      Map<String, dynamic>.from(item),
                    ))
                .toList(),
      );
}

@immutable
class UploadProgress {
  const UploadProgress({
    required this.name,
    required this.progress,
    required this.stage,
  });

  final String name;
  final double progress;
  final String stage;
}
