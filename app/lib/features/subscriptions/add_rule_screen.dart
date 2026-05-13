import 'package:flutter/material.dart';

import '../../core/api/models/risk_level.dart';
import '../../core/constants/stations.dart';
import '../../core/storage/subscriptions_storage.dart';
import '../../core/theme/airvlc_theme.dart';

class AddRuleScreen extends StatefulWidget {
  const AddRuleScreen({super.key});

  @override
  State<AddRuleScreen> createState() => _AddRuleScreenState();
}

class _AddRuleScreenState extends State<AddRuleScreen> {
  String _station = V2Stations.all.first;
  String _pollutant = 'worst';
  String _triggerType = 'level_at_least';
  String _minLevel = 'malo';
  double _minValue = 100;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Nueva alerta')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _dropdown<String>(
            label: 'Estación',
            value: _station,
            values: V2Stations.all,
            onChanged: (v) => setState(() => _station = v ?? _station),
            itemLabel: (s) => s,
          ),
          const SizedBox(height: 8),
          _dropdown<String>(
            label: 'Contaminante',
            value: _pollutant,
            values: const ['worst', 'pm25', 'no2', 'o3'],
            onChanged: (v) => setState(() => _pollutant = v ?? _pollutant),
            itemLabel: (s) =>
                {'worst': 'Cualquiera (peor)', 'pm25': 'PM2.5', 'no2': 'NO₂', 'o3': 'O₃'}[s] ??
                s,
          ),
          const SizedBox(height: 8),
          _dropdown<String>(
            label: 'Tipo de aviso',
            value: _triggerType,
            values: const ['level_at_least', 'value_above'],
            onChanged: (v) =>
                setState(() => _triggerType = v ?? _triggerType),
            itemLabel: (s) => s == 'level_at_least'
                ? 'Cuando el nivel sea X o peor'
                : 'Cuando el valor supere µg/m³',
          ),
          const SizedBox(height: 12),
          if (_triggerType == 'level_at_least')
            _dropdown<String>(
              label: 'Nivel mínimo',
              value: _minLevel,
              values: const ['moderado', 'malo', 'peligroso'],
              onChanged: (v) => setState(() => _minLevel = v ?? _minLevel),
              itemLabel: (s) =>
                  RiskLevelX.fromString(s).displayName,
            )
          else
            _valueField(),
          const SizedBox(height: 24),
          ElevatedButton.icon(
            onPressed: _save,
            icon: const Icon(Icons.notifications_active),
            label: const Text('Guardar alerta'),
          ),
        ],
      ),
    );
  }

  Widget _valueField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Umbral: ${_minValue.toStringAsFixed(0)} µg/m³',
            style: const TextStyle(fontWeight: FontWeight.bold)),
        Slider(
          value: _minValue,
          min: 10,
          max: 250,
          divisions: 24,
          label: _minValue.toStringAsFixed(0),
          activeColor: AirVLCTheme.valenciaOrange,
          onChanged: (v) => setState(() => _minValue = v),
        ),
      ],
    );
  }

  Widget _dropdown<T>({
    required String label,
    required T value,
    required List<T> values,
    required ValueChanged<T?> onChanged,
    required String Function(T) itemLabel,
  }) {
    return InputDecorator(
      decoration: InputDecoration(
        labelText: label,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<T>(
          isExpanded: true,
          value: value,
          items: values
              .map(
                  (v) => DropdownMenuItem(value: v, child: Text(itemLabel(v))))
              .toList(),
          onChanged: onChanged,
        ),
      ),
    );
  }

  void _save() {
    final rule = AlertRule(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      station: _station,
      pollutant: _pollutant,
      triggerType: _triggerType,
      minLevel: _triggerType == 'level_at_least' ? _minLevel : null,
      minValue: _triggerType == 'value_above' ? _minValue : null,
    );
    Navigator.of(context).pop(rule);
  }
}
