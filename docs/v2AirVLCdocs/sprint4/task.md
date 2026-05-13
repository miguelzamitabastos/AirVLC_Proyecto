# Sprint 4 — Tareas operativas

> Checklist por bloques. Cada bloque enlaza al fichero implementado.

## 0. Documentación

- [x] `docs/v2AirVLCdocs/sprint4/implementation_plan.md`
- [x] `docs/v2AirVLCdocs/sprint4/task.md` (este fichero)
- [x] `docs/v2AirVLCdocs/sprint4/walkthrough.md`
- [x] `docs/v2AirVLCdocs/sprint4/aws_keys_setup.md`
- [x] Actualizar `docs/v2AirVLCdocs/task_sprints.md` con bloque Sprint 4.

## 1. Backend Flask v2 (extensiones)

- [x] `POST /api/v2/profile/recommend` en [`src/api/routes_v2.py`](../../../src/api/routes_v2.py).
- [x] `POST /api/v2/route` en [`src/api/routes_v2.py`](../../../src/api/routes_v2.py).
- [x] `ChatbotOrchestratorV2` con 3 intents nuevos: `ConsultarContaminante`, `CompararEstaciones`, `ConsejoSalud` ([`src/services/chatbot_orchestrator_v2.py`](../../../src/services/chatbot_orchestrator_v2.py)).
- [x] Reuso de `STATION_COORDS` desde [`src/api/es_indexer.py`](../../../src/api/es_indexer.py) para el cálculo de tramos.

## 2. App Flutter — scaffolding

- [x] `app/pubspec.yaml` con `flutter_local_notifications`, `shared_preferences`, `intl`, `permission_handler`.
- [x] `app/lib/main.dart` (bootstrap).
- [x] `app/lib/app.dart` (`MaterialApp` + bottom nav: Dashboard / Chat / Voz / Perfil).
- [x] `app/lib/core/theme/airvlc_theme.dart` con paleta accesible (verde/amarillo/naranja/rojo).
- [x] `app/lib/core/constants/api_constants.dart` (baseUrl) + `stations.dart` (7 estaciones v2).

## 3. API client + modelos

- [x] `app/lib/core/api/airvlc_api_client.dart` con métodos:
  - `predict(station)` → `Prediction`
  - `risk(station)` → `RiskResponse`
  - `chat(text, sessionId)` → `ChatResponse`
  - `recommend(station, profile, activity)` → `RecommendResponse`
  - `route(from, to)` → `List<RouteSegment>`
- [x] `app/lib/core/api/models/prediction.dart`
- [x] `app/lib/core/api/models/risk_level.dart`
- [x] `app/lib/core/api/models/pollutant_reading.dart`
- [x] `app/lib/core/api/models/route_segment.dart`
- [x] `app/lib/core/api/models/chat_response.dart`

## 4. F1 — Perfil persistente + Onboarding + Dashboard

- [x] `app/lib/core/storage/profile_storage.dart` — `SharedPreferences` con keys `age/condition/sensitivity/activity`.
- [x] `app/lib/features/profile/onboarding_screen.dart` — primer arranque.
- [x] `app/lib/features/profile/profile_screen.dart` — edición.
- [x] `app/lib/features/dashboard/dashboard_screen.dart` — 3 cards PM2.5/NO2/O3 + ICA.
- [x] `app/lib/features/dashboard/pollutant_card.dart` — card con color adaptado al perfil.

## 5. F2 — Planificador de Ruta

- [x] `app/lib/features/route_planner/route_planner_screen.dart` con dropdowns de 7 estaciones y barra horizontal coloreada.

## 6. F3 — Suscripciones + Notificaciones locales

- [x] `app/lib/core/storage/subscriptions_storage.dart`.
- [x] `app/lib/core/notifications/local_notifications.dart` — `flutter_local_notifications` + permission_handler.
- [x] `app/lib/features/subscriptions/subscriptions_screen.dart` con polling cada 15 min.
- [x] `app/lib/features/subscriptions/add_rule_screen.dart`.

## 7. F4 — Modo Voz

- [x] `app/lib/core/voice/stt_service.dart` (`speech_to_text`).
- [x] `app/lib/core/voice/tts_service.dart` (`flutter_tts`).
- [x] `app/lib/features/voice_mode/voice_mode_screen.dart`.

## 8. F5 — Comparador de Estaciones

- [x] `app/lib/features/stations_compare/compare_screen.dart` con slider temporal.

## 9. Lex — 3 intents nuevos

- [x] Documentado paso a paso en [`aws_keys_setup.md`](aws_keys_setup.md):
  - `ConsultarContaminante` (slots: `Estacion`, `Contaminante`).
  - `CompararEstaciones` (slots: `EstacionA`, `EstacionB`).
  - `ConsejoSalud` (slots: `Estacion`, `Actividad`).
- [x] `ChatbotOrchestratorV2._handle_consultar_contaminante` etc.

## 10. Tests

- [x] `tests/api/test_routes_v2_sprint4.py` — contratos `/api/v2/profile/recommend` y `/api/v2/route`.
- [x] `app/test/widget_test.dart` — smoke test del bootstrap.

## 11. Demo final

- [ ] Capturas + métricas reales en [`walkthrough.md`](walkthrough.md).
