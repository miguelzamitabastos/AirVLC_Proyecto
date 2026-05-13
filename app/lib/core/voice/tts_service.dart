import 'package:flutter_tts/flutter_tts.dart';

/// Wrapper sobre `flutter_tts` con voz en español (Castellano) y velocidad
/// algo más lenta para que se entienda bien en conducción.
class TtsService {
  final FlutterTts _tts = FlutterTts();
  bool _initialized = false;

  Future<void> init() async {
    if (_initialized) return;
    await _tts.setLanguage('es-ES');
    await _tts.setPitch(1.0);
    await _tts.setSpeechRate(0.5);
    await _tts.awaitSpeakCompletion(true);
    _initialized = true;
  }

  Future<void> speak(String text) async {
    if (text.trim().isEmpty) return;
    if (!_initialized) await init();
    await _tts.stop();
    await _tts.speak(text);
  }

  Future<void> stop() async {
    await _tts.stop();
  }
}
