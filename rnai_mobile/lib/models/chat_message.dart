class ChatMessage {
  final String id;
  final String role; // 'user' or 'assistant' / 'bot'
  final String content;
  final String? model;
  final DateTime timestamp;
  final bool isError;

  ChatMessage({
    String? id,
    required this.role,
    required this.content,
    this.model,
    DateTime? timestamp,
    this.isError = false,
  })  : id = id ?? DateTime.now().millisecondsSinceEpoch.toString(),
        timestamp = timestamp ?? DateTime.now();

  bool get isUser => role == 'user';

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
      role: json['role'] ?? 'user',
      content: json['content'] ?? '',
      model: json['model'],
      timestamp: json['ts'] != null
          ? DateTime.fromMillisecondsSinceEpoch((json['ts'] * 1000).toInt())
          : DateTime.now(),
    );
  }
}
