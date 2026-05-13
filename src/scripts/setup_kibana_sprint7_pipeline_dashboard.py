"""
===================================================================
📈 AirVLC — Kibana Dashboard: Pipeline Status (Sprint 7)
===================================================================
Crea automáticamente en Kibana (8.x) el Data View y un dashboard con
visualizaciones Lens sobre el índice:
    airvlc-predictions-v2*

Paneles (según docs/v2AirVLCdocs/sprint7/kibana_dashboard_setup.md):
  1) Última inferencia (max @timestamp)
  2) Distribución de riesgo por contaminante (bars)
  3) PM2.5 / NO₂ / O₃ predichos (line)
  4) Estaciones por peor nivel (bars)
  5) Inferencias por hora × estación (heatmap)

Nota Kibana 8.10: `operationType: count` sin sourceField dispara aggValueCount sin campo.
  Usar count sobre `pm25_pred` (siempre indexado) como recuento de documentos por bucket.

Uso:
  venv/bin/python src/scripts/setup_kibana_sprint7_pipeline_dashboard.py
===================================================================
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

import requests

KIBANA = "http://localhost:5601"
ES = "http://localhost:9200"
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-predictions-v2*"
DV_ID = "dv-airvlc-predictions-v2"
DV_TITLE = "AirVLC — Predictions v2 (multitarget)"
TIME_FIELD = "@timestamp"
DASHBOARD_ID = "airvlc-sprint7-pipeline"


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
    r = requests.post(f"{KIBANA}/api/data_views/data_view", headers=H, json=payload)
    if r.status_code in (200, 201):
        print(f"✅ Data View '{DV_TITLE}' creado")
    elif "Duplicate" in r.text or "already exists" in r.text.lower():
        print(f"⏭  Data View '{DV_TITLE}' ya existe")
    else:
        sys.exit(f"❌ Error creando Data View: {r.status_code} {r.text[:300]}")
    return DV_ID


def upsert_saved_object(obj_type: str, obj_id: str, attributes: dict, references: list[dict]) -> None:
    body = {"attributes": attributes, "references": references}
    r = requests.post(
        f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true",
        headers=H,
        json=body,
        timeout=20,
    )
    if r.status_code not in (200, 201):
        sys.exit(f"❌ Error creando {obj_type}/{obj_id}: {r.status_code} {r.text[:600]}")


def _ref_data_view(dv_id: str, layer_name: str = "layer1") -> list[dict]:
    return [
        {
            "id": dv_id,
            "name": f"indexpattern-datasource-layer-{layer_name}",
            "type": "index-pattern",
        }
    ]


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


def _col_metric(field: str | None, op: str, label: str, decimals: int = 2) -> dict:
    col: dict[str, Any] = {
        "label": label,
        "dataType": "number",
        "operationType": op,
        "scale": "ratio",
        "isBucketed": False,
    }
    if field:
        col["sourceField"] = field
    col["params"] = {"format": {"id": "number", "params": {"decimals": decimals}}}
    return col


def _col_max_timestamp(label: str) -> dict:
    """Métrica Max sobre @timestamp (tipo date). Evita usar dataType number en fechas."""
    return {
        "label": label,
        "dataType": "date",
        "operationType": "max",
        "scale": "interval",
        "sourceField": "@timestamp",
        "isBucketed": False,
        "params": {
            "format": {
                "id": "date",
                "params": {"format": "YYYY-MM-DD HH:mm:ss"},
            }
        },
    }


def _col_records_count(label: str) -> dict:
    """Recuento de filas por bucket: equivale a doc count si el campo existe en todos los docs."""
    return _col_metric("pm25_pred", "count", label, decimals=0)


def lens_metric_max_timestamp(title: str, kuery: str, color: str) -> dict:
    layer_id = "layer1"
    col_id = "metric_col"
    layers = {
        layer_id: {
            "columnOrder": [col_id],
            "columns": {col_id: _col_max_timestamp(title)},
            "incompleteColumns": {},
        }
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {
            "layerId": layer_id,
            "layerType": "data",
            "metricAccessor": col_id,
            "color": color,
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsMetric", "state": state}


def lens_bar_count(title: str, x_terms: str, split_terms: str | None, kuery: str, horizontal: bool = True) -> dict:
    layer_id = "layer1"
    x_id, y_id = "x_col", "y_col"
    columns = {
        x_id: _col_terms(x_terms, label=x_terms, size=25),
        y_id: _col_records_count("Count"),
    }
    column_order = [x_id]
    split_id = None
    if split_terms:
        split_id = "split_col"
        columns[split_id] = _col_terms(split_terms, label=split_terms, size=10)
        column_order.append(split_id)
    column_order.append(y_id)

    layers_state = {layer_id: {"columnOrder": column_order, "columns": columns, "incompleteColumns": {}}}
    vis_layer: dict[str, Any] = {
        "layerId": layer_id,
        "layerType": "data",
        "seriesType": "bar",
        "xAccessor": x_id,
        "accessors": [y_id],
        "position": "top",
        "showGridlines": False,
    }
    if split_id:
        vis_layer["splitAccessor"] = split_id

    state = {
        "datasourceStates": {"formBased": {"layers": layers_state}},
        "visualization": {
            "preferredSeriesType": "bar_horizontal" if horizontal else "bar",
            "legend": {"isVisible": True, "position": "bottom"},
            "valueLabels": "show",
            "fittingFunction": "None",
            "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsXY", "state": state}


def lens_line_multi(title: str, kuery: str) -> dict:
    layer_id = "layer1"
    x_id = "x_time"
    pm_id, n2_id, o3_id = "pm25", "no2", "o3"
    layers = {
        layer_id: {
            "columnOrder": [x_id, pm_id, n2_id, o3_id],
            "columns": {
                x_id: _col_date_histogram("@timestamp", "Tiempo"),
                pm_id: _col_metric("pm25_pred", "average", "PM2.5 (avg)", decimals=2),
                n2_id: _col_metric("no2_pred", "average", "NO₂ (avg)", decimals=2),
                o3_id: _col_metric("o3_pred", "average", "O₃ (avg)", decimals=2),
            },
            "incompleteColumns": {},
        }
    }
    vis_layer = {
        "layerId": layer_id,
        "layerType": "data",
        "seriesType": "line",
        "xAccessor": x_id,
        "accessors": [pm_id, n2_id, o3_id],
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {
            "preferredSeriesType": "line",
            "legend": {"isVisible": True, "position": "bottom"},
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsXY", "state": state}


def lens_bar_single_terms(title: str, terms_field: str, kuery: str, horizontal: bool = True) -> dict:
    """Barra horizontal: una dimensión categórica + count (sustituye donut si lnsPie falla)."""
    layer_id = "layer1"
    x_id, y_id = "x_col", "y_col"
    columns = {
        x_id: _col_terms(terms_field, label=terms_field, size=15),
        y_id: _col_records_count("Count"),
    }
    layers_state = {layer_id: {"columnOrder": [x_id, y_id], "columns": columns, "incompleteColumns": {}}}
    vis_layer: dict[str, Any] = {
        "layerId": layer_id,
        "layerType": "data",
        "seriesType": "bar",
        "xAccessor": x_id,
        "accessors": [y_id],
        "position": "top",
        "showGridlines": False,
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers_state}},
        "visualization": {
            "preferredSeriesType": "bar_horizontal" if horizontal else "bar",
            "legend": {"isVisible": False, "position": "bottom"},
            "valueLabels": "show",
            "fittingFunction": "None",
            "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": False},
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {"title": title, "visualizationType": "lnsXY", "state": state}


def lens_heatmap_time_station_count(title: str, kuery: str) -> dict:
    """Panel 6 del doc: actividad de inferencias por hora y estación (count)."""
    layer_id = "layer1"
    x_id, y_id, m_id = "x_time", "y_station", "m_count"
    layers = {
        layer_id: {
            "columnOrder": [x_id, y_id, m_id],
            "columns": {
                x_id: _col_date_histogram("@timestamp", "Tiempo"),
                y_id: _col_terms("station.keyword", "Estación", size=15),
                m_id: _col_records_count("Inferencias"),
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


def main() -> None:
    print("\n" + "=" * 60)
    print("📈 AirVLC — Setup Dashboard Pipeline (Sprint 7)")
    print("=" * 60 + "\n")
    check_services()
    dv_id = create_data_view()
    time.sleep(1)

    # Filtro sobre .keyword: el mapping indexa source como text+keyword; KQL sin .keyword puede fallar en agregaciones/filtros.
    kuery_sources = (
        '(source.keyword: "api-v2") or (source.keyword: "api-v2-profile")'
    )

    # Campos categóricos: usar .keyword (ver mapping del índice airvlc-predictions-v2).
    lens_specs = [
        ("last-inference", lens_metric_max_timestamp("Última inferencia", kuery_sources, color="#6092C0")),
        (
            "risk-dist",
            lens_bar_count(
                "Distribución de riesgo por contaminante",
                "worst_pollutant.keyword",
                "worst_level.keyword",
                kuery_sources,
                horizontal=True,
            ),
        ),
        ("pred-lines", lens_line_multi("PM2.5 / NO₂ / O₃ predichos (avg)", kuery_sources)),
        (
            "worst-level-bars",
            lens_bar_single_terms("Estaciones por peor nivel", "worst_level.keyword", kuery_sources, horizontal=True),
        ),
        (
            "heatmap-station-time",
            lens_heatmap_time_station_count("Inferencias por hora y estación", kuery_sources),
        ),
    ]

    print(f"🎨 Creando {len(lens_specs)} visualizaciones Lens...")
    for so_id, attrs in lens_specs:
        full_id = f"airvlc-s7-{so_id}"
        refs = _ref_data_view(dv_id, "layer1")
        upsert_saved_object("lens", full_id, attrs, refs)
        print(f"  ✅ {full_id}")

    # Dashboard panels layout (48 columns grid). Sin panel "Estaciones predichas".
    layout = [
        ("p1", "airvlc-s7-last-inference", 0, 0, 18, 10, "Última inferencia"),
        ("p2", "airvlc-s7-worst-level-bars", 18, 0, 30, 18, "Estaciones por peor nivel"),
        ("p3", "airvlc-s7-risk-dist", 0, 10, 18, 18, "Distribución de riesgo por contaminante"),
        ("p4", "airvlc-s7-pred-lines", 0, 28, 48, 14, "PM2.5 / NO₂ / O₃ predichos (avg)"),
        ("p5", "airvlc-s7-heatmap-station-time", 0, 42, 48, 14, "Inferencias por hora y estación"),
    ]

    panels = []
    references = []
    for panel_idx, so_id, x, y, w, h, title in layout:
        panels.append(
            {
                "type": "lens",
                "panelIndex": panel_idx,
                "panelRefName": f"panel_{panel_idx}",
                "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_idx},
                "embeddableConfig": {"hidePanelTitles": False, "enhancements": {}},
                "title": title,
                "version": "8.10.4",
            }
        )
        references.append({"type": "lens", "id": so_id, "name": f"panel_{panel_idx}"})

    dashboard_attrs = {
        "title": "AirVLC — Pipeline Status (Sprint 7)",
        "description": "Dashboard operacional: última inferencia, riesgo por contaminante, series v2 e inferencias por estación/hora.",
        "panelsJSON": json.dumps(panels),
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        },
        "version": 1,
    }
    upsert_saved_object("dashboard", DASHBOARD_ID, dashboard_attrs, references)

    print("\n" + "=" * 60)
    print("✅ Dashboard creado/actualizado")
    print("=" * 60)
    print(f"\n🔗 {KIBANA}/app/dashboards#/view/{DASHBOARD_ID}\n")


if __name__ == "__main__":
    main()

