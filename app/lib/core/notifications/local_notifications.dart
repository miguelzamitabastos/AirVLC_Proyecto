import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';

/// Singleton que envuelve `flutter_local_notifications` con la configuración
/// que usa la app: canal Android `airvlc_alerts`, sonidos por defecto.
class LocalNotifications {
  LocalNotifications._();
  static final instance = LocalNotifications._();

  final _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;

  static const _androidChannel = AndroidNotificationChannel(
    'airvlc_alerts',
    'Alertas de calidad del aire',
    description:
        'Notificaciones cuando una de tus reglas de calidad del aire se cumple.',
    importance: Importance.high,
  );

  Future<void> init() async {
    if (_initialized) return;
    const androidInit =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosInit = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    await _plugin.initialize(
      const InitializationSettings(android: androidInit, iOS: iosInit),
    );

    final androidImpl = _plugin.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    await androidImpl?.createNotificationChannel(_androidChannel);

    _initialized = true;
  }

  /// Pide los permisos necesarios. Devuelve true si quedaron concedidos.
  Future<bool> requestPermissions() async {
    if (!_initialized) await init();
    bool ok = true;

    if (defaultTargetPlatform == TargetPlatform.android) {
      final status = await Permission.notification.request();
      ok = status.isGranted || status.isLimited;
    } else if (defaultTargetPlatform == TargetPlatform.iOS) {
      final iosImpl = _plugin.resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin>();
      ok = await iosImpl?.requestPermissions(
            alert: true,
            badge: true,
            sound: true,
          ) ??
          false;
    }
    return ok;
  }

  /// Lanza una notificación inmediata. [id] permite agrupar/sustituir
  /// (mismas reglas → mismo id evita inundar).
  Future<void> show({
    required int id,
    required String title,
    required String body,
    String? payload,
  }) async {
    if (!_initialized) await init();
    const androidDetails = AndroidNotificationDetails(
      'airvlc_alerts',
      'Alertas de calidad del aire',
      channelDescription:
          'Notificaciones cuando una de tus reglas de calidad del aire se cumple.',
      importance: Importance.high,
      priority: Priority.high,
    );
    // iOS: por defecto, si la app está en primer plano puede no mostrar banner.
    // Forzamos presentación en foreground para la demo.
    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );
    await _plugin.show(
      id,
      title,
      body,
      const NotificationDetails(android: androidDetails, iOS: iosDetails),
      payload: payload,
    );
  }
}
