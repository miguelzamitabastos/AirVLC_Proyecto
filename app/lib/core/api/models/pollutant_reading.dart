import 'risk_level.dart';

/// Lectura puntual de un contaminante (PM2.5 / NO₂ / O₃) tal como llega en
/// `pollutants[<key>]` desde `/api/v2/risk` o `/api/v2/profile/recommend`.
class PollutantReading {
  final String pollutant;
  final double value;
  final String unit;
  final RiskLevel level;
  final String colorHex;
  final String emoji;
  final String description;
  final String recommendation;

  const PollutantReading({
    required this.pollutant,
    required this.value,
    required this.unit,
    required this.level,
    required this.colorHex,
    required this.emoji,
    required this.description,
    required this.recommendation,
  });

  String get prettyName => switch (pollutant) {
        'pm25' => 'PM2.5',
        'no2' => 'NO₂',
        'o3' => 'O₃',
        _ => pollutant.toUpperCase(),
      };

  factory PollutantReading.fromJson(String key, Map<String, dynamic> j) {
    return PollutantReading(
      pollutant: key,
      value: (j['value'] as num?)?.toDouble() ?? 0,
      unit: j['unit']?.toString() ?? 'µg/m³',
      level: RiskLevelX.fromString(j['level']?.toString()),
      colorHex: j['color']?.toString() ?? '',
      emoji: j['emoji']?.toString() ?? '',
      description: j['description']?.toString() ?? '',
      recommendation: j['recommendation']?.toString() ?? '',
    );
  }
}
