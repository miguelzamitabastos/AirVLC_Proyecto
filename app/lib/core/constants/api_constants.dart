/// Constantes de la API.
///
/// Cambia [baseUrl] según el entorno desde el que pruebas:
/// - **iOS Simulator** y desktop: `http://localhost:5001`
/// - **Android Emulator**: `http://10.0.2.2:5001`
/// - **Móvil físico** (en la misma red WiFi que el portátil con Flask):
///   `http://<IP_LOCAL>:5001` (ej: `http://192.168.1.42:5001`).
class ApiConstants {
  static const String baseUrl = String.fromEnvironment(
    'AIRVLC_BASE_URL',
    defaultValue: 'http://localhost:5001',
  );

  static const String apiV2 = '$baseUrl/api/v2';

  // Endpoints v2
  static const String predict = '$apiV2/predict';
  static const String risk = '$apiV2/risk';
  static const String chat = '$apiV2/chat';
  static const String profileRecommend = '$apiV2/profile/recommend';
  static const String route = '$apiV2/route';
  static const String health = '$apiV2/health';

  // Sprint 7 — Visualisation endpoints
  static const String map = '$apiV2/map';
  static const String timeseries = '$apiV2/timeseries';
  static const String ranking = '$apiV2/ranking';

  static const Duration defaultTimeout = Duration(seconds: 12);
}
