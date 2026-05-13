import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/risk_level.dart';
import '../../core/api/models/risk_response.dart';
import '../../core/constants/stations.dart';
import '../../core/theme/airvlc_theme.dart';

/// Comparador de estaciones (F5).
///
/// El slider temporal "Ahora / 6h / 24h" es por ahora una etiqueta
/// informativa: el backend v2 reusa la última ventana del CSV histórico, así
/// que las 3 opciones devuelven la misma inferencia. Cuando se implemente el
/// offset temporal en `/api/v2/risk` (parámetro `offset_hours`) bastará con
/// pasarlo en el body — el resto de la UI ya está listo.
class CompareScreen extends StatefulWidget {
  final AirVLCApiClient api;
  const CompareScreen({super.key, required this.api});

  @override
  State<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends State<CompareScreen> {
  String _stationA = V2Stations.all.first;
  String _stationB = V2Stations.all.last;
  int _timeIndex = 0; // 0 = ahora, 1 = 6h, 2 = 24h

  Future<RiskResponse>? _futureA;
  Future<RiskResponse>? _futureB;

  static const _timeLabels = ['Ahora', 'Hace 6 h', 'Hace 24 h'];

  int _offsetHoursForIndex() {
    switch (_timeIndex) {
      case 1:
        return 6;
      case 2:
        return 24;
      default:
        return 0;
    }
  }

  void _refresh() {
    final offset = _offsetHoursForIndex();
    setState(() {
      _futureA = widget.api.risk(_stationA, offsetHours: offset);
      _futureB = widget.api.risk(_stationB, offsetHours: offset);
    });
  }

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Comparar estaciones')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _selectorRow(),
          const SizedBox(height: 12),
          _timeSlider(),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _columnFor(_futureA, _stationA)),
              const SizedBox(width: 8),
              Expanded(child: _columnFor(_futureB, _stationB)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _selectorRow() {
    return Row(
      children: [
        Expanded(
          child: _stationDropdown(
              'A', _stationA, (v) => setState(() => _stationA = v)),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _stationDropdown(
              'B', _stationB, (v) => setState(() => _stationB = v)),
        ),
      ],
    );
  }

  Widget _stationDropdown(
      String label, String value, ValueChanged<String> onChanged) {
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          isExpanded: true,
          value: value,
          items: V2Stations.all
              .map((s) => DropdownMenuItem(value: s, child: Text(s)))
              .toList(),
          onChanged: (v) {
            if (v != null) {
              onChanged(v);
              _refresh();
            }
          },
        ),
      ),
    );
  }

  Widget _timeSlider() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Column(
          children: [
            Text('Ventana temporal: ${_timeLabels[_timeIndex]}',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            Slider(
              value: _timeIndex.toDouble(),
              min: 0,
              max: 2,
              divisions: 2,
              label: _timeLabels[_timeIndex],
              activeColor: AirVLCTheme.valenciaOrange,
              onChanged: (v) {
                setState(() => _timeIndex = v.round());
                _refresh();
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _columnFor(Future<RiskResponse>? f, String station) {
    return FutureBuilder<RiskResponse>(
      future: f,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Card(
            child: Padding(
              padding: EdgeInsets.all(24),
              child: Center(child: CircularProgressIndicator()),
            ),
          );
        }
        if (snap.hasError) {
          return Card(
            color: AirVLCTheme.levelDangerous.withOpacity(0.08),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Text('Error en $station: ${snap.error}'),
            ),
          );
        }
        final data = snap.data!;
        final color = AirVLCTheme.colorForLevel(data.worst.level);
        return Card(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(color: color, width: 2),
          ),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(data.station,
                    style: const TextStyle(
                        fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                _smallBadge('Worst: ${data.worst.pollutant.toUpperCase()}',
                    color),
                const SizedBox(height: 8),
                ...['pm25', 'no2', 'o3'].map((k) {
                  final r = data.pollutants[k];
                  if (r == null) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 4),
                    child: Row(
                      children: [
                        Text(r.prettyName,
                            style:
                                const TextStyle(fontWeight: FontWeight.bold)),
                        const Spacer(),
                        Text('${r.value.toStringAsFixed(0)} µg/m³'),
                        const SizedBox(width: 8),
                        Container(
                          width: 14,
                          height: 14,
                          decoration: BoxDecoration(
                            color: AirVLCTheme.colorForLevel(r.level.raw),
                            shape: BoxShape.circle,
                          ),
                        ),
                      ],
                    ),
                  );
                }),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _smallBadge(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        text,
        style: const TextStyle(
            color: Colors.white, fontWeight: FontWeight.bold, fontSize: 11),
      ),
    );
  }
}
