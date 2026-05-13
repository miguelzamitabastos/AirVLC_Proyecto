/// Niveles de riesgo ICA-like, alineados con `RISK_LEVELS` del backend.
enum RiskLevel { bueno, moderado, malo, peligroso }

extension RiskLevelX on RiskLevel {
  static RiskLevel fromString(String? raw) {
    switch ((raw ?? '').toLowerCase()) {
      case 'bueno':
        return RiskLevel.bueno;
      case 'moderado':
        return RiskLevel.moderado;
      case 'malo':
        return RiskLevel.malo;
      case 'peligroso':
        return RiskLevel.peligroso;
      default:
        return RiskLevel.bueno;
    }
  }

  String get displayName {
    switch (this) {
      case RiskLevel.bueno:
        return 'Bueno';
      case RiskLevel.moderado:
        return 'Moderado';
      case RiskLevel.malo:
        return 'Malo';
      case RiskLevel.peligroso:
        return 'Peligroso';
    }
  }

  /// Orden severidad creciente (igual que LEVEL_ORDER en backend).
  int get severity => RiskLevel.values.indexOf(this);

  String get raw => name;
}
