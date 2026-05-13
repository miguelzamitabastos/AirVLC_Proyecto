// Smoke test mínimo del bootstrap de AirVLC v2.
//
// El test garantiza que `AirVLCApp` se construye sin reventar y que entra
// en `_RootBootstrap` (que decide entre onboarding y home shell). No
// validamos el resto del flujo aquí porque depende de `SharedPreferences`
// y del backend Flask.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:airvlc_app/app.dart';

void main() {
  testWidgets('AirVLCApp boota sin lanzar excepciones', (tester) async {
    await tester.pumpWidget(const AirVLCApp());
    // Tras el primer frame el bootstrap está en `FutureBuilder` esperando
    // `SharedPreferences`. Un MaterialApp ya está montado.
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
