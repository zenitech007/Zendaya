import 'package:flutter/foundation.dart';
import 'dart:typed_data';

import '../services/api_service.dart';
import '../services/audio_service.dart';
import '../models/chat_message.dart';

class ChatProvider extends ChangeNotifier {
  final ApiService _apiService;
  final AudioService _audioService;
  
  final List<ChatMessage> _messages = [];
  bool _isLoading = false;
  bool _isRecording = false;
  bool _isConnected = true;
  String _connectionStatus = 'Connected';

  ChatProvider({
    required ApiService apiService,
    required AudioService audioService,
  }) : _apiService = apiService, _audioService = audioService {
    _checkConnection();
  }

  List<ChatMessage> get messages => List.unmodifiable(_messages);
  bool get isLoading => _isLoading;
  bool get isRecording => _isRecording;
  bool get isConnected => _isConnected;
  String get connectionStatus => _connectionStatus;

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    // Add user message
    final userMessage = ChatMessage(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    );
    _messages.add(userMessage);
    notifyListeners();

    _isLoading = true;
    notifyListeners();

    try {
      final response = await _apiService.sendMessage(
        message: text,
        voiceEnabled: true,
      );

      // Add AI response
      final aiMessage = ChatMessage(
        text: response['text'] ?? 'No response',
        isUser: false,
        timestamp: DateTime.now(),
        audioUrl: response['audio_url'],
      );
      _messages.add(aiMessage);

      // Play audio if available
      if (aiMessage.audioUrl != null) {
        await _audioService.playAudioFromUrl(aiMessage.audioUrl!);
      }

    } catch (e) {
      final errorMessage = ChatMessage(
        text: 'Sorry, I encountered an error: ${e.toString()}',
        isUser: false,
        timestamp: DateTime.now(),
        isError: true,
      );
      _messages.add(errorMessage);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> startVoiceRecording() async {
    try {
      _isRecording = await _audioService.startRecording();
      notifyListeners();
    } catch (e) {
      print('Failed to start recording: $e');
    }
  }

  Future<void> stopVoiceRecording() async {
    try {
      final audioData = await _audioService.stopRecording();
      _isRecording = false;
      notifyListeners();

      if (audioData != null && audioData.isNotEmpty) {
        _isLoading = true;
        notifyListeners();

        try {
          final transcript = await _apiService.transcribeAudio(audioData);
          if (transcript.isNotEmpty) {
            await sendMessage(transcript);
          }
        } catch (e) {
          final errorMessage = ChatMessage(
            text: 'Voice transcription failed: ${e.toString()}',
            isUser: false,
            timestamp: DateTime.now(),
            isError: true,
          );
          _messages.add(errorMessage);
        } finally {
          _isLoading = false;
          notifyListeners();
        }
      }
    } catch (e) {
      _isRecording = false;
      notifyListeners();
      print('Failed to stop recording: $e');
    }
  }

  Future<void> _checkConnection() async {
    try {
      final health = await _apiService.getHealth();
      _isConnected = health['status'] == 'healthy';
      _connectionStatus = _isConnected ? 'Connected' : 'Service Degraded';
    } catch (e) {
      _isConnected = false;
      _connectionStatus = 'Offline';
    }
    notifyListeners();
  }

  void clearMessages() {
    _messages.clear();
    notifyListeners();
  }

  @override
  void dispose() {
    _audioService.dispose();
    _apiService.dispose();
    super.dispose();
  }
}