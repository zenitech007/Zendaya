import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

class ApiService {
  static const String baseUrl = 'http://localhost:8000';
  
  final http.Client _client = http.Client();

  Future<Map<String, dynamic>> sendMessage({
    required String message,
    String userId = 'default',
    Map<String, dynamic>? context,
    bool voiceEnabled = true,
  }) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/chat'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'message': message,
          'user_id': userId,
          'context': context,
          'voice_enabled': voiceEnabled,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Failed to send message: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Network error: $e');
    }
  }

  Future<String> transcribeAudio(Uint8List audioData) async {
    try {
      final request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/transcribe'),
      );
      
      request.files.add(
        http.MultipartFile.fromBytes(
          'audio_file',
          audioData,
          filename: 'audio.webm',
        ),
      );

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['transcript'] ?? '';
      } else {
        throw Exception('Transcription failed: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Transcription error: $e');
    }
  }

  Future<String?> synthesizeSpeech(String text) async {
    try {
      final response = await _client.post(
        Uri.parse('$baseUrl/synthesize'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'text': text,
          'voice_id': 'mxTlDrtKZzOqgjtBw4hM',
        }),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['audio_url'];
      } else {
        print('Speech synthesis failed: ${response.statusCode}');
        return null;
      }
    } catch (e) {
      print('Speech synthesis error: $e');
      return null;
    }
  }

  Future<Map<String, dynamic>> getHealth() async {
    try {
      final response = await _client.get(
        Uri.parse('$baseUrl/health'),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception('Health check failed: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Health check error: $e');
    }
  }

  void dispose() {
    _client.close();
  }
}