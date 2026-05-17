import 'dart:async';

import 'package:flutter/material.dart';

import '../../core/api/models/prediction.dart';
import '../../core/theme/airvlc_theme.dart';

/// Chip que muestra la frescura de los datos (contrato de la guía de
/// implementación GVA-RealTime):
///
/// - **< 2 h** (120 min): "Datos hasta HH:MM — hace N min/h" (verde)
/// - **2 h – 24 h**: "Datos hasta HH:MM — hace N h" (ámbar)
/// - **24 h – 30 d**: "Datos del dd/MM — hace N días" (rojo)
/// - **> 30 d**: "Datos históricos (dd/MM/YYYY)" (azul info)
///
/// Se actualiza cada minuto automáticamente (tick del [Timer.periodic]).
class FreshnessChip extends StatefulWidget {
  final Prediction? prediction;
  final bool isRefreshing;

  const FreshnessChip({
    super.key,
    required this.prediction,
    this.isRefreshing = false,
  });

  @override
  State<FreshnessChip> createState() => _FreshnessChipState();
}

class _FreshnessChipState extends State<FreshnessChip> {
  Timer? _minuteTicker;

  @override
  void initState() {
    super.initState();
    _minuteTicker = Timer.periodic(
      const Duration(seconds: 60),
      (_) => setState(() {}),
    );
  }

  @override
  void dispose() {
    _minuteTicker?.cancel();
    super.dispose();
  }

  /// Calcula la edad en minutos para textos y umbrales legacy.
  int _computeAge() {
    final pred = widget.prediction;
    final dataTs = pred?.dataTimestamp;
    if (dataTs != null) {
      return DateTime.now().difference(dataTs).inMinutes;
    }
    return pred?.dataAgeMinutes ?? 0;
  }

  /// Devuelve true si los datos son históricos (más de 30 días).
  bool _isHistorical(int ageMinutes) => ageMinutes > 43200; // ~30 días

  Color _chipColor(Prediction pred, int ageMinutes) {
    // API v2 (`is_realtime` desde Mongo): verde / amarillo semántico.
    if (pred.isRealtime != null) {
      return pred.isRealtime!
          ? AirVLCTheme.levelGood
          : AirVLCTheme.levelModerate;
    }
    if (_isHistorical(ageMinutes)) return AirVLCTheme.primaryBlue;
    // Contrato GVA-RealTime: <2h verde, 2-24h ámbar, >24h rojo.
    if (ageMinutes < 120) return AirVLCTheme.levelGood;
    if (ageMinutes < 1440) return AirVLCTheme.levelModerate;
    return AirVLCTheme.levelDangerous;
  }

  IconData _chipIcon(Prediction pred, int ageMinutes) {
    if (pred.isRealtime != null) {
      return pred.isRealtime! ? Icons.check_circle : Icons.warning_amber_rounded;
    }
    if (_isHistorical(ageMinutes)) return Icons.history;
    if (ageMinutes < 120) return Icons.check_circle;
    if (ageMinutes < 1440) return Icons.warning_amber_rounded;
    return Icons.error_outline;
  }

  String _formatHHMM(DateTime? dt) {
    if (dt == null) return '--:--';
    final h = dt.hour.toString().padLeft(2, '0');
    final m = dt.minute.toString().padLeft(2, '0');
    return '$h:$m';
  }

  String _formatDate(DateTime? dt) {
    if (dt == null) return '--/--';
    final d = dt.day.toString().padLeft(2, '0');
    final mo = dt.month.toString().padLeft(2, '0');
    return '$d/$mo';
  }

  String _formatFullDate(DateTime? dt) {
    if (dt == null) return '--/--/----';
    final d = dt.day.toString().padLeft(2, '0');
    final mo = dt.month.toString().padLeft(2, '0');
    final y = dt.year;
    return '$d/$mo/$y';
  }

  /// Formatea la antigüedad de forma legible.
  String _formatAge(int ageMinutes) {
    if (ageMinutes < 1) return 'ahora mismo';
    if (ageMinutes < 60) return 'hace $ageMinutes min';
    if (ageMinutes < 1440) return 'hace ${ageMinutes ~/ 60} h';
    if (ageMinutes < 43200) return 'hace ${ageMinutes ~/ 1440} días';
    // > 30 días: ya no mostramos "hace", es histórico
    return '';
  }

  /// Construye la línea principal del chip.
  String _buildMainText(int ageMinutes, DateTime? dataTs) {
    if (_isHistorical(ageMinutes)) {
      return 'Datos históricos (${_formatFullDate(dataTs)})';
    }
    if (ageMinutes >= 1440) {
      // Más de 1 día: mostrar fecha
      return 'Datos del ${_formatDate(dataTs)} — ${_formatAge(ageMinutes)}';
    }
    // Menos de 1 día: mostrar hora
    return 'Datos hasta ${_formatHHMM(dataTs)} — ${_formatAge(ageMinutes)}';
  }

  /// Subtítulo contextual.
  String _buildSubText(int ageMinutes) {
    if (_isHistorical(ageMinutes)) {
      return 'Activa el pipeline horario para datos en tiempo real';
    }
    final now = DateTime.now();
    final next = DateTime(now.year, now.month, now.day, now.hour + 1, 0);
    return 'Próxima actualización ~${_formatHHMM(next)}';
  }

  @override
  Widget build(BuildContext context) {
    final pred = widget.prediction;
    if (pred == null) return const SizedBox.shrink();

    if (pred.dataTimestamp == null &&
        pred.dataAgeMinutes == null &&
        pred.isRealtime == null) {
      return const SizedBox.shrink();
    }

    final age = _computeAge();
    final color = _chipColor(pred, age);
    final icon = _chipIcon(pred, age);
    final mainText = (pred.dataTimestamp == null &&
            pred.dataAgeMinutes == null &&
            pred.isRealtime != null)
        ? (pred.isRealtime!
            ? 'Datos en tiempo real'
            : 'Datos fuera de ventana en tiempo real (<2 h)')
        : _buildMainText(age, pred.dataTimestamp);
    final subText = _buildSubText(age);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withOpacity(0.10),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withOpacity(0.5), width: 1.5),
      ),
      child: Row(
        children: [
          if (widget.isRefreshing)
            SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: color,
              ),
            )
          else
            Icon(icon, color: color, size: 20),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  mainText,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: color,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subText,
                  style: TextStyle(
                    fontSize: 11,
                    color: color.withOpacity(0.7),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
