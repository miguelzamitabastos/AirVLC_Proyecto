import 'package:flutter/material.dart';

import '../../core/api/models/health_profile.dart';
import '../../core/api/models/pollutant_reading.dart';
import '../../core/api/models/risk_level.dart';
import '../../core/theme/airvlc_theme.dart';

/// Card individual de un contaminante (PM2.5 / NO₂ / O₃).
/// El color y el nivel se ajustan al perfil sensible: si el perfil es sensible
/// el nivel se sube un escalón visualmente como hace el backend en
/// `/api/v2/profile/recommend`.
class PollutantCard extends StatelessWidget {
  final PollutantReading reading;
  final HealthProfile profile;

  const PollutantCard({
    super.key,
    required this.reading,
    required this.profile,
  });

  RiskLevel get _adjustedLevel {
    if (!profile.isSensitive) return reading.level;
    final next = reading.level.severity + 1;
    if (next >= RiskLevel.values.length) return RiskLevel.peligroso;
    return RiskLevel.values[next];
  }

  @override
  Widget build(BuildContext context) {
    final level = _adjustedLevel;
    final color = AirVLCTheme.colorForLevel(level.raw);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: BoxDecoration(
                color: color.withOpacity(0.18),
                shape: BoxShape.circle,
              ),
              alignment: Alignment.center,
              child: Text(
                reading.emoji.isEmpty ? '·' : reading.emoji,
                style: const TextStyle(fontSize: 26),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    reading.prettyName,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    '${reading.value.toStringAsFixed(1)} ${reading.unit}',
                    style: const TextStyle(fontSize: 14),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Text(
                level.displayName,
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
