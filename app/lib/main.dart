import 'package:flutter/material.dart';

import 'app.dart';
import 'core/notifications/local_notifications.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Init perezoso de notificaciones — no bloquea el arranque si falla.
  unawaited(LocalNotifications.instance.init());
  runApp(const AirVLCApp());
}

void unawaited(Future<void> future) {
  // Helper local para evitar `unawaited_futures`. No usamos `dart:async` aquí.
  future.catchError((_) {});
}
