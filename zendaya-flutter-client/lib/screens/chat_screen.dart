import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../providers/chat_provider.dart';
import '../widgets/chat_message_widget.dart';
import '../widgets/voice_button.dart';
import '../widgets/connection_status.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  @override
  void dispose() {
    _textController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _sendMessage() {
    final text = _textController.text.trim();
    if (text.isNotEmpty) {
      context.read<ChatProvider>().sendMessage(text);
      _textController.clear();
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary,
                shape: BoxShape.circle,
                boxShadow: [
                  BoxShadow(
                    color: Theme.of(context).colorScheme.primary.withOpacity(0.5),
                    blurRadius: 8,
                    spreadRadius: 2,
                  ),
                ],
              ),
            ).animate(onPlay: (controller) => controller.repeat())
                .scale(duration: 1000.ms, begin: const Offset(0.8, 0.8), end: const Offset(1.2, 1.2))
                .then()
                .scale(duration: 1000.ms, begin: const Offset(1.2, 1.2), end: const Offset(0.8, 0.8)),
            const SizedBox(width: 12),
            const Text('Zendaya'),
          ],
        ),
        actions: [
          Consumer<ChatProvider>(
            builder: (context, chatProvider, child) {
              return ConnectionStatus(
                isConnected: chatProvider.isConnected,
                status: chatProvider.connectionStatus,
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                return ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(16),
                  itemCount: chatProvider.messages.length,
                  itemBuilder: (context, index) {
                    final message = chatProvider.messages[index];
                    return ChatMessageWidget(
                      message: message,
                      index: index,
                    ).animate()
                        .slideY(
                          begin: 0.3,
                          duration: 400.ms,
                          curve: Curves.easeOut,
                        )
                        .fadeIn(duration: 400.ms);
                  },
                );
              },
            ),
          ),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.surface,
              border: Border(
                top: BorderSide(
                  color: Theme.of(context).dividerColor.withOpacity(0.1),
                ),
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    decoration: InputDecoration(
                      hintText: 'Ask Zendaya anything...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(24),
                        borderSide: BorderSide.none,
                      ),
                      filled: true,
                      fillColor: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.3),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 20,
                        vertical: 12,
                      ),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                    textInputAction: TextInputAction.send,
                  ),
                ),
                const SizedBox(width: 12),
                Consumer<ChatProvider>(
                  builder: (context, chatProvider, child) {
                    return VoiceButton(
                      isRecording: chatProvider.isRecording,
                      isLoading: chatProvider.isLoading,
                      onStartRecording: () => chatProvider.startVoiceRecording(),
                      onStopRecording: () => chatProvider.stopVoiceRecording(),
                    );
                  },
                ),
                const SizedBox(width: 8),
                Consumer<ChatProvider>(
                  builder: (context, chatProvider, child) {
                    return FloatingActionButton(
                      onPressed: chatProvider.isLoading ? null : _sendMessage,
                      mini: true,
                      child: chatProvider.isLoading
                          ? SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Theme.of(context).colorScheme.onPrimary,
                              ),
                            )
                          : const Icon(Icons.send),
                    );
                  },
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}