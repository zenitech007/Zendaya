class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final String? audioUrl;
  final bool isError;
  final Map<String, dynamic>? metadata;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.audioUrl,
    this.isError = false,
    this.metadata,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      text: json['text'] ?? '',
      isUser: json['isUser'] ?? false,
      timestamp: DateTime.parse(json['timestamp']),
      audioUrl: json['audioUrl'],
      isError: json['isError'] ?? false,
      metadata: json['metadata'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'text': text,
      'isUser': isUser,
      'timestamp': timestamp.toIso8601String(),
      'audioUrl': audioUrl,
      'isError': isError,
      'metadata': metadata,
    };
  }
}