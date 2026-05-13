# Plan de Implementación Fase 2: AirVLC v2.0

Basado en nuestro debate, esta es la hoja de ruta definitiva para evolucionar el proyecto hacia su segunda versión. Hemos tomado decisiones estratégicas y realistas para maximizar el impacto (nota del proyecto) minimizando la fricción técnica (configuraciones de GPU/entornos).

## 1. Decisiones Arquitectónicas Acordadas

1.  **Predicción Multivariante (NO2, O3, PM2.5)**: 
    *   **Por qué**: Diferencia un proyecto académico básico de un sistema Smart City real. El Índice de Calidad del Aire (ICA) oficial se calcula cogiendo el *peor* valor de estos tres.
    *   **Impacto**: El modelo tendrá 3 salidas. Si el PM2.5 está bajo pero el O3 se dispara por el calor, el sistema alertará del riesgo correctamente.
2.  **Modelo (Keras/TensorFlow Nativo)**:
    *   **Por qué**: Configurar PyTorch y TFT en Colab sin experiencia previa puede consumir semanas de debuggeo. 
    *   **Alternativa Pro**: Nos quedamos en Keras, pero subimos el nivel. Crearemos una arquitectura **CNN-LSTM con Mecanismo de Atención** o un **Transformer Encoder nativo en Keras**. Esto es más que suficiente para demostrar vanguardia tecnológica.
3.  **Estrategia de Datos (Trabajar con lo que hay)**:
    *   **Por qué**: Tienes pocas estaciones meteorológicas (Viveros y Aeropuerto), pero cubren la climatología general de Valencia ciudad. Buscar datos de tráfico ahora mismo podría bloquearnos.
    *   **Solución**: Exprimiremos los datos actuales con **Feature Engineering Extremo**. Crearemos variables que el modelo no tenía antes: medias móviles (rolling means), retardos (lags de hace 24h), y marcas de calendario (fin de semana, mes). Esto por sí solo mejora el modelo drásticamente.

---

## 2. Hoja de Ruta de Desarrollo (Sprints)

Aquí tienes el flujo técnico ordenado cronológicamente que ejecutaremos para esta Fase 2.

### Sprint 1: Ingeniería de Datos 2.0 (ETL y Feature Engineering)
El objetivo es crear un nuevo CSV maestro que el modelo pueda devorar.
*   **Añadir Targets**: Modificar la consulta a PostgreSQL para extraer no solo `pm25`, sino `no2` y `o3`.
*   **Feature Engineering Temporal**: Añadir columnas como `pm25_lag24` (valor de ayer a esta hora), `no2_rolling_mean_6h` (media de las últimas 6 horas).
*   **Feature Engineering Cíclico**: Añadir variables booleanas `is_weekend`, y codificación trigonométrica (seno/coseno) para el mes y la hora.
*   **Interpolación Meteorológica**: Cruce de las estaciones de calidad del aire con la estación meteo de Viveros (y Aeropuerto como backup).

### Sprint 2: Modelado en Google Colab
*   **Arquitectura Multi-Target**: Modificar la última capa Densas del modelo para que tenga 3 neuronas de salida en lugar de 1 (predice los 3 contaminantes a la vez).
*   **Manejo de Desbalanceo (Opcional)**: Añadir una función de pérdida (Loss) asimétrica que penalice más a la red si predice que "no hay contaminación" cuando en realidad hay un pico.
*   **Generación de Artefactos**: Exportar el modelo `.keras` y el nuevo `MinMaxScaler` (que ahora tendrá más columnas).

### Sprint 3: Backend Flask v2
*   **Actualizar Extractor**: Modificar `FeatureExtractor` para que genere la matriz de entrada con todas las nuevas columnas de lags y rolling means.
*   **Cálculo de Riesgo Real**: Actualizar `RiskClassifier` para que calcule el riesgo de PM2.5, el de NO2 y el de O3, y devuelva el **peor** de los tres (estándar ICA).
*   **Actualizar Orquestador NLU**: El chatbot ahora responderá algo como: *"El índice de calidad es MALO debido a los altos niveles de NO2 (45 µg/m³), aunque el PM2.5 está normal."*

### Sprint 4: Evolución de la App (Flutter)
*   **UI Multicontaminante**: Mostrar 3 tarjetas o barras circulares en la app con los niveles de cada gas.
*   **Mensajes de Voz**: Adaptar el motor de Text-To-Speech para que lea el desglose de los contaminantes de forma natural.

---

## ⚠️ Próximo Paso (Luz Verde)
Si estás de acuerdo con este plan, **aprueba el documento**. En cuanto lo hagas, crearé la lista de tareas detallada (`task.md`) y empezaré a picar el código del **Sprint 1**, concretamente actualizando tu script de preparación de datos (`prepare_colab_dataset.py`) para incluir el NO2, el O3 y las nuevas técnicas de Feature Engineering.
