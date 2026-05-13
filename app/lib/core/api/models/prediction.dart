/// Bloque `predictions` que envuelve los 3 valores numéricos.
///
/// Sprint 5 añade campos de frescura de datos:
/// - [dataTimestamp]: cuándo se midieron los datos usados para la predicción.
/// - [dataAgeMinutes]: antigüedad en minutos respecto al servidor.
/// - [dataWindowStart]: inicio de la ventana de 24h usada.
/// - [serverTimestamp]: cuándo respondió el backend.
///
/// API v2 (Mongo): prioriza `fecha_iso`, `updated_minutes_ago` e `is_realtime`
/// en la raíz o dentro de `meta` (p. ej. filas de `/api/v2/map`).
class Prediction {
  final double pm25;
  final double no2;
  final double o3;
  final String unit;

  /// Sprint 5 — freshness fields
  final DateTime? serverTimestamp;
  final DateTime? dataTimestamp;
  final int? dataAgeMinutes;
  final DateTime? dataWindowStart;

  /// Mongo v2: si viene en el JSON, el chip puede colorear por realtime vs histórico.
  final bool? isRealtime;

  const Prediction({
    required this.pm25,
    required this.no2,
    required this.o3,
    this.unit = 'µg/m³',
    this.serverTimestamp,
    this.dataTimestamp,
    this.dataAgeMinutes,
    this.dataWindowStart,
    this.isRealtime,
  });

  /// Campos de frescura para [fromJson] leyendo raíz y `meta` anidado.
  static Map<String, dynamic>? _metaFrom(Map<String, dynamic> root) {
    final m = root['meta'];
    if (m is Map<String, dynamic>) return m;
    if (m is Map) return m.cast<String, dynamic>();
    return null;
  }

  static DateTime? _parseIso(dynamic value) {
    if (value == null) return null;
    final s = value.toString().trim();
    if (s.isEmpty) return null;
    return DateTime.tryParse(s);
  }

  /// Une `meta` con claves de la fila de estación para `/api/v2/map`.
  static Map<String, dynamic> mapStationFreshnessParent(
    Map<String, dynamic> stationRow,
    Map<String, dynamic> mapResponse,
  ) {
    final meta = _metaFrom(stationRow) ?? {};
    return {
      ...meta,
      if (stationRow['fecha_iso'] != null) 'fecha_iso': stationRow['fecha_iso'],
      if (mapResponse['server_timestamp'] != null)
        'server_timestamp': mapResponse['server_timestamp'],
    };
  }

  factory Prediction.fromJson(Map<String, dynamic> j, {Map<String, dynamic>? parentJson}) {
    final root = parentJson ?? j;
    final nested = _metaFrom(root);

    dynamic pick(dynamic Function(Map<String, dynamic>? m) fn) =>
        fn(root) ?? (nested != null ? fn(nested) : null);

    final fechaIso = pick((m) => m?['fecha_iso']);
    final dataTsStr = pick((m) => m?['data_timestamp']);
    final ageFromApi = pick((m) => m?['updated_minutes_ago']) ??
        pick((m) => m?['data_age_minutes']);
    final ageInt = (ageFromApi as num?)?.toInt();

    final rtRaw = pick((m) => m?['is_realtime']);
    bool? isRt;
    if (rtRaw != null) {
      isRt = rtRaw == true;
    }

    return Prediction(
      pm25: (j['pm25'] as num?)?.toDouble() ?? 0,
      no2: (j['no2'] as num?)?.toDouble() ?? 0,
      o3: (j['o3'] as num?)?.toDouble() ?? 0,
      unit: j['unit']?.toString() ?? 'µg/m³',
      serverTimestamp:
          _parseIso(root['server_timestamp']) ?? _parseIso(nested?['server_timestamp']),
      dataTimestamp: _parseIso(fechaIso) ?? _parseIso(dataTsStr),
      dataAgeMinutes: ageInt ?? (root['data_age_minutes'] as num?)?.toInt(),
      dataWindowStart: _parseIso(pick((m) => m?['data_window_start'])),
      isRealtime: isRt,
    );
  }

  Map<String, dynamic> toJson() => {
        'pm25': pm25,
        'no2': no2,
        'o3': o3,
        'unit': unit,
      };
}

/// Worst pollutant resaltado por el backend.
class WorstPollutant {
  final String pollutant;
  final double value;
  final String unit;
  final String level;
  final String colorHex;
  final String emoji;

  const WorstPollutant({
    required this.pollutant,
    required this.value,
    required this.unit,
    required this.level,
    required this.colorHex,
    required this.emoji,
  });

  factory WorstPollutant.fromJson(Map<String, dynamic> j) => WorstPollutant(
        pollutant: j['pollutant']?.toString() ?? 'pm25',
        value: (j['value'] as num?)?.toDouble() ?? 0,
        unit: j['unit']?.toString() ?? 'µg/m³',
        level: j['level']?.toString() ?? 'bueno',
        colorHex: j['color']?.toString() ?? '',
        emoji: j['emoji']?.toString() ?? '',
      );
}
