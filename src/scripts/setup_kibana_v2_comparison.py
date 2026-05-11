"""
===================================================================
📊 AirVLC — Dashboard Kibana: Comparativa Modelo v1 vs v2
===================================================================
Crea en Kibana (8.10.4) un dashboard con **visualizaciones Lens
reales** (gráficos, no markdown) sobre el índice
``airvlc-model-comparison-v1v2`` (alimentado por el pipeline Logstash
``model_comparison.conf``).

Layout del dashboard (`airvlc-v1-vs-v2`):

```
┌─ Métricas ganador v1 (PM2.5) ─┐ ┌─ Métricas ganador v2 (PM2.5) ─┐
│ R² · MAE · RMSE                │ │ R² · MAE · RMSE                │
└────────────────────────────────┘ └────────────────────────────────┘
┌─ R² PM2.5 v1 vs v2 ───────────┐ ┌─ MAE PM2.5 v1 vs v2 ──────────┐
│ bar chart, split por version   │ │ bar chart, split por version   │
└────────────────────────────────┘ └────────────────────────────────┘
┌─ R² por target × arch (solo v2) ─────────────────────────────────┐
│ bar chart, eje x=architecture, split=target                      │
└──────────────────────────────────────────────────────────────────┘
┌─ MAE por target × arch (v2) ──┐ ┌─ Heatmap R² (arch × target) ──┐
└────────────────────────────────┘ └────────────────────────────────┘
┌─ Training time × arch (v1+v2)  ┐ ┌─ Params × arch (v1+v2) ───────┐
└────────────────────────────────┘ └────────────────────────────────┘
┌─ Tabla detalle (todas filas) ─────────────────────────────────────┐
└──────────────────────────────────────────────────────────────────┘
```

Pre-requisitos:
1. ``data/processed/model_comparison_v1_v2.csv`` ya generado.
2. Logstash arriba con el pipeline ``model_comparison.conf`` activo.
3. ES tiene 16 docs en ``airvlc-model-comparison-v1v2``.

Uso:
    venv/bin/python src/scripts/setup_kibana_v2_comparison.py
===================================================================
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from typing import Any

import requests

KIBANA = "http://localhost:5601"
ES = "http://localhost:9200"
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-model-comparison-v1v2"
DV_ID = "dv-airvlc-model-comparison-v1v2"
DV_TITLE = "AirVLC — Model Comparison v1 vs v2"
DASHBOARD_ID = "airvlc-v1-vs-v2"


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

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
    try:
        c = requests.get(f"{ES}/{INDEX}/_count", timeout=5).json().get("count", 0)
        if c == 0:
            sys.exit(f"❌ Índice '{INDEX}' está vacío. Ejecuta primero "
                     f"`python src/scripts/build_model_comparison_csv.py` "
                     f"y reinicia logstash.")
        print(f"✅ Índice '{INDEX}' tiene {c} documentos")
    except Exception as e:
        sys.exit(f"❌ No se pudo consultar índice: {e}")


def create_data_view() -> str:
    """Crea el Data View si no existe. No hay timeFieldName porque no es
    una serie temporal: cada doc es un resultado de evaluación puntual."""
    payload = {"data_view": {
        "id": DV_ID,
        "title": INDEX,
        "name": DV_TITLE,
    }}
    r = requests.post(f"{KIBANA}/api/data_views/data_view", headers=H, json=payload)
    if r.status_code in (200, 201):
        print(f"✅ Data View '{DV_TITLE}' creado")
    elif "Duplicate" in r.text or "already exists" in r.text.lower():
        print(f"⏭  Data View '{DV_TITLE}' ya existe")
    else:
        print(f"⚠  {r.status_code}: {r.text[:200]}")
    return DV_ID


def upsert_saved_object(obj_type: str, obj_id: str, attributes: dict,
                        references: list[dict]) -> None:
    """Crea o actualiza un saved object via la API."""
    requests.delete(f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}", headers=H)
    body = {"attributes": attributes, "references": references}
    r = requests.post(
        f"{KIBANA}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true",
        headers=H, json=body,
    )
    if r.status_code not in (200, 201):
        print(f"❌ Error creando {obj_type}/{obj_id}: {r.status_code}")
        print(f"   body: {r.text[:500]}")
        sys.exit(1)


def _col_terms(field: str, label: str | None = None, size: int = 25,
               order_by_col: str | None = None) -> dict:
    """Columna de tipo 'terms' (bucket categórico)."""
    if order_by_col is None:
        order = {"type": "alphabetical", "fallback": True}
    else:
        order = {"type": "column", "columnId": order_by_col}
    return {
        "label": label or field,
        "dataType": "string",
        "operationType": "terms",
        "scale": "ordinal",
        "sourceField": field,
        "isBucketed": True,
        "params": {
            "size": size,
            "orderBy": order,
            "orderDirection": "asc",
            "otherBucket": False,
            "missingBucket": False,
            "parentFormat": {"id": "terms"},
        },
    }


def _col_metric(field: str, op: str = "average",
                label: str | None = None, fmt: str | None = None) -> dict:
    """Columna métrica (avg/sum/max/etc) — no bucket."""
    col = {
        "label": label or f"{op} of {field}",
        "dataType": "number",
        "operationType": op,
        "scale": "ratio",
        "sourceField": field,
        "isBucketed": False,
    }
    if fmt:
        col["params"] = {"format": {"id": fmt, "params": {"decimals": 4}}}
    return col


def _filter_query(kuery: str) -> dict:
    return {
        "query": {"language": "kuery", "query": kuery},
        "filter": [],
    }


# ──────────────────────────────────────────────────────────────────────
# Builders Lens (cada función devuelve attributes para saved_objects/lens)
# ──────────────────────────────────────────────────────────────────────

def lens_metric(title: str, field: str, op: str, kuery: str,
                color: str = "#54B399",
                fmt_decimals: int = 4) -> dict:
    """KPI grande con el valor agregado de un campo, filtrado por kuery."""
    layer_id = "layer1"
    col_id = "metric_col"
    layers = {
        layer_id: {
            "columnOrder": [col_id],
            "columns": {
                col_id: {
                    "label": title,
                    "dataType": "number",
                    "operationType": op,
                    "scale": "ratio",
                    "sourceField": field,
                    "isBucketed": False,
                    "params": {"format": {"id": "number",
                                          "params": {"decimals": fmt_decimals}}},
                },
            },
            "incompleteColumns": {},
        },
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
    return {
        "title": title,
        "visualizationType": "lnsMetric",
        "state": state,
    }


def lens_bar(title: str, x_field: str, y_field: str, y_op: str,
             kuery: str = "",
             split_field: str | None = None,
             y_label: str | None = None,
             y_decimals: int = 4,
             horizontal: bool = False) -> dict:
    """Bar chart: x=x_field (terms), y=y_op(y_field), opcional split=split_field."""
    layer_id = "layer1"
    x_id, y_id = "x_col", "y_col"
    columns = {
        x_id: _col_terms(x_field, label=x_field, size=25),
        y_id: _col_metric(y_field, y_op, label=y_label or f"{y_op}({y_field})",
                          fmt="number"),
    }
    column_order = [x_id]
    split_acc = None
    if split_field:
        split_id = "split_col"
        columns[split_id] = _col_terms(split_field, label=split_field, size=10)
        column_order.append(split_id)
        split_acc = split_id
    column_order.append(y_id)

    layer = {
        "columnOrder": column_order,
        "columns": columns,
        "incompleteColumns": {},
    }
    layers_state = {layer_id: layer}

    vis_layer = {
        "layerId": layer_id,
        "layerType": "data",
        "seriesType": "bar",
        "xAccessor": x_id,
        "accessors": [y_id],
        "position": "top",
        "showGridlines": False,
    }
    if split_acc:
        vis_layer["splitAccessor"] = split_acc

    state = {
        "datasourceStates": {"formBased": {"layers": layers_state}},
        "visualization": {
            "preferredSeriesType": "bar" if not horizontal else "bar_horizontal",
            "legend": {"isVisible": True, "position": "bottom"},
            "valueLabels": "show",
            "fittingFunction": "None",
            "axisTitlesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
            "tickLabelsVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
            "labelsOrientation": {"x": 0, "yLeft": 0, "yRight": 0},
            "gridlinesVisibilitySettings": {"x": True, "yLeft": True, "yRight": True},
            "layers": [vis_layer],
        },
        "query": {"language": "kuery", "query": kuery},
        "filters": [],
    }
    return {
        "title": title,
        "visualizationType": "lnsXY",
        "state": state,
    }


def lens_heatmap(title: str, x_field: str, y_field: str,
                 metric_field: str, metric_op: str = "average",
                 kuery: str = "") -> dict:
    """Heatmap (x × y) con celdas coloreadas por la métrica."""
    layer_id = "layer1"
    x_id, y_id, m_id = "x_col", "y_col", "m_col"
    layers = {
        layer_id: {
            "columnOrder": [x_id, y_id, m_id],
            "columns": {
                x_id: _col_terms(x_field, x_field, size=10),
                y_id: _col_terms(y_field, y_field, size=10),
                m_id: _col_metric(metric_field, metric_op,
                                  label=f"{metric_op}({metric_field})",
                                  fmt="number"),
            },
            "incompleteColumns": {},
        },
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
            "legend": {"isVisible": True, "position": "right",
                       "type": "heatmap_legend"},
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
    return {
        "title": title,
        "visualizationType": "lnsHeatmap",
        "state": state,
    }


def lens_table(title: str, columns_spec: list[tuple[str, str, str]],
               kuery: str = "") -> dict:
    """Tabla. columns_spec: lista de (field, op, label).
    op='terms' para campo categórico, 'average'/'max'/etc. para métricas."""
    layer_id = "layer1"
    cols = {}
    order = []
    for i, (field, op, label) in enumerate(columns_spec):
        col_id = f"col_{i}"
        if op == "terms":
            cols[col_id] = _col_terms(field, label, size=50)
        else:
            cols[col_id] = _col_metric(field, op, label, fmt="number")
        order.append(col_id)

    layers = {layer_id: {"columnOrder": order, "columns": cols,
                         "incompleteColumns": {}}}
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
    return {
        "title": title,
        "visualizationType": "lnsDatatable",
        "state": state,
    }


# ──────────────────────────────────────────────────────────────────────
# Construcción de saved objects + dashboard
# ──────────────────────────────────────────────────────────────────────

def build_lens_so(so_id: str, attrs: dict, dv_id: str) -> dict:
    """Empaqueta los attributes + reference al data view."""
    refs = [{
        "id": dv_id,
        "name": "indexpattern-datasource-layer-layer1",
        "type": "index-pattern",
    }]
    return {"id": so_id, "type": "lens", "attributes": attrs, "references": refs}


def panel(panel_id: str, so_id: str, x: int, y: int, w: int, h: int,
          title: str) -> dict:
    """Construye un panel del dashboard que referencia un saved object Lens."""
    return {
        "type": "lens",
        "panelIndex": panel_id,
        "panelRefName": f"panel_{panel_id}",
        "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_id},
        "embeddableConfig": {"hidePanelTitles": False, "enhancements": {}},
        "title": title,
        "version": "8.10.4",
    }


def main() -> None:
    print("\n" + "=" * 60)
    print("📊 AirVLC — Setup Dashboard Comparativo v1 vs v2")
    print("=" * 60 + "\n")
    check_services()

    dv_id = create_data_view()
    time.sleep(1)

    # ─── Definimos las visualizaciones Lens ────────────────────────────
    KQ_PM25 = 'target : "pm25"'
    KQ_V1_WIN = 'version : "v1" and is_winner : 1 and target : "pm25"'
    KQ_V2_WIN = 'version : "v2" and is_winner : 1 and target : "pm25"'
    KQ_V2 = 'version : "v2"'

    lens_specs = [
        # ── KPIs ganador v1 (PM2.5) ────────────────────────────
        ("kpi-v1-r2",   lens_metric("R² ganador v1 (PM2.5)",   "r2",   "max", KQ_V1_WIN, color="#6092C0", fmt_decimals=4)),
        ("kpi-v1-mae",  lens_metric("MAE ganador v1 (µg/m³)",  "mae",  "min", KQ_V1_WIN, color="#6092C0", fmt_decimals=4)),
        ("kpi-v1-rmse", lens_metric("RMSE ganador v1 (µg/m³)", "rmse", "min", KQ_V1_WIN, color="#6092C0", fmt_decimals=4)),
        # ── KPIs ganador v2 (PM2.5) ────────────────────────────
        ("kpi-v2-r2",   lens_metric("R² ganador v2 (PM2.5)",   "r2",   "max", KQ_V2_WIN, color="#54B399", fmt_decimals=4)),
        ("kpi-v2-mae",  lens_metric("MAE ganador v2 (µg/m³)",  "mae",  "min", KQ_V2_WIN, color="#54B399", fmt_decimals=4)),
        ("kpi-v2-rmse", lens_metric("RMSE ganador v2 (µg/m³)", "rmse", "min", KQ_V2_WIN, color="#54B399", fmt_decimals=4)),
        # ── Comparativa apples-to-apples PM2.5 ─────────────────
        ("bar-r2-pm25",   lens_bar("R² PM2.5 por arquitectura (v1 vs v2)",
                                   "architecture", "r2",   "max", kuery=KQ_PM25,
                                   split_field="version", y_label="R²", y_decimals=4)),
        ("bar-mae-pm25",  lens_bar("MAE PM2.5 por arquitectura (v1 vs v2)",
                                   "architecture", "mae",  "min", kuery=KQ_PM25,
                                   split_field="version", y_label="MAE (µg/m³)")),
        ("bar-rmse-pm25", lens_bar("RMSE PM2.5 por arquitectura (v1 vs v2)",
                                   "architecture", "rmse", "min", kuery=KQ_PM25,
                                   split_field="version", y_label="RMSE (µg/m³)")),
        # ── v2 multitarget breakdown ───────────────────────────
        ("bar-r2-v2",   lens_bar("R² por target × arquitectura (solo v2)",
                                 "architecture", "r2",  "max", kuery=KQ_V2,
                                 split_field="target", y_label="R²")),
        ("bar-mae-v2",  lens_bar("MAE por target × arquitectura (solo v2)",
                                 "architecture", "mae", "min", kuery=KQ_V2,
                                 split_field="target", y_label="MAE (µg/m³)")),
        ("heat-r2-v2",  lens_heatmap("Heatmap R² (arquitectura × target) — v2",
                                     "architecture", "target", "r2",
                                     metric_op="max", kuery=KQ_V2)),
        # ── Eficiencia ──────────────────────────────────────────
        ("bar-time",    lens_bar("Tiempo de entrenamiento (s) — v1 vs v2",
                                 "architecture", "training_time_sec", "max",
                                 split_field="version",
                                 y_label="seg",
                                 horizontal=True)),
        ("bar-params",  lens_bar("Nº parámetros por arquitectura — v1 vs v2",
                                 "architecture", "n_params", "max",
                                 split_field="version",
                                 y_label="params",
                                 horizontal=True)),
        # ── Tabla detalle ───────────────────────────────────────
        ("table-detail", lens_table("Tabla detalle — todos los resultados",
                                    [
                                        ("version", "terms", "Version"),
                                        ("architecture", "terms", "Architecture"),
                                        ("target", "terms", "Target"),
                                        ("r2", "max", "R²"),
                                        ("mae", "min", "MAE"),
                                        ("rmse", "min", "RMSE"),
                                        ("n_params", "max", "Params"),
                                        ("training_time_sec", "max", "Time (s)"),
                                    ])),
    ]

    # ─── Crear cada saved object Lens ──────────────────────────────────
    print(f"\n🎨 Creando {len(lens_specs)} visualizaciones Lens...")
    for so_id, attrs in lens_specs:
        full_id = f"airvlc-v1v2-{so_id}"
        ref = [{"id": dv_id, "name": "indexpattern-datasource-layer-layer1",
                "type": "index-pattern"}]
        upsert_saved_object("lens", full_id, attrs, ref)
        print(f"  ✅ {full_id}")

    # ─── Componer panelsJSON del dashboard ─────────────────────────────
    print("\n📐 Componiendo dashboard con grid 48-col...")
    # Layout (cada panel es x,y,w,h en grid de 48 columnas).
    layout = [
        # Row 1: KPIs (3 v1 + 3 v2)
        ("kpi-v1-r2",     0,  0,  8, 6, "R² ganador v1 (PM2.5)"),
        ("kpi-v1-mae",    8,  0,  8, 6, "MAE ganador v1 (µg/m³)"),
        ("kpi-v1-rmse",   16, 0,  8, 6, "RMSE ganador v1 (µg/m³)"),
        ("kpi-v2-r2",     24, 0,  8, 6, "R² ganador v2 (PM2.5)"),
        ("kpi-v2-mae",    32, 0,  8, 6, "MAE ganador v2 (µg/m³)"),
        ("kpi-v2-rmse",   40, 0,  8, 6, "RMSE ganador v2 (µg/m³)"),
        # Row 2: Apples-to-apples PM2.5
        ("bar-r2-pm25",    0,  6, 24, 14, "R² PM2.5 por arquitectura (v1 vs v2)"),
        ("bar-mae-pm25",  24,  6, 24, 14, "MAE PM2.5 por arquitectura (v1 vs v2)"),
        # Row 3: RMSE + heatmap v2
        ("bar-rmse-pm25",  0, 20, 24, 14, "RMSE PM2.5 por arquitectura (v1 vs v2)"),
        ("heat-r2-v2",    24, 20, 24, 14, "Heatmap R² (arquitectura × target) — v2"),
        # Row 4: v2 multitarget
        ("bar-r2-v2",      0, 34, 24, 14, "R² por target × arquitectura (solo v2)"),
        ("bar-mae-v2",    24, 34, 24, 14, "MAE por target × arquitectura (solo v2)"),
        # Row 5: Eficiencia
        ("bar-time",       0, 48, 24, 12, "Tiempo de entrenamiento (s)"),
        ("bar-params",    24, 48, 24, 12, "Nº parámetros por arquitectura"),
        # Row 6: Tabla
        ("table-detail",   0, 60, 48, 16, "Tabla detalle — todos los resultados"),
    ]

    panels = []
    references = []
    for so_id, x, y, w, h, title in layout:
        full_id = f"airvlc-v1v2-{so_id}"
        panel_idx = so_id  # estable y descriptivo
        panels.append({
            "type": "lens",
            "panelIndex": panel_idx,
            "panelRefName": f"panel_{panel_idx}",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": panel_idx},
            "embeddableConfig": {"hidePanelTitles": False, "enhancements": {}},
            "title": title,
            "version": "8.10.4",
        })
        references.append({
            "type": "lens",
            "id": full_id,
            "name": f"panel_{panel_idx}",
        })

    dashboard_attrs = {
        "title": "📊 AirVLC — Comparativa Modelo v1 vs v2",
        "description": ("Comparativa de las 7 arquitecturas v1 (monotarget "
                        "PM2.5) frente a las 3 arquitecturas v2 (multitarget "
                        "PM2.5/NO₂/O₃). Incluye KPIs del ganador, comparativa "
                        "apples-to-apples PM2.5, breakdown multitarget v2, "
                        "heatmap, eficiencia y tabla detallada."),
        "panelsJSON": json.dumps(panels),
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [],
            }),
        },
        "version": 1,
    }
    upsert_saved_object("dashboard", DASHBOARD_ID, dashboard_attrs, references)

    print("\n" + "=" * 60)
    print("✅ Dashboard creado")
    print("=" * 60)
    print(f"\n🔗 {KIBANA}/app/dashboards#/view/{DASHBOARD_ID}\n")


if __name__ == "__main__":
    main()
