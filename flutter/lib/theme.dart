// lib/theme.dart
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class PBTheme {
  // ── Culori principale ────────────────────────────────────────────────────
  static const Color bg = Color(0xFF0D0D14);
  static const Color surface = Color(0xFF12121E);
  static const Color card = Color(0xFF16162A);
  static const Color border = Color(0xFF222232);
  static const Color accent = Color(0xFF00D4FF); // albastru PBRunner
  static const Color accentGlow = Color(0x3300D4FF);
  static const Color green = Color(0xFF00D264);
  static const Color orange = Color(0xFFFFA500);
  static const Color red = Color(0xFFDD2222);
  static const Color textPrimary = Color(0xFFE8E8F0);
  static const Color textSecondary = Color(0xFF8888A0);
  static const Color textDim = Color(0xFF555568);

  // ── Gradiente ────────────────────────────────────────────────────────────
  static const LinearGradient accentGrad = LinearGradient(
    colors: [Color(0xFF00D4FF), Color(0xFF0066FF)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );
  static const LinearGradient bgGrad = LinearGradient(
    colors: [Color(0xFF0D0D14), Color(0xFF111120)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static ThemeData get theme => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: bg,
    colorScheme: const ColorScheme.dark(
      primary: accent,
      secondary: green,
      surface: surface,
      error: red,
    ),
    textTheme: GoogleFonts.interTextTheme(
      const TextTheme(
        displayLarge: TextStyle(
          color: textPrimary,
          fontWeight: FontWeight.w700,
          fontSize: 32,
        ),
        displayMedium: TextStyle(
          color: textPrimary,
          fontWeight: FontWeight.w700,
          fontSize: 26,
        ),
        titleLarge: TextStyle(
          color: textPrimary,
          fontWeight: FontWeight.w600,
          fontSize: 20,
        ),
        titleMedium: TextStyle(
          color: textPrimary,
          fontWeight: FontWeight.w600,
          fontSize: 16,
        ),
        bodyLarge: TextStyle(color: textPrimary, fontSize: 15),
        bodyMedium: TextStyle(color: textSecondary, fontSize: 13),
        labelLarge: TextStyle(
          color: textPrimary,
          fontWeight: FontWeight.w600,
          fontSize: 14,
        ),
      ),
    ),
    cardTheme: CardThemeData(
      color: card,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: border),
      ),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: bg,
      foregroundColor: textPrimary,
      elevation: 0,
      centerTitle: false,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: accent,
        foregroundColor: Colors.black,
        minimumSize: const Size(double.infinity, 52),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surface,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: accent, width: 1.5),
      ),
      labelStyle: const TextStyle(color: textSecondary),
      hintStyle: const TextStyle(color: textDim),
    ),
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: surface,
      selectedItemColor: accent,
      unselectedItemColor: textDim,
      type: BottomNavigationBarType.fixed,
    ),
  );

  // ── Helper widgets ───────────────────────────────────────────────────────
  static Color scoreColor(double score) {
    if (score >= 85) return green;
    if (score >= 65) return orange;
    return red;
  }

  static BoxDecoration cardDecor({
    Color? color,
    double radius = 16,
    bool glow = false,
  }) => BoxDecoration(
    color: color ?? card,
    borderRadius: BorderRadius.circular(radius),
    border: Border.all(color: glow ? accent.withOpacity(0.4) : border),
    boxShadow: glow
        ? [const BoxShadow(color: accentGlow, blurRadius: 20, spreadRadius: 2)]
        : null,
  );
}
