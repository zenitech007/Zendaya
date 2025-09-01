import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:record/record.dart';
import 'package:permission_handler/permission_handler.dart';

class AudioService {
  final AudioRecorder _recorder = AudioRecorder();
  final AudioPlayer _player = AudioPlayer();
  
  bool _isRecording = false;
  bool _isPlaying = false;

  bool get isRecording => _isRecording;
  bool get isPlaying => _isPlaying;

  Future<bool> requestPermissions() async {
    final status = await Permission.microphone.request();
    return status == PermissionStatus.granted;
  }

  Future<bool> startRecording() async {
    try {
      if (!await requestPermissions()) {
        throw Exception('Microphone permission denied');
      }

      if (await _recorder.hasPermission()) {
        await _recorder.start(
          const RecordConfig(
            encoder: AudioEncoder.opus,
            bitRate: 128000,
            sampleRate: 48000,
          ),
        );
        _isRecording = true;
        return true;
      }
      return false;
    } catch (e) {
      print('Recording start error: $e');
      return false;
    }
  }

  Future<Uint8List?> stopRecording() async {
    try {
      final path = await _recorder.stop();
      _isRecording = false;
      
      if (path != null) {
        // In a real implementation, you'd read the file and return the bytes
        // For now, return empty data as placeholder
        return Uint8List(0);
      }
      return null;
    } catch (e) {
      print('Recording stop error: $e');
      _isRecording = false;
      return null;
    }
  }

  Future<void> playAudioFromUrl(String audioUrl) async {
    try {
      _isPlaying = true;
      await _player.play(UrlSource(audioUrl));
      
      // Listen for completion
      _player.onPlayerComplete.listen((_) {
        _isPlaying = false;
      });
      
    } catch (e) {
      print('Audio playback error: $e');
      _isPlaying = false;
    }
  }

  Future<void> stopPlayback() async {
    try {
      await _player.stop();
      _isPlaying = false;
    } catch (e) {
      print('Stop playback error: $e');
    }
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
  }
}