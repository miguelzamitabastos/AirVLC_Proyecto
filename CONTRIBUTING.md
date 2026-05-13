# Guía de contribución a AirVLC

Gracias por tu interés en contribuir a AirVLC. Este documento describe cómo configurar el entorno de desarrollo, los criterios de calidad que sigue el proyecto y el procedimiento recomendado para proponer cambios.

## Tabla de contenidos

1. [Configuración inicial](#configuración-inicial)
2. [Dataset histórico](#dataset-histórico)
3. [Flujo de trabajo](#flujo-de-trabajo)
4. [Estilo de código](#estilo-de-código)
5. [Tests y cobertura](#tests-y-cobertura)
6. [Convenciones de commits](#convenciones-de-commits)
7. [Reporte de incidencias](#reporte-de-incidencias)
8. [Código de conducta](#código-de-conducta)

## Configuración inicial

### Requisitos previos

| Componente | Versión mínima | Recomendado |
|---|---|---|
| Python | 3.11 | 3.11.x |
| Flutter | 3.41 | 3.41.9 |
| Docker | 24.0 | 25.0 o superior |
| Docker Compose | v2 | v2.20 o superior |
| Memoria RAM | 8 GB | 16 GB |
| Espacio en disco | 20 GB libres | 40 GB |

### Pasos de instalación

Clona el repositorio y prepara el entorno virtual de Python:

```bash
git clone https://github.com/miguelzamitabastos/AirVLC_Proyecto.git
cd AirVLC_Proyecto

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov pytest-xdist ruff black bandit
```

Levanta la infraestructura de bases de datos y servicios auxiliares:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Esto inicia los siguientes servicios:

- PostgreSQL en `localhost:5432`
- MongoDB en `localhost:27017`
- Elasticsearch en `localhost:9200`
- Kibana en `localhost:5601`
- Redis en `localhost:6379`
- Node-RED en `localhost:1880`

Verifica que todos los servicios están en estado saludable:

```bash
docker compose -f docker/docker-compose.yml ps
```

### Variables de entorno

Crea un archivo `.env` en la raíz del proyecto a partir de la plantilla:

```bash
cp .env.example .env
```

Edita el archivo con tus credenciales locales. Las variables sensibles (claves de AWS, URI de Mongo en producción, tokens de servicios externos) **nunca** deben subirse al repositorio. El archivo `.env` está incluido en `.gitignore`.

## Dataset histórico

El modelo de aprendizaje profundo se entrena sobre el dataset histórico publicado por el Ajuntament de València. Este dataset no se incluye en el repositorio por motivos de tamaño y se debe descargar una sola vez como parte de la configuración inicial.

### Descarga manual

1. Accede al portal de datos abiertos del Ajuntament:
   https://opendata.vlci.valencia.es/dataset/hourly-air-quality-data-since-2016

2. Descarga el fichero CSV completo desde el botón "Descargar" del portal.

3. Guárdalo en la ruta:

   ```
   data/raw/rvvcca_historic_ayto.csv
   ```

4. Ejecuta el script de preprocesado, que normaliza nombres de columna, gestiona valores nulos y genera el dataset canónico:

   ```bash
   python -m src.scripts.prepare_historical_data
   ```

   El resultado se escribe en `data/processed/master_dataset_v2.csv`.

### Descarga programática vía API CKAN

Como alternativa, se puede consultar la API CKAN del portal:

```bash
curl -o data/raw/rvvcca_historic_ayto.json \
  "https://opendata.vlci.valencia.es/api/3/action/datastore_search?resource_id=4be7248b-9597-4017-89af-82a9b6e2382f&limit=32000"
```

Ten en cuenta que la API limita cada petición a 32 000 registros y que el dataset completo supera los 449 000 registros, por lo que es necesario paginar con el parámetro `offset`. El script `src/scripts/download_via_ckan.py` automatiza este proceso.

### Datos en tiempo real

Para la operación en producción, los datos se ingieren cada hora desde la RVVCCA de la Generalitat Valenciana a través del workflow de GitHub Actions `ingesta_v2.yml`. Esta ingesta es totalmente automática y no requiere intervención manual.

## Flujo de trabajo

El proyecto sigue un flujo de trabajo basado en ramas:

- **`main`**: rama de producción. Sólo se mergea desde `develop` o desde ramas de hotfix tras pasar todos los workflows de CI.
- **`develop`**: rama de integración. Se mergean aquí las ramas de feature antes de promocionar a `main`.
- **`feature/nombre-de-la-feature`**: ramas de trabajo para nuevas funcionalidades.
- **`fix/nombre-del-bug`**: ramas de trabajo para correcciones puntuales.

### Crear una contribución

1. Crea una rama desde `develop`:

   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/mi-nueva-funcionalidad
   ```

2. Realiza tus cambios y asegúrate de que los tests pasan localmente:

   ```bash
   bash scripts/run_tests.sh
   ```

3. Haz commit siguiendo las convenciones descritas más abajo:

   ```bash
   git add .
   git commit -m "feat(modulo): descripción breve del cambio"
   ```

4. Sube la rama y abre un pull request hacia `develop`:

   ```bash
   git push origin feature/mi-nueva-funcionalidad
   ```

5. Los workflows de CI se ejecutarán automáticamente. No mergees hasta que los cuatro workflows estén en verde.

## Estilo de código

### Python

Se utiliza **ruff** para el análisis estático y **black** para el formateo automático. Configuración:

- Longitud máxima de línea: 120 caracteres
- Indentación: 4 espacios
- Imports ordenados con isort (integrado en ruff)
- Strings con comillas dobles

Antes de cada commit, ejecuta:

```bash
ruff check src/ tests/
black src/ tests/
```

### Dart / Flutter

Se sigue la guía oficial de estilo de Dart. Antes de hacer commit en la aplicación:

```bash
cd app
flutter analyze
dart format lib/ test/
```

### Documentación

Toda función pública del backend Python debe incluir docstring siguiendo el formato Google. Ejemplo:

```python
def calcular_aqi(pm25: float, no2: float) -> int:
    """Calcula el Air Quality Index a partir de valores de contaminantes.

    Args:
        pm25: Concentración de PM2.5 en μg/m³.
        no2: Concentración de NO2 en μg/m³.

    Returns:
        Valor entero del AQI en el rango 0-500.

    Raises:
        ValueError: Si alguno de los valores es negativo.
    """
```

## Tests y cobertura

El proyecto mantiene una suite de tests organizada en tres categorías:

- `tests/api/`: tests de contratos de la API REST
- `tests/ingestion/`: tests de clientes de ingesta y parsers
- `tests/ml/`: tests del pipeline de machine learning

### Ejecutar tests

Para ejecutar la suite completa con cobertura:

```bash
bash scripts/run_tests.sh
```

Para ejecutar un subconjunto:

```bash
pytest tests/api/ -v                          # Sólo tests de la API
pytest tests/ml/test_feature_eng.py -v        # Un archivo concreto
pytest tests/ -k "test_health" -v             # Tests cuyo nombre contiene "test_health"
```

### Añadir nuevos tests

Toda nueva funcionalidad debe ir acompañada de tests. Como criterio orientativo:

- Funciones puras: tests unitarios con casos típicos, límite y de error
- Endpoints de la API: tests de contrato (formato de respuesta y códigos HTTP)
- Pipelines de ML: tests que verifiquen propiedades invariantes (shapes, rangos, monotonía)

## Convenciones de commits

Se sigue el estándar [Conventional Commits](https://www.conventionalcommits.org/) con los siguientes tipos:

| Tipo | Uso |
|---|---|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Cambios en documentación |
| `style` | Formateo, sin cambio funcional |
| `refactor` | Refactorización sin cambio de comportamiento |
| `test` | Añadir o modificar tests |
| `chore` | Tareas de mantenimiento (deps, config, etc.) |
| `ci` | Cambios en pipelines de CI/CD |
| `perf` | Mejora de rendimiento |

Ejemplos:

```
feat(api): add /predict/batch endpoint for multi-station forecasts
fix(ingestion): handle missing PM2.5 values in GVA CSV parser
docs(readme): update results table with walk-forward CV metrics
ci(tests): increase pytest timeout for slow ML tests
```

## Reporte de incidencias

Si encuentras un problema o tienes una sugerencia, abre una issue en el repositorio describiendo:

1. Comportamiento observado
2. Comportamiento esperado
3. Pasos para reproducirlo
4. Entorno (sistema operativo, versión de Python, versión de Flutter)
5. Capturas de pantalla o logs relevantes (si aplica)

Para vulnerabilidades de seguridad, contacta directamente con el autor por canales privados en lugar de abrir una issue pública.

## Código de conducta

Este proyecto se adhiere al espíritu del Contributor Covenant. Esperamos que toda interacción en el repositorio (issues, pull requests, discusiones) sea respetuosa, constructiva y centrada en el trabajo técnico. No se tolerarán comportamientos discriminatorios, acosadores o que perjudiquen el ambiente colaborativo.

## Licencia

Al contribuir a AirVLC aceptas que tus aportaciones se distribuyan bajo la licencia MIT del proyecto.
