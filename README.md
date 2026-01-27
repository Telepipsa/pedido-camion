# Pedido Camión — App de Estimación

Esta es una aplicación inicial para trabajar la estimación de pedidos por camión.

Requisitos
- Python 3.10+ (probado con 3.10/3.11)

Instalación rápida

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1   # PowerShell
pip install -r requirements.txt
```

Ejecutar la app

```powershell
streamlit run app.py
```

Estructura mínima generada
Herramienta Streamlit para preparar el pedido del camión a partir de consumos teóricos, ventas y
un inventario real. Incluye utilidades para convertir ficheros XLS/XLSX a CSV, emparejar ficheros
de consumo con ventas reales/estimadas y calcular una `Cantidad a pedir` por artículo con reglas
operativas (colchón, desperdicio, ajuste por diferencia de totales y manejo especial para masas).

## Requisitos

- Dependencias: ver `requirements.txt` (principalmente `pandas`, `streamlit`, `openpyxl`)

Instalar dependencias:

```bash
python -m pip install -r requirements.txt
```

## Ejecutar la app

```bash
streamlit run app.py
```

La interfaz abre en el navegador. La barra lateral contiene controles de conversión y cargadores de
ficheros; la página principal permite seleccionar el rango de fechas y calcular las ventas y el pedido.

## Flujo y ficheros relevantes

- `consumo_teorico/`: CSVs con consumo teórico. Se generan desde XLS/XLSX usando los botones o
	subiendo XLS a la barra lateral (días sueltos o bulk).
- `ficheros_a_convertir/`: carpeta temporal para XLS que quieras convertir manualmente con el botón
	"Convertir todos los XLS".
- `ficheros_a_convertir_bulk/`: carpeta para ficheros bulk (se usa el botón "Convertir bulk XLS (añadir segundo jueves)").
- `inventario_actual/inventario_real.csv`: CSV con la columna `Real` generado desde `inventario_actual.xls`.

## Subir ficheros (barra lateral)

1. Subir un XLS/XLSX como inventario actual — se guarda como `inventario_actual.xls` en la raíz.
2. Subir varios XLS/XLSX de consumo (días sueltos) — se guardan en `ficheros_a_convertir/`.
3. Subir varios XLS/XLSX de consumo (bulk) — se guardan en `ficheros_a_convertir_bulk/`.

También hay botones para convertir las carpetas en lote y generar CSV en `consumo_teorico/`.

## Interfaz principal

- Selector de rango de fechas: define la ventana para las ventas.
- Botón `Calcular ventas`: calcula totales (ventas reales y estimadas), busca combinación de ficheros
	de `consumo_teorico` que aproxime las ventas y genera tablas con:
	- `Cantidad a pedir` (reglas: +20% consumo, -4% inventario disponible, ajuste por diferencia de totales).
	- `Productos a Revisar` (artículos en inventario que no están en consumo agregado y viceversa).
	- `Consumo agregado` y `Inventario actual`.

Controles importantes:

- `Evitar usar ficheros con jueves` (toggle): cuando está ON se preferirán ficheros sin jueves si hay alternativas.
- `Ocultar cantidad 0`: checkbox que aparece encima de la tabla `Cantidad a pedir` (activo por defecto) y
	oculta filas con cantidad a pedir igual a 0.
- Filtrado: artículos cuyo `Articulo` empieza por `ZZ` o `YY` se excluyen del pedido y de `Productos a Revisar`.

## Reglas especiales

- Nombres de ficheros en `consumo_teorico` pueden ser `DD-MM-YY.csv` o rangos `DD-MM-YY_DD-MM-YY.csv`.
	Los rangos se interpretan como días consecutivos y se suman las ventas por día.
- Masas (códigos `BF`, `BM`, `BP`): se añaden 4 días extra de consumo basados en ventas estimadas
	si no hubiera consumo directo para esos días; el cálculo reparte la masa necesaria por participación histórica.

## Ubicación de resultados

- Las tablas se muestran en la app y se conservan en `st.session_state` para permitir filtros sin recalcular.
- `inventario_real.csv` se guarda en `inventario_actual/`.

## Contribuir / desplegar

- Repositorio remoto: https://github.com/Telepipsa/pedido-camion.git
- Para contribuciones, crear ramas y PR desde `main`.

## Contacto

Si necesitas ajustes (guardar CSVs automáticamente, cambiar fórmulas, añadir validaciones), dime exactamente
qué criterio quieres y lo implemento.

Sigue editando `app.py` para añadir tu lógica de estimación.
