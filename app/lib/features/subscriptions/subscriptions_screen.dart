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
  DateTime? _lastCheckTime;

  /// Estado actual de riesgo por estación (cacheado tras el último check).
  final Map<String, RiskResponse> _currentRisk = {};

  /// Resultado de la última evaluación de cada regla (true = condición cumplida).
  final Map<String, bool> _ruleResults = {};

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
          _currentRisk[r.station] = resp;
          final matches = _ruleMatches(r, resp);
          _ruleResults[r.id] = matches;
          if (matches) {
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
      _lastCheckTime = DateTime.now();
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

  /// Obtiene la información del nivel actual para mostrar en la tarjeta de la regla.
  String _currentStatusText(AlertRule r) {
    final resp = _currentRisk[r.station];
    if (resp == null) return 'Sin datos';

    if (r.pollutant == 'worst') {
      return 'Actual: ${resp.worst.pollutant.toUpperCase()} → ${resp.worst.level.toUpperCase()} '
          '(${resp.worst.value.toStringAsFixed(1)} µg/m³)';
    }
    final reading = resp.pollutants[r.pollutant];
    if (reading == null) return 'Sin datos para ${r.pollutant}';
    return 'Actual: ${reading.prettyName} → ${reading.level.displayName.toUpperCase()} '
        '(${reading.value.toStringAsFixed(1)} µg/m³)';
  }

  Color _currentLevelColor(AlertRule r) {
    final resp = _currentRisk[r.station];
    if (resp == null) return Colors.grey;
    if (r.pollutant == 'worst') {
      return AirVLCTheme.colorForLevel(resp.worst.level);
    }
    final reading = resp.pollutants[r.pollutant];
    if (reading == null) return Colors.grey;
    return AirVLCTheme.colorForLevel(reading.level.raw);
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
            icon: _checking
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : const Icon(Icons.refresh),
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
                  child: ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      // Info banner sobre el último check
                      if (_lastCheckTime != null)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 8),
                          child: _buildLastCheckBanner(),
                        ),
                      ..._rules.asMap().entries.map((entry) {
                        final r = entry.value;
                        return _buildRuleCard(r);
                      }),
                    ],
                  ),
                ),
    );
  }

  Widget _buildLastCheckBanner() {
    final ago = DateTime.now().difference(_lastCheckTime!);
    String agoText;
    if (ago.inSeconds < 60) {
      agoText = 'hace ${ago.inSeconds}s';
    } else if (ago.inMinutes < 60) {
      agoText = 'hace ${ago.inMinutes} min';
    } else {
      agoText = 'hace ${ago.inHours}h';
    }

    final anyTriggered = _ruleResults.values.any((v) => v);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: anyTriggered
            ? AirVLCTheme.levelBad.withOpacity(0.1)
            : AirVLCTheme.levelGood.withOpacity(0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: anyTriggered
              ? AirVLCTheme.levelBad.withOpacity(0.3)
              : AirVLCTheme.levelGood.withOpacity(0.3),
        ),
      ),
      child: Row(
        children: [
          Icon(
            anyTriggered ? Icons.warning_amber_rounded : Icons.check_circle_outline,
            size: 18,
            color: anyTriggered ? AirVLCTheme.levelBad : AirVLCTheme.levelGood,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              anyTriggered
                  ? '⚠️ Alguna alerta se ha activado · Última comprobación: $agoText'
                  : '✅ Todo en orden · Última comprobación: $agoText',
              style: TextStyle(
                fontSize: 12,
                color: anyTriggered ? Colors.red.shade800 : Colors.green.shade800,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRuleCard(AlertRule r) {
    final triggered = _ruleResults[r.id] ?? false;
    final hasData = _currentRisk.containsKey(r.station);
    final levelColor = _currentLevelColor(r);

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: triggered
            ? BorderSide(color: AirVLCTheme.levelBad, width: 2)
            : BorderSide.none,
      ),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: station name + toggle
            Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.delete_outline, size: 20),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  onPressed: () async {
                    await _storage.remove(r.id);
                    _ruleResults.remove(r.id);
                    await _reload();
                  },
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        r.station,
                        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15),
                      ),
                      Text(
                        r.summary,
                        style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
                      ),
                    ],
                  ),
                ),
                Switch(
                  value: r.enabled,
                  onChanged: (_) async {
                    await _storage.toggle(r.id);
                    await _reload();
                  },
                  activeColor: AirVLCTheme.valenciaOrange,
                ),
              ],
            ),
            // Status info — muestra el nivel actual
            if (hasData && r.enabled) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                decoration: BoxDecoration(
                  color: triggered
                      ? AirVLCTheme.levelBad.withOpacity(0.08)
                      : levelColor.withOpacity(0.08),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(
                    color: triggered
                        ? AirVLCTheme.levelBad.withOpacity(0.3)
                        : levelColor.withOpacity(0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: levelColor,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _currentStatusText(r),
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade800,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                    Icon(
                      triggered ? Icons.notifications_active : Icons.notifications_off_outlined,
                      size: 16,
                      color: triggered ? AirVLCTheme.levelBad : Colors.grey,
                    ),
                  ],
                ),
              ),
              if (!triggered)
                Padding(
                  padding: const EdgeInsets.only(top: 4, left: 4),
                  child: Text(
                    'La condición no se cumple ahora — se notificará cuando empeore.',
                    style: TextStyle(fontSize: 10, color: Colors.grey.shade500, fontStyle: FontStyle.italic),
                  ),
                ),
              if (triggered)
                Padding(
                  padding: const EdgeInsets.only(top: 4, left: 4),
                  child: Text(
                    '¡Alerta activada! La calidad del aire ha empeorado.',
                    style: TextStyle(fontSize: 10, color: Colors.red.shade700, fontWeight: FontWeight.w600),
                  ),
                ),
            ],
          ],
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

