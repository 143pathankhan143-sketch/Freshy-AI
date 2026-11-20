class ChatMessage {
  final String id;
  final String sender; // 'user' | 'freshy' | 'system'
  final String text;
  final DateTime timestamp;
  final String? intentName;
  final bool actionExecuted;

  ChatMessage({
    required this.id,
    required this.sender,
    required this.text,
    required this.timestamp,
    this.intentName,
    this.actionExecuted = false,
  });

  bool get isUser => sender == 'user';
  bool get isFreshy => sender == 'freshy';
}
