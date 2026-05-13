import 'package:shared_preferences/shared_preferences.dart';

import '../api/models/health_profile.dart';

/// Persistencia local del perfil de salud (F1).
/// Mantenemos campos planos en `SharedPreferences` para evitar dependencia
/// de `path_provider` y mantenernos compatibles con simulador iOS.
class ProfileStorage {
  static const _kAge = 'profile.age';
  static const _kCondition = 'profile.condition';
  static const _kSensitivity = 'profile.sensitivity';
  static const _kActivity = 'profile.activity';
  static const _kOnboardingDone = 'profile.onboarding_done';

  Future<bool> isOnboardingDone() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_kOnboardingDone) ?? false;
  }

  Future<void> markOnboardingDone() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kOnboardingDone, true);
  }

  Future<HealthProfile> load() async {
    final prefs = await SharedPreferences.getInstance();
    return HealthProfile(
      age: AgeRange.values.firstWhere(
        (e) => e.name == prefs.getString(_kAge),
        orElse: () => HealthProfile.defaultProfile.age,
      ),
      condition: Condition.values.firstWhere(
        (e) => e.name == prefs.getString(_kCondition),
        orElse: () => HealthProfile.defaultProfile.condition,
      ),
      sensitivity: Sensitivity.values.firstWhere(
        (e) => e.name == prefs.getString(_kSensitivity),
        orElse: () => HealthProfile.defaultProfile.sensitivity,
      ),
      activity: Activity.values.firstWhere(
        (e) => e.name == prefs.getString(_kActivity),
        orElse: () => HealthProfile.defaultProfile.activity,
      ),
    );
  }

  Future<void> save(HealthProfile p) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAge, p.age.name);
    await prefs.setString(_kCondition, p.condition.name);
    await prefs.setString(_kSensitivity, p.sensitivity.name);
    await prefs.setString(_kActivity, p.activity.name);
  }

  Future<void> reset() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kAge);
    await prefs.remove(_kCondition);
    await prefs.remove(_kSensitivity);
    await prefs.remove(_kActivity);
    await prefs.remove(_kOnboardingDone);
  }
}
