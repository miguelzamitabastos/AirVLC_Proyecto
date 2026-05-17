import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/health_profile.dart';
import '../../core/api/models/recommend_response.dart';
import '../../core/constants/stations.dart';
import '../../core/services/refresh_scheduler.dart';
import '../../core/storage/profile_storage.dart';
import '../../core/theme/airvlc_theme.dart';
import '../map/map_risk_screen.dart';
import '../route_planner/route_planner_screen.dart';
import '../stations_compare/compare_screen.dart';
import '../timeseries/timeseries_screen.dart';
import '../voice_mode/voice_mode_screen.dart';
import 'freshness_chip.dart';
import 'pollutant_card.dart';

class DashboardScreen extends StatefulWidget {
  final AirVLCApiClient api;
  final ProfileStorage profileStorage;

  const DashboardScreen({
    super.key,
    required this.api,
    required this.profileStorage,
  });

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  String _station = V2Stations.all.first;
  HealthProfile _profile = HealthProfile.defaultProfile;

  Future<RecommendResponse>? _future;
  bool _profileLoaded = false;
  bool _isRefreshing = false;

  /// Sprint 5: scheduler de refresco automático horario
  late final RefreshScheduler _scheduler;

  /// Sprint 5: última respuesta cacheada para el FreshnessChip
  RecommendResponse? _lastResponse;

  @override
  void initState() {
    super.initState();
    _scheduler = RefreshScheduler(onRefreshNeeded: _refresh);
    _scheduler.start();
    _bootstrap();
  }

  @override
  void dispose() {
    _scheduler.dispose();
    super.dispose();
  }

  Future<void> _bootstrap() async {
    final p = await widget.profileStorage.load();
    setState(() {
      _profile = p;
      _profileLoaded = true;
      _refresh();
    });
  }

  void _refresh() {
    setState(() {
      _isRefreshing = true;
      _future = widget.api
          .recommend(
            station: _station,
            profile: _profile,
            activity: _profile.activity.apiValue,
          )
          .then((resp) {
        // Actualizar el scheduler con la edad del dato
        _scheduler.updateDataAge(resp.predictions.dataAgeMinutes);
        setState(() {
          _lastResponse = resp;
          _isRefreshing = false;
        });
        return resp;
      }).catchError((e) {
        setState(() => _isRefreshing = false);
        throw e;
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AirVLC'),
        actions: [
          IconButton(
            tooltip: 'Refrescar',
            icon: const Icon(Icons.refresh),
            onPressed: _refresh,
          ),
        ],
      ),
      body: !_profileLoaded
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: () async => _refresh(),
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  _buildStationSelector(),
                  const SizedBox(height: 8),
                  // --- Sprint 5: FreshnessChip ---
                  FreshnessChip(
                    prediction: _lastResponse?.predictions,
                    isRefreshing: _isRefreshing,
                  ),
                  const SizedBox(height: 4),
                  _buildIcaCard(),
                  const SizedBox(height: 8),
                  _buildPollutantsList(),
                  const SizedBox(height: 16),
                  _buildQuickActions(),
                ],
              ),
            ),
    );
  }

  Widget _buildStationSelector() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: Row(
          children: [
            const Icon(Icons.location_on, color: AirVLCTheme.primaryBlue),
            const SizedBox(width: 8),
            Expanded(
              child: DropdownButtonHideUnderline(
                child: DropdownButton<String>(
                  isExpanded: true,
                  value: _station,
                  items: V2Stations.all
                      .map(
                          (s) => DropdownMenuItem(value: s, child: Text(s)))
                      .toList(),
                  onChanged: (v) {
                    if (v != null) {
                      setState(() => _station = v);
                      _refresh();
                    }
                  },
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildIcaCard() {
    return FutureBuilder<RecommendResponse>(
      future: _future,
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
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('No se pudo conectar con el backend',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 6),
                  Text(snap.error.toString()),
                  const SizedBox(height: 6),
                  TextButton.icon(
                    onPressed: _refresh,
                    icon: const Icon(Icons.refresh),
                    label: const Text('Reintentar'),
                  ),
                ],
              ),
            ),
          );
        }
        final data = snap.data;
        if (data == null) return const SizedBox.shrink();

        final color = AirVLCTheme.colorFromHex(data.colorHex,
            fallbackLevel: data.levelAdjusted);
        return Card(
          color: color.withOpacity(0.10),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(20),
            side: BorderSide(color: color, width: 2),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 12, vertical: 6),
                      decoration: BoxDecoration(
                        color: color,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        'ICA: ${data.levelAdjusted.toUpperCase()}',
                        style: const TextStyle(
                            color: Colors.white,
                            fontWeight: FontWeight.bold),
                      ),
                    ),
                    const Spacer(),
                    if (data.isSensitiveProfile)
                      const Icon(Icons.health_and_safety,
                          color: AirVLCTheme.primaryBlue),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  data.recommendationText,
                  style: const TextStyle(fontSize: 16, height: 1.4),
                ),
                const SizedBox(height: 8),
                Text(
                  data.replyText,
                  style: const TextStyle(
                      fontSize: 13, color: AirVLCTheme.textDark),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildPollutantsList() {
    return FutureBuilder<RecommendResponse>(
      future: _future,
      builder: (context, snap) {
        if (!snap.hasData) return const SizedBox.shrink();
        final data = snap.data!;
        final keys = ['pm25', 'no2', 'o3'];
        return Column(
          children: keys
              .where((k) => data.pollutants.containsKey(k))
              .map((k) => PollutantCard(
                    reading: data.pollutants[k]!,
                    profile: _profile,
                  ))
              .toList(),
        );
      },
    );
  }

  Widget _buildQuickActions() {
    final api = widget.api;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Text(
                'Acciones rápidas',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
              ),
            ),
            Wrap(
              children: [
                _actionTile(
                  icon: Icons.map,
                  label: 'Mapa de riesgo',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => MapRiskScreen(api: api),
                  )),
                ),
                _actionTile(
                  icon: Icons.show_chart,
                  label: 'Serie temporal',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => TimeseriesScreen(
                      api: api,
                      station: _station,
                    ),
                  )),
                ),
                _actionTile(
                  icon: Icons.alt_route,
                  label: 'Planificar ruta',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => RoutePlannerScreen(api: api),
                  )),
                ),
                _actionTile(
                  icon: Icons.compare_arrows,
                  label: 'Comparar estaciones',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => CompareScreen(api: api),
                  )),
                ),
                _actionTile(
                  icon: Icons.mic,
                  label: 'Modo voz',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => VoiceModeScreen(
                      api: api,
                      profileStorage: widget.profileStorage,
                    ),
                  )),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionTile({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return SizedBox(
      width: 160,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Icon(icon, color: AirVLCTheme.primaryBlue, size: 32),
              const SizedBox(height: 6),
              Text(label, textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}
