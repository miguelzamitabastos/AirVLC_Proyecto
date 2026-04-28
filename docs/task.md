# Tareas Semana 1 — Martes 29 y Miércoles 30

## Martes 29 — PostgreSQL
- [x] Crear script `src/scripts/load_postgres.py`
  - [x] Esquema DDL (4 tablas + índices)
  - [x] Carga GeoJSON → tabla `estaciones`
  - [x] Carga CSV calidad aire → tabla `mediciones_aire` (~449K filas)
  - [x] Carga CSV ruido Russafa → tabla `ruido_russafa`
  - [x] Carga CSV emisiones GEI → tabla `emisiones_gei`
- [x] Ejecutar y verificar carga PostgreSQL

## Miércoles 30 — Elasticsearch / Logstash
- [x] Crear `docker/logstash/config/logstash.yml`
- [x] Crear `docker/logstash/pipeline/logstash.conf`
- [x] Modificar `docker-compose.yml` (añadir servicio Logstash)
- [x] Crear `src/scripts/verify_elasticsearch.py`
- [x] Levantar Logstash y verificar indexación en ES
