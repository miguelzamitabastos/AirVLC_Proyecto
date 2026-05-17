import 'package:flutter/material.dart';

import '../../core/api/models/health_profile.dart';
import '../../core/storage/profile_storage.dart';
import '../../core/theme/airvlc_theme.dart';

class OnboardingScreen extends StatefulWidget {
  final VoidCallback onCompleted;
  const OnboardingScreen({super.key, required this.onCompleted});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  final _storage = ProfileStorage();
  HealthProfile _profile = HealthProfile.defaultProfile;
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AirVLCTheme.backgroundLight,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const SizedBox(height: 16),
              Text('Bienvenido a AirVLC',
                  style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 8),
              Text(
                'Cuéntanos sobre ti para personalizar las recomendaciones de calidad del aire. Tus datos no salen de este dispositivo.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      _buildDropdown<AgeRange>(
                        label: 'Edad',
                        value: _profile.age,
                        values: AgeRange.values,
                        labelOf: (e) => e.displayName,
                        onChanged: (v) =>
                            setState(() => _profile = _profile.copyWith(age: v)),
                      ),
                      _buildDropdown<Condition>(
                        label: 'Condición',
                        value: _profile.condition,
                        values: Condition.values,
                        labelOf: (e) => e.displayName,
                        onChanged: (v) => setState(
                            () => _profile = _profile.copyWith(condition: v)),
                      ),
                      _buildDropdown<Sensitivity>(
                        label: 'Sensibilidad declarada',
                        value: _profile.sensitivity,
                        values: Sensitivity.values,
                        labelOf: (e) => e.displayName,
                        onChanged: (v) => setState(
                            () => _profile = _profile.copyWith(sensitivity: v)),
                      ),
                      _buildDropdown<Activity>(
                        label: 'Actividad típica',
                        value: _profile.activity,
                        values: Activity.values,
                        labelOf: (e) => e.displayName,
                        onChanged: (v) => setState(
                            () => _profile = _profile.copyWith(activity: v)),
                      ),
                    ],
                  ),
                ),
              ),
              ElevatedButton(
                onPressed: _saving ? null : _save,
                child: _saving
                    ? const SizedBox(
                        height: 18,
                        width: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Text('Empezar'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDropdown<T>({
    required String label,
    required T value,
    required List<T> values,
    required String Function(T) labelOf,
    required ValueChanged<T?> onChanged,
  }) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<T>(
            isExpanded: true,
            value: value,
            items: values
                .map((e) =>
                    DropdownMenuItem(value: e, child: Text(labelOf(e))))
                .toList(),
            onChanged: onChanged,
          ),
        ),
      ),
    );
  }

  Future<void> _save() async {
    setState(() => _saving = true);
    await _storage.save(_profile);
    await _storage.markOnboardingDone();
    if (!mounted) return;
    setState(() => _saving = false);
    widget.onCompleted();
  }
}
