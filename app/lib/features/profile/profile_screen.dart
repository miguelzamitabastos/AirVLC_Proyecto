import 'package:flutter/material.dart';

import '../../core/api/models/health_profile.dart';
import '../../core/storage/profile_storage.dart';
import '../../core/theme/airvlc_theme.dart';

class ProfileScreen extends StatefulWidget {
  final ProfileStorage profileStorage;
  const ProfileScreen({super.key, required this.profileStorage});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  HealthProfile? _profile;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final p = await widget.profileStorage.load();
    setState(() => _profile = p);
  }

  Future<void> _save() async {
    if (_profile == null) return;
    await widget.profileStorage.save(_profile!);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Perfil guardado')),
    );
  }

  @override
  Widget build(BuildContext context) {
    final profile = _profile;
    return Scaffold(
      appBar: AppBar(title: const Text('Perfil')),
      body: profile == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Card(
                  color: profile.isSensitive
                      ? AirVLCTheme.levelBad.withOpacity(0.1)
                      : AirVLCTheme.levelGood.withOpacity(0.1),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Icon(
                          profile.isSensitive
                              ? Icons.warning_amber
                              : Icons.check_circle,
                          color: profile.isSensitive
                              ? AirVLCTheme.levelBad
                              : AirVLCTheme.levelGood,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            profile.isSensitive
                                ? 'Tu perfil es sensible: aplicamos umbrales más estrictos.'
                                : 'Perfil estándar: aplicamos los umbrales ICA estándar.',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
                _dropdown<AgeRange>(
                  label: 'Edad',
                  value: profile.age,
                  values: AgeRange.values,
                  labelOf: (e) => e.displayName,
                  onChanged: (v) => setState(
                      () => _profile = profile.copyWith(age: v)),
                ),
                _dropdown<Condition>(
                  label: 'Condición',
                  value: profile.condition,
                  values: Condition.values,
                  labelOf: (e) => e.displayName,
                  onChanged: (v) => setState(
                      () => _profile = profile.copyWith(condition: v)),
                ),
                _dropdown<Sensitivity>(
                  label: 'Sensibilidad',
                  value: profile.sensitivity,
                  values: Sensitivity.values,
                  labelOf: (e) => e.displayName,
                  onChanged: (v) => setState(
                      () => _profile = profile.copyWith(sensitivity: v)),
                ),
                _dropdown<Activity>(
                  label: 'Actividad',
                  value: profile.activity,
                  values: Activity.values,
                  labelOf: (e) => e.displayName,
                  onChanged: (v) => setState(
                      () => _profile = profile.copyWith(activity: v)),
                ),
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: _save,
                  icon: const Icon(Icons.save),
                  label: const Text('Guardar cambios'),
                ),
              ],
            ),
    );
  }

  Widget _dropdown<T>({
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
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: DropdownButtonHideUnderline(
          child: DropdownButton<T>(
            isExpanded: true,
            value: value,
            items: values
                .map((e) => DropdownMenuItem(value: e, child: Text(labelOf(e))))
                .toList(),
            onChanged: onChanged,
          ),
        ),
      ),
    );
  }
}
