# Sprint 7 — Nuevos Intents en AWS Lex

## Intents a crear en la consola de Lex

### 1. `VerMapaRiesgo`

**Descripción:** El usuario quiere ver el mapa de niveles de riesgo.

**Slots (opcionales):**
| Slot | Tipo | Obligatorio |
|------|------|-------------|
| `Contaminante` | Custom / `AMAZON.SearchQuery` | No |

**Sample Utterances:**
```
muéstrame el mapa
ver mapa de riesgo
mapa del {Contaminante}
muéstrame el mapa de {Contaminante}
enséñame los niveles en el mapa
quiero ver el mapa de calidad del aire
mapa de contaminación
cómo está Valencia en el mapa
```

**Fulfillment:** Return intent → el backend genera `ui_payload.action = "open_map"`.

---

### 2. `PrevisionRiesgo`

**Descripción:** El usuario quiere saber la previsión futura de un contaminante en una estación.

**Slots:**
| Slot | Tipo | Obligatorio |
|------|------|-------------|
| `Estacion` | Custom (`EstacionValencia`) | Sí |
| `Contaminante` | Custom / `AMAZON.SearchQuery` | No |
| `Horizonte` | Custom (`HorizonteTemporal`) | No |

**Slot Type `HorizonteTemporal` (Custom):**
- Valores: `24`, `48`, `72`
- Sinónimos: `24h`, `mañana`, `un día` → 24; `48h`, `dos días` → 48; `72h`, `tres días` → 72

**Sample Utterances:**
```
cómo estará el {Contaminante} en {Estacion} en {Horizonte} horas
previsión de {Contaminante} en {Estacion}
qué se espera en {Estacion} en {Horizonte} horas
predicción de {Contaminante} para {Estacion}
cómo estará {Estacion} mañana
forecast de {Estacion}
previsión para {Horizonte} horas en {Estacion}
```

**Fulfillment:** Return intent → el backend genera `ui_payload.action = "open_station_detail"`.

---

### 3. `TopPeoresEstaciones` (Opcional)

**Descripción:** El usuario quiere saber qué estaciones están peor.

**Slots:**
| Slot | Tipo | Obligatorio |
|------|------|-------------|
| `Contaminante` | Custom / `AMAZON.SearchQuery` | No |
| `Horizonte` | `HorizonteTemporal` | No |

**Sample Utterances:**
```
cuáles están peor
qué estaciones tienen más contaminación
cuáles son las peores estaciones
dónde hay más {Contaminante}
ranking de estaciones
cuáles están peor en {Horizonte} horas
```

---

## Notas de Implementación

- Los nuevos intents se manejan en `chatbot_orchestrator_v2.py` (handlers ya implementados).
- El `ui_payload` se devuelve en la respuesta JSON del `/api/v2/chat` y Flutter lo usa para navegar.
- Cuando crees los intents en Lex, selecciona `Return parameters to client` como tipo de fulfillment.
- Recuerda hacer **Build** del bot después de añadir los intents.
