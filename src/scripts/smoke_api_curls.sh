#!/usr/bin/env bash
# ===================================================================
# AirVLC — Pruebas curl de todos los endpoints Flask
# ===================================================================
# Uso:
#   ./src/scripts/smoke_api_curls.sh
#   API_BASE=http://127.0.0.1:5001 ./src/scripts/smoke_api_curls.sh
#
# Requiere: API en marcha (python src/api/app.py), jq opcional (pretty).
# ===================================================================
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:5001}"
INTERNAL_TOKEN="${AIRVLC_INTERNAL_RELOAD_TOKEN:-airvlc-reload-secret}"
# Modelo v1 con entrada 24×20 (evita usar el multitarget en /api/predict v1)
V1_PREDICT_MODEL="${V1_PREDICT_MODEL:-Best_Day7}"

pretty() {
  if command -v jq >/dev/null 2>&1; then
    jq .
  else
    cat
  fi
}

echo "=== API_BASE=$API_BASE ==="
echo

echo "--- v1 GET|HEAD /api/health ---"
curl -sS -o /dev/null -w "HEAD HTTP %{http_code}\n" -I -X HEAD "${API_BASE}/api/health"
curl -sS "${API_BASE}/api/health" | pretty
echo

echo "--- v1 GET /api/model/info ---"
curl -sS "${API_BASE}/api/model/info" | pretty
echo

echo "--- v1 POST /api/predict (tensor dummy 24×20, modelo $V1_PREDICT_MODEL) ---"
FEATS_JSON=$(python3 -c 'import json; print(json.dumps([[0.0]*20 for _ in range(24)]))')
curl -sS -X POST "${API_BASE}/api/predict" \
  -H "Content-Type: application/json" \
  -d "{\"model\": \"${V1_PREDICT_MODEL}\", \"features\": ${FEATS_JSON}}" | pretty
echo

echo "--- v1 POST /api/risk (pm25 directo) ---"
curl -sS -X POST "${API_BASE}/api/risk" \
  -H "Content-Type: application/json" \
  -d '{"pm25": 28.5, "station": "Francia"}' | pretty
echo

echo "--- v1 POST /api/chat ---"
curl -sS -X POST "${API_BASE}/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola", "session_id": "smoke-test"}' | pretty
echo

echo "--- v2 GET|HEAD /api/v2/health ---"
curl -sS -o /dev/null -w "HEAD HTTP %{http_code}\n" -I -X HEAD "${API_BASE}/api/v2/health"
curl -sS "${API_BASE}/api/v2/health" | pretty
echo

echo "--- v2 GET /api/v2/health/freshness ---"
curl -sS "${API_BASE}/api/v2/health/freshness" | pretty
echo

echo "--- v2 POST /api/v2/predict ---"
curl -sS -X POST "${API_BASE}/api/v2/predict" \
  -H "Content-Type: application/json" \
  -d '{"station": "Francia"}' | pretty
echo

echo "--- v2 POST /api/v2/risk ---"
curl -sS -X POST "${API_BASE}/api/v2/risk" \
  -H "Content-Type: application/json" \
  -d '{"station": "Francia"}' | pretty
echo

echo "--- v2 POST /api/v2/profile/recommend ---"
curl -sS -X POST "${API_BASE}/api/v2/profile/recommend" \
  -H "Content-Type: application/json" \
  -d '{"station": "Francia", "profile": {"activity": "caminar"}}' | pretty
echo

echo "--- v2 POST /api/v2/route ---"
curl -sS -X POST "${API_BASE}/api/v2/route" \
  -H "Content-Type: application/json" \
  -d '{"from_station": "Francia", "to_station": "Universidad Politécnica"}' | pretty
echo

echo "--- v2 GET /api/v2/map ---"
curl -sS "${API_BASE}/api/v2/map?pollutant=pm25&horizon=0" | pretty
echo

echo "--- v2 GET /api/v2/timeseries (default 72h) ---"
curl -sS "${API_BASE}/api/v2/timeseries?station=Francia&pollutant=pm25" | pretty
echo

echo "--- v2 GET /api/v2/timeseries?window_hours=24 ---"
curl -sS "${API_BASE}/api/v2/timeseries?station=Francia&pollutant=pm25&window_hours=24" | pretty
echo

echo "--- v2 GET /api/v2/timeseries?window_hours=48 ---"
curl -sS "${API_BASE}/api/v2/timeseries?station=Francia&pollutant=pm25&window_hours=48" | pretty
echo

echo "--- v2 GET /api/v2/stations (catálogo completo GVA RVVCCA) ---"
curl -sS "${API_BASE}/api/v2/stations" | pretty
echo

echo "--- v2 GET /api/v2/stations?only_canonical=true ---"
curl -sS "${API_BASE}/api/v2/stations?only_canonical=true" | pretty
echo

echo "--- v2 GET /api/v2/stations?province=Valencia ---"
curl -sS "${API_BASE}/api/v2/stations?province=Valencia" | pretty
echo

echo "--- v2 GET /api/v2/ranking ---"
curl -sS "${API_BASE}/api/v2/ranking?pollutant=pm25&horizon=0&top=7" | pretty
echo

echo "--- v2 POST /api/v2/chat ---"
curl -sS -X POST "${API_BASE}/api/v2/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hola", "session_id": "smoke-v2"}' | pretty
echo

echo "--- v2 POST /api/v2/_internal/reload (token) ---"
curl -sS -X POST "${API_BASE}/api/v2/_internal/reload" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: ${INTERNAL_TOKEN}" \
  -d '{}' | pretty
echo

echo "--- v2 POST /api/v2/_internal/append_and_reload (token) ---"
curl -sS -X POST "${API_BASE}/api/v2/_internal/append_and_reload" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: ${INTERNAL_TOKEN}" \
  -d '{}' | pretty
echo

echo "--- v2 POST /api/v2/_internal/predict_horizons (token; usa Mongo si está) ---"
curl -sS -X POST "${API_BASE}/api/v2/_internal/predict_horizons" \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: ${INTERNAL_TOKEN}" \
  -d '{}' | pretty
echo

echo "=== Fin smoke (revisa códigos HTTP y success en JSON) ==="
