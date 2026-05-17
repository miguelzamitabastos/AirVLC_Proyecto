import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/constants/stations.dart';
import '../../core/theme/airvlc_theme.dart';

/// Sprint 7 — Serie temporal: observado vs forecast 24-72h.
///
/// Muestra las últimas 72h de datos reales y las predicciones
/// a 0/24/48/72h, con badges de freshness y transparencia.
class TimeseriesScreen extends StatefulWidget {
  final AirVLCApiClient api;
  final String station;
  final String pollutant;

  const TimeseriesScreen({
    super.key,
    required this.api,
    required this.station,
    this.pollutant = 'pm25',
  });

  @override
  State<TimeseriesScreen> createState() => _TimeseriesScreenState();
}

class _TimeseriesScreenState extends State<TimeseriesScreen> {
  late String _station;
  late String _pollutant;

  /// Ventana observada fija (72 h). Antes era seleccionable mediante chips,
  /// pero los horizontes ya están etiquetados en el eje X del gráfico, así
  /// que el selector resultaba redundante.
  static const int _windowHours = 72;

  bool _loading = true;
  String? _error;

  List<Map<String, dynamic>> _observed = [];
  List<Map<String, dynamic>> _forecast = [];
  Map<String, dynamic> _meta = const {};
  bool _futureAvailable = false;

  static const _pollutantLabels = {'pm25': 'PM2.5', 'no2': 'NO₂', 'o3': 'O₃'};

  @override
  void initState() {
    super.initState();
    _station = widget.station;
    _pollutant = widget.pollutant;
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await widget.api.timeseries(
        station: _station,
        pollutant: _pollutant,
        windowHours: _windowHours,
      );
      _observed = ((data['observed'] as List?) ?? []).cast<Map<String, dynamic>>();
      _forecast = ((data['forecast'] as List?) ?? []).cast<Map<String, dynamic>>();
      _meta = (data['meta'] as Map?)?.cast<String, dynamic>() ?? const {};
      _futureAvailable = _forecast.any((f) {
        final h = (f['horizon_hours'] as num?)?.toInt() ?? 0;
        final v = f['value'];
        if (h == 0) return false;
        return v != null;
      });
    } catch (e) {
      _error = e.toString();
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('$_station — ${_pollutantLabels[_pollutant] ?? _pollutant}'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? _buildError()
              : RefreshIndicator(
                  onRefresh: _fetch,
              child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    _buildSelectors(),
                    const SizedBox(height: 12),
                    _buildTransparencyBadge(),
                    const SizedBox(height: 12),
                    _buildSourceBanner(),
                    const SizedBox(height: 8),
                    _buildChart(),
                    const SizedBox(height: 16),
                    _buildForecastCards(),
                    const SizedBox(height: 16),
                    _buildFreshnessInfo(),
                  ],
                ),
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, size: 48, color: AirVLCTheme.levelDangerous),
            const SizedBox(height: 12),
            Text('Error: $_error', textAlign: TextAlign.center),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _fetch,
              icon: const Icon(Icons.refresh),
              label: const Text('Reintentar'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSelectors() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          children: [
            // Station
            Row(
              children: [
                const Icon(Icons.location_on, size: 18, color: AirVLCTheme.primaryBlue),
                const SizedBox(width: 8),
                Expanded(
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      isExpanded: true,
                      value: _station,
                      items: V2Stations.all
                          .map((s) => DropdownMenuItem(value: s, child: Text(s)))
                          .toList(),
                      onChanged: (v) {
                        if (v != null) {
                          setState(() => _station = v);
                          _fetch();
                        }
                      },
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            // Pollutant chips
            Row(
              children: ['pm25', 'no2', 'o3'].map((p) {
                final sel = p == _pollutant;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: ChoiceChip(
                    label: Text(_pollutantLabels[p] ?? p),
                    selected: sel,
                    selectedColor: AirVLCTheme.primaryBlue.withOpacity(0.15),
                    onSelected: (_) {
                      setState(() => _pollutant = p);
                      _fetch();
                    },
                  ),
                );
              }).toList(),
            ),
          ],
        ),
      ),
    );
  }

  bool get _isWaqiSource {
    final src = _meta['air_source']?.toString() ?? _meta['observed_source']?.toString();
    return src == 'waqi';
  }

  bool get _isGvaProxySource {
    final src = _meta['air_source']?.toString() ?? _meta['observed_source']?.toString();
    return src == 'gva_proxy';
  }

  Widget _buildSourceBanner() {
    if (!_isWaqiSource && !_isGvaProxySource) return const SizedBox.shrink();
    final proxy = _meta['waqi_proxy_label']?.toString() ??
        _meta['data_source_label']?.toString();
    final city = _meta['waqi_city_name']?.toString();
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFE3F2FD),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AirVLCTheme.primaryBlue.withOpacity(0.35)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(
            _isGvaProxySource ? Icons.link : Icons.cloud,
            size: 18,
            color: AirVLCTheme.primaryBlue,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              _isGvaProxySource
                  ? 'Observados vía proxy GVA (Puerto Moll, ~300 m). Puerto Valencia no tiene sensor en red GVA.\n${proxy ?? ''}'
                  : (proxy != null && proxy.isNotEmpty
                      ? 'Observados vía WAQI (proxy). Puerto Valencia no está en red GVA.\n$proxy'
                      : (city != null && city.isNotEmpty
                          ? 'Observados vía WAQI. Sensor: $city'
                          : 'Observados vía WAQI (fallback). Puerto Valencia no está en red GVA.')),
              style: TextStyle(fontSize: 12, color: Colors.blue.shade900),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTransparencyBadge() {
    final msg = 'Las predicciones muestran tendencia estimada (R²≈0.86). '
            'La precisión disminuye a mayor horizonte temporal.';
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF3E0),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AirVLCTheme.valenciaOrange.withOpacity(0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.info_outline, size: 18, color: AirVLCTheme.valenciaOrange),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              msg,
              style: TextStyle(fontSize: 12, color: Colors.brown.shade700),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildChart() {
    if (_observed.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.timeline, size: 40, color: Colors.grey),
              const SizedBox(height: 12),
              Text(
                _isWaqiSource
                    ? 'Aún no hay histórico WAQI en las últimas $_windowHours h.\n'
                        'Desliza hacia abajo para refrescar; cada hora de ingesta añadirá un punto.'
                    : 'Sin datos observados disponibles.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.grey),
              ),
            ],
          ),
        ),
      );
    }

    // Construimos puntos observados anclados al timestamp REAL, no al índice
    // del array. Así, si faltan horas, queda un hueco visual en lugar de un
    // pico falso en cero (Recomendación de la guía: "no dibujes el punto en
    // 0, usa interpolación lineal o deja el hueco").
    final now = DateTime.now().toUtc();
    final observedSpotsRel = <FlSpot>[];

    for (final pt in _observed) {
      final v = (pt['value'] as num?)?.toDouble();
      final tsStr = pt['timestamp']?.toString();
      if (v == null || v <= 0 || tsStr == null) continue;
      final ts = DateTime.tryParse(tsStr);
      if (ts == null) continue;
      final hoursAgo = ts.difference(now).inMinutes / 60.0;
      observedSpotsRel.add(FlSpot(hoursAgo, v));
    }
    observedSpotsRel.sort((a, b) => a.x.compareTo(b.x));

    // Predicción: el primer punto debe coincidir EXACTAMENTE con el último
    // observado (misma X/Y) y, a partir de ahí, dejamos que la spline
    // (isCurved) realice la transición suave hasta el primer horizonte
    // (+24h). Evitamos cualquier tramo horizontal sintético en x=0 para no
    // crear escalones ni picos artificiales.
    final forecastSpots = <FlSpot>[];
    if (observedSpotsRel.isNotEmpty) {
      final anchor = observedSpotsRel.last;
      forecastSpots.add(FlSpot(anchor.x, anchor.y));
    }
    for (final f in _forecast) {
      final h = (f['horizon_hours'] as num?)?.toDouble() ?? 0;
      final v = (f['value'] as num?)?.toDouble();
      if (h == 0) continue;
      if (v != null) forecastSpots.add(FlSpot(h, v));
    }
    forecastSpots.sort((a, b) => a.x.compareTo(b.x));

    final double minX = -_windowHours.toDouble();
    final double maxX = forecastSpots.isNotEmpty ? forecastSpots.last.x : 72.0;

    // Escala Y compacta: 15% de margen sobre el máximo (observados +
    // predicción) y un margen equivalente bajo el mínimo, sin bajar de 0
    // (los contaminantes nunca son negativos). Esto evita que la gráfica
    // quede medio vacía cuando los valores se mueven en un rango estrecho
    // (p. ej. 5–10 µg/m³ → eje hasta ~12, no hasta 50).
    final allYs = [
      ...observedSpotsRel.map((s) => s.y),
      ...forecastSpots.map((s) => s.y),
    ];
    double minY = 0.0;
    double maxY = 50.0;
    if (allYs.isNotEmpty) {
      final yMaxVal = allYs.reduce((a, b) => a > b ? a : b);
      final yMinVal = allYs.reduce((a, b) => a < b ? a : b);
      final pad = (yMaxVal * 0.15).clamp(0.5, double.infinity);
      maxY = yMaxVal + pad;
      final lowerCandidate = yMinVal - pad;
      minY = lowerCandidate < 0 ? 0.0 : lowerCandidate;
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(4, 14, 10, 6),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(left: 12, bottom: 6),
              child: Row(
                children: [
                  Container(width: 16, height: 3, color: AirVLCTheme.primaryBlue),
                  const SizedBox(width: 6),
                  const Text('Observado', style: TextStyle(fontSize: 12)),
                  const SizedBox(width: 16),
                  Container(
                    width: 16, height: 3,
                    decoration: BoxDecoration(
                      color: AirVLCTheme.valenciaOrange,
                      borderRadius: BorderRadius.circular(2),
                    ),
                  ),
                  const SizedBox(width: 6),
                  const Text('Predicción', style: TextStyle(fontSize: 12)),
                ],
              ),
            ),
            SizedBox(
              height: 220,
              child: LineChart(
                LineChartData(
                  minX: minX,
                  maxX: maxX,
                  minY: minY,
                  maxY: maxY,
                  gridData: FlGridData(
                    show: true,
                    drawVerticalLine: false,
                    horizontalInterval: (maxY - minY) / 4,
                    getDrawingHorizontalLine: (v) => FlLine(
                      color: const Color(0x20000000),
                      strokeWidth: 0.8,
                    ),
                  ),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        interval: 24,
                        reservedSize: 22,
                        getTitlesWidget: (value, meta) {
                          // Sólo etiquetamos los múltiplos de 24h y "Ahora";
                          // así evitamos el solapamiento que aparecía cuando
                          // fl_chart inyectaba ticks intermedios.
                          if (value.abs() < 0.5) {
                            return const Padding(
                              padding: EdgeInsets.only(top: 4),
                              child: Text(
                                'Ahora',
                                style: TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
                              ),
                            );
                          }
                          final rounded = value.round();
                          if (rounded % 24 != 0) return const SizedBox.shrink();
                          final label = rounded < 0 ? '${rounded}h' : '+${rounded}h';
                          return Padding(
                            padding: const EdgeInsets.only(top: 4),
                            child: Text(label, style: const TextStyle(fontSize: 10)),
                          );
                        },
                      ),
                    ),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 30,
                        interval: ((maxY - minY) / 4).clamp(0.5, double.infinity),
                        getTitlesWidget: (v, _) {
                          final span = (maxY - minY).abs();
                          final text = span < 10 ? v.toStringAsFixed(1) : v.toStringAsFixed(0);
                          return Padding(
                            padding: const EdgeInsets.only(right: 4),
                            child: Text(text, style: const TextStyle(fontSize: 10)),
                          );
                        },
                      ),
                    ),
                  ),
                  borderData: FlBorderData(show: false),
                  lineBarsData: [
                    // Observed line
                    if (observedSpotsRel.isNotEmpty)
                      LineChartBarData(
                        spots: observedSpotsRel,
                        isCurved: observedSpotsRel.length > 2,
                        color: AirVLCTheme.primaryBlue,
                        barWidth: 2.5,
                        dotData: FlDotData(
                          show: observedSpotsRel.length <= 3,
                          getDotPainter: (_, __, ___, ____) => FlDotCirclePainter(
                            radius: 5,
                            color: AirVLCTheme.primaryBlue,
                            strokeWidth: 2,
                            strokeColor: Colors.white,
                          ),
                        ),
                        belowBarData: BarAreaData(
                          show: true,
                          color: AirVLCTheme.primaryBlue.withOpacity(0.08),
                        ),
                      ),
                    // Forecast line
                    if (forecastSpots.length > 1)
                      LineChartBarData(
                        spots: forecastSpots,
                        isCurved: true,
                        color: AirVLCTheme.valenciaOrange,
                        barWidth: 2.5,
                        dashArray: [6, 4],
                        dotData: FlDotData(
                          show: true,
                          getDotPainter: (spot, _, __, ___) => FlDotCirclePainter(
                            radius: 4,
                            color: AirVLCTheme.valenciaOrange,
                            strokeWidth: 1.5,
                            strokeColor: Colors.white,
                          ),
                        ),
                        belowBarData: BarAreaData(
                          show: true,
                          color: AirVLCTheme.valenciaOrange.withOpacity(0.08),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildForecastCards() {
    if (_forecast.isEmpty) return const SizedBox.shrink();

    // Para que la tarjeta "Ahora" coincida con el inicio de la gráfica y con
    // el chip de freshness, mostramos el último valor observado real en
    // lugar de la predicción del modelo a horizonte 0.
    final double? lastObservedValue = _observed.isNotEmpty
        ? (_observed.last['value'] as num?)?.toDouble()
        : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 4),
          child: Text('Predicción por horizonte',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        ),
        const SizedBox(height: 8),
        Row(
          children: _forecast.where((f) {
            final h = (f['horizon_hours'] as num?)?.toInt() ?? -1;
            if (h == 0) {
              // La tarjeta "Ahora" siempre se renderiza si hay observado real,
              // aunque la predicción del modelo venga vacía.
              return lastObservedValue != null || f['value'] != null;
            }
            return f['value'] != null;
          }).map((f) {
            final h = (f['horizon_hours'] as num?)?.toInt() ?? -1;
            final isNow = h == 0;
            final label = f['label']?.toString() ?? '';
            final dynamic value = isNow && lastObservedValue != null
                ? lastObservedValue
                : f['value'];
            final level = isNow && lastObservedValue != null
                ? _levelForValue(_pollutant, lastObservedValue)
                : f['level']?.toString();
            final color = AirVLCTheme.colorForLevel(level);
            return Expanded(
              child: Card(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                  side: BorderSide(color: color, width: 2),
                ),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                  child: Column(
                    children: [
                      Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
                      const SizedBox(height: 4),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: color,
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          (level ?? '').toUpperCase(),
                          style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        value != null ? '${(value as num).toStringAsFixed(1)}' : '–',
                        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                      ),
                      const Text('µg/m³', style: TextStyle(fontSize: 10, color: Colors.grey)),
                    ],
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildFreshnessInfo() {
    final hasData = _observed.isNotEmpty;
    final lastTs = _meta['fecha_iso']?.toString() ??
        (hasData ? _observed.last['timestamp']?.toString() : null);
    final ageMin = (_meta['updated_minutes_ago'] as num?)?.toInt() ??
        (_meta['observed_age_minutes'] as num?)?.toInt();
    final coverage = (_meta['coverage_ratio'] as num?)?.toDouble();
    final freshness = _meta['freshness']?.toString();
    final isRt = _meta['is_realtime'];
    final isWaqi = _isWaqiSource;

    Color chipColor;
    IconData chipIcon;
    String chipLabel;
    if (isRt == true) {
      chipColor = AirVLCTheme.levelGood;
      chipIcon = Icons.check_circle;
      chipLabel = 'Datos en tiempo real (<2 h)';
    } else if (isRt == false) {
      chipColor = AirVLCTheme.levelModerate;
      chipIcon = Icons.warning_amber_rounded;
      chipLabel = 'Datos no en tiempo real (≥2 h)';
    } else {
      switch (freshness) {
        case 'fresh':
          chipColor = AirVLCTheme.levelGood;
          chipIcon = Icons.check_circle;
          chipLabel = 'Datos frescos (<2h)';
          break;
        case 'stale':
          chipColor = AirVLCTheme.levelModerate;
          chipIcon = Icons.warning_amber_rounded;
          chipLabel = 'Datos antiguos (2–24h)';
          break;
        case 'missing':
          chipColor = AirVLCTheme.levelDangerous;
          chipIcon = Icons.error_outline;
          chipLabel = 'Sin datos recientes (>24h)';
          break;
        default:
          chipColor = Colors.grey;
          chipIcon = Icons.help_outline;
          chipLabel = 'Frescura desconocida';
      }
    }

    return Card(
      color: const Color(0xFFF5F5F5),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: chipColor.withOpacity(0.12),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: chipColor.withOpacity(0.5)),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(chipIcon, size: 14, color: chipColor),
                  const SizedBox(width: 6),
                  Text(
                    chipLabel,
                    style: TextStyle(fontSize: 12, color: chipColor, fontWeight: FontWeight.w600),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const Icon(Icons.access_time, size: 16, color: Colors.grey),
                const SizedBox(width: 6),
                Text(
                  'Observados: ${_observed.length}/$_windowHours puntos'
                  '${coverage != null ? '  (cobertura ${(coverage * 100).toStringAsFixed(0)}%)' : ''}',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                ),
              ],
            ),
            if (lastTs != null) ...[
              const SizedBox(height: 4),
              Text(
                'Último dato: $lastTs'
                '${ageMin != null ? '  (hace ${_humanizeMinutes(ageMin)})' : ''}',
                style: const TextStyle(fontSize: 11, color: Colors.grey),
              ),
            ],
            if (isWaqi) ...[
              const SizedBox(height: 6),
              Text(
                'ℹ️ Histórico limitado: WAQI aporta el último punto en vivo; '
                'la serie se irá rellenando con la ingesta horaria.',
                style: TextStyle(fontSize: 11, color: Colors.blue.shade800),
              ),
            ],
            const SizedBox(height: 6),
            const Text(
              'ℹ️ El modelo LSTM con atención (R²≈0.86) predice tendencia general. '
              'Los valores individuales pueden desviarse ±3–9 µg/m³ (RMSE).',
              style: TextStyle(fontSize: 11, color: Color(0xFF616161)),
            ),
          ],
        ),
      ),
    );
  }

  String _humanizeMinutes(int m) {
    if (m < 60) return '$m min';
    if (m < 1440) return '${(m / 60).toStringAsFixed(0)} h';
    return '${(m / 1440).toStringAsFixed(0)} d';
  }

  /// Replica local de `POLLUTANT_THRESHOLDS` (src/ml/risk_classifier_v2.py),
  /// usada para recalcular el nivel de la tarjeta "Ahora" cuando mostramos
  /// el valor observado en vez de la predicción del modelo.
  static const Map<String, Map<String, double>> _pollutantThresholds = {
    'pm25': {'bueno': 12.0, 'moderado': 35.4, 'malo': 55.4},
    'no2': {'bueno': 50.0, 'moderado': 100.0, 'malo': 200.0},
    'o3': {'bueno': 100.0, 'moderado': 160.0, 'malo': 240.0},
  };

  String _levelForValue(String pollutant, double value) {
    final t = _pollutantThresholds[pollutant] ?? _pollutantThresholds['pm25']!;
    if (value <= (t['bueno'] ?? 12.0)) return 'bueno';
    if (value <= (t['moderado'] ?? 35.4)) return 'moderado';
    if (value <= (t['malo'] ?? 55.4)) return 'malo';
    return 'peligroso';
  }
}
