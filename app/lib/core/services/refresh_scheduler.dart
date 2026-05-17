import 'dart:async';

import 'package:flutter/widgets.dart';

/// Scheduler que dispara un callback de refresco:
///
/// 1. **Cada minuto** comprueba si ha cambiado la hora (`DateTime.now().hour`)
///    o si `dataAgeMinutes > 70` → dispara [onRefreshNeeded].
/// 2. **Al reanudar la app** (AppLifecycleState.resumed) fuerza un check
///    inmediato.
///
/// Ejemplo de uso:
/// ```dart
/// late final RefreshScheduler _scheduler;
///
/// @override void initState() {
///   super.initState();
///   _scheduler = RefreshScheduler(onRefreshNeeded: _refresh);
///   _scheduler.start();
/// }
///
/// @override void dispose() {
///   _scheduler.dispose();
///   super.dispose();
/// }
/// ```
class RefreshScheduler with WidgetsBindingObserver {
  /// Callback que se ejecuta cuando el scheduler decide que hay que refrescar.
  final VoidCallback onRefreshNeeded;

  /// Edad máxima en minutos antes de forzar un refresco.
  final int maxAgeMinutes;

  Timer? _ticker;
  int? _lastRefreshHour;
  int _currentDataAgeMinutes = 0;

  RefreshScheduler({
    required this.onRefreshNeeded,
    this.maxAgeMinutes = 70,
  });

  /// Inicia el scheduler y registra el observer del ciclo de vida.
  void start() {
    _lastRefreshHour = DateTime.now().hour;
    WidgetsBinding.instance.addObserver(this);
    _ticker = Timer.periodic(const Duration(minutes: 1), (_) => _check());
  }

  /// Actualiza la edad del dato tras cada respuesta del backend.
  void updateDataAge(int? ageMinutes) {
    _currentDataAgeMinutes = ageMinutes ?? 0;
  }

  /// Fuerza un check inmediato.
  void checkNow() => _check();

  void _check() {
    final now = DateTime.now();
    final hourChanged = now.hour != _lastRefreshHour;
    final tooOld = _currentDataAgeMinutes > maxAgeMinutes;

    if (hourChanged || tooOld) {
      _lastRefreshHour = now.hour;
      onRefreshNeeded();
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _check();
    }
  }

  /// Detiene el scheduler y elimina el observer.
  void dispose() {
    _ticker?.cancel();
    WidgetsBinding.instance.removeObserver(this);
  }
}
