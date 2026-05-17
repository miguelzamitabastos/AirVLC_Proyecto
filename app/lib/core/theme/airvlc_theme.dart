import 'package:flutter/material.dart';

/// Tema y paleta accesible de AirVLC.
///
/// Los colores semánticos por nivel de riesgo (verde/amarillo/naranja/rojo)
/// son los mismos que devuelve el backend, pero los duplicamos aquí como
/// fallback cuando el JSON no incluye `color` (modo offline).
class AirVLCTheme {
  static const Color primaryBlue = Color(0xFF0F3A5A);
  static const Color valenciaOrange = Color(0xFFFF7E00);
  static const Color backgroundLight = Color(0xFFF4F7F6);
  static const Color textDark = Color(0xFF2C3E50);
  static const Color cardBackground = Colors.white;

  // Paleta semántica por nivel ICA
  static const Color levelGood = Color(0xFF2BB673);
  static const Color levelModerate = Color(0xFFF2C744);
  static const Color levelBad = Color(0xFFF4A300);
  static const Color levelDangerous = Color(0xFFD62828);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      primaryColor: primaryBlue,
      scaffoldBackgroundColor: backgroundLight,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryBlue,
        primary: primaryBlue,
        secondary: valenciaOrange,
        surface: cardBackground,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: backgroundLight,
        foregroundColor: primaryBlue,
        elevation: 0,
        centerTitle: true,
        titleTextStyle: TextStyle(
          color: primaryBlue,
          fontSize: 20,
          fontWeight: FontWeight.bold,
        ),
      ),
      // Flutter 3.44+ uses CardThemeData in ThemeData.cardTheme.
      cardTheme: CardThemeData(
        color: cardBackground,
        elevation: 2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 4),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: valenciaOrange,
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(28),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 12),
          textStyle:
              const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          color: textDark,
          fontWeight: FontWeight.bold,
          fontSize: 22,
        ),
        bodyLarge: TextStyle(color: textDark, fontSize: 16),
        bodyMedium: TextStyle(color: textDark, fontSize: 14),
      ),
    );
  }

  /// Devuelve el color local correspondiente a un nivel de riesgo en string.
  static Color colorForLevel(String? level) {
    switch ((level ?? '').toLowerCase()) {
      case 'bueno':
        return levelGood;
      case 'moderado':
        return levelModerate;
      case 'malo':
        return levelBad;
      case 'peligroso':
        return levelDangerous;
      default:
        return levelGood;
    }
  }

  /// Convierte un string hex (`#RRGGBB`) — el formato que envía el backend —
  /// a `Color`. Cae a [colorForLevel] si el string no es válido.
  static Color colorFromHex(String? hex, {String? fallbackLevel}) {
    if (hex == null || hex.isEmpty) {
      return colorForLevel(fallbackLevel);
    }
    final cleaned = hex.replaceAll('#', '');
    final value = int.tryParse(cleaned, radix: 16);
    if (value == null) return colorForLevel(fallbackLevel);
    if (cleaned.length == 6) return Color(value | 0xFF000000);
    if (cleaned.length == 8) return Color(value);
    return colorForLevel(fallbackLevel);
  }
}
