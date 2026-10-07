import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/chat_screen.dart';
import 'services/api_service.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // ปรับแต่ง System UI Overlay (Status bar ให้เข้ากับแบรนด์)
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );

  final apiService = ApiService();
  await apiService.init();

  runApp(RnaiApp(apiService: apiService));
}

class RnaiApp extends StatelessWidget {
  final ApiService apiService;

  const RnaiApp({super.key, required this.apiService});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Rnai',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.system,
      home: ChatScreen(apiService: apiService),
    );
  }
}
