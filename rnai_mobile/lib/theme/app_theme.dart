import 'package:flutter/material.dart';

class AppColors {
  static const Color primary = Color(0xFF0B3945);
  static const Color accent = Color(0xFFD77757);
  static const Color tint = Color(0xFFFDF3EE);
  static const Color darkBg = Color(0xFF16191C);
  static const Color darkCard = Color(0xFF1E2226);
  static const Color lightBg = Color(0xFFF8F9FA);
  static const Color lightCard = Colors.white;
}

class AppTheme {
  static const Color brandInk = AppColors.primary;
  static const Color brandAccent = AppColors.accent;
  static const Color brandTint = AppColors.tint;
  static const Color darkBg = AppColors.darkBg;
  static const Color darkCard = AppColors.darkCard;
  static const Color lightBg = AppColors.lightBg;
  static const Color lightCard = AppColors.lightCard;

  static const List<String> thaiFontFallbacks = [
    'Thonburi',
    'Sukhumvit Set',
    'PingFang SC',
    'Helvetica Neue',
    'Apple Color Emoji',
  ];

  static ThemeData lightTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    fontFamilyFallback: thaiFontFallbacks,
    colorScheme: ColorScheme.fromSeed(
      seedColor: brandInk,
      primary: brandInk,
      secondary: brandAccent,
      surface: lightCard,
    ),
    scaffoldBackgroundColor: lightBg,
    appBarTheme: const AppBarTheme(
      backgroundColor: lightCard,
      foregroundColor: brandInk,
      elevation: 0,
      centerTitle: false,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: TextStyle(
        color: brandInk,
        fontSize: 18,
        fontWeight: FontWeight.bold,
        fontFamilyFallback: thaiFontFallbacks,
      ),
    ),
    cardTheme: CardThemeData(
      color: lightCard,
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFFE5E7EB)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: brandInk, width: 1.8),
      ),
    ),
  );

  static ThemeData darkTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    fontFamilyFallback: thaiFontFallbacks,
    colorScheme: ColorScheme.fromSeed(
      seedColor: brandAccent,
      brightness: Brightness.dark,
      primary: brandAccent,
      secondary: const Color(0xFFE8946F),
      surface: darkCard,
    ),
    scaffoldBackgroundColor: darkBg,
    appBarTheme: const AppBarTheme(
      backgroundColor: darkCard,
      foregroundColor: Colors.white,
      elevation: 0,
      centerTitle: false,
      surfaceTintColor: Colors.transparent,
      titleTextStyle: TextStyle(
        color: Colors.white,
        fontSize: 18,
        fontWeight: FontWeight.bold,
        fontFamilyFallback: thaiFontFallbacks,
      ),
    ),
    cardTheme: CardThemeData(
      color: darkCard,
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF23272B),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFF333940)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: Color(0xFF333940)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: brandAccent, width: 1.8),
      ),
    ),
  );
}
