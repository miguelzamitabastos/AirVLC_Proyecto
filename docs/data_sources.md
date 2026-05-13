# Fuentes de Datos

## Dataset Histórico (2016–2021): Portal de Datos Abiertos del Ayuntamiento de Valencia

- **URL**: https://opendata.vlci.valencia.es/dataset/hourly-air-quality-data-since-2016
- **Plataforma**: VLCi (CKAN)
- **Volumen**: 449.026 registros horarios
- **Estaciones**: Av. França, Bulevard Sud, Molí del Sol, Pista Silla, Politècnic, Vivers, Centre, Conselleria Meteo, Natzaret Meteo, Port València
- **Variables**: PM1, PM2.5, PM10, NO, NO₂, NOx, O₃, SO₂, CO, NH₃, C₆H₆, C₇H₈, C₈H₁₀, velocidad/dirección viento, temperatura, humedad, presión, radiación solar, precipitación
- **Formato descarga**: CSV
- **Licencia**: Creative Commons Attribution (CC-BY)

**Uso en AirVLC**: 
- Dataset íntegro para entrenar el modelo LSTM-Attention-Multi (§3.5)
- Análisis exploratorio de datos (EDA, §3.3)
- Validación temporal (walk-forward CV, §3.4)
- Archivo local: `data/raw/rvvcca_historic_2016_2021.csv`

**Nota técnica**: El portal CKAN del Ayuntamiento no actualiza este dataset
desde 2021. El endpoint `datastore_upsert` de la API requiere autenticación
específica no disponible públicamente. Ver §2.2 para detalles sobre el diseño
de la ingesta en producción.

---

## Datos en Tiempo Real (Producción): RVVCCA — Generalitat Valenciana

- **Fuente**: Red de Vigilancia y Control de Contaminación Atmosférica (RVVCCA)
- **Proveedor**: Generalitat Valenciana
- **Acceso**: Web scraping de CSV horario (descarga automática)
- **URL base**: https://terramapas.icv.gva.es/
- **Actualización**: cada hora (comprobado: retraso < 2h respecto a la lectura sensor)
- **Variables**: idénticas al dataset histórico (PM2.5, NO₂, O₃, etc.)
- **Formato**: CSV
- **Licencia**: [Por confirmar con GVA]

**Uso en AirVLC**:
- Ingesta horaria automática vía GitHub Actions (`.github/workflows/ingesta_v2.yml`)
- Predicción LSTM a 24–48h (modelo entrenado con datos 2016–2021 del Ayuntamiento)
- Alertas y clasificación de riesgo en tiempo real
- Visualización en Kibana (últimas 72h)
- Consumo por app Flutter (última hora disponible + predicción)

**Justificación de dos fuentes**:

El proyecto cumple el requisito de Base 5 ("utilisant conjunts de dades del
Portal de Dades Obertes de l'Ajuntament") usando el dataset histórico del
Ayuntamiento para todo el desarrollo, validación y entrenamiento del modelo.

Para la operación en producción, utiliza la RVVCCA de la Generalitat porque:
1. El mismo sensor network es gestionado por la GVA con actualización horaria
2. El portal del Ayuntamiento no actualiza desde 2021 (último registro: 31 dic 2021)
3. El sistema necesita datos frescos (<2h) para predicciones confiables
4. Ambas fuentes son idénticas en esquema y variables

Este enfoque dual (histórico del Ayuntamiento + tiempo real de GVA) maximiza
la trazabilidad de datos públicos mientras garantiza operabilidad en vivo.

---

## Arquitectura de Ingesta