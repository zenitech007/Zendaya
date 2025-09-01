import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';

class VoiceButton extends StatelessWidget {
  final bool isRecording;
  final bool isLoading;
  final VoidCallback onStartRecording;
  final VoidCallback onStopRecording;

  const VoiceButton({
    super.key,
    required this.isRecording,
    required this.isLoading,
    required this.onStartRecording,
    required this.onStopRecording,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    
    return GestureDetector(
      onTapDown: isLoading ? null : (_) => onStartRecording(),
      onTapUp: isLoading ? null : (_) => onStopRecording(),
      onTapCancel: isLoading ? null : onStopRecording,
      child: Container(
        width: 56,
        height: 56,
        decoration: BoxDecoration(
          color: isRecording
              ? theme.colorScheme.error
              : theme.colorScheme.primary,
          shape: BoxShape.circle,
          boxShadow: [
            BoxShadow(
              color: (isRecording
                      ? theme.colorScheme.error
                      : theme.colorScheme.primary)
                  .withOpacity(0.3),
              blurRadius: isRecording ? 20 : 8,
              spreadRadius: isRecording ? 4 : 0,
            ),
          ],
        ),
        child: Icon(
          isRecording ? Icons.stop : Icons.mic,
          color: theme.colorScheme.onPrimary,
          size: 24,
        ),
      ).animate(target: isRecording ? 1 : 0)
          .scale(
            begin: const Offset(1.0, 1.0),
            end: const Offset(1.1, 1.1),
            duration: 200.ms,
          )
          .then()
          .scale(
            begin: const Offset(1.1, 1.1),
            end: const Offset(1.0, 1.0),
            duration: 800.ms,
          ),
    );
  }
}