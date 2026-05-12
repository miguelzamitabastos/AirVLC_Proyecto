markdown_content = """# Plan de Implementación: Migración a Datos de Tiempo Real (GVA) para Valencia

Este documento detalla los pasos técnicos para migrar la fuente de datos de WAQI a la API oficial de la Generalitat Valenciana (GVA), optimizando el almacenamiento en MongoDB Atlas y la visualización en la aplicación Flutter.

## 1. Fase de Ingesta: El "Motor de Tiempo Real" (Python)

Para obtener el "chip verde", necesitamos un script que actúe como puente entre la GVA y tu base de datos.

### Acción: Script de Ingesta Programado
- **Tecnología:** Python (ideal para manipulación de datos).
- **Frecuencia:** Ejecución cada 60 minutos (vía GitHub Actions o un Cron Job).
- **Lógica:**
    1. Llamar al endpoint `datastore_search` de la GVA filtrando por el municipio "VALÈNCIA".
    2. Filtrar los contaminantes específicos: `PM2.5`, `NO2`, `O3`.
    3. Mapear los campos de la GVA a tu esquema de MongoDB.
    4. **Upsert:** Usar una clave compuesta (ID_Estacion + Timestamp) para evitar duplicados si la API devuelve datos ya procesados.