import 'prediction.dart';

/// Respuesta de `/api/v2/chat`. El backend envía formas distintas según el
/// intent resuelto por Lex; este modelo unifica los campos comunes y guarda
/// el resto del JSON para que la pantalla pueda hacer drill-down.
///
/// Sprint 7: se añade `uiPayload` con acción + parámetros para que Flutter
/// pueda navegar automáticamente a la pantalla correspondiente.
class ChatResponse {
  final String reply;
  final String intent;
  final String? station;
  final Prediction? predictions;
  final WorstPollutant? worst;
  final ChatUiPayload? uiPayload;
  final Map<String, dynamic> raw;

  const ChatResponse({
    required this.reply,
    required this.intent,
    this.station,
    this.predictions,
    this.worst,
    this.uiPayload,
    this.raw = const {},
  });

  factory ChatResponse.fromJson(Map<String, dynamic> j) {
    Prediction? preds;
    if (j['predictions'] is Map) {
      preds = Prediction.fromJson((j['predictions'] as Map).cast<String, dynamic>());
    }
    WorstPollutant? worst;
    if (j['worst'] is Map) {
      worst =
          WorstPollutant.fromJson((j['worst'] as Map).cast<String, dynamic>());
    }
    ChatUiPayload? uiPayload;
    if (j['ui_payload'] is Map) {
      uiPayload = ChatUiPayload.fromJson(
          (j['ui_payload'] as Map).cast<String, dynamic>());
    }
    return ChatResponse(
      reply: (j['reply'] ?? j['reply_text'] ?? '').toString(),
      intent: j['intent']?.toString() ?? 'Unknown',
      station: j['station']?.toString(),
      predictions: preds,
      worst: worst,
      uiPayload: uiPayload,
      raw: j,
    );
  }
}

/// Sprint 7 — Payload estructurado que indica a Flutter qué vista abrir.
class ChatUiPayload {
  final String action; // open_map | open_station_detail | open_comparison | open_advice
  final String? station;
  final String? pollutant;
  final String? horizon;
  final String? stationA;
  final String? stationB;
  final String? cta;

  const ChatUiPayload({
    required this.action,
    this.station,
    this.pollutant,
    this.horizon,
    this.stationA,
    this.stationB,
    this.cta,
  });

  factory ChatUiPayload.fromJson(Map<String, dynamic> j) => ChatUiPayload(
        action: j['action']?.toString() ?? '',
        station: j['station']?.toString(),
        pollutant: j['pollutant']?.toString(),
        horizon: j['horizon']?.toString(),
        stationA: j['station_a']?.toString(),
        stationB: j['station_b']?.toString(),
        cta: j['cta']?.toString(),
      );
}
