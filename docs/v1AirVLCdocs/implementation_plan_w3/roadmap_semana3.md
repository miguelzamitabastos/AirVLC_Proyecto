# 🚀 Preparación Semana 3: Servicios, Voz y Despliegue

## 1. Contexto de IA para Visualización (Kibana & PowerBI)
Ahora que tenemos modelos y métricas, el objetivo es que el usuario no solo vea "puntos en un mapa", sino que entienda **qué tan bueno es el cerebro** del sistema.

### Ideas para Kibana (Foco en Ingesta y Salud del Modelo)
*   **Gauge de Confianza del Modelo:** Un visualizador que muestre el R² actual del modelo vs. el objetivo (ej: 0.77 vs 0.85).
*   **Mapa de Calor de Errores (MAE por Estación):** Ya que tienes coordenadas, visualiza qué estaciones son más difíciles de predecir. ¿Se equivoca más el modelo en el centro o en el aeropuerto?
*   **Histograma de Residuos en Tiempo Real:** Si logras ingestar las predicciones vs. la realidad en Elasticsearch, puedes ver si el modelo está sesgado (infravalorando o sobrevalorando) "en vivo".
*   **Timeline de Niveles de Riesgo:** Un gráfico de barras apiladas que muestre cuántas horas al día hemos estado en cada nivel (Bueno, Moderado, Malo, Peligroso).

### Ideas para PowerBI (Foco en Análisis de Negocio e Insights)
*   **Análisis de "Driver de Contaminación":** Un gráfico de correlación que muestre qué variable meteorológica (Humedad, Temperatura, Viento) "empuja" más el PM2.5 según los datos del modelo.
*   **Forecast vs. Actual (Drill-down):** Una visualización donde puedas filtrar por estación y ver la línea de predicción del LSTM superpuesta a la real, con el área de error sombreada.
*   **Dashboard de Impacto en Salud:** Basado en el `RiskClassifier`, crear un contador de "Horas de Exposición Peligrosa" acumuladas por zona.

---

## 2. Hoja de Ruta: El "Turbo-Weekend"

### Mañana Sábado (AM): Días 11 y 12 - Consolidación de Servicios
*   **Tarea:** Integrar el `RiskClassifier` y el `EnsemblePredictor` en un servicio central.
*   **Objetivo:** Que una sola función reciba datos crudos y devuelva: `Predicción + Nivel de Riesgo + Alerta de Texto`.
*   **Kibana:** Asegurar que los resultados de la API se están indexando en Elasticsearch para poder visualizarlos.

### Tarde Sábado (PM): Días 13, 14, 15 y 16 - El "Cerebro" de AWS
Como ya tienes los scripts de TTS (Polly) y ASR (Transcribe), el reto es el **NLU (Lex o similar)**:
*   **Configuración de Intenciones (Intents):**
    1.  `GetAirQuality`: "Dime cómo está el aire en Viveros".
    2.  `GetRiskAlert`: "¿Hay algún peligro hoy?".
    3.  `PredictFuture`: "¿Cómo estará la contaminación mañana?".
*   **Pipeline de Voz:** `Voz Usuario (Mic) → Transcribe (Texto) → NLU (Intención) → API Flask (Lógica/IA) → Polly (Respuesta Voz)`.

### Domingo: Día 17 - CI/CD y Robustez
*   **Dockerización:** Crear el `Dockerfile` para la API Flask. Esto es clave para el concurso (portabilidad).
*   **GitHub Actions:** Configurar un test automático que verifique que la API levanta y carga los modelos `.keras` sin errores.

---

## 3. Preparación Técnica (Checklist para Mañana)

1.  **[ ] Datos para PowerBI:** Exportar un CSV con `Real vs Predicción` de tus mejores modelos para empezar a jugar en Windows.
2.  **[ ] Estructura de Mensajes NLU:** Definir qué frases "disparan" qué acciones.
3.  **[ ] API Pública:** Si vas a conectar servicios externos (como AWS) a tu API local, considera usar `ngrok` para exponer el puerto 5001 temporalmente.

---

## 4. Elementos "Wow" para el Jurado
*   **Audio Proactivo:** "Hola Miguel, el modelo detecta un pico de contaminación en 2 horas. Te recomiendo cerrar las ventanas." (Esto une IA + RiskClassifier + Polly).
*   **Dashboard de Incertidumbre:** Mostrar no solo el valor, sino el "rango de error" del modelo.
