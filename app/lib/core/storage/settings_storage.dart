import 'package:shared_preferences/shared_preferences.dart';

/// Ajustes simples de UI/voz (persistentes) para no depender de backend.
class SettingsStorage {
  static const _kTtsEnabled = 'settings.tts_enabled.v1';

  Future<bool> getTtsEnabled({bool defaultValue = false}) async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_kTtsEnabled) ?? defaultValue;
  }

  Future<void> setTtsEnabled(bool enabled) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_kTtsEnabled, enabled);
  }
}

