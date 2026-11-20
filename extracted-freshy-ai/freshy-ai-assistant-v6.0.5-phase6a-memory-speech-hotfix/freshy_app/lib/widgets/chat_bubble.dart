import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../models/chat_message.dart';

class ChatBubble extends StatelessWidget {
  final ChatMessage message;

  const ChatBubble({Key? key, required this.message}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final timeStr = DateFormat('hh:mm a').format(message.timestamp);

    return LayoutBuilder(
      builder: (context, constraints) {
        final maxBubbleWidth = (constraints.maxWidth * 0.86)
            .clamp(240.0, 560.0)
            .toDouble();
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6.0, horizontal: 12.0),
          child: Align(
            alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              constraints: BoxConstraints(maxWidth: maxBubbleWidth),
          padding: const EdgeInsets.all(14.0),
          decoration: BoxDecoration(
            color: isUser
                ? const Color(0xFF003859)
                : const Color(0xFF131F33),
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: Radius.circular(isUser ? 16 : 4),
              bottomRight: Radius.circular(isUser ? 4 : 16),
            ),
            border: Border.all(
              color: isUser
                  ? const Color(0xFF00F2FE).withOpacity(0.5)
                  : const Color(0xFF1E2D4A),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: isUser
                    ? const Color(0xFF00F2FE).withOpacity(0.08)
                    : Colors.black.withOpacity(0.3),
                blurRadius: 8,
                offset: const Offset(0, 4),
              )
            ],
          ),
          child: Column(
            crossAxisAlignment:
                isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    isUser ? 'YOU' : 'FRESHY AI',
                    style: TextStyle(
                      color: isUser ? const Color(0xFF00F2FE) : const Color(0xFF4FACFE),
                      fontSize: 10,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.0,
                    ),
                  ),
                  if (message.intentName != null) ...[
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: const Color(0xFF00F2FE).withOpacity(0.15),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        message.intentName!,
                        style: const TextStyle(
                          color: Color(0xFF00F2FE),
                          fontSize: 9,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 6),
              Text(
                message.text,
                style: const TextStyle(
                  color: Color(0xFFE2E8F0),
                  fontSize: 14,
                  height: 1.4,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                timeStr,
                style: TextStyle(
                  color: Colors.white.withOpacity(0.4),
                  fontSize: 10,
                ),
              ),
            ],
          ),
            ),
          ),
        );
      },
    );
  }
}
