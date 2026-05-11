# Sprint 3 — Walkthrough (stub)

> Rellenar al cierre del sprint con comandos reales, capturas y latencias.

## Qué se añadió

- Rutas `/api/v2/*` (multitarget)
- Extractor v2 (44 features)
- Clasificador de riesgo ICA-like (peor de 3 contaminantes)
- Indexación a `airvlc-predictions-v2`

## Comandos de demo (pendiente)

### Health

```bash
curl -s localhost:5001/api/v2/health | jq
```

### Predict

```bash
curl -s -X POST localhost:5001/api/v2/predict \
  -H "Content-Type: application/json" \
  -d '{"station":"Politécnico"}' | jq
```

### Risk

```bash
curl -s -X POST localhost:5001/api/v2/risk \
  -H "Content-Type: application/json" \
  -d '{"station":"Politécnico"}' | jq
```

## Resultados y métricas (pendiente)

- Latencia p50/p95 en M1/M2:
- Docs indexados en `airvlc-predictions-v2`:

## Referencias

- Sprint 2: [`../sprint2/walkthrough.md`](../sprint2/walkthrough.md)

