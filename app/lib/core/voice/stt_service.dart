import 'dart:async';

import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:speech_to_text/speech_recognition_result.dart';

/// Wrapper sobre `speech_to_text` con la API que usa F4 (modo voz).
/// La inicialización es perezosa para no pedir permisos al arrancar la app.
class SttService {
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _initialized = false;
  bool _listening = false;

  bool get isListening => _listening;
  bool get isInitialized => _initialized;

  Future<bool> init({
    void Function(String status)? onStatus,
    void Function(String error)? onError,
  }) async {
    if (_initialized) return true;
    _initialized = await _speech.initialize(
      onStatus: (s) {
        if (s == 'notListening' || s == 'done') _listening = false;
        onStatus?.call(s);
      },
      onError: (e) => onError?.call(e.errorMsg),
    );
    return _initialized;
  }

  /// Pone el reconocedor en marcha y resuelve el `Completer` con el
  /// resultado final cuando el reconocedor decide parar (o tras [maxSilence]).
  Future<String> listenOnce({
    String localeId = 'es_ES',
    Duration maxSilence = const Duration(seconds: 3),
    Duration listenFor = const Duration(seconds: 12),
    void Function(String partial)? onPartial,
  }) async {
    if (!_initialized) {
      final ok = await init();
      if (!ok) {
        throw StateError('No se pudo inicializar speech_to_text');
      }
    }
    final completer = Completer<String>();
    String last = '';

    _listening = true;
    await _speech.listen(
      localeId: localeId,
      pauseFor: maxSilence,
      listenFor: listenFor,
      // speech_to_text 6.x sigue usando este parámetro top-level. La 7.x
      // lo migra a SpeechListenOptions, pero está fuera del constraint del SDK.
      // ignore: deprecated_member_use
      partialResults: true,
      onResult: (SpeechRecognitionResult r) {
        last = r.recognizedWords;
        if (!r.finalResult) {
          onPartial?.call(last);
        } else if (!completer.isCompleted) {
          completer.complete(last);
        }
      },
    );

    // Failsafe: si el plugin no entrega final, paramos a los listenFor segundos.
    Future.delayed(listenFor + const Duration(milliseconds: 500), () async {
      if (!completer.isCompleted) {
        await stop();
        completer.complete(last);
      }
    });

    return completer.future;
  }

  Future<void> stop() async {
    _listening = false;
    await _speech.stop();
  }

  Future<void> cancel() async {
    _listening = false;
    await _speech.cancel();
  }
}
