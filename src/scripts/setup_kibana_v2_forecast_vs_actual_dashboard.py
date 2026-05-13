"""
===================================================================
📈 AirVLC — Kibana Dashboard: Forecast vs Actual (v2)
===================================================================
Crea en Kibana (8.10.4) un dashboard con visualizaciones Lens de
líneas para comparar:
  - PM2.5 real (h=-1, prediction_type=actual) vs predicciones
    (h=0/24/48/72, prediction_type=forecast)

Y también incluye paneles de predicción por horizonte para NO₂ y O₃
(en el índice actual no hay campos no2_actual/o3_actual indexados,
así que la serie "Actual" solo se crea para PM2.5).

Uso:
  venv/bin/python src/scripts/setup_kibana_v2_forecast_vs_actual_dashboard.py
===================================================================
"""

from __future__ import annotations

import json
import sys
from typing import Any

import requests

KIBANA = "http://localhost:5601"
ES = "http://localhost:9200"
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-predictions-v2*"
DV_ID = "dv-airvlc-predictions-v2"
DV_TITLE = "AirVLC — Predictions v2 (multitarget)"
TIME_FIELD = "@timestamp"

DASHBOARD_ID = "airvlc-v2-forecast-vs-actual"


def check_services() -> None:
    try:
        r = requests.get(f"{KIBANA}/api/status", timeout=10)
        v = r.json().get("version", {}).get("number", "?")
        print(f"✅ Kibana {v}")
    except Exception as e:
        sys.exit(f"❌ Kibana no disponible: {e}")

    try:
        requests.get(f"{ES}/_cluster/health", timeout=5).raise_for_status()
        print("✅ Elasticsearch")
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


def _ref_data_view(dv_id: str, layer_name: str) -> list[dict]:
    return [{"id": dv_id, "name": f"indexpattern-datasource-layer-{layer_name}", "type": "index-pattern"}]


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
    """Split series by KQL filters."""
    # Kibana Lens expects `operationType: filters` with a `params.filters` list.
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
                x_id: _col_date_histogram("@timestamp", "Tiempo"),
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


def _lens_saved_object(lens_attrs: dict, dv_id: str, layer_name: str = "layer1") -> tuple[dict, list[dict]]:
    attributes = {
        "title": lens_attrs["title"],
        "visualizationType": lens_attrs["visualizationType"],
        "state": lens_attrs["state"],
    }
    references = _ref_data_view(dv_id, layer_name)
    return attributes, references


def _dashboard_panel(lens_id: str, title: str, x: int, y: int, w: int, h: int) -> dict:
    embeddable = {
        "id": lens_id,
        "type": "lens",
        "input": {
            "id": lens_id,
            "title": title,
            "savedObjectId": lens_id,
            "viewMode": "view",
        },
    }
    return {
        "type": "lens",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": lens_id},
        "panelIndex": lens_id,
        "embeddableConfig": embeddable["input"],
        "version": "8.10.4",
        "title": title,
        "explicitInput": embeddable["input"],
    }


def main() -> None:
    print("\n" + "=" * 70)
    print("📈 AirVLC — Setup Kibana Dashboard: Forecast vs Actual (v2)")
    print("=" * 70 + "\n")

    check_services()
    dv_id = create_data_view()

    # --- Lens visualizations ---
    # PM2.5: Actual vs Forecast (0/24/48/72)
    pm25_filters = [
        {"label": "Actual", "query": 'prediction_type.keyword:"actual" and horizon_hours:-1'},
        {"label": "+0h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:0'},
        {"label": "+24h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:24'},
        {"label": "+48h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:48'},
        {"label": "+72h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:72'},
    ]
    pm25_lens = lens_line_filters(
        "PM2.5 — Real vs Predicción (+0/+24/+48/+72)",
        y_field="pm25_actual",
        series_filters=pm25_filters,
        y_label="PM2.5 (µg/m³) · avg",
        y_decimals=2,
        y_op="average",
    )
    # Nota: para las series forecast usamos el mismo y_field, pero en docs forecast
    # pm25_actual no existe. En Lens, el split por filtros creará series vacías
    # para forecast si no hay pm25_actual. Por eso duplicamos con segundo panel
    # usando pm25_pred para forecast (más robusto).

    pm25_forecast_only = lens_line_filters(
        "PM2.5 — Predicción por horizonte (+0/+24/+48/+72)",
        y_field="pm25_pred",
        series_filters=pm25_filters[1:],  # solo forecasts
        y_label="PM2.5 pred (µg/m³) · avg",
        y_decimals=2,
        y_op="average",
    )

    # PM2.5 actual only (para ver la verdad terreno limpia)
    pm25_actual_only = lens_line_filters(
        "PM2.5 — Real (ground truth)",
        y_field="pm25_actual",
        series_filters=[pm25_filters[0]],
        y_label="PM2.5 real (µg/m³) · avg",
        y_decimals=2,
        y_op="average",
    )

    # NO2 / O3 (preds por horizonte)
    no2_filters = [
        {"label": "+0h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:0'},
        {"label": "+24h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:24'},
        {"label": "+48h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:48'},
        {"label": "+72h", "query": 'prediction_type.keyword:"forecast" and horizon_hours:72'},
    ]
    no2_forecast = lens_line_filters(
        "NO₂ — Predicción por horizonte (+0/+24/+48/+72)",
        y_field="no2_pred",
        series_filters=no2_filters,
        y_label="NO₂ pred (µg/m³) · avg",
        y_decimals=2,
    )
    o3_forecast = lens_line_filters(
        "O₃ — Predicción por horizonte (+0/+24/+48/+72)",
        y_field="o3_pred",
        series_filters=no2_filters,
        y_label="O₃ pred (µg/m³) · avg",
        y_decimals=2,
    )

    # Actuals NO2 / O3 (si se indexan desde Mongo)
    no2_actual_only = lens_line_filters(
        "NO₂ — Real (ground truth)",
        y_field="no2_actual",
        series_filters=[{"label": "Actual", "query": 'prediction_type.keyword:"actual" and horizon_hours:-1'}],
        y_label="NO₂ real (µg/m³) · avg",
        y_decimals=2,
    )
    o3_actual_only = lens_line_filters(
        "O₃ — Real (ground truth)",
        y_field="o3_actual",
        series_filters=[{"label": "Actual", "query": 'prediction_type.keyword:"actual" and horizon_hours:-1'}],
        y_label="O₃ real (µg/m³) · avg",
        y_decimals=2,
    )

    lens_objects = [
        ("airvlc-v2-pm25-actual-only", pm25_actual_only),
        ("airvlc-v2-pm25-forecast-only", pm25_forecast_only),
        ("airvlc-v2-no2-actual-only", no2_actual_only),
        ("airvlc-v2-no2-forecast", no2_forecast),
        ("airvlc-v2-o3-actual-only", o3_actual_only),
        ("airvlc-v2-o3-forecast", o3_forecast),
    ]

    print("\n🧩 Creando visualizaciones Lens...")
    for lens_id, lens_def in lens_objects:
        attrs, refs = _lens_saved_object(lens_def, dv_id, layer_name="layer1")
        upsert_saved_object("lens", lens_id, attrs, refs)
        print(f"  ✅ Lens: {lens_id}")

    # --- Dashboard ---
    panels = [
        _dashboard_panel("airvlc-v2-pm25-actual-only", "PM2.5 — Real (ground truth)", x=0, y=0, w=24, h=15),
        _dashboard_panel("airvlc-v2-pm25-forecast-only", "PM2.5 — Predicción por horizonte (+0/+24/+48/+72)", x=24, y=0, w=24, h=15),
        _dashboard_panel("airvlc-v2-no2-actual-only", "NO₂ — Real (ground truth)", x=0, y=15, w=24, h=15),
        _dashboard_panel("airvlc-v2-no2-forecast", "NO₂ — Predicción por horizonte (+0/+24/+48/+72)", x=24, y=15, w=24, h=15),
        _dashboard_panel("airvlc-v2-o3-actual-only", "O₃ — Real (ground truth)", x=0, y=30, w=24, h=15),
        _dashboard_panel("airvlc-v2-o3-forecast", "O₃ — Predicción por horizonte (+0/+24/+48/+72)", x=24, y=30, w=24, h=15),
    ]

    dashboard_attrs = {
        "title": "AirVLC — Forecast vs Real (v2)",
        "description": (
            "Dashboard Lens para comparar predicción vs observado. "
            "Filtra por estación con el filtro global del dashboard (campo station.keyword)."
        ),
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        },
    }
    dash_refs: list[dict] = []
    for lens_id, _ in lens_objects:
        dash_refs.append({"id": lens_id, "name": f"panel_{lens_id}", "type": "lens"})

    print("\n📌 Creando dashboard...")
    upsert_saved_object("dashboard", DASHBOARD_ID, dashboard_attrs, dash_refs)

    print(f"\n🔗 {KIBANA}/app/dashboards#/view/{DASHBOARD_ID}\n")


if __name__ == "__main__":
    main()

