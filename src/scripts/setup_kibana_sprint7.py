"""
===================================================================
📊 AirVLC — Dashboard Kibana: Sprint 7 (Pipeline)
===================================================================
Crea en Kibana (8.10.4) el dashboard operacional del Sprint 7 con
los paneles de monitorización de inferencias en producción.
===================================================================
"""

from __future__ import annotations

import json
import sys
import time
import requests

KIBANA = "http://localhost:5601"
ES = "http://localhost:9200"
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-predictions-v2*"
DV_ID = "dv-airvlc-predictions-v2"
DV_TITLE = "airvlc-predictions-v2"
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
    payload = {"data_view": {"id": DV_ID, "title": INDEX, "name": DV_TITLE, "timeFieldName": "@timestamp"}}
    r = requests.post(f"{KIBANA}/api/data_views/data_view", headers=H, json=payload)
    if r.status_code in (200, 201):
        print(f"✅ Data View '{DV_TITLE}' creado")
    elif "Duplicate" in r.text or "already exists" in r.text.lower():
        print(f"⏭  Data View '{DV_TITLE}' ya existe")
    else:
        print(f"⚠  {r.status_code}: {r.text[:200]}")
    return DV_ID

def upsert_saved_object(obj_type: str, obj_id: str, attributes: dict, references: list[dict]) -> None:
    requests.delete(f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}", headers=H)
    body = {"attributes": attributes, "references": references}
    r = requests.post(f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true", headers=H, json=body)
    if r.status_code not in (200, 201):
        print(f"❌ Error creando {obj_type}/{obj_id}: {r.status_code}")
        print(f"   body: {r.text[:500]}")

def _col_terms(field: str, label: str | None = None, size: int = 25) -> dict:
    return {
        "label": label or field, "dataType": "string", "operationType": "terms",
        "scale": "ordinal", "sourceField": field, "isBucketed": True,
        "params": {"size": size, "orderBy": {"type": "alphabetical", "fallback": True}, "orderDirection": "asc"}
    }

def _col_metric(field: str, op: str = "average", label: str | None = None) -> dict:
    return {
        "label": label or f"{op} of {field}", "dataType": "number",
        "operationType": op, "scale": "ratio", "sourceField": field, "isBucketed": False,
        "params": {"format": {"id": "number", "params": {"decimals": 2}}}
    }

def lens_metric(title: str, field: str, op: str, kuery: str, color: str = "#54B399") -> dict:
    layer_id = "layer1"
    col_id = "metric_col"
    layers = {
        layer_id: {
            "columnOrder": [col_id],
            "columns": {col_id: _col_metric(field, op, label=title)},
            "incompleteColumns": {},
        },
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {"layerId": layer_id, "layerType": "data", "metricAccessor": col_id, "color": color},
        "query": {"language": "kuery", "query": kuery}, "filters": [],
    }
    return {"title": title, "visualizationType": "lnsMetric", "state": state}

def lens_bar(title: str, x_field: str, y_field: str, y_op: str,
             kuery: str = "", split_field: str | None = None,
             horizontal: bool = False, line: bool = False) -> dict:
    layer_id = "layer1"
    x_id, y_id = "x_col", "y_col"
    x_col = {
        "label": "@timestamp", "dataType": "date", "operationType": "date_histogram",
        "sourceField": "@timestamp", "isBucketed": True, "params": {"interval": "auto"}
    } if x_field == "@timestamp" else _col_terms(x_field, label=x_field, size=25)
    
    columns = {x_id: x_col, y_id: _col_metric(y_field, y_op, label=title)}
    column_order = [x_id]
    split_acc = None
    if split_field:
        split_id = "split_col"
        columns[split_id] = _col_terms(split_field, label=split_field, size=10)
        column_order.append(split_id)
        split_acc = split_id
    column_order.append(y_id)

    layers_state = {layer_id: {"columnOrder": column_order, "columns": columns, "incompleteColumns": {}}}
    
    vis_layer = {
        "layerId": layer_id, "layerType": "data", "seriesType": "line" if line else "bar",
        "xAccessor": x_id, "accessors": [y_id], "position": "top",
    }
    if split_acc: vis_layer["splitAccessor"] = split_acc

    state = {
        "datasourceStates": {"formBased": {"layers": layers_state}},
        "visualization": {
            "preferredSeriesType": "line" if line else ("bar_horizontal" if horizontal else "bar"),
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": kuery}, "filters": [],
    }
    return {"title": title, "visualizationType": "lnsXY", "state": state}

def lens_heatmap(title: str, x_field: str, y_field: str, metric_field: str, metric_op: str = "max") -> dict:
    layer_id = "layer1"
    x_id, y_id, m_id = "x_col", "y_col", "m_col"
    layers = {
        layer_id: {
            "columnOrder": [x_id, y_id, m_id],
            "columns": {
                x_id: {"label": "@timestamp", "dataType": "date", "operationType": "date_histogram",
                       "sourceField": "@timestamp", "isBucketed": True, "params": {"interval": "1h"}},
                y_id: _col_terms(y_field, y_field, size=25),
                m_id: _col_metric(metric_field, metric_op, label=metric_field),
            },
            "incompleteColumns": {},
        },
    }
    state = {
        "datasourceStates": {"formBased": {"layers": layers}},
        "visualization": {"layerId": layer_id, "layerType": "data", "shape": "heatmap",
                          "xAccessor": x_id, "yAccessor": y_id, "valueAccessor": m_id},
        "query": {"language": "kuery", "query": ""}, "filters": [],
    }
    return {"title": title, "visualizationType": "lnsHeatmap", "state": state}

def main() -> None:
    print("\n" + "=" * 60)
    print("📊 AirVLC — Setup Dashboard Sprint 7 (Pipeline)")
    print("=" * 60 + "\n")
    check_services()
    dv_id = create_data_view()
    time.sleep(1)

    lens_specs = [
        ("metric-last", lens_metric("Última Inferencia", "pm25_pred", "average", "source: api-v2 OR source: api-v2-profile", color="#6092C0")),
        ("metric-stations", lens_metric("Estaciones Predichas", "station.keyword", "unique_count", "")),
        ("bar-risk", lens_bar("Distribución Riesgo", "worst_pollutant.keyword", "pm25_pred", "count", split_field="worst_level.keyword", horizontal=True)),
        ("line-preds", lens_bar("Evolución PM2.5", "@timestamp", "pm25_pred", "average", line=True)),
        ("heat-risk", lens_heatmap("Histórico de Riesgo por Estación", "@timestamp", "station.keyword", "pm25_pred", "max")),
    ]

    print(f"\n🎨 Creando {len(lens_specs)} visualizaciones Lens...")
    for so_id, attrs in lens_specs:
        full_id = f"airvlc-s7-{so_id}"
        ref = [{"id": dv_id, "name": "indexpattern-datasource-layer-layer1", "type": "index-pattern"}]
        upsert_saved_object("lens", full_id, attrs, ref)
        print(f"  ✅ {full_id}")

    layout = [
        ("metric-last",     0,  0, 12, 8, "Última Inferencia"),
        ("metric-stations", 12, 0, 12, 8, "Estaciones Predichas"),
        ("bar-risk",        24, 0, 24, 12, "Distribución de Riesgo"),
        ("line-preds",      0, 12, 24, 14, "Evolución de Contaminantes"),
        ("heat-risk",       24, 12, 24, 14, "Histórico Riesgo Estación"),
    ]

    panels = []
    references = []
    for so_id, x, y, w, h, title in layout:
        full_id = f"airvlc-s7-{so_id}"
        panels.append({
            "type": "lens", "panelIndex": so_id, "panelRefName": f"panel_{so_id}",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": so_id},
            "embeddableConfig": {"hidePanelTitles": False, "enhancements": {}},
            "title": title, "version": "8.10.4",
        })
        references.append({"type": "lens", "id": full_id, "name": f"panel_{so_id}"})

    dashboard_attrs = {
        "title": "AirVLC — Pipeline Status (Sprint 7)",
        "description": "Dashboard operacional del Sprint 7",
        "panelsJSON": json.dumps(panels),
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})},
        "version": 1,
    }
    upsert_saved_object("dashboard", DASHBOARD_ID, dashboard_attrs, references)

    print("\n" + "=" * 60)
    print("✅ Dashboard creado")
    print(f"🔗 {KIBANA}/app/dashboards#/view/{DASHBOARD_ID}\n")

if __name__ == "__main__":
    main()
