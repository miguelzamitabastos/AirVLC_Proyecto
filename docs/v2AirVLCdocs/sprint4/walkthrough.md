# Sprint 4 — Walkthrough (App Flutter v2)

> Documento vivo. Las capturas, métricas reales y vídeo se añaden tras la demo. La estructura ya queda lista para rellenarse.

## 1. Prerrequisitos

1. Backend v2 arrancado:

   ```bash
   ./.venv/bin/python src/api/app.py
   ```

2. Credenciales AWS frescas en `.env` (ver [`aws_keys_setup.md`](aws_keys_setup.md)).
3. Bot Lex con 4 intents (`ConsultarCalidad` + 3 nuevos) y `Build` aplicado.
4. App Flutter:

   ```bash
   cd app
   flutter pub get
   flutter run            # selecciona iOS/Android
   ```

## 2. Onboarding (F1)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Primer arranque | Aparece `OnboardingScreen` con 4 dropdowns (edad/condición/sensibilidad/actividad). |
| 2 | Selecciono "asma" + "alta" + "corredor" | Botón "Empezar" se habilita. |
| 3 | Pulso "Empezar" | Navega al Dashboard y persiste en `SharedPreferences`. |
| 4 | Mato la app y vuelvo a entrar | Dashboard directo, sin onboarding. |
| 5 | Pulso tab "Perfil" | Veo los 4 valores guardados y puedo editarlos. |

> Captura: `docs/v2AirVLCdocs/sprint4/img/01_onboarding.png` (pendiente).

## 3. Dashboard adaptado (F1)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Selector estación = "Politécnico" | 3 cards: PM2.5 / NO₂ / O₃ con valor en µg/m³ y color. |
| 2 | Cambio el perfil a "asma + alta" | Las cards bajan los umbrales: NO₂ a 80 pasa de "bueno" a "moderado". |
| 3 | Card grande arriba "ICA" | Muestra el peor de los 3 con `reply_text`. |

Latencia objetivo: < 500 ms por consulta (Sprint 3 mide ~250 ms en `/api/v2/risk`).

> Métricas reales (rellenar tras demo):
>
> | Endpoint | p50 (ms) | p95 (ms) | n |
> |---|---:|---:|---:|
> | `/api/v2/risk` | _pendiente_ | _pendiente_ | _pendiente_ |
> | `/api/v2/profile/recommend` | _pendiente_ | _pendiente_ | _pendiente_ |
> | `/api/v2/route` | _pendiente_ | _pendiente_ | _pendiente_ |
> | `/api/v2/chat` | _pendiente_ | _pendiente_ | _pendiente_ |

## 4. Planificador de Ruta (F2)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Origen = "Francia", Destino = "Universidad Politécnica" | Pulso "Calcular ruta". |
| 2 | Backend devuelve N tramos ordenados por proximidad | App pinta una barra horizontal con N segmentos coloreados. |
| 3 | Tap sobre segmento amarillo "Pista de Silla" | Bottom sheet con el desglose PM2.5/NO₂/O₃ y el `worst`. |
| 4 | Mensaje resumen | "Ruta saludable: pasa por Viveros (bueno) en lugar de Pista de Silla (malo NO₂)". |

> Captura: `docs/v2AirVLCdocs/sprint4/img/02_route.png` (pendiente).

## 5. Suscripciones de alerta (F3)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Tab "Alertas" → "+" | Pantalla `AddRuleScreen`. |
| 2 | Estación = "Pista de Silla", contaminante = NO₂, umbral = 100 | Guardar. |
| 3 | App hace polling cada 15 min | Si NO₂ > 100, dispara una notificación local "Alerta calidad — Pista de Silla NO₂ supera 100 µg/m³". |
| 4 | Pulso la notificación | Abre la app en el Dashboard de Pista de Silla. |
| 5 | Edito la regla y la borro | El polling deja de dispararla. |

> En Android API 33+ se solicita `POST_NOTIFICATIONS` en runtime con `permission_handler`.

## 6. Modo Voz (F4)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Tab "Voz" → botón grande "Habla" | El botón pulsa y `speech_to_text` graba. |
| 2 | Digo "puedo correr en Politécnico" | Aparece el texto transcrito. |
| 3 | App envía a `/api/v2/chat` | Lex resuelve `ConsejoSalud` y el orquestador v2 llama a `RiskClassifierV2`. |
| 4 | Backend responde `reply` | `flutter_tts` lo lee en voz alta y la pantalla muestra una card con el `worst` + recomendación adaptada al perfil. |

> Demo en dispositivo físico: el simulador iOS no soporta `speech_to_text` de manera fiable.

## 7. Comparador (F5)

| Paso | Acción | Resultado esperado |
|---|---|---|
| 1 | Tab "Comparar" | 2 columnas con dropdowns A y B, slider "ahora / 6 h / 24 h". |
| 2 | A = Viveros, B = Pista de Silla | App lanza 2 `/api/v2/risk` en paralelo. |
| 3 | Slider a "hace 6 h" | App envía el ts en el body para forzar lectura de tail-6 (cuando esté implementado el offset; ahora reusa la última ventana). |
| 4 | UI | Dos paneles con 3 contaminantes cada uno + el `worst`. |

## 8. Lex — verificación de los 3 intents

```bash
for q in "cómo está el NO2 en Politécnico" \
         "compara Viveros con Pista de Silla" \
         "puedo correr en Universidad Politécnica"; do
  curl -s -X POST http://localhost:5001/api/v2/chat \
    -H 'Content-Type: application/json' \
    -d "{\"message\":\"$q\",\"session_id\":\"demo\"}" | jq -r '.intent + " -> " + .reply'
done
```

Salida esperada (ejemplo):

```
ConsultarContaminante -> El NO₂ en Universidad Politécnica está MODERADO (75.2 µg/m³).
CompararEstaciones -> Viveros (BUENO por O₃) está mejor que Pista de Silla (MODERADO por NO₂).
ConsejoSalud -> Con asma puedes pasear pero evita correr en Universidad Politécnica: NO₂ moderado.
```

## 9. Métricas Elastic (rellenar)

Con la app abierta durante el día:

- **Docs en `airvlc-predictions-v2`** tras 1 día: _pendiente_.
- **Top 3 estaciones consultadas**: _pendiente_.
- **% de respuestas con `worst.level == 'moderado'` o peor**: _pendiente_.

## 10. Checklist final

- [ ] App compila para **Android** (`flutter build apk`).
- [ ] App compila para **iOS** (`flutter build ios --no-codesign`).
- [ ] `pytest -q` en verde — incluye los nuevos tests de `route` y `profile/recommend`.
- [ ] Backend `/api/v1/*` y `/api/v2/*` previos sin cambios de contrato.
- [ ] Demo en vídeo (≤ 3 min) grabada.
- [ ] Capturas en `docs/v2AirVLCdocs/sprint4/img/`.
- [ ] `aws_keys_setup.md` validado por el alumno regenerando token y haciendo Build de Lex.
