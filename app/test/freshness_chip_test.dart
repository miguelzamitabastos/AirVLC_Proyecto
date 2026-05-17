import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:airvlc_app/core/api/models/prediction.dart';
import 'package:airvlc_app/features/dashboard/freshness_chip.dart';

void main() {
  group('FreshnessChip', () {
    Widget buildChip(Prediction prediction, {bool isRefreshing = false}) {
      return MaterialApp(
        home: Scaffold(
          body: FreshnessChip(
            prediction: prediction,
            isRefreshing: isRefreshing,
          ),
        ),
      );
    }

    testWidgets('muestra chip verde cuando datos son recientes (<90 min)',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        dataTimestamp: DateTime.now().subtract(const Duration(minutes: 30)),
        dataAgeMinutes: 30,
        dataWindowStart: DateTime.now().subtract(const Duration(hours: 24)),
        serverTimestamp: DateTime.now(),
      );

      await tester.pumpWidget(buildChip(pred));
      await tester.pump();

      // Debe mostrar "Datos hasta" y "hace 30 min" (approx)
      expect(find.textContaining('Datos hasta'), findsOneWidget);
      expect(find.textContaining('Próxima actualización'), findsOneWidget);
    });

    testWidgets('muestra chip ámbar cuando datos tienen 90-180 min',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        dataTimestamp: DateTime.now().subtract(const Duration(minutes: 120)),
        dataAgeMinutes: 120,
        dataWindowStart: DateTime.now().subtract(const Duration(hours: 24)),
        serverTimestamp: DateTime.now(),
      );

      await tester.pumpWidget(buildChip(pred));
      await tester.pump();

      expect(find.textContaining('Datos hasta'), findsOneWidget);
    });

    testWidgets('muestra chip rojo cuando datos son muy antiguos (>180 min)',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        dataTimestamp: DateTime.now().subtract(const Duration(minutes: 200)),
        dataAgeMinutes: 200,
        dataWindowStart: DateTime.now().subtract(const Duration(hours: 24)),
        serverTimestamp: DateTime.now(),
      );

      await tester.pumpWidget(buildChip(pred));
      await tester.pump();

      expect(find.textContaining('Datos hasta'), findsOneWidget);
    });

    testWidgets('no muestra nada si prediction es null', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: FreshnessChip(prediction: null),
          ),
        ),
      );

      expect(find.byType(FreshnessChip), findsOneWidget);
      // El SizedBox.shrink debería ser el contenido
      expect(find.textContaining('Datos hasta'), findsNothing);
    });

    testWidgets('muestra spinner cuando isRefreshing es true',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        dataTimestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        dataAgeMinutes: 5,
        dataWindowStart: DateTime.now().subtract(const Duration(hours: 24)),
        serverTimestamp: DateTime.now(),
      );

      await tester.pumpWidget(buildChip(pred, isRefreshing: true));
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('prioriza is_realtime true: texto tiempo real (API v2 Mongo)',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        isRealtime: true,
      );

      await tester.pumpWidget(buildChip(pred));
      await tester.pump();

      expect(find.textContaining('tiempo real'), findsOneWidget);
    });

    testWidgets('prioriza is_realtime false: texto fuera de ventana tiempo real',
        (tester) async {
      final pred = Prediction(
        pm25: 10,
        no2: 20,
        o3: 30,
        isRealtime: false,
      );

      await tester.pumpWidget(buildChip(pred));
      await tester.pump();

      expect(find.textContaining('fuera de ventana'), findsOneWidget);
    });
  });
}
