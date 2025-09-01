import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flutter_animate/flutter_animate.dart';

import 'services/api_service.dart';
import 'services/audio_service.dart';
import 'providers/chat_provider.dart';
import 'screens/chat_screen.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ZendayaApp());
}

class ZendayaApp extends StatelessWidget {
  const ZendayaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
        Provider<AudioService>(create: (_) => AudioService()),
        ChangeNotifierProvider<ChatProvider>(
          create: (context) => ChatProvider(
            apiService: context.read<ApiService>(),
            audioService: context.read<AudioService>(),
          ),
        ),
      ],
      child: MaterialApp(
        title: 'Zendaya AI Assistant',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        home: const ChatScreen(),
        debugShowCheckedModeBanner: false,
      ).animate().fadeIn(duration: 800.ms),
    );
  }
}