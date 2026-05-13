import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/prediction.dart';
import '../../core/theme/airvlc_theme.dart';
import '../dashboard/freshness_chip.dart';
import '../timeseries/timeseries_screen.dart';

/// Sprint 7 — Mapa de riesgo por estaciones.
///
/// Muestra un diagrama esquemático de Valencia con marcadores circulares
/// por estación, coloreados según el nivel de riesgo del contaminante
/// seleccionado y el horizonte temporal.
class MapRiskScreen extends StatefulWidget {
  final AirVLCApiClient api;
  final String initialPollutant;
  final int initialHorizon;

  const MapRiskScreen({
    super.key,
    required this.api,
    this.initialPollutant = 'pm25',
    this.initialHorizon = 0,
  });

  @override
  State<MapRiskScreen> createState() => _MapRiskScreenState();
}

class _MapRiskScreenState extends State<MapRiskScreen> {
  late String _pollutant;
  late int _horizon;
  bool _loading = true;
  bool _highRiskOnly = false;
  List<Map<String, dynamic>> _stations = [];
  Map<String, dynamic> _mapRoot = const {};
  String? _error;

  static const _pollutants = ['pm25', 'no2', 'o3'];
  static const _pollutantLabels = {'pm25': 'PM2.5', 'no2': 'NO₂', 'o3': 'O₃'};
  static const _horizonLabels = {0: 'Ahora', 24: '+24h', 48: '+48h', 72: '+72h'};

  @override
  void initState() {
    super.initState();
    _pollutant = widget.initialPollutant;
    _horizon = widget.initialHorizon;
    _fetchMap();
  }

  Future<void> _fetchMap() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await widget.api.mapStations(
        pollutant: _pollutant,
        horizon: _horizon,
      );
      _mapRoot = data;
      final raw = (data['stations'] as List?) ?? [];
      _stations = raw.cast<Map<String, dynamic>>();
    } catch (e) {
      _error = e.toString();
    }
    if (mounted) setState(() => _loading = false);
  }

  Color _colorForLevel(String? level) => AirVLCTheme.colorForLevel(level);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Mapa de Riesgo')),
      body: Column(
        children: [
          _buildControls(),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildControls() {
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 0),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        child: Column(
          children: [
            // Pollutant selector
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.science, size: 20, color: AirVLCTheme.primaryBlue),
                const SizedBox(width: 8),
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text('Contaminante:', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: _pollutants.map((p) {
                      final sel = p == _pollutant;
                      return ChoiceChip(
                        label: Text(_pollutantLabels[p] ?? p),
                        selected: sel,
                        selectedColor: AirVLCTheme.primaryBlue.withOpacity(0.12),
                        onSelected: (_) {
                          setState(() => _pollutant = p);
                          _fetchMap();
                        },
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Horizon selector
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.access_time, size: 20, color: AirVLCTheme.primaryBlue),
                const SizedBox(width: 8),
                const Padding(
                  padding: EdgeInsets.only(top: 6),
                  child: Text('Momento:', style: TextStyle(fontWeight: FontWeight.bold)),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: _horizonLabels.entries.map((e) {
                      final sel = e.key == _horizon;
                      return ChoiceChip(
                        label: Text(e.value),
                        selected: sel,
                        selectedColor: AirVLCTheme.primaryBlue.withOpacity(0.12),
                        onSelected: (_) {
                          setState(() => _horizon = e.key);
                          _fetchMap();
                        },
                      );
                    }).toList(),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            // Filter toggle
            Row(
              children: [
                Switch(
                  value: _highRiskOnly,
                  onChanged: (v) => setState(() => _highRiskOnly = v),
                  activeColor: AirVLCTheme.levelDangerous,
                ),
                const Text('Solo estaciones con riesgo Alto/Peligroso'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.error_outline, size: 48, color: AirVLCTheme.levelDangerous),
              const SizedBox(height: 12),
              Text('Error cargando mapa: $_error', textAlign: TextAlign.center),
              const SizedBox(height: 12),
              ElevatedButton.icon(
                onPressed: _fetchMap,
                icon: const Icon(Icons.refresh),
                label: const Text('Reintentar'),
              ),
            ],
          ),
        ),
      );
    }

    var filtered = _stations;
    if (_highRiskOnly) {
      filtered = _stations.where((s) {
        final l = (s['level'] ?? '').toString().toLowerCase();
        return l == 'malo' || l == 'peligroso';
      }).toList();
    }

    if (filtered.isEmpty) {
      return const Center(
        child: Text('No hay estaciones que coincidan con el filtro.'),
      );
    }

    return _buildSchematicMap(filtered);
  }

  /// Dibuja un mapa esquemático: posiciona las estaciones según sus
  /// coordenadas normalizadas dentro del espacio disponible.
  Widget _buildSchematicMap(List<dynamic> stations) {
    if (stations.isEmpty) return const Center(child: Text('Sin datos'));

    // Calcular bounding box para initial bounds
    double minLat = 90, maxLat = -90, minLon = 180, maxLon = -180;
    for (var s in stations) {
      final loc = s['location'];
      if (loc != null) {
        final lat = (loc['lat'] as num?)?.toDouble() ?? 0;
        final lon = (loc['lon'] as num?)?.toDouble() ?? 0;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
      }
    }
    if (minLat == maxLat) {
      minLat -= 0.05;
      maxLat += 0.05;
    }
    if (minLon == maxLon) {
      minLon -= 0.05;
      maxLon += 0.05;
    }

    return Stack(
      children: [
        FlutterMap(
          options: MapOptions(
            initialCameraFit: CameraFit.bounds(
              bounds: LatLngBounds(LatLng(minLat, minLon), LatLng(maxLat, maxLon)),
              padding: const EdgeInsets.all(40),
            ),
          ),
          children: [
            TileLayer(
              urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
              // OSM recomienda un User-Agent identificable; esto evita bloqueos
              // intermitentes en iOS cuando el UA queda genérico.
              userAgentPackageName: 'airvlc_app',
              maxZoom: 19,
              tileProvider: NetworkTileProvider(),
            ),
            MarkerLayer(
              markers: stations.map((s) {
                final loc = s['location'];
                if (loc == null) return null;
                final lat = (loc['lat'] as num?)?.toDouble() ?? 0.0;
                final lon = (loc['lon'] as num?)?.toDouble() ?? 0.0;
                final level = s['level']?.toString();
                final color = _colorForLevel(level);
                final station = s['station']?.toString() ?? '';
                final value = (s['value'] as num?)?.toDouble();

                return Marker(
                  point: LatLng(lat, lon),
                  width: 100,
                  height: 60,
                  alignment: Alignment.topCenter,
                  child: GestureDetector(
                    onTap: () => _showStationDetail(s),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        _AnimatedMarker(color: color, value: value),
                        const SizedBox(height: 2),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.9),
                            borderRadius: BorderRadius.circular(6),
                            boxShadow: [
                              BoxShadow(color: color.withOpacity(0.3), blurRadius: 4),
                            ],
                          ),
                          child: Text(
                            station.length > 14 ? '${station.substring(0, 12)}…' : station,
                            style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w600),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              }).whereType<Marker>().toList(),
            ),
          ],
        ),
        // Legend
        Positioned(
          right: 12,
          bottom: 12,
          child: _buildLegend(),
        ),
      ],
    );
  }

  Widget _buildLegend() {
    const levels = [
      ('Bueno', AirVLCTheme.levelGood),
      ('Moderado', AirVLCTheme.levelModerate),
      ('Malo', AirVLCTheme.levelBad),
      ('Peligroso', AirVLCTheme.levelDangerous),
    ];
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.92),
        borderRadius: BorderRadius.circular(10),
        boxShadow: const [BoxShadow(color: Color(0x22000000), blurRadius: 6)],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Nivel', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
          const SizedBox(height: 4),
          ...levels.map((l) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(width: 12, height: 12, decoration: BoxDecoration(color: l.$2, shape: BoxShape.circle)),
                    const SizedBox(width: 4),
                    Text(l.$1, style: const TextStyle(fontSize: 10)),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  void _showStationDetail(Map<String, dynamic> s) {
    final station = s['station']?.toString() ?? '';
    final level = s['level']?.toString() ?? 'bueno';
    final color = _colorForLevel(level);
    final allPreds = (s['all_predictions'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};
    final meta = (s['meta'] as Map?) ?? {};
    final dataTs = meta['data_timestamp']?.toString();
    final modelUsed = meta['model_used']?.toString() ?? 'LSTM_Attention_Multi';
    final predictionBundle = Prediction.fromJson(
      allPreds,
      parentJson: Prediction.mapStationFreshnessParent(s, _mapRoot),
    );

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 16, height: 16,
                  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(station, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(12)),
                  child: Text(level.toUpperCase(), style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 12)),
                ),
              ],
            ),
            const Divider(height: 20),
            // Predictions summary
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _predChip('PM2.5', allPreds['pm25']),
                _predChip('NO₂', allPreds['no2']),
                _predChip('O₃', allPreds['o3']),
              ],
            ),
            if (_horizon == 0)
              FreshnessChip(prediction: predictionBundle),
            const SizedBox(height: 4),
            // Transparency badge
            Container(
              margin: const EdgeInsets.symmetric(vertical: 8),
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: const Color(0xFFFFF3E0),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: AirVLCTheme.valenciaOrange.withOpacity(0.3)),
              ),
              child: Row(
                children: [
                  const Icon(Icons.info_outline, size: 16, color: AirVLCTheme.valenciaOrange),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _horizon == 0
                          ? 'Dato actual — basado en la última ventana del modelo.'
                          : 'Forecast +${_horizon}h — tendencia estimada, no valor exacto.',
                      style: const TextStyle(fontSize: 11, color: Color(0xFF795548)),
                    ),
                  ),
                ],
              ),
            ),
            if (dataTs != null && dataTs.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  'Ventana base: $dataTs · Modelo: $modelUsed',
                  style: const TextStyle(fontSize: 11, color: Colors.grey),
                ),
              ),
            const SizedBox(height: 8),
            // CTA → Serie temporal
            SizedBox(
              width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: () {
                  Navigator.pop(context);
                  Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => TimeseriesScreen(
                      api: widget.api,
                      station: station,
                      pollutant: _pollutant,
                    ),
                  ));
                },
                icon: const Icon(Icons.show_chart),
                label: const Text('Ver serie temporal'),
              ),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _predChip(String label, dynamic val) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        Text(
          val != null ? '${(val as num).toStringAsFixed(1)} µg/m³' : '–',
          style: const TextStyle(fontSize: 12),
        ),
      ],
    );
  }
}

/// Animated pulsing marker for the map.
class _AnimatedMarker extends StatefulWidget {
  final Color color;
  final double? value;
  const _AnimatedMarker({required this.color, this.value});

  @override
  State<_AnimatedMarker> createState() => _AnimatedMarkerState();
}

class _AnimatedMarkerState extends State<_AnimatedMarker>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, child) {
        final scale = 1.0 + _ctrl.value * 0.15;
        return Transform.scale(
          scale: scale,
          child: Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: widget.color.withOpacity(0.85),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: widget.color.withOpacity(0.4),
                  blurRadius: 8 + _ctrl.value * 4,
                  spreadRadius: _ctrl.value * 2,
                ),
              ],
            ),
            child: Center(
              child: widget.value != null
                  ? Text(
                      widget.value!.toStringAsFixed(0),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      ),
                    )
                  : const Text('?', style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
            ),
          ),
        );
      },
    );
  }
}

/// Subtle grid lines for the map background.
class _MapGridPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = const Color(0x15000000)
      ..strokeWidth = 0.5;
    const spacing = 40.0;
    for (double x = 0; x <= size.width; x += spacing) {
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
    }
    for (double y = 0; y <= size.height; y += spacing) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
