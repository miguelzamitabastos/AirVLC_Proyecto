import 'pollutant_reading.dart';
import 'prediction.dart';

/// Respuesta de `/api/v2/risk` y base reutilizada por `route` y
/// `profile/recommend` (ambas añaden campos extra).
class RiskResponse {
  final String station;
  final Prediction predictions;
  final Map<String, PollutantReading> pollutants;
  final WorstPollutant worst;
  final String replyText;
  final DateTime timestamp;

  const RiskResponse({
    required this.station,
    required this.predictions,
    required this.pollutants,
    required this.worst,
    required this.replyText,
    required this.timestamp,
  });

  factory RiskResponse.fromJson(Map<String, dynamic> j) {
    final pollutantsRaw = (j['pollutants'] as Map?)?.cast<String, dynamic>() ?? {};
    final readings = <String, PollutantReading>{};
    pollutantsRaw.forEach((k, v) {
      readings[k] = PollutantReading.fromJson(
          k, (v as Map).cast<String, dynamic>());
    });

    return RiskResponse(
      station: j['station']?.toString() ?? '',
      predictions: Prediction.fromJson(
          (j['predictions'] as Map).cast<String, dynamic>(),
          parentJson: j),
      pollutants: readings,
      worst:
          WorstPollutant.fromJson((j['worst'] as Map).cast<String, dynamic>()),
      replyText: j['reply_text']?.toString() ?? '',
      timestamp: DateTime.tryParse(j['timestamp']?.toString() ?? '') ??
          DateTime.now(),
    );
  }
}
