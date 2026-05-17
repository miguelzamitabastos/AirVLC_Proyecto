import 'risk_response.dart';

/// Respuesta de `/api/v2/profile/recommend`.
/// Hereda los campos de [RiskResponse] y añade los específicos del perfil.
class RecommendResponse extends RiskResponse {
  final String recommendationText;
  final String colorHex;
  final String levelAdjusted;
  final bool isSensitiveProfile;
  final Map<String, dynamic> profileUsed;

  const RecommendResponse({
    required super.station,
    required super.predictions,
    required super.pollutants,
    required super.worst,
    required super.replyText,
    required super.timestamp,
    required this.recommendationText,
    required this.colorHex,
    required this.levelAdjusted,
    required this.isSensitiveProfile,
    required this.profileUsed,
  });

  factory RecommendResponse.fromJson(Map<String, dynamic> j) {
    final base = RiskResponse.fromJson(j);
    return RecommendResponse(
      station: base.station,
      predictions: base.predictions,
      pollutants: base.pollutants,
      worst: base.worst,
      replyText: base.replyText,
      timestamp: base.timestamp,
      recommendationText: j['recommendation_text']?.toString() ?? base.replyText,
      colorHex: j['color']?.toString() ?? '',
      levelAdjusted: j['level_adjusted']?.toString() ?? base.worst.level,
      isSensitiveProfile: j['is_sensitive_profile'] == true,
      profileUsed:
          (j['profile_used'] as Map?)?.cast<String, dynamic>() ?? const {},
    );
  }
}
