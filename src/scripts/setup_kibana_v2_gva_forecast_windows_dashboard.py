"""
===================================================================
📊 AirVLC — Kibana: GVA observado vs predicciones por ventana (0/24/48/72 h)
===================================================================
Crea un dashboard orientado al mismo modelo mental que la app Flutter
(`/api/v2/timeseries`: observado Mongo/GVA + horizontes del modelo):

  - Mapas de calor: estación × horizonte (µg/m³) para PM2.5, NO₂ y O₃
    sobre documentos `forecast` indexados por `predict_horizons`.
  - Series temporales: real (ground truth, `prediction_type: actual`,
    `horizon_hours: -1`) y predicción media por horizonte (+0/+24/+48/+72).
  - Tabla resumen: media por estación y horizonte (últimos datos indexados).

Requisitos:
  - Elasticsearch + Kibana 8.10.x (p. ej. `docker compose up -d`).
  - Índice `airvlc-predictions-v2` con datos (tras Node-RED o POST
    `POST /api/v2/_internal/predict_horizons` con token interno).

Variables opcionales:
  KIBANA_URL (default http://localhost:5601)
  ES_HOST    (default http://localhost:9200)

Uso:
  venv/bin/python src/scripts/setup_kibana_v2_gva_forecast_windows_dashboard.py
===================================================================
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests

KIBANA = os.environ.get("KIBANA_URL", "http://localhost:5601").rstrip("/")
ES = os.environ.get("ES_HOST", "http://localhost:9200").rstrip("/")
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-predictions-v2*"
DV_ID = "dv-airvlc-predictions-v2"
DV_TITLE = "AirVLC — Predictions v2 (multitarget)"
TIME_FIELD = "@timestamp"

DASHBOARD_ID = "airvlc-v2-gva-forecast-windows"

# Filtro alineado con la ingesta v2 (`routes_v2.internal_predict_horizons`)
KQ_FORECAST = (
    'source.keyword: "api_predict_horizons" and prediction_type.keyword: "forecast"'
)


def check_services() -> None:
    try:
        r = requests.get(f"{KIBANA}/api/status", timeout=10)
        v = r.json().get("version", {}).get("number", "?")
        print(f"✅ Kibana {v}")
    except Exception as e:
        sys.exit(f"❌ Kibana no disponible en {KIBANA}: {e}")

    try:
        requests.get(f"{ES}/_cluster/health", timeout=5).raise_for_status()
        print(f"✅ Elasticsearch ({ES})")
    except Exception as e:
        sys.exit(f"❌ Elasticsearch no disponible: {e}")


def create_data_view() -> str:
    payload = {
        "data_view": {
            "id": DV_ID,
            "title": INDEX,
            "name": DV_TITLE,
            "timeFieldName": TIME_FIELD,
        }
    }
    r = requests.post(f"{KIBANA}/api/data_views/data_view", headers=H, json=payload, timeout=20)
    if r.status_code in (200, 201):
        print(f"✅ Data View '{DV_TITLE}' creado")
    elif "Duplicate" in r.text or "already exists" in r.text.lower():
        print(f"⏭  Data View '{DV_TITLE}' ya existe")
    else:
        sys.exit(f"❌ Error creando Data View: {r.status_code} {r.text[:400]}")
    return DV_ID


def upsert_saved_object(obj_type: str, obj_id: str, attributes: dict, references: list[dict]) -> None:
    body = {"attributes": attributes, "references": references}
    r = requests.post(
        f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true",
        headers=H,
        json=body,
        timeout=30,
    )
    if r.status_code not in (200, 201):
        sys.exit(f"❌ Error creando {obj_type}/{obj_id}: {r.status_code} {r.text[:800]}")


def _ref_data_view(dv_id: str, layer_name: str = "layer1") -> list[dict]:
    return [{"id": dv_id, "name": f"indexpattern-datasource-layer-{layer_name}", "type": "index-pattern"}]


def _col_terms(field: str, label: str | None = None, size: int = 25) -> dict:
    return {
        "label": label or field,
        "dataType": "string",
        "operationType": "terms",
        "scale": "ordinal",
        "sourceField": field,
        "isBucketed": True,
        "params": {
            "size": size,
            "orderBy": {"type": "alphabetical", "fallback": True},
            "orderDirection": "asc",
            "otherBucket": False,
            "missingBucket": False,
            "parentFormat": {"id": "terms"},
        },
    }


def _col_terms_number(field: str, label: str | None = None, size: int = 10) -> dict:
    """Terms sobre campo numérico (p. ej. horizon_hours: 0, 24, 48, 72)."""
    return {
        "label": label or field,
        "dataType": "number",
        "operationType": "terms",
        "scale": "ordinal",
        "sourceField": field,
        "isBucketed": True,
        "params": {
            "size": size,
            "orderBy": {"type": "alphabetical", "fallback": True},
            "orderDirection": "asc",
            "otherBucket": False,
            "missingBucket": False,
            "parentFormat": {"id": "terms"},
        },
    }


def _col_date_histogram(field: str = "@timestamp", label: str = "Tiempo") -> dict:
    return {
        "label": label,
        "dataType": "date",
        "operationType": "date_histogram",
        "scale": "interval",
        "sourceField": field,
        "isBucketed": True,
        "params": {
            "interval": "auto",
            "includeEmptyRows": True,
            "dropPartials": False,
        },
    }


def _col_metric(field: str, op: str, label: str, decimals: int = 2) -> dict:
    return {
        "label": label,
        "dataType": "number",
        "operationType": op,
        "scale": "ratio",
        "sourceField": field,
        "isBucketed": False,
        "params": {"format": {"id": "number", "params": {"decimals": decimals}}},
    }


def _col_filters(label: str, filters: list[dict[str, Any]]) -> dict:
    return {
        "label": label,
        "dataType": "string",
        "operationType": "filters",
        "scale": "ordinal",
        "isBucketed": True,
        "params": {
            "filters": [
                {
                    "input": {"query": f["query"], "language": "kuery"},
                    "label": f["label"],
                }
                for f in filters
            ]
        },
    }


def lens_line_filters(
    title: str,
    y_field: str,
    series_filters: list[dict[str, str]],
    y_label: str,
    y_decimals: int = 2,
    y_op: str = "average",
) -> dict:
    layer_id = "layer1"
    x_id, y_id, s_id = "x_time", "y_metric", "series_filters"

    layers_state = {
        layer_id: {
            "columnOrder": [x_id, s_id, y_id],
            "columns": {
                x_id: _col_date_histogram("@timestamp", "Tiempo (@timestamp = instante objetivo)"),
                s_id: _col_filters("Serie", series_filters),
                y_id: _col_metric(y_field, y_op, y_label, decimals=y_decimals),
            },
            "incompleteColumns": {},
        }
    }

    vis_layer: dict[str, Any] = {
        "layerId": layer_id,
        "layerType": "data",
        "seriesType": "line",
        "xAccessor": x_id,
        "accessors": [y_id],
        "splitAccessor": s_id,
        "showGridlines": False,
        "yConfig": [{"forAccessor": y_id, "axisMode": "left"}],
    }

    state = {
        "datasourceStates": {"formBased": {"layers": layers_state}},
        "visualization": {
            "legend": {"isVisible": True, "position": "right"},
            "valueLabels": "hide",
            "fittingFunction": "None",
            "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": ""},
        "filters": [],
    }

    return {"title": title, "visualizationType": "lnsXY", "state": state}


def lens_heatmap_station_horizon(title: str, value_field: str, kuery: str) -> dict:
    """Estación (Y) × horizonte en horas (X), color = media del contaminante predicho."""
    layer_id = "layer1"
    x_id, y_id, m_id = "x_horizon", "y_station", "m_avg"
    layers = {
        layer_id: {
            "columnOrder": [x_id, y_id, m_id],
            "columns": {
                x_id: _col_terms_number("horizon_hours", "Horizonte (h)", size=8),
                y_id: _col_terms("station.keyword", "Estación", size=20),
                m_id: _col_metric(value_field, "average", "µg/m³ (media)", decimals=2),
            },
            "incompleteColumns": {},
        }
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {
            "layerId": layer_id,
            "layerType": "data",
            "shape": "heatmap",
            "xAccessor": x_id,
            "yAccessor": y_id,
            "valueAccessor": m_id,
            "legend": {"isVisible": True, "position": "right", "type": "heatmap_legend"},
            "gridConfig": {
                "type": "heatmap_grid",
                "isCellLabelVisible": True,
                "isYAxisLabelVisible": True,
                "isXAxisLabelVisible": True,
                "isYAxisTitleVisible": False,
                "isXAxisTitleVisible": False,
            },
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsHeatmap", "state": state}


def lens_table_forecast_snapshot(title: str, kuery: str) -> dict:
    """Tabla: estación, horizonte, medias de predicción multitarget."""
    layer_id = "layer1"
    c_st, c_h, c_pm, c_no2, c_o3 = "t1", "t2", "m1", "m2", "m3"
    cols = {
        c_st: _col_terms("station.keyword", "Estación", size=25),
        c_h: _col_terms_number("horizon_hours", "Horizonte (h)", size=8),
        c_pm: _col_metric("pm25_pred", "average", "PM2.5 pred (avg)", decimals=2),
        c_no2: _col_metric("no2_pred", "average", "NO₂ pred (avg)", decimals=2),
        c_o3: _col_metric("o3_pred", "average", "O₃ pred (avg)", decimals=2),
    }
    order = [c_st, c_h, c_pm, c_no2, c_o3]
    layers = {layer_id: {"columnOrder": order, "columns": cols, "incompleteColumns": {}}}
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {
            "layerId": layer_id,
            "columns": [{"columnId": cid, "alignment": "left"} for cid in order],
            "layerType": "data",
            "headerRowHeight": "auto",
            "rowHeight": "single",
            "rowHeightLines": 1,
            "headerRowHeightLines": 1,
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsDatatable", "state": state}


def _lens_saved_object(lens_attrs: dict, dv_id: str, layer_name: str = "layer1") -> tuple[dict, list[dict]]:
    attributes = {
        "title": lens_attrs["title"],
        "visualizationType": lens_attrs["visualizationType"],
        "state": lens_attrs["state"],
    }
    references = _ref_data_view(dv_id, layer_name)
    return attributes, references


def _panel_lens(panel_idx: str, so_id: str, x: int, y: int, w: int, h: int, title: str) -> dict:
    return {
        "type": "lens",
        "panelIndex": panel_idx,
        "panelRefName": f"panel_{panel_idx}",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_idx},
        "embeddableConfig": {"hidePanelTitles": False, "enhancements": {}},
        "title": title,
        "version": "8.10.4",
    }


def main() -> None:
    print("\n" + "=" * 72)
    print("📊 AirVLC — Dashboard Kibana: GVA + ventanas 0/24/48/72 h (v2)")
    print("=" * 72 + "\n")

    check_services()
    dv_id = create_data_view()

    pm25_filters = [
        {"label": "Actual (GVA)", "query": 'prediction_type.keyword:"actual" and horizon_hours:-1'},
        {"label": "+0h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:0'},
        {"label": "+24h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:24'},
        {"label": "+48h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:48'},
        {"label": "+72h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:72'},
    ]
    forecast_only = pm25_filters[1:]

    lens_specs: list[tuple[str, dict]] = [
        ("win-hmap-pm25", lens_heatmap_station_horizon(
            "PM2.5 predicho — estación × horizonte", "pm25_pred", KQ_FORECAST)),
        ("win-hmap-no2", lens_heatmap_station_horizon(
            "NO₂ predicho — estación × horizonte", "no2_pred", KQ_FORECAST)),
        ("win-hmap-o3", lens_heatmap_station_horizon(
            "O₃ predicho — estación × horizonte", "o3_pred", KQ_FORECAST)),
        ("win-pm25-actual", lens_line_filters(
            "PM2.5 — observado GVA (Mongo)",
            y_field="pm25_actual",
            series_filters=[pm25_filters[0]],
            y_label="PM2.5 real (µg/m³) · avg",
        )),
        ("win-pm25-forecast", lens_line_filters(
            "PM2.5 — modelo por ventana (+0/+24/+48/+72 h)",
            y_field="pm25_pred",
            series_filters=forecast_only,
            y_label="PM2.5 pred (µg/m³) · avg",
        )),
        ("win-no2-actual", lens_line_filters(
            "NO₂ — observado GVA (Mongo)",
            y_field="no2_actual",
            series_filters=[pm25_filters[0]],
            y_label="NO₂ real (µg/m³) · avg",
        )),
        ("win-no2-forecast", lens_line_filters(
            "NO₂ — modelo por ventana (+0/+24/+48/+72 h)",
            y_field="no2_pred",
            series_filters=forecast_only,
            y_label="NO₂ pred (µg/m³) · avg",
        )),
        ("win-o3-actual", lens_line_filters(
            "O₃ — observado GVA (Mongo)",
            y_field="o3_actual",
            series_filters=[pm25_filters[0]],
            y_label="O₃ real (µg/m³) · avg",
        )),
        ("win-o3-forecast", lens_line_filters(
            "O₃ — modelo por ventana (+0/+24/+48/+72 h)",
            y_field="o3_pred",
            series_filters=forecast_only,
            y_label="O₃ pred (µg/m³) · avg",
        )),
        ("win-table", lens_table_forecast_snapshot(
            "Predicciones medias por estación y horizonte (ingesta predict_horizons)",
            KQ_FORECAST,
        )),
    ]

    print("\n🧩 Creando visualizaciones Lens...")
    full_ids: list[tuple[str, str]] = []
    for short_id, lens_def in lens_specs:
        full_id = f"airvlc-v2-{short_id}"
        attrs, refs = _lens_saved_object(lens_def, dv_id)
        upsert_saved_object("lens", full_id, attrs, refs)
        full_ids.append((full_id, short_id))
        print(f"  ✅ {full_id}")

    layout: list[tuple[str, str, int, int, int, int, str]] = [
        ("r1c1", "airvlc-v2-win-hmap-pm25", 0, 0, 16, 14, "Mapa: PM2.5 × horizonte"),
        ("r1c2", "airvlc-v2-win-hmap-no2", 16, 0, 16, 14, "Mapa: NO₂ × horizonte"),
        ("r1c3", "airvlc-v2-win-hmap-o3", 32, 0, 16, 14, "Mapa: O₃ × horizonte"),
        ("r2a", "airvlc-v2-win-pm25-actual", 0, 14, 24, 14, "PM2.5 observado"),
        ("r2b", "airvlc-v2-win-pm25-forecast", 24, 14, 24, 14, "PM2.5 predicho por ventana"),
        ("r3a", "airvlc-v2-win-no2-actual", 0, 28, 24, 14, "NO₂ observado"),
        ("r3b", "airvlc-v2-win-no2-forecast", 24, 28, 24, 14, "NO₂ predicho por ventana"),
        ("r4a", "airvlc-v2-win-o3-actual", 0, 42, 24, 14, "O₃ observado"),
        ("r4b", "airvlc-v2-win-o3-forecast", 24, 42, 24, 14, "O₃ predicho por ventana"),
        ("r5", "airvlc-v2-win-table", 0, 56, 48, 12, "Tabla resumen forecast"),
    ]

    panels = []
    references: list[dict] = []
    for panel_idx, so_id, x, y, w, h, title in layout:
        panels.append(_panel_lens(panel_idx, so_id, x, y, w, h, title))
        references.append({"type": "lens", "id": so_id, "name": f"panel_{panel_idx}"})

    dashboard_attrs = {
        "title": "AirVLC — GVA vs predicciones por ventana (0/24/48/72 h)",
        "description": (
            "Observaciones en vivo desde Mongo (fuente GVA) frente a predicciones "
            "multitarget por horizonte, alineadas con la app Flutter. Filtra por "
            "estación con el control de filtros de Kibana (campo station.keyword). "
            "Los datos forecast provienen de la ingesta `api_predict_horizons`."
        ),
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        },
    }

    print("\n📌 Creando dashboard...")
    upsert_saved_object("dashboard", DASHBOARD_ID, dashboard_attrs, references)

    print("\n" + "-" * 72)
    print("Hecho. En Kibana:")
    print(f"  • Ajusta el rango temporal (arriba) para cubrir cuando se indexaron datos.")
    print(f"  • Si no ves forecast: ejecuta la ingesta interna o Node-RED que llama a")
    print(f"    POST /api/v2/_internal/predict_horizons (índice airvlc-predictions-v2).")
    print(f"\n🔗 {KIBANA}/app/dashboards#/view/{DASHBOARD_ID}\n")


if __name__ == "__main__":
    main()
