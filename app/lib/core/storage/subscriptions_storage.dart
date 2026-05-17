import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// Una regla de alerta de aire. Coincidencia se evalúa contra la respuesta
/// de `/api/v2/risk` para la estación seleccionada.
class AlertRule {
  final String id;
  final String station;
  final String pollutant; // pm25 | no2 | o3 | worst
  final String triggerType; // level_at_least | value_above
  final String? minLevel; // moderado | malo | peligroso (si triggerType=level_at_least)
  final double? minValue; // µg/m³ (si triggerType=value_above)
  final bool enabled;

  const AlertRule({
    required this.id,
    required this.station,
    required this.pollutant,
    required this.triggerType,
    this.minLevel,
    this.minValue,
    this.enabled = true,
  });

  AlertRule copyWith({bool? enabled}) => AlertRule(
        id: id,
        station: station,
        pollutant: pollutant,
        triggerType: triggerType,
        minLevel: minLevel,
        minValue: minValue,
        enabled: enabled ?? this.enabled,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'station': station,
        'pollutant': pollutant,
        'triggerType': triggerType,
        'minLevel': minLevel,
        'minValue': minValue,
        'enabled': enabled,
      };

  factory AlertRule.fromJson(Map<String, dynamic> j) => AlertRule(
        id: j['id']?.toString() ?? '',
        station: j['station']?.toString() ?? '',
        pollutant: j['pollutant']?.toString() ?? 'worst',
        triggerType: j['triggerType']?.toString() ?? 'level_at_least',
        minLevel: j['minLevel']?.toString(),
        minValue: (j['minValue'] as num?)?.toDouble(),
        enabled: j['enabled'] != false,
      );

  String get summary {
    if (triggerType == 'level_at_least') {
      return '$station: avísame si ${pollutant.toUpperCase()} pasa a ${minLevel ?? 'malo'} o peor';
    }
    return '$station: avísame si ${pollutant.toUpperCase()} supera ${(minValue ?? 0).toStringAsFixed(0)} µg/m³';
  }
}

class SubscriptionsStorage {
  static const _kRules = 'subscriptions.rules.v1';

  Future<List<AlertRule>> loadAll() async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_kRules);
    if (raw == null || raw.isEmpty) return const [];
    final list = (jsonDecode(raw) as List)
        .map((e) => AlertRule.fromJson((e as Map).cast<String, dynamic>()))
        .toList();
    return list;
  }

  Future<void> saveAll(List<AlertRule> rules) async {
    final prefs = await SharedPreferences.getInstance();
    final encoded = jsonEncode(rules.map((e) => e.toJson()).toList());
    await prefs.setString(_kRules, encoded);
  }

  Future<void> add(AlertRule rule) async {
    final all = await loadAll();
    await saveAll([...all, rule]);
  }

  Future<void> remove(String id) async {
    final all = await loadAll();
    await saveAll(all.where((r) => r.id != id).toList());
  }

  Future<void> toggle(String id) async {
    final all = await loadAll();
    await saveAll(
      all.map((r) => r.id == id ? r.copyWith(enabled: !r.enabled) : r).toList(),
    );
  }
}
