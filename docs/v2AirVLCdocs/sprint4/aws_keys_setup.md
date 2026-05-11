# AWS Keys + Lex — preparación previa al Sprint 4

> **Antes** de arrancar la app Flutter: hay que actualizar las credenciales AWS y dar `Build` al bot de Lex con los 3 intents nuevos. La app **no** lleva credenciales: todo se canaliza por el backend Flask.

## 1. Por qué hay que tocar el `.env` cada lab

El proyecto usa una cuenta **AWS Academy / Educate**. Las credenciales son **temporales** (`AWS_SESSION_TOKEN`) y caducan **cada 3-4 horas**, o cuando se cierra el lab.

Si Lex/Polly/Transcribe devuelven `ExpiredTokenException`, la causa es siempre la misma: el token caducó. Hay que regenerarlo desde el panel de AWS Academy.

## 2. Cómo regenerar las credenciales

1. Entra al panel de AWS Academy del curso.
2. Pulsa **Start Lab** (espera al "ready" verde).
3. Pulsa **AWS Details** → **AWS CLI**.
4. Copia el bloque `aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`.
5. Pega los valores en `.env` del proyecto Python (no en la app):

```env
AWS_ACCESS_KEY_ID="ASIA..."
AWS_SECRET_ACCESS_KEY="..."
AWS_SESSION_TOKEN="IQoJ..."
AWS_REGION="us-east-1"

LEX_BOT_ID="XSNZESMBDT"
LEX_BOT_ALIAS_ID="TSTALIASID"
```

6. Reinicia el backend:

```bash
./.venv/bin/python src/api/app.py
```

> **Nunca** uses `python3` pelado: es el del sistema y no tiene `tensorflow` ni `pandas`.

## 3. Síntoma cuando el token caduca

```
ExpiredTokenException: The security token included in the request is expired
```

La app degrada con elegancia:
- El chat textual y `/api/v2/predict|risk` siguen funcionando (no necesitan AWS).
- El **modo voz** muestra el banner "voz desactivada — credenciales temporales caducadas".
- `/api/v2/chat` devuelve `503` con `error` legible.

## 4. Añadir los 3 intents nuevos al bot de Lex

Mantenemos `ConsultarCalidad` (Sprint 3, **no se toca**). Se añaden:

### 4.1. Slot types reutilizables

- `ValenciaStation` — ya existe (Sprint 3). Slots de tipo "estación".
- **`PollutantType`** (nuevo) — custom slot type. Valores:
  - `pm25` (sinónimos: `PM2.5`, `partículas`, `partículas finas`)
  - `no2` (sinónimos: `NO2`, `dióxido de nitrógeno`, `nitrógeno`)
  - `o3` (sinónimos: `O3`, `ozono`)
- **`Activity`** (nuevo) — custom slot type. Valores:
  - `correr` (sinónimos: `running`, `salir a correr`, `trotar`)
  - `pasear` (sinónimos: `andar`, `caminar`, `dar un paseo`)
  - `pasear al perro` (sinónimos: `sacar al perro`, `pasear el perro`)
  - `ir en bici` (sinónimos: `bicicleta`, `pedalear`, `ir en bicicleta`)
  - `quedarme en casa` (sinónimos: `salir`, `abrir la ventana`)

### 4.2. Intents

#### `ConsultarContaminante`

- Slots:
  - `Estacion` (`ValenciaStation`, requerido).
  - `Contaminante` (`PollutantType`, requerido).
- Sample utterances (mín. 3):
  - `cómo está el {Contaminante} en {Estacion}`
  - `dime el {Contaminante} en {Estacion}`
  - `qué nivel de {Contaminante} hay en {Estacion}`
  - `valor del {Contaminante} en {Estacion}`

#### `CompararEstaciones`

- Slots:
  - `EstacionA` (`ValenciaStation`, requerido).
  - `EstacionB` (`ValenciaStation`, requerido).
- Sample utterances (mín. 3):
  - `compara {EstacionA} con {EstacionB}`
  - `dónde se respira mejor {EstacionA} o {EstacionB}`
  - `qué estación está peor {EstacionA} o {EstacionB}`
  - `compara la calidad entre {EstacionA} y {EstacionB}`

#### `ConsejoSalud`

- Slots:
  - `Estacion` (`ValenciaStation`, requerido).
  - `Actividad` (`Activity`, requerido).
- Sample utterances (mín. 3):
  - `puedo {Actividad} en {Estacion}`
  - `es buen momento para {Actividad} en {Estacion}`
  - `me recomiendas {Actividad} hoy en {Estacion}`
  - `puedo salir a {Actividad} si estoy en {Estacion}`

### 4.3. Build del bot

1. En la consola de Lex V2 → **Bots** → tu bot (`LEX_BOT_ID`).
2. **Locale** `es_ES` → **Intents** → añade los 3 nuevos.
3. Haz **Build** del locale (tarda ~1 min).
4. Verifica desde local:

```bash
./venv/bin/python -c "
from src.services.aws.lex_service import LexService
import os
s = LexService()
r = s.recognize_text(
    bot_id=os.environ['LEX_BOT_ID'],
    bot_alias_id=os.environ['LEX_BOT_ALIAS_ID'],
    locale_id='es_ES',
    text='compara Viveros con Politécnico',
    session_id='setup-check',
)
print(r['interpretations'][0]['intent']['name'])
"
```

Debe imprimir `CompararEstaciones`.

## 5. Comprobación end-to-end

```bash
# Backend
./.venv/bin/python src/api/app.py

# En otra terminal
curl -s -X POST http://localhost:5001/api/v2/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"puedo correr en Politécnico","session_id":"demo"}' | jq .
```

Debe responder con `intent: ConsejoSalud` y un `reply` adaptado.

## 6. Privacidad

La app **nunca** sube datos personales sensibles. El `profile` que viaja en `POST /api/v2/profile/recommend` es un dict pequeño (`age`, `condition`, `sensitivity`, `activity`) que el backend usa solo en memoria para componer el `recommendation_text`. No se persiste en ES ni en ninguna BD.
