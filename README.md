# AirVLC — Sistema Inteligente de Monitorización y Predicción de la Calidad del Aire en València

[![Tests Python](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/tests.yml)
[![Tests Flutter](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/flutter-tests.yml/badge.svg?branch=main)](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/flutter-tests.yml)
[![Lint & Quality](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/miguelzamitabastos/AirVLC_Proyecto/actions/workflows/lint.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![Flutter 3.41](https://img.shields.io/badge/flutter-3.41.9-blue.svg)](https://docs.flutter.dev/release/release-notes)

> Plataforma integral de análisis, predicción y alerta de la calidad del aire en la ciudad de València, basada en inteligencia artificial y datos abiertos de la Red de Vigilancia y Control de Contaminación Atmosférica (RVVCCA).

---

## Tabla de contenidos

1. [Resumen ejecutivo](#resumen-ejecutivo)
2. [Motivación y contexto](#motivación-y-contexto)
3. [Arquitectura del sistema](#arquitectura-del-sistema)
4. [Fuentes de datos](#fuentes-de-datos)
5. [Resultados del modelo](#resultados-del-modelo)
6. [Tecnologías utilizadas](#tecnologías-utilizadas)
7. [Estructura del repositorio](#estructura-del-repositorio)
8. [Instalación y arranque](#instalación-y-arranque)
9. [Servicios y endpoints](#servicios-y-endpoints)
10. [Pruebas e integración continua](#pruebas-e-integración-continua)
11. [Lenguaje inclusivo y no sexista](#lenguaje-inclusivo-y-no-sexista)
12. [Licencia](#licencia)
13. [Cómo citar este proyecto](#cómo-citar-este-proyecto)
14. [Autoría y agradecimientos](#autoría-y-agradecimientos)

---

## Resumen ejecutivo

AirVLC es una plataforma end-to-end que ingiere datos horarios de las diez estaciones de la RVVCCA en la ciudad de València, entrena modelos de aprendizaje profundo para predecir niveles de PM2.5, NO₂ y O₃ a 24 horas vista, y expone los resultados a través de una API REST, dashboards interactivos en Kibana y una aplicación móvil multiplataforma desarrollada en Flutter. El sistema incorpora servicios de procesamiento de lenguaje natural (NLU, TTS, ASR) sobre AWS para permitir interacción por voz, y se despliega como microservicios orquestados con Docker Compose.

## Motivación y contexto

La contaminación atmosférica es uno de los principales determinantes ambientales de la salud pública según la Organización Mundial de la Salud. En contextos urbanos como València, la exposición prolongada a partículas finas (PM2.5) y dióxido de nitrógeno (NO₂) está asociada a enfermedades cardiovasculares, respiratorias y a una reducción medible de la esperanza de vida. Disponer de información predictiva, accesible y comprensible para la ciudadanía es por tanto un objetivo de relevancia social directa.

AirVLC nace en el marco del curso de especialización en Inteligencia Artificial y Big Data del IES Abastos (curso 2025-2026) con el objetivo de demostrar que las herramientas de IA aplicadas a datos abiertos pueden generar valor público real: anticipar episodios de mala calidad del aire, ofrecer recomendaciones contextualizadas y facilitar la toma de decisiones tanto a la ciudadanía como a la administración.

## Arquitectura del sistema

El sistema se organiza en cinco capas funcionales claramente separadas:

```
┌──────────────────────────────────────────────────────────────────────┐
│ CAPA 1 — INGESTA                                                     │
│  - Portal Datos Abiertos Ajuntament de València (histórico CSV)      │
│  - RVVCCA Generalitat Valenciana (horario CSV)                       │
│  - Node-RED: orquestación de flujos                                  │
│  - GitHub Actions: cron horario para ingesta de producción           │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ CAPA 2 — ALMACENAMIENTO POLÍGLOTA                                    │
│  - PostgreSQL: series temporales históricas relacionales             │
│  - MongoDB: predicciones, alertas y datos semiestructurados          │
│  - Elasticsearch: indexación para búsqueda y dashboards              │
│  - Redis: caché de lecturas recientes                                │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ CAPA 3 — INTELIGENCIA ARTIFICIAL                                     │
│  - Preprocesado y feature engineering                                │
│  - LSTM con mecanismo de atención (modelo de producción)             │
│  - Modelos comparativos: CNN-LSTM, Transformer Encoder               │
│  - Clasificación de niveles de riesgo (HuggingFace)                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ CAPA 4 — SERVICIOS                                                   │
│  - API REST en Flask (predicciones, alertas, contexto)               │
│  - Servicios de voz sobre AWS: Polly (TTS), Transcribe (ASR), Lex   │
│  - Notificaciones push y alertas geolocalizadas                      │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ CAPA 5 — VISUALIZACIÓN Y CONSUMO                                     │
│  - Aplicación móvil multiplataforma en Flutter                       │
│  - Dashboards analíticos en Kibana                                   │
│  - Informes ejecutivos en Power BI                                   │
└──────────────────────────────────────────────────────────────────────┘
```

Todo el sistema se despliega como microservicios independientes coordinados mediante Docker Compose, lo que garantiza reproducibilidad y portabilidad entre entornos.

## Fuentes de datos

El proyecto utiliza dos fuentes complementarias, ambas correspondientes a la misma red de sensores (RVVCCA), publicadas en portales distintos según la administración responsable.

### Fuente principal: Portal de Datos Abiertos del Ajuntament de València

- **URL**: https://opendata.vlci.valencia.es/dataset/hourly-air-quality-data-since-2016
- **Plataforma**: VLCi (CKAN)
- **Volumen**: 449 026 registros horarios desde 2016
- **Estaciones**: Avinguda de França, Bulevard Sud, Molí del Sol, Pista de Silla, Politècnic, Vivers, Centre, Conselleria Meteo, Natzaret Meteo, Port de València
- **Variables**: PM1, PM2.5, PM10, NO, NO₂, NOₓ, O₃, SO₂, CO, NH₃, C₆H₆, C₇H₈, C₈H₁₀, además de meteorología (velocidad y dirección del viento, temperatura, humedad, presión, radiación solar, precipitación) y nivel sonoro
- **Licencia**: Creative Commons Attribution (CC-BY)
- **Uso en AirVLC**: dataset íntegro para el entrenamiento del modelo, análisis exploratorio y validación temporal walk-forward

### Fuente secundaria: RVVCCA — Generalitat Valenciana

- **Origen**: Red de Vigilancia y Control de Contaminación Atmosférica gestionada por la Conselleria de Medi Ambient
- **Acceso**: descarga programática de CSV horario
- **Uso en AirVLC**: ingesta horaria en producción para alimentar predicciones en tiempo real, dashboards de Kibana y la aplicación móvil

### Justificación de la arquitectura dual

El Portal de Datos Abiertos del Ajuntament publica el histórico completo y exhaustivo del dataset, pero no se actualiza en tiempo real más allá del año 2021 a través de su API CKAN pública. La RVVCCA de la Generalitat publica el mismo conjunto de sensores con actualización horaria, lo que permite mantener un sistema operativo en producción. Esta arquitectura dual garantiza simultáneamente la trazabilidad del entrenamiento sobre datos municipales y la frescura de las predicciones servidas a la ciudadanía.

La documentación completa del mapeo de campos entre ambas fuentes está disponible en [`docs/data_sources.md`](docs/data_sources.md).

## Resultados del modelo

Se han evaluado tres arquitecturas de aprendizaje profundo sobre el mismo conjunto de datos y particiones temporales. La tabla resume las métricas obtenidas para predicciones a 24 horas vista en las tres variables objetivo:

| Arquitectura | Variable | MAE | RMSE | R² | Parámetros |
|---|---|---|---|---|---|
| **LSTM-Attention-Multi** | PM2.5 | 1.568 | 2.828 | **0.857** | 148 548 |
| **LSTM-Attention-Multi** | NO₂ | 3.865 | 5.914 | **0.840** | 148 548 |
| **LSTM-Attention-Multi** | O₃ | 6.256 | 8.875 | **0.886** | 148 548 |
| CNN-LSTM-Attention-Multi | PM2.5 | 1.666 | 2.911 | 0.849 | 98 372 |
| CNN-LSTM-Attention-Multi | NO₂ | 4.000 | 6.016 | 0.834 | 98 372 |
| CNN-LSTM-Attention-Multi | O₃ | 6.502 | 9.043 | 0.882 | 98 372 |
| Transformer-Encoder-Multi | PM2.5 | 1.800 | 2.981 | 0.841 | 107 331 |
| Transformer-Encoder-Multi | NO₂ | 4.348 | 6.212 | 0.823 | 107 331 |
| Transformer-Encoder-Multi | O₃ | 6.952 | 9.337 | 0.874 | 107 331 |

> Las unidades de MAE y RMSE corresponden a μg/m³ para todas las variables.

**Modelo seleccionado para producción**: la arquitectura **LSTM-Attention-Multi** obtiene los mejores resultados en las tres variables objetivo simultáneamente, con un R² promedio de 0.861 y un coste computacional inferior al del Transformer en términos de tiempo de entrenamiento. La documentación detallada del modelo está disponible en `docs/model_card.md`.

## Tecnologías utilizadas

| Categoría | Tecnologías |
|---|---|
| Lenguajes | Python 3.11, Dart 3.11 (Flutter 3.41.9), SQL, JavaScript |
| Aprendizaje profundo | TensorFlow / Keras, scikit-learn |
| Procesamiento del lenguaje natural | HuggingFace Transformers, AWS Polly, AWS Transcribe, AWS Lex |
| Backend | Flask, REST |
| Bases de datos | PostgreSQL, MongoDB, Elasticsearch, Redis |
| Visualización | Kibana, Power BI, Flutter (frontend) |
| Orquestación | Node-RED, Docker Compose |
| CI/CD | GitHub Actions, pytest, Codecov, ruff, bandit |
| Datos | OpenData VLCi (CKAN), RVVCCA, CSV |

## Estructura del repositorio

```
AirVLC_Proyecto/
├── .github/
│   └── workflows/                  Workflows de integración continua
│       ├── tests.yml               Tests del backend Python
│       ├── flutter-tests.yml       Tests de la aplicación Flutter
│       ├── lint.yml                Análisis de calidad de código
│       └── ingesta_v2.yml          Ingesta horaria automática
├── app/                            Aplicación móvil Flutter
│   ├── lib/                        Código fuente
│   └── test/                       Tests de widget
├── data/                           Datasets (excluidos de git)
│   ├── raw/                        Datos brutos del Ajuntament
│   └── processed/                  Datos preprocesados
├── docker/                         Configuración Docker
│   ├── docker-compose.yml
│   ├── elasticsearch/
│   ├── mongodb/
│   ├── postgres/
│   └── redis/
├── docs/                           Documentación
│   ├── data_sources.md             Mapeo de fuentes de datos
│   ├── model_card.md               Ficha del modelo (próximamente)
│   └── architecture.md             Detalle arquitectónico
├── notebooks/                      Análisis exploratorio
│   ├── 01_eda.ipynb
│   ├── 02_feature_engineering.ipynb
│   └── 03_model_training.ipynb
├── src/                            Código del backend
│   ├── api/                        API REST Flask
│   ├── ingestion/                  Clientes de ingesta
│   ├── ml/                         Pipeline de ML
│   ├── scripts/                    Scripts auxiliares
│   └── services/                   Integraciones AWS
├── tests/                          Tests Python
│   ├── api/
│   ├── ingestion/
│   └── ml/
├── scripts/                        Utilidades
│   └── run_tests.sh                Ejecutor local de tests
├── requirements.txt
├── pytest.ini
├── LICENSE
├── CONTRIBUTING.md
├── CITATION.cff
└── README.md
```

## Instalación y arranque

### Requisitos previos

- Python 3.11
- Docker y Docker Compose
- Flutter 3.41.9 (sólo si se va a compilar la aplicación móvil)
- 8 GB de RAM disponibles para el stack completo

### Pasos

1. Clonar el repositorio:

   ```bash
   git clone https://github.com/miguelzamitabastos/AirVLC_Proyecto.git
   cd AirVLC_Proyecto
   ```

2. Crear entorno virtual e instalar dependencias del backend:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Levantar la infraestructura con Docker Compose:

   ```bash
   docker compose -f docker/docker-compose.yml up -d
   ```

4. Descargar el dataset histórico desde el Portal del Ajuntament y colocarlo en `data/raw/` (ver `CONTRIBUTING.md` para instrucciones detalladas).

5. Iniciar la API de predicción:

   ```bash
   python -m src.api.app
   ```

6. (Opcional) Lanzar la aplicación Flutter:

   ```bash
   cd app
   flutter pub get
   flutter run --dart-define=AIRVLC_BASE_URL=http://localhost:5001
   ```

## Servicios y endpoints

La API REST expone los siguientes endpoints principales:

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Comprobación de estado del servicio |
| GET | `/predict/latest` | Última predicción para todas las estaciones |
| GET | `/predict/{station}` | Predicción 24 h para una estación concreta |
| GET | `/risk/{station}` | Nivel de riesgo categórico (bueno / moderado / malo / peligroso) |
| GET | `/stations` | Listado de estaciones con coordenadas |
| POST | `/chat` | Consulta en lenguaje natural |
| POST | `/voice/transcribe` | Transcripción de audio mediante AWS Transcribe |
| POST | `/voice/synthesize` | Síntesis de voz mediante AWS Polly |

El dashboard Kibana es accesible en `http://localhost:5601` una vez levantada la infraestructura. Los dashboards exportados están disponibles en `kibana/exports/` para su importación en cualquier instancia.

## Pruebas e integración continua

El proyecto incorpora un pipeline completo de integración continua mediante GitHub Actions con cuatro workflows independientes:

- **Tests Python (Backend)**: ejecución de la suite de pytest con cobertura sobre la API, los clientes de ingesta y el pipeline de machine learning.
- **Tests Flutter (App)**: ejecución de tests de widget sobre la aplicación móvil.
- **Lint & Code Quality**: análisis estático con ruff, verificación de seguridad con bandit y revisión de dependencias con safety.
- **Ingesta automática horaria**: cron que actualiza los datos en producción cada hora.

Para ejecutar los tests localmente:

```bash
bash scripts/run_tests.sh
```

Este script reproduce el comportamiento del workflow de CI y genera un informe HTML de cobertura en `htmlcov/index.html`.

## Lenguaje inclusivo y no sexista

Este proyecto se ha redactado siguiendo las recomendaciones de uso de lenguaje inclusivo y no sexista recogidas en la *Guía de uso no sexista del lenguaje* de la Generalitat Valenciana. Se han priorizado fórmulas neutras (la ciudadanía, las personas usuarias, el equipo desarrollador, la administración) y se han evitado los masculinos genéricos cuando ha sido posible, manteniendo siempre la claridad y la legibilidad como criterios principales. La documentación técnica, el código fuente y los textos visibles en la aplicación móvil siguen el mismo criterio.

## Licencia

Este proyecto se distribuye bajo licencia **MIT**. Consultar el archivo [`LICENSE`](LICENSE) para los términos completos. Los datos utilizados conservan la licencia original de sus respectivas fuentes (Creative Commons Attribution para el Portal del Ajuntament de València).

## Cómo citar este proyecto

Si reutilizas este trabajo en investigación, docencia o desarrollos derivados, te agradeceríamos la siguiente cita:

```
Zamit Monsalve, M. (2026). AirVLC: Sistema Inteligente de Monitorización
y Predicción de la Calidad del Aire en València.
https://github.com/miguelzamitabastos/AirVLC_Proyecto
```

El fichero [`CITATION.cff`](CITATION.cff) en la raíz del repositorio proporciona los metadatos necesarios para que GitHub muestre automáticamente la cita.

## Autoría y agradecimientos

**Autor**: Miguel Zamit Monsalve

**Tutor**: Vicent Pavel Tortosa Lorenzo

**Centro**: IES Abastos — Máster en Inteligencia Artificial y Big Data, curso 2025-2026

Agradecimientos a la Red de Vigilancia y Control de Contaminación Atmosférica (RVVCCA), gestionada conjuntamente por el Ajuntament de València y la Conselleria de Medi Ambient de la Generalitat Valenciana, por publicar los datos en abierto y hacer posible este tipo de iniciativas. Agradecimientos también al equipo docente del IES Abastos por la formación recibida durante el máster.

---
