import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api/airvlc_api_client.dart';
import '../../core/api/models/risk_level.dart';
import '../../core/api/models/risk_response.dart';
import '../../core/notifications/local_notifications.dart';
import '../../core/storage/subscriptions_storage.dart';
import '../../core/theme/airvlc_theme.dart';
import 'add_rule_screen.dart';

class SubscriptionsScreen extends StatefulWidget {
  final AirVLCApiClient api;
  const SubscriptionsScreen({super.key, required this.api});

  @override
  State<SubscriptionsScreen> createState() => _SubscriptionsScreenState();
}

class _SubscriptionsScreenState extends State<SubscriptionsScreen>
    with WidgetsBindingObserver {
  static const _pollingInterval = Duration(minutes: 15);

  final _storage = SubscriptionsStorage();
  List<AlertRule> _rules = const [];
  bool _loading = true;
  bool _checking = false;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _bootstrap();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _timer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkAllNow();
    }
  }

  Future<void> _bootstrap() async {
    await LocalNotifications.instance.init();
    await LocalNotifications.instance.requestPermissions();
    await _reload();
    _timer = Timer.periodic(_pollingInterval, (_) => _checkAllNow());
    // Primera evaluación al entrar
    _checkAllNow();
  }

  Future<void> _reload() async {
    final all = await _storage.loadAll();
    setState(() {
      _rules = all;
      _loading = false;
    });
  }

  Future<void> _checkAllNow() async {
    if (_checking || _rules.isEmpty) return;
    setState(() => _checking = true);
    try {
      // Cacheamos por estación para no llamar 2 veces si hay varias reglas
      final byStation = <String, RiskResponse>{};
      for (final r in _rules.where((r) => r.enabled)) {
        try {
          final resp = byStation[r.station] ??=
              await widget.api.risk(r.station);
          if (_ruleMatches(r, resp)) {
            await LocalNotifications.instance.show(
              id: r.id.hashCode,
              title: 'AirVLC — Alerta de calidad',
              body: _alertBody(r, resp),
              payload: r.id,
            );
          }
        } catch (_) {
          // Silenciamos: el polling no debe interrumpir al usuario.
        }
      }
    } finally {
      if (mounted) setState(() => _checking = false);
    }
  }

  bool _ruleMatches(AlertRule r, RiskResponse resp) {
    if (r.pollutant == 'worst') {
      if (r.triggerType == 'level_at_least') {
        final cur = RiskLevelX.fromString(resp.worst.level);
        final wanted = RiskLevelX.fromString(r.minLevel);
        return cur.severity >= wanted.severity;
      }
      return resp.worst.value >= (r.minValue ?? double.infinity);
    }
    final reading = resp.pollutants[r.pollutant];
    if (reading == null) return false;
    if (r.triggerType == 'level_at_least') {
      final wanted = RiskLevelX.fromString(r.minLevel);
      return reading.level.severity >= wanted.severity;
    }
    return reading.value >= (r.minValue ?? double.infinity);
  }

  String _alertBody(AlertRule r, RiskResponse resp) {
    if (r.pollutant == 'worst') {
      return '${resp.station}: ${resp.worst.pollutant.toUpperCase()} '
          '${resp.worst.value.toStringAsFixed(0)} µg/m³ — ${resp.worst.level.toUpperCase()}';
    }
    final reading = resp.pollutants[r.pollutant]!;
    return '${resp.station}: ${reading.prettyName} '
        '${reading.value.toStringAsFixed(0)} µg/m³ — ${reading.level.displayName.toUpperCase()}';
  }

  Future<void> _addRule() async {
    final result = await Navigator.of(context).push<AlertRule?>(
      MaterialPageRoute(builder: (_) => const AddRuleScreen()),
    );
    if (result != null) {
      await _storage.add(result);
      await _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mis alertas'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_active_outlined),
            tooltip: 'Notificación de prueba',
            onPressed: () async {
              await LocalNotifications.instance.show(
                id: DateTime.now().millisecondsSinceEpoch ~/ 1000,
                title: 'AirVLC — Prueba de alerta',
                body: 'Esto es un simulacro de notificación local.',
                payload: 'test',
              );
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Notificación de prueba enviada')),
                );
              }
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Comprobar ahora',
            onPressed: _checkAllNow,
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _addRule,
        child: const Icon(Icons.add),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _rules.isEmpty
              ? const _EmptyState()
              : RefreshIndicator(
                  onRefresh: _checkAllNow,
                  child: ListView.builder(
                    padding: const EdgeInsets.all(12),
                    itemCount: _rules.length,
                    itemBuilder: (_, i) {
                      final r = _rules[i];
                      return Card(
                        child: SwitchListTile(
                          value: r.enabled,
                          onChanged: (_) async {
                            await _storage.toggle(r.id);
                            await _reload();
                          },
                          title: Text(r.station,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold)),
                          subtitle: Text(r.summary),
                          secondary: IconButton(
                            icon: const Icon(Icons.delete_outline),
                            onPressed: () async {
                              await _storage.remove(r.id);
                              await _reload();
                            },
                          ),
                          activeColor: AirVLCTheme.valenciaOrange,
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(40),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.notifications_none,
              size: 80, color: AirVLCTheme.primaryBlue),
          const SizedBox(height: 12),
          Text(
            'Aún no tienes alertas',
            style: Theme.of(context).textTheme.headlineMedium,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 6),
          const Text(
            'Toca "+" para suscribirte a una estación. Te avisaremos cuando la calidad del aire empeore.',
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}
