# Contenido para el Anteproyecto 8IA — Copiar en la plantilla .docx

> ⚠️ Este archivo contiene el texto que debes copiar en cada sección de la plantilla `anteproyecto 8IA.docx`. Copia cada sección en su apartado correspondiente.

---

## TITULACIÓN
Máster de FP en Inteligencia Artificial y Big Data.

## CURSO
2025/2026

## Nombre y apellidos / Rol
*(Rellena con tus datos)*

| Nombre y Apellidos | Rol |
|---------------------|-----|
| *(tu nombre)* | Desarrollador único — Análisis de datos, IA, infraestructura, documentación |

## Tutor responsable
*(Rellena con el nombre del tutor)*

---

## 1. Título del Proyecto

**AirVLC — Sistema Inteligente de Monitorización y Predicción de la Calidad del Aire en València**

---

## 2. Objetivos

El objetivo principal del proyecto es desarrollar una plataforma integral de análisis, predicción y alerta sobre la calidad del aire en la ciudad de València, utilizando datos abiertos del portal OpenData del Ayuntamiento de València.

Los objetivos específicos son:

1. **Ingestar y almacenar** datos históricos de calidad del aire de València (2016–actualidad) desde el portal OpenData, enriqueciéndolos con datos meteorológicos obtenidos mediante web scraping de fuentes externas (OpenWeather / AEMET).

2. **Analizar y visualizar** los patrones de contaminación atmosférica por estación de medida, franja horaria, día de la semana y estación del año, mediante dashboards interactivos en Kibana y Power BI.

3. **Entrenar modelos predictivos** de inteligencia artificial (LSTM y CNN 1D) capaces de predecir los niveles de contaminantes clave (PM2.5, NO₂) con un horizonte de 24 a 48 horas.

4. **Detectar anomalías y clasificar niveles de riesgo** utilizando modelos preentrenados de HuggingFace (Transformers) para generar alertas en lenguaje natural.

5. **Implementar un asistente vocal** que permita consultar el estado actual y las predicciones de calidad del aire mediante servicios de NLP, TTS (AWS Polly) y ASR (AWS Transcribe).

6. **Desplegar** todo el sistema como microservicios orquestados con Docker Compose, con integración continua y despliegue continuo (CI/CD) mediante GitHub Actions.

---

## 3. Propuesta de índice o estructura del Proyecto

1. Identificación y objetivos del proyecto
   1.1. Motivación y contexto (Smart Cities, salud pública)
   1.2. Objetivos generales y específicos
   1.3. Alcance del proyecto

2. Diseño del proyecto
   2.1. Arquitectura del sistema (diagrama de capas)
   2.2. Tecnologías utilizadas (por módulo formativo)
   2.3. Fuentes de datos
   2.4. Flujo de trabajo y procesamiento de datos

3. Desarrollo del proyecto
   3.1. Ingesta de datos (Logstash + Node-RED + Web Scraping)
   3.2. Almacenamiento (PostgreSQL + MongoDB + Elasticsearch + Redis)
   3.3. Análisis exploratorio de datos (EDA)
   3.4. Preprocesado y Feature Engineering
   3.5. Modelos de Inteligencia Artificial
      3.5.1. LSTM — Predicción de series temporales
      3.5.2. CNN 1D — Detección de patrones de contaminación
      3.5.3. Transformers (HuggingFace) — Clasificación de alertas
   3.6. Servicios NLP / NLU / TTS / ASR (AWS)
   3.7. API REST con Flask y despliegue (Docker + CI/CD)
   3.8. Visualización (Kibana Dashboards + Power BI)

4. Evaluación y resultados
   4.1. Métricas de rendimiento de los modelos (MAE, RMSE, R²)
   4.2. Comparativa de modelos (Fully Connected vs LSTM vs CNN)
   4.3. Resultados de los dashboards y valor analítico

5. Conclusiones y trabajo futuro

6. Referencias

Anexos
   A. Configuración Docker (docker-compose.yml, Dockerfiles)
   B. Configuración ELK (elasticsearch.yml, kibana.yml, logstash.conf)
   C. Flujos Node-RED (flows.json)
   D. Capturas de pantalla de Dashboards (Kibana + Power BI)
   E. Notebooks Jupyter (EDA + entrenamiento de modelos)

---

## 4. Fuentes de datos

| Fuente | Descripción | URL |
|--------|-------------|-----|
| **Calidad del aire (principal)** | Datos horarios de 10 estaciones de la Red de Vigilancia Atmosférica de València desde 2016. Incluye 22 parámetros: PM1, PM2.5, PM10, NO, NO₂, NOx, O₃, SO₂, CO, NH₃, tolueno, benceno, xileno, ruido, velocidad/dirección del viento, temperatura, humedad, presión, radiación solar, precipitación. Formato CSV. | https://opendata.vlci.valencia.es/dataset/hourly-air-quality-data-since-2016 |
| **Estaciones de contaminación** | Ubicación geográfica (coordenadas) de las estaciones de monitorización atmosférica. Formatos JSON, GeoJSON, KMZ. | https://opendata.vlci.valencia.es/dataset/estacions-contaminacio-atmosferiques-estaciones-contaminacion-atmosfericas |
| **Sensor de ruido (Russafa)** | Datos diarios del sensor de ruido ubicado en el barrio de Russafa. Para correlación ruido-contaminación. Formato CSV. | https://opendata.vlci.valencia.es/dataset/t251234-daily |
| **Emisiones GEI València** | Datos de emisiones de gases de efecto invernadero de la ciudad, desagregados por sectores. Para contexto macro. Formato CSV. | https://opendata.vlci.valencia.es/dataset/gei-emissions-data-in-valencia |
| **Datos meteorológicos (externo)** | Datos meteorológicos históricos y en tiempo real de València, obtenidos mediante web scraping / API. Para enriquecer las predicciones. | https://openweathermap.org/api o https://opendata.aemet.es/ |

---

## 5. Calendario de trabajo hasta la entrega final / Hitos

| Semana | Fechas | Hito | Descripción |
|--------|--------|------|-------------|
| **Semana 1** | 27 abril — 3 mayo | **Infraestructura + Datos** | Configurar repositorio GitHub, Docker Compose (PostgreSQL + MongoDB + ELK + Redis), descargar y cargar dataset principal, configurar Logstash pipeline, web scraping datos meteorológicos, Node-RED flujo de ingesta. |
| **Semana 2** | 4 mayo — 10 mayo | **Inteligencia Artificial** | Preprocesado y feature engineering, entrenamiento de modelos (LSTM, CNN 1D, Transformers HuggingFace), evaluación de métricas, comparativa de modelos, API Flask con endpoints de predicción. |
| **Semana 3** | 11 mayo — 17 mayo | **Servicios + Visualización** | Dashboards Kibana y Power BI, generación de boletines NLP, integración TTS/ASR con AWS, NLU para consultas de usuario, GitHub Actions CI/CD pipeline. |
| **Semana 4** | 18 mayo — 25 mayo | **Documentación + Entrega** | Redacción de la memoria (≤30 páginas), revisión ortográfica y de formato, preparación de presentación (10 minutos), empaquetado de código y configuraciones. |
| **Entrega** | **Lunes 25 mayo** | **📤 Entrega memoria** | Envío de memoria impresa + archivos digitales al tutor. |
| **Presentación** | **Jueves 28 mayo** | **🎤 Exposición** | Presentación oral de 10 minutos + turno de preguntas de 5 minutos. |

---

## Fecha
23 de abril de 2026
