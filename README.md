# Pedido Camión — App de Estimación

Esta es una aplicación inicial para trabajar la estimación de pedidos por camión.

Requisitos
- Python 3.9+

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
- `app.py`: app Streamlit inicial
- `requirements.txt`: dependencias
- `consumo_teorico/` y `inventario_actual/`: carpetas con CSV (conservadas)

Sigue editando `app.py` para añadir tu lógica de estimación.
