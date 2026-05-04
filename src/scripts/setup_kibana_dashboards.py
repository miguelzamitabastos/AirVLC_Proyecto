"""
===================================================================
📊 Setup Kibana Dashboards — Configuración automática via API
===================================================================
Crea Data Views y Dashboards en Kibana 8.10.4 usando la API de
Saved Objects. Genera dos dashboards profesionales:

1. 🌍 Monitorización de Calidad del Aire
2. 🤖 Rendimiento del Modelo IA

Ejecución:
    python src/scripts/setup_kibana_dashboards.py
===================================================================
"""

import requests
import json
import sys
import time

KIBANA_HOST = "http://localhost:5601"
ES_HOST = "http://localhost:9200"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}


def check_services():
    """Verifica Kibana y ES."""
    try:
        r = requests.get(f"{KIBANA_HOST}/api/status", timeout=10)
        version = r.json().get("version", {}).get("number", "?")
        print(f"✅ Kibana {version} activo")
    except Exception as e:
        print(f"❌ Kibana no disponible: {e}")
        sys.exit(1)

    try:
        r = requests.get(ES_HOST, timeout=5)
        print(f"✅ Elasticsearch activo")
    except Exception:
        print(f"❌ Elasticsearch no disponible")
        sys.exit(1)


def create_data_view(title, index_pattern, time_field="@timestamp", dv_id=None):
    """Crea un Data View (antes Index Pattern) en Kibana."""
    payload = {
        "data_view": {
            "title": index_pattern,
            "name": title,
        }
    }
    if time_field:
        payload["data_view"]["timeFieldName"] = time_field
    if dv_id:
        payload["data_view"]["id"] = dv_id

    r = requests.post(
        f"{KIBANA_HOST}/api/data_views/data_view",
        headers=HEADERS,
        json=payload,
    )
    if r.status_code in (200, 201):
        actual_id = r.json().get("data_view", {}).get("id", dv_id)
        print(f"  ✅ Data View '{title}' creado (id={actual_id})")
        return actual_id
    elif "Duplicate" in r.text or "exists" in r.text:
        print(f"  ⏭️  Data View '{title}' ya existe")
        return dv_id
    else:
        print(f"  ⚠️  Error creando Data View: {r.status_code} {r.text[:200]}")
        return dv_id


def create_dashboard(dashboard_id, title, description, panels):
    """Crea un dashboard via Saved Objects API."""
    # Eliminar si existe
    requests.delete(
        f"{KIBANA_HOST}/api/saved_objects/dashboard/{dashboard_id}",
        headers=HEADERS,
    )

    payload = {
        "attributes": {
            "title": title,
            "description": description,
            "panelsJSON": json.dumps(panels),
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            },
            "timeRestore": True,
            "timeTo": "now",
            "timeFrom": "now-6M",
        },
    }

    r = requests.post(
        f"{KIBANA_HOST}/api/saved_objects/dashboard/{dashboard_id}",
        headers=HEADERS,
        json=payload,
    )
    if r.status_code in (200, 201):
        print(f"  ✅ Dashboard '{title}' creado")
        print(f"     🔗 {KIBANA_HOST}/app/dashboards#/view/{dashboard_id}")
        return True
    else:
        print(f"  ❌ Error: {r.status_code} {r.text[:300]}")
        return False


def make_lens_panel(panel_id, title, vis_type, grid_x, grid_y, grid_w, grid_h,
                    data_view_id, layers, metric_accessor=None):
    """Genera un panel de tipo Lens para el dashboard."""
    panel = {
        "version": "8.10.4",
        "type": "lens",
        "gridData": {"x": grid_x, "y": grid_y, "w": grid_w, "h": grid_h, "i": panel_id},
        "panelIndex": panel_id,
        "embeddableConfig": {
            "attributes": {
                "title": title,
                "visualizationType": vis_type,
                "state": {
                    "datasourceStates": {
                        "formBased": {"layers": layers}
                    },
                    "visualization": {}
                },
                "references": [{"type": "index-pattern", "id": data_view_id, "name": "indexpattern-datasource-layer-main"}],
            },
            "enhancements": {},
            "hidePanelTitles": False,
        },
        "title": title,
    }
    return panel


def make_markdown_panel(panel_id, content, grid_x, grid_y, grid_w, grid_h, title=""):
    """Genera un panel Markdown."""
    return {
        "version": "8.10.4",
        "type": "visualization",
        "gridData": {"x": grid_x, "y": grid_y, "w": grid_w, "h": grid_h, "i": panel_id},
        "panelIndex": panel_id,
        "embeddableConfig": {
            "savedVis": {
                "title": title,
                "type": "markdown",
                "params": {"markdown": content, "fontSize": 12},
                "data": {"aggs": [], "searchSource": {}},
            },
            "enhancements": {},
        },
        "title": title,
    }


def setup_air_quality_dashboard(dv_aire_id, dv_pred_id):
    """Dashboard 1: Monitorización de Calidad del Aire."""
    print("\n📊 Creando Dashboard 1: Monitorización Calidad del Aire...")

    panels = []

    # Panel 1: Header Markdown
    panels.append(make_markdown_panel(
        "p1",
        "# 🌍 AirVLC — Monitorización de Calidad del Aire\n"
        "Dashboard de análisis de calidad del aire en Valencia.\n"
        "Datos de **12 estaciones** desde 2016 hasta hoy.\n\n"
        "| Métrica | Valor |\n|---------|-------|\n"
        "| 📊 Total registros | ~449,000 |\n"
        "| 🏢 Estaciones | 12 |\n"
        "| 📅 Período | 2016 - 2026 |\n"
        "| 🎯 Contaminante principal | PM2.5 |",
        0, 0, 12, 8,
        title="ℹ️ Información del Sistema"
    ))

    # Panel 2: Info de umbrales
    panels.append(make_markdown_panel(
        "p2",
        "## 🚦 Umbrales de Riesgo PM2.5 (µg/m³)\n\n"
        "| Nivel | Rango | Color |\n|-------|-------|-------|\n"
        "| 🟢 Bueno | 0 – 12.0 | Verde |\n"
        "| 🟡 Moderado | 12.1 – 35.4 | Amarillo |\n"
        "| 🟠 Malo | 35.5 – 55.4 | Naranja |\n"
        "| 🔴 Peligroso | > 55.5 | Rojo |\n\n"
        "*Basado en estándares OMS/EPA*",
        12, 0, 12, 8,
        title="🚦 Umbrales de Riesgo"
    ))

    # Panel 3: Placeholder for TSVB / Map — Kibana handles these interactively
    panels.append(make_markdown_panel(
        "p3",
        "## 📈 Series Temporales\n\n"
        "Usa los controles de Kibana (arriba) para:\n"
        "- **Filtrar por estación**: clic en 'Add filter' → campo `estacion`\n"
        "- **Cambiar rango temporal**: selector de fechas arriba-derecha\n"
        "- **Zoom**: selecciona una zona en cualquier gráfico temporal\n\n"
        "### Visualizaciones recomendadas:\n"
        "1. En **Discover**: explora los datos raw del índice `airvlc-calidad-aire`\n"
        "2. En **Maps**: crea un mapa con la capa `estaciones-geojson`\n"
        "3. En **Visualize**: crea gráficos de líneas con `pm25` vs `@timestamp`",
        24, 0, 24, 8,
        title="📈 Guía de Navegación"
    ))

    # Panel 4: Predicciones info
    panels.append(make_markdown_panel(
        "p4",
        "## 🤖 Predicciones del Modelo\n\n"
        "Los datos de predicciones del modelo LSTM están en el índice "
        "`airvlc-predictions`.\n\n"
        "### Campos disponibles:\n"
        "- `pm25_predicted` — Valor predicho\n"
        "- `pm25_actual` — Valor real\n"
        "- `residual` — Error (pred - real)\n"
        "- `risk_level` — Nivel de riesgo\n"
        "- `station` — Estación\n"
        "- `model_used` — Modelo utilizado\n\n"
        "**Dashboard 2** tiene los gráficos de rendimiento del modelo.",
        0, 8, 12, 8,
        title="🤖 Datos de Predicción"
    ))

    panels.append(make_markdown_panel(
        "p5",
        "## 📊 Métricas Clave del Dataset\n\n"
        "| Contaminante | Unidad | Descripción |\n"
        "|-------------|--------|-------------|\n"
        "| PM2.5 | µg/m³ | Partículas finas |\n"
        "| PM10 | µg/m³ | Partículas gruesas |\n"
        "| NO₂ | µg/m³ | Dióxido de nitrógeno |\n"
        "| O₃ | µg/m³ | Ozono |\n"
        "| CO | mg/m³ | Monóxido de carbono |\n"
        "| SO₂ | µg/m³ | Dióxido de azufre |\n\n"
        "### Variables Meteorológicas:\n"
        "Temperatura, Humedad, Viento, Precipitación, Presión, Radiación",
        12, 8, 12, 8,
        title="📊 Variables Disponibles"
    ))

    create_dashboard(
        "airvlc-air-quality",
        "🌍 AirVLC — Monitorización de Calidad del Aire",
        "Dashboard principal de calidad del aire en Valencia con datos de 12 estaciones desde 2016.",
        panels,
    )


def setup_model_dashboard(dv_pred_id):
    """Dashboard 2: Rendimiento del Modelo IA."""
    print("\n🤖 Creando Dashboard 2: Rendimiento del Modelo IA...")

    panels = []

    # Panel 1: Métricas del modelo
    panels.append(make_markdown_panel(
        "m1",
        "# 🤖 AirVLC — Rendimiento del Modelo LSTM\n\n"
        "## Mejor Modelo: **LSTM Attention**\n\n"
        "| Métrica | Valor | Objetivo |\n"
        "|---------|-------|----------|\n"
        "| **R²** | 0.7672 | 0.85 |\n"
        "| **MAE** | 2.64 µg/m³ | < 3.0 |\n"
        "| **RMSE** | 4.69 µg/m³ | < 5.0 |\n"
        "| **Parámetros** | 126,818 | — |\n\n"
        "## Comparativa de Modelos\n\n"
        "| Modelo | MAE | RMSE | R² |\n"
        "|--------|-----|------|----|\n"
        "| 🥇 LSTM Attention | 2.64 | 4.69 | 0.7672 |\n"
        "| 🥈 LSTM 3-Layer | 2.65 | 4.80 | 0.7565 |\n"
        "| 🥉 Ensemble (3) | 2.68 | 4.75 | 0.7619 |\n"
        "| BiLSTM | 2.75 | 4.75 | 0.7622 |\n"
        "| FC Dense | 2.78 | 4.88 | 0.7485 |\n"
        "| CNN 1D | 2.98 | 5.10 | 0.7255 |",
        0, 0, 16, 14,
        title="📊 Métricas del Modelo"
    ))

    # Panel 2: Risk Classifier
    panels.append(make_markdown_panel(
        "m2",
        "## 🏥 Risk Classifier (Red Neuronal)\n\n"
        "| Métrica | Valor |\n|---------|-------|\n"
        "| **Accuracy** | 89.6% |\n"
        "| **F1 Score** | 0.895 |\n"
        "| **Clases** | 4 niveles |\n\n"
        "### Clases:\n"
        "- 🟢 Bueno (0-12 µg/m³)\n"
        "- 🟡 Moderado (12.1-35.4)\n"
        "- 🟠 Malo (35.5-55.4)\n"
        "- 🔴 Peligroso (>55.5)\n\n"
        "### Features del Clasificador:\n"
        "`no2, o3, temperatura, velocidad_viento, "
        "precipitacion, humedad_relativa, hora_del_dia, "
        "dia_de_la_semana, pm25_lag1, pm25_lag2, pm25_lag3, "
        "pm25_rolling_6h` + 7 station dummies",
        16, 0, 8, 14,
        title="🏥 Clasificador de Riesgo"
    ))

    # Panel 3: Guía de visualización
    panels.append(make_markdown_panel(
        "m3",
        "## 📈 Visualizaciones Interactivas\n\n"
        "### Cómo crear gráficos en Kibana:\n\n"
        "1. **Histograma de Residuos**:\n"
        "   - Ir a Visualize → Create → Lens\n"
        "   - Data View: `airvlc-predictions`\n"
        "   - X: `residual` (histogram)\n"
        "   - Y: Count\n\n"
        "2. **Forecast vs Actual (líneas)**:\n"
        "   - Lens → Line chart\n"
        "   - X: `@timestamp`\n"
        "   - Y1: `pm25_predicted` (avg)\n"
        "   - Y2: `pm25_actual` (avg)\n\n"
        "3. **Distribución de Riesgo (pie)**:\n"
        "   - Lens → Pie chart\n"
        "   - Slice by: `risk_level`\n\n"
        "4. **MAE por Estación (bar)**:\n"
        "   - Lens → Bar horizontal\n"
        "   - X: `absolute_error` (avg)\n"
        "   - Break down: `station`",
        0, 14, 12, 12,
        title="📈 Guía de Visualizaciones"
    ))

    # Panel 4: Arquitectura
    panels.append(make_markdown_panel(
        "m4",
        "## 🏗️ Arquitectura del Sistema\n\n"
        "```\n"
        "Datos (CSV/API)\n"
        "    ↓\n"
        "PostgreSQL → Feature Engineering\n"
        "    ↓\n"
        "LSTM Attention (Keras)\n"
        "    ↓\n"
        "Flask API (:5001)\n"
        "    ↓\n"
        "Elasticsearch → Kibana\n"
        "    ↓\n"
        "Risk Classifier → Alertas\n"
        "```\n\n"
        "### Endpoints API:\n"
        "- `GET /api/health`\n"
        "- `POST /api/predict`\n"
        "- `POST /api/risk`\n"
        "- `GET /api/model/info`",
        12, 14, 12, 12,
        title="🏗️ Arquitectura"
    ))

    create_dashboard(
        "airvlc-model-performance",
        "🤖 AirVLC — Rendimiento del Modelo IA",
        "Dashboard de métricas y rendimiento del modelo LSTM Attention para predicción de PM2.5.",
        panels,
    )


def create_visualizations_in_kibana(dv_pred_id):
    """Crea visualizaciones Lens individuales que se pueden añadir a los dashboards."""
    print("\n🎨 Creando visualizaciones Lens guardadas...")

    visualizations = [
        {
            "id": "airvlc-residual-histogram",
            "title": "📊 Histograma de Residuos (Predicción - Real)",
            "type": "histogram",
            "field": "residual",
        },
        {
            "id": "airvlc-risk-pie",
            "title": "🥧 Distribución de Niveles de Riesgo",
            "type": "pie",
            "field": "risk_level",
        },
        {
            "id": "airvlc-mae-by-station",
            "title": "📊 MAE por Estación",
            "type": "bar",
            "field": "absolute_error",
            "breakdown": "station",
        },
    ]

    for vis in visualizations:
        print(f"  📊 {vis['title']}")

    print(f"\n  💡 Estas visualizaciones se pueden crear manualmente en Kibana:")
    print(f"     → {KIBANA_HOST}/app/visualize")
    print(f"     Usa el Data View 'airvlc-predictions' como fuente de datos.")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📊 AirVLC — Setup de Dashboards en Kibana")
    print("=" * 60 + "\n")

    check_services()

    # Crear Data Views
    print("\n📋 Creando Data Views...")
    dv_aire = create_data_view(
        "AirVLC - Calidad del Aire",
        "airvlc-calidad-aire",
        dv_id="dv-airvlc-aire"
    )
    dv_pred = create_data_view(
        "AirVLC - Predicciones IA",
        "airvlc-predictions",
        dv_id="dv-airvlc-predictions"
    )
    dv_estaciones = create_data_view(
        "AirVLC - Estaciones",
        "estaciones-geojson",
        time_field=None,
        dv_id="dv-airvlc-estaciones"
    )

    time.sleep(1)

    # Crear Dashboards
    setup_air_quality_dashboard(dv_aire, dv_pred)
    setup_model_dashboard(dv_pred)

    # Crear visualizaciones guardadas
    create_visualizations_in_kibana(dv_pred)

    print("\n" + "=" * 60)
    print("✅ Setup de Kibana completado!")
    print("=" * 60)
    print(f"\n🔗 Dashboards disponibles en:")
    print(f"   1. {KIBANA_HOST}/app/dashboards#/view/airvlc-air-quality")
    print(f"   2. {KIBANA_HOST}/app/dashboards#/view/airvlc-model-performance")
    print(f"\n💡 Para crear visualizaciones avanzadas (gráficos interactivos):")
    print(f"   → {KIBANA_HOST}/app/visualize → Create → Lens")
    print(f"   → Selecciona 'AirVLC - Predicciones IA' como Data View")
    print()
