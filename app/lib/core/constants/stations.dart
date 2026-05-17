/// Lista canónica de las 7 estaciones soportadas por el modelo v2
/// (deben coincidir con `master_dataset_colab_v2.csv`).
class V2Stations {
  static const List<String> all = [
    'Francia',
    'Molí del Sol',
    'Pista de Silla',
    'Puerto Moll Trans. Ponent',
    'Puerto Valencia',
    'Puerto llit antic Túria',
    'Universidad Politécnica',
  ];

  /// Aliases / nombres cortos que el usuario podría escribir o decir.
  static const Map<String, String> aliases = {
    'francia': 'Francia',
    'avda francia': 'Francia',
    'avenida francia': 'Francia',
    'moli del sol': 'Molí del Sol',
    'molí del sol': 'Molí del Sol',
    'pista silla': 'Pista de Silla',
    'pista de silla': 'Pista de Silla',
    'puerto valencia': 'Puerto Valencia',
    'puerto': 'Puerto Valencia',
    'puerto moll': 'Puerto Moll Trans. Ponent',
    'puerto turia': 'Puerto llit antic Túria',
    'politécnico': 'Universidad Politécnica',
    'politecnico': 'Universidad Politécnica',
    'universidad politécnica': 'Universidad Politécnica',
    'universidad politecnica': 'Universidad Politécnica',
  };

  static String resolve(String input) {
    final norm = input.trim().toLowerCase();
    if (all.any((s) => s.toLowerCase() == norm)) {
      return all.firstWhere((s) => s.toLowerCase() == norm);
    }
    return aliases[norm] ?? input;
  }

  /// Sprint 7: coordenadas de las estaciones para el mapa.
  /// Coinciden con STATION_COORDS del backend (es_indexer.py).
  static const Map<String, List<double>> coords = {
    'Francia': [39.4578, -0.343],
    'Molí del Sol': [39.4811, -0.4088],
    'Pista de Silla': [39.4581, -0.3766],
    'Puerto Moll Trans. Ponent': [39.4470, -0.3200],
    'Puerto Valencia': [39.4484, -0.3172],
    'Puerto llit antic Túria': [39.4560, -0.3300],
    'Universidad Politécnica': [39.4796, -0.3374],
  };
}
