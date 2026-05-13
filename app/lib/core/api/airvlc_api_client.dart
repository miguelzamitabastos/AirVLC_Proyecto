import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../constants/api_constants.dart';
import 'models/chat_response.dart';
import 'models/health_profile.dart';
import 'models/recommend_response.dart';
import 'models/risk_response.dart';
import 'models/route_segment.dart';

/// Excepción enriquecida del cliente HTTP. La UI puede mostrar [.message]
/// directamente o decidir según [.statusCode].
class AirVLCApiException implements Exception {
  final String message;
  final int? statusCode;
  final Object? cause;

  const AirVLCApiException(this.message, {this.statusCode, this.cause});

  @override
  String toString() =>
      'AirVLCApiException($statusCode): $message${cause == null ? '' : ' (cause=$cause)'}';
}

/// Cliente HTTP único hacia el backend Flask v2. Todas las features del
/// Sprint 4 pasan por aquí — la app **no** habla nunca con AWS directamente.
class AirVLCApiClient {
  final http.Client _http;
  final Duration timeout;

  AirVLCApiClient({http.Client? client, Duration? timeout})
      : _http = client ?? http.Client(),
        timeout = timeout ?? ApiConstants.defaultTimeout;

  void close() => _http.close();

  Future<Map<String, dynamic>> _post(
    String url,
    Map<String, dynamic> body,
  ) async {
    try {
      final response = await _http
          .post(
            Uri.parse(url),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode(body),
          )
          .timeout(timeout);

      final decoded =
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;

      if (response.statusCode >= 400) {
        throw AirVLCApiException(
          decoded['error']?.toString() ?? 'Error HTTP ${response.statusCode}',
          statusCode: response.statusCode,
        );
      }
      return decoded;
    } on TimeoutException catch (e) {
      throw AirVLCApiException(
        'Timeout conectando con el backend. Comprueba que Flask v2 está arrancado.',
        cause: e,
      );
    } on AirVLCApiException {
      rethrow;
    } catch (e) {
      throw AirVLCApiException(
        'No se pudo contactar con el backend: $e',
        cause: e,
      );
    }
  }

  Future<Map<String, dynamic>> _get(String url) async {
    try {
      final response =
          await _http.get(Uri.parse(url)).timeout(timeout);
      final decoded =
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      if (response.statusCode >= 400) {
        throw AirVLCApiException(
          decoded['error']?.toString() ?? 'Error HTTP ${response.statusCode}',
          statusCode: response.statusCode,
        );
      }
      return decoded;
    } on TimeoutException catch (e) {
      throw AirVLCApiException('Timeout conectando con el backend.', cause: e);
    } on AirVLCApiException {
      rethrow;
    } catch (e) {
      throw AirVLCApiException('No se pudo contactar con el backend: $e',
          cause: e);
    }
  }

  /// `GET /api/v2/health` — útil para mostrar el banner de estado.
  Future<Map<String, dynamic>> health() => _get(ApiConstants.health);

  /// `POST /api/v2/risk` — devuelve el ICA-like + 3 contaminantes para
  /// la estación dada.
  Future<RiskResponse> risk(String station, {int offsetHours = 0}) async {
    final j = await _post(ApiConstants.risk, {
      'station': station,
      if (offsetHours > 0) 'offset_hours': offsetHours,
    });
    return RiskResponse.fromJson(j);
  }

  /// `POST /api/v2/predict` — solo los valores numéricos (sin clasificación).
  Future<Map<String, dynamic>> predict(String station) async {
    return _post(ApiConstants.predict, {'station': station});
  }

  /// `POST /api/v2/profile/recommend` — combina riesgo v2 + perfil del usuario.
  Future<RecommendResponse> recommend({
    required String station,
    HealthProfile? profile,
    String? activity,
  }) async {
    final body = <String, dynamic>{
      'station': station,
      if (profile != null) 'profile': profile.toApiPayload(),
      if (activity != null) 'activity': activity,
    };
    final j = await _post(ApiConstants.profileRecommend, body);
    return RecommendResponse.fromJson(j);
  }

  /// `POST /api/v2/route` — planificador A → B con tramos intermedios.
  Future<RouteResponse> route({
    required String fromStation,
    required String toStation,
  }) async {
    final j = await _post(ApiConstants.route, {
      'from_station': fromStation,
      'to_station': toStation,
    });
    return RouteResponse.fromJson(j);
  }

  /// `POST /api/v2/chat` — Lex en backend. La app solo envía el texto.
  Future<ChatResponse> chat({
    required String message,
    String sessionId = 'flutter_user',
  }) async {
    final j = await _post(ApiConstants.chat, {
      'message': message,
      'session_id': sessionId,
    });
    return ChatResponse.fromJson(j);
  }

  // ─────────────────────────────────────────────────────────
  // Sprint 7 — Visualisation endpoints
  // ─────────────────────────────────────────────────────────

  /// `GET /api/v2/map?pollutant=...&horizon=...` — stations + risk for map.
  Future<Map<String, dynamic>> mapStations({
    String pollutant = 'pm25',
    int horizon = 0,
  }) async {
    final url =
        '${ApiConstants.map}?pollutant=$pollutant&horizon=$horizon';
    return _get(url);
  }

  /// `GET /api/v2/timeseries?station=...&pollutant=...&window_hours=...`
  ///
  /// [windowHours]: tamaño de la ventana observada (24, 48 o 72). Default 72.
  Future<Map<String, dynamic>> timeseries({
    required String station,
    String pollutant = 'pm25',
    int windowHours = 72,
  }) async {
    final encoded = Uri.encodeComponent(station);
    final url = '${ApiConstants.timeseries}'
        '?station=$encoded&pollutant=$pollutant&window_hours=$windowHours';
    return _get(url);
  }

  /// `GET /api/v2/stations` — catálogo completo de estaciones de la RVVCCA-GVA.
  ///
  /// [onlyCanonical]: si `true`, solo las 7 canónicas del modelo v2.
  /// [province]: filtra por substring de provincia (ej: "Valencia").
  Future<Map<String, dynamic>> stations({
    bool onlyCanonical = false,
    String? province,
  }) async {
    final params = <String, String>{
      if (onlyCanonical) 'only_canonical': 'true',
      if (province != null && province.isNotEmpty) 'province': province,
    };
    final qs = params.entries
        .map((e) => '${e.key}=${Uri.encodeComponent(e.value)}')
        .join('&');
    final url =
        '${ApiConstants.apiV2}/stations${qs.isEmpty ? '' : '?$qs'}';
    return _get(url);
  }

  /// `GET /api/v2/ranking?pollutant=...&horizon=...` — top N worst stations.
  Future<Map<String, dynamic>> ranking({
    String pollutant = 'pm25',
    int horizon = 0,
    int top = 7,
  }) async {
    final url =
        '${ApiConstants.ranking}?pollutant=$pollutant&horizon=$horizon&top=$top';
    return _get(url);
  }
}
