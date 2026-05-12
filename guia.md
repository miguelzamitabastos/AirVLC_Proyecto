2. Optimización en MongoDB Atlas

Para corregir los "picos extraños" y la lentitud en los gráficos:

    Estructura Time Series: Utiliza las Time Series Collections de MongoDB. Esto optimiza drásticamente las consultas de históricos para Flutter.

    Limpieza de Datos (Data Cleaning):

        Implementar un filtro de "outliers" en la ingesta. Si un valor de PM2.5 salta de 10 a 500 en una hora y vuelve a 10, descartar el pico como error de sensor (frecuente en estaciones automáticas sin validar).

    Índices: Asegúrate de tener índices en fecha (descendente) y estacion.

3. Integración en Flutter (App)

Sustitución de la lógica de WAQI por tu propia API o conexión directa a Atlas.
Cambio de Proveedor (Data Provider)

    Eliminar: Llamadas a api.waqi.info.

    Nuevo Flujo: - La App consulta un endpoint de tu backend (o un servicio de Atlas Device Sync) que devuelva el último registro para el chip y los últimos 24/48/72 registros para la serie temporal.

    Estado del Chip:

        Verde: Si DateTime.now().difference(fechaDato) < 2 horas.

        Amarillo: Si es > 2 horas.

        Rojo: Si no hay datos en 24h.

Visualización de Gráficos

    Usar fl_chart o syncfusion_flutter_charts.

    Manejo de Huecos: Si falta una hora en la serie temporal, no dibujes el punto en 0 (eso genera los picos raros), usa interpolación lineal o deja el hueco visualmente para mantener la escala temporal real.

4. Alimentación del Modelo de Predicción

Tus predicciones a 24, 48 y 72 horas ahora serán más precisas:

    Input Fijo: El modelo leerá de MongoDB los datos reales de la GVA de las últimas 24h.

    Coherencia: Al usar estaciones oficiales, el ruido en el entrenamiento del modelo ML disminuirá significativamente comparado con los datos "vecinos" de WAQI que a veces daban datos de Murcia.

5. Checklist de Validación para "Chip Verde"

    [ ] ¿El script de Python corre cada hora sin fallos?

    [ ] ¿Los datos en MongoDB coinciden con lo que muestra el portal de la GVA?

    [ ] ¿La App de Flutter muestra la hora de la última actualización?

    [ ] ¿Se han eliminado los valores "nulos" o "0" falsos de la serie temporal?

Este plan garantiza que la aplicación sea una herramienta profesional de vigilancia atmosférica basada en datos gubernamentales validados.
"""

with open("Plan_Implementacion_GVA_RealTime.md", "w", encoding="utf-8") as f:
f.write(markdown_content)

print("Plan_Implementacion_GVA_RealTime.md")

### Resumen de la estrategia

He estructurado el plan en 4 fases clave para atacar exactamente los problemas que mencionas:

1.  **Motor de Ingesta (El puente):** No puedes conectar Flutter directamente a la GVA. Necesitas un pequeño *worker* (ej. un script de Python en la nube) que lea de la GVA cada hora y guarde en tu base de datos de Mongo Atlas. Esto soluciona la **frescura (chip verde)**.
2.  **Arquitectura en Atlas:** Almacenar los datos como series temporales (`Time Series Collections`). Esto es vital para que las gráficas no tarden en cargar.
3.  **Filtrado de "Picos":** El problema de las gráficas (los saltos raros) suele darse cuando una fuente falla y devuelve un "0" o un nulo, y la gráfica cae en picado para luego subir. En el plan te explico cómo Flutter debe manejar esto (no dibujando el cero, sino interpolando o dejando el hueco).
4.  **Despliegue en Flutter:** Quitar las URLs de WAQI y apuntar al endpoint de tu backend que lee de Atlas, basando el color del chip estrictamente en la diferencia horaria entre el `timestamp` del último registro y la hora actual del dispositivo.

Revisa el documento y dime si quieres que profundicemos en el código de alguna de las partes, como el script exacto de ingesta o el manejo del *Provider* en Flutter.
