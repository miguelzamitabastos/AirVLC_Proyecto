"""
===================================================================
📈 AirVLC — Kibana Data View: Predicciones v2 (multitarget)
===================================================================
Crea en Kibana (8.10.4) un Data View para el índice:
    airvlc-predictions-v2

Uso:
    python3 src/scripts/setup_kibana_v2_predictions_dataview.py
===================================================================
"""

from __future__ import annotations

import sys
import requests

KIBANA = "http://localhost:5601"
ES = "http://localhost:9200"
H = {"kbn-xsrf": "true", "Content-Type": "application/json"}

INDEX = "airvlc-predictions-v2"
DV_ID = "dv-airvlc-predictions-v2"
DV_TITLE = "AirVLC — Predictions v2 (multitarget)"
TIME_FIELD = "@timestamp"


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

    # No exigimos que el índice tenga docs (puede ser el primer arranque)
    try:
        r = requests.get(f"{ES}/{INDEX}/_count", timeout=5)
        if r.status_code == 404:
            print(f"⚠️ Índice '{INDEX}' aún no existe (ok si aún no has llamado /api/v2/risk).")
        else:
            c = r.json().get("count", 0)
            print(f"✅ Índice '{INDEX}' accesible (docs: {c})")
    except Exception as e:
        print(f"⚠️ No se pudo consultar '{INDEX}': {e}")


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
        print(f"✅ Data View '{DV_TITLE}' creado (time field: {TIME_FIELD})")
    elif "Duplicate" in r.text or "already exists" in r.text.lower():
        print(f"⏭  Data View '{DV_TITLE}' ya existe")
    else:
        sys.exit(f"❌ Error creando Data View: {r.status_code} {r.text[:300]}")
    return DV_ID


def main() -> None:
    print("\n" + "=" * 60)
    print("📈 AirVLC — Setup Data View: Predictions v2")
    print("=" * 60 + "\n")
    check_services()
    create_data_view()
    print(f"\n🔗 Abre Kibana → Stack Management → Data Views → {DV_TITLE}\n")


if __name__ == "__main__":
    main()

