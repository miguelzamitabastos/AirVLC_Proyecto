/// Perfil de salud del usuario (F1). Se persiste en `SharedPreferences`
/// y se envía en el body de `/api/v2/profile/recommend`. **Nunca** se sube
/// a un servidor terceros: solo viaja al backend Flask local.
class HealthProfile {
  final AgeRange age;
  final Condition condition;
  final Sensitivity sensitivity;
  final Activity activity;

  const HealthProfile({
    required this.age,
    required this.condition,
    required this.sensitivity,
    required this.activity,
  });

  static const HealthProfile defaultProfile = HealthProfile(
    age: AgeRange.adulto,
    condition: Condition.sano,
    sensitivity: Sensitivity.media,
    activity: Activity.paseoDiario,
  );

  HealthProfile copyWith({
    AgeRange? age,
    Condition? condition,
    Sensitivity? sensitivity,
    Activity? activity,
  }) =>
      HealthProfile(
        age: age ?? this.age,
        condition: condition ?? this.condition,
        sensitivity: sensitivity ?? this.sensitivity,
        activity: activity ?? this.activity,
      );

  Map<String, String> toApiPayload() => {
        'age': age.apiValue,
        'condition': condition.apiValue,
        'sensitivity': sensitivity.apiValue,
        'activity': activity.apiValue,
      };

  bool get isSensitive {
    if (condition == Condition.asma ||
        condition == Condition.epoc ||
        condition == Condition.embarazada ||
        condition == Condition.cardiopatia) return true;
    if (sensitivity == Sensitivity.alta) return true;
    if (age == AgeRange.nino || age == AgeRange.mayor65) return true;
    return false;
  }
}

enum AgeRange { nino, adulto, mayor65 }
enum Condition { sano, asma, epoc, embarazada, cardiopatia }
enum Sensitivity { alta, media, baja }
enum Activity { sedentario, paseoDiario, corredor, ciclista }

extension AgeRangeX on AgeRange {
  String get displayName => switch (this) {
        AgeRange.nino => 'Niño',
        AgeRange.adulto => 'Adulto',
        AgeRange.mayor65 => 'Mayor de 65',
      };
  String get apiValue => switch (this) {
        AgeRange.nino => 'niño',
        AgeRange.adulto => 'adulto',
        AgeRange.mayor65 => 'mayor de 65',
      };
}

extension ConditionX on Condition {
  String get displayName => switch (this) {
        Condition.sano => 'Sano',
        Condition.asma => 'Asma',
        Condition.epoc => 'EPOC',
        Condition.embarazada => 'Embarazada',
        Condition.cardiopatia => 'Cardiopatía',
      };
  String get apiValue => switch (this) {
        Condition.sano => 'sano',
        Condition.asma => 'asma',
        Condition.epoc => 'epoc',
        Condition.embarazada => 'embarazada',
        Condition.cardiopatia => 'cardiopatía',
      };
}

extension SensitivityX on Sensitivity {
  String get displayName => switch (this) {
        Sensitivity.alta => 'Alta',
        Sensitivity.media => 'Media',
        Sensitivity.baja => 'Baja',
      };
  String get apiValue => switch (this) {
        Sensitivity.alta => 'alta',
        Sensitivity.media => 'media',
        Sensitivity.baja => 'baja',
      };
}

extension ActivityX on Activity {
  String get displayName => switch (this) {
        Activity.sedentario => 'Sedentario',
        Activity.paseoDiario => 'Paseo diario',
        Activity.corredor => 'Corredor',
        Activity.ciclista => 'Ciclista',
      };
  String get apiValue => switch (this) {
        Activity.sedentario => 'quedarme en casa',
        Activity.paseoDiario => 'pasear',
        Activity.corredor => 'correr',
        Activity.ciclista => 'ir en bici',
      };
}
