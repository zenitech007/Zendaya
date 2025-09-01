import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:intl/intl.dart';

import '../models/chat_message.dart';

class ChatMessageWidget extends StatelessWidget {
  final ChatMessage message;
  final int index;

  const ChatMessageWidget({
    super.key,
    required this.message,
    required this.index,
  });

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;
    final theme = Theme.of(context);
    
    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            _buildAvatar(context, false),
            const SizedBox(width: 12),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: isUser
                    ? theme.colorScheme.primary
                    : message.isError
                        ? theme.colorScheme.errorContainer
                        : theme.colorScheme.surfaceVariant,
                borderRadius: BorderRadius.circular(20).copyWith(
                  bottomLeft: isUser ? const Radius.circular(20) : const Radius.circular(4),
                  bottomRight: isUser ? const Radius.circular(4) : const Radius.circular(20),
                ),
                boxShadow: [
                  BoxShadow(
                    color: (isUser ? theme.colorScheme.primary : theme.colorScheme.surfaceVariant)
                        .withOpacity(0.3),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    message.text,
                    style: TextStyle(
                      color: isUser
                          ? theme.colorScheme.onPrimary
                          : message.isError
                              ? theme.colorScheme.onErrorContainer
                              : theme.colorScheme.onSurfaceVariant,
                      fontSize: 16,
                      height: 1.4,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        DateFormat('HH:mm').format(message.timestamp),
                        style: TextStyle(
                          color: (isUser
                                  ? theme.colorScheme.onPrimary
                                  : theme.colorScheme.onSurfaceVariant)
                              .withOpacity(0.7),
                          fontSize: 12,
                        ),
                      ),
                      if (message.audioUrl != null) ...[
                        const SizedBox(width: 8),
                        Icon(
                          Icons.volume_up,
                          size: 16,
                          color: (isUser
                                  ? theme.colorScheme.onPrimary
                                  : theme.colorScheme.onSurfaceVariant)
                              .withOpacity(0.7),
                        ),
                      ],
                    ],
                  ),
                ],
              ),
            ),
          ),
          if (isUser) ...[
            const SizedBox(width: 12),
            _buildAvatar(context, true),
          ],
        ],
      ),
    );
  }

  Widget _buildAvatar(BuildContext context, bool isUser) {
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        color: isUser
            ? Theme.of(context).colorScheme.primary.withOpacity(0.1)
            : Theme.of(context).colorScheme.secondary.withOpacity(0.1),
        shape: BoxShape.circle,
        border: Border.all(
          color: isUser
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.secondary,
          width: 2,
        ),
      ),
      child: Icon(
        isUser ? Icons.person : Icons.smart_toy,
        color: isUser
            ? Theme.of(context).colorScheme.primary
            : Theme.of(context).colorScheme.secondary,
        size: 20,
      ),
    );
  }
}