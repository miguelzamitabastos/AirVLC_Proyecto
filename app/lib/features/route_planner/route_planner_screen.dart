import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/risk_level.dart';
import '../../core/api/models/route_segment.dart';
import '../../core/constants/stations.dart';
import '../../core/theme/airvlc_theme.dart';

class RoutePlannerScreen extends StatefulWidget {
  final AirVLCApiClient api;
  const RoutePlannerScreen({super.key, required this.api});

  @override
  State<RoutePlannerScreen> createState() => _RoutePlannerScreenState();
}

class _RoutePlannerScreenState extends State<RoutePlannerScreen> {
  String _from = V2Stations.all.first;
  String _to = V2Stations.all.last;
  Future<RouteResponse>? _future;

  void _calcular() {
    setState(() {
      _future = widget.api.route(fromStation: _from, toStation: _to);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Planificador de Ruta')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildSelectors(),
          const SizedBox(height: 16),
          if (_future != null) _buildResult(),
        ],
      ),
    );
  }

  Widget _buildSelectors() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            _stationDropdown('Origen', _from, (v) => setState(() => _from = v)),
            const SizedBox(height: 8),
            _stationDropdown('Destino', _to, (v) => setState(() => _to = v)),
            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _calcular,
              icon: const Icon(Icons.alt_route),
              label: const Text('Calcular ruta saludable'),
            ),
          ],
        ),
      ),
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
            if (v != null) onChanged(v);
          },
        ),
      ),
    );
  }

  Widget _buildResult() {
    return FutureBuilder<RouteResponse>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState == ConnectionState.waiting) {
          return const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        if (snap.hasError) {
          return Card(
            color: AirVLCTheme.levelDangerous.withOpacity(0.08),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Text('Error: ${snap.error}'),
            ),
          );
        }
        final data = snap.data!;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (data.replyText != null && data.replyText!.isNotEmpty)
              Card(
                color: AirVLCTheme.primaryBlue.withOpacity(0.08),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      const Icon(Icons.directions_walk,
                          color: AirVLCTheme.primaryBlue),
                      const SizedBox(width: 12),
                      Expanded(child: Text(data.replyText!)),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 8),
            _buildBar(data),
            const SizedBox(height: 12),
            ...data.segments.asMap().entries.map((entry) {
              final idx = entry.key;
              final seg = entry.value;
              return _segmentTile(seg, isWorst: idx == data.worstSegmentIndex);
            }),
          ],
        );
      },
    );
  }

  Widget _buildBar(RouteResponse data) {
    final children = <Widget>[];
    for (var i = 0; i < data.segments.length; i++) {
      final seg = data.segments[i];
      final color = AirVLCTheme.colorForLevel(seg.worst.level);
      children.add(Expanded(
        child: GestureDetector(
          onTap: () => _showSegmentSheet(seg),
          child: Container(
            height: 36,
            decoration: BoxDecoration(
              color: color,
              borderRadius: BorderRadius.horizontal(
                left: i == 0 ? const Radius.circular(18) : Radius.zero,
                right: i == data.segments.length - 1
                    ? const Radius.circular(18)
                    : Radius.zero,
              ),
              border: Border(
                right: i == data.segments.length - 1
                    ? BorderSide.none
                    : const BorderSide(color: Colors.white, width: 2),
              ),
            ),
            alignment: Alignment.center,
            child: Text(
              seg.worst.pollutant.toUpperCase(),
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 12,
              ),
            ),
          ),
        ),
      ));
    }
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Row(children: children),
      ),
    );
  }

  Widget _segmentTile(RouteSegment seg, {required bool isWorst}) {
    final color = AirVLCTheme.colorForLevel(seg.worst.level);
    return Card(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: isWorst
            ? BorderSide(color: color, width: 2)
            : BorderSide.none,
      ),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: color.withOpacity(0.25),
          foregroundColor: color,
          child: Text(seg.worst.pollutant.toUpperCase().substring(0, 2),
              style: const TextStyle(fontWeight: FontWeight.bold)),
        ),
        title: Text(seg.station),
        subtitle: Text(
          'PM2.5 ${seg.predictions.pm25.toStringAsFixed(0)} · '
          'NO₂ ${seg.predictions.no2.toStringAsFixed(0)} · '
          'O₃ ${seg.predictions.o3.toStringAsFixed(0)} µg/m³',
        ),
        trailing: Container(
          padding:
              const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            seg.worst.level.toUpperCase(),
            style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.bold,
                fontSize: 11),
          ),
        ),
        onTap: () => _showSegmentSheet(seg),
      ),
    );
  }

  void _showSegmentSheet(RouteSegment seg) {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(seg.station,
                style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.bold)),
            const SizedBox(height: 12),
            ...seg.pollutants.entries.map((e) {
              final r = e.value;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(
                  children: [
                    Text(r.prettyName,
                        style:
                            const TextStyle(fontWeight: FontWeight.bold)),
                    const Spacer(),
                    Text('${r.value.toStringAsFixed(1)} µg/m³'),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AirVLCTheme.colorForLevel(r.level.raw),
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        r.level.displayName,
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold,
                            fontSize: 11),
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
  }
}
