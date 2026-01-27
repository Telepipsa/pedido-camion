from pathlib import Path
import pandas as pd
from datetime import datetime, date, timedelta
import re

SPANISH_MONTHS = {
    'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
    'julio':7,'agosto':8,'septiembre':9,'octubre':10,'noviembre':11,'diciembre':12
}


def parse_spanish_date(s: str):
    if s is None:
        return None
    s = str(s).strip()
    # try ISO/standard first
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if not pd.isna(dt):
            return dt.date()
    except Exception:
        pass
    # match patterns like '27 enero 2026' or '1 febrero 2026'
    m = re.search(r"(\d{1,2})\s+([A-Za-záéíóúñ]+)\s+(\d{4})", s)
    if m:
        day = int(m.group(1))
        monname = m.group(2).lower()
        year = int(m.group(3))
        mon = SPANISH_MONTHS.get(monname)
        if mon:
            return date(year, mon, day)
    # fallback: try direct pandas again with dayfirst
    try:
        dt = pd.to_datetime(s, dayfirst=True, errors='coerce')
        if not pd.isna(dt):
            return dt.date()
    except Exception:
        pass
    return None


def load_real_sales(base: Path):
    f = base / 'venta.xlsx'
    if not f.exists():
        return {}
    df = pd.read_excel(f)
    # expect columns 'fecha' and 'ventas'
    if 'fecha' not in df.columns or 'ventas' not in df.columns:
        # try lowercase
        df.columns = [c.lower() for c in df.columns]
    df['fecha'] = pd.to_datetime(df['fecha'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['fecha']).copy()
    df['date'] = df['fecha'].dt.date
    sales = df.groupby('date')['ventas'].sum().to_dict()
    return sales


def load_estimated_sales(base: Path):
    dirp = base / 'venta_estimada'
    if not dirp.exists():
        return {}
    mapping = {}
    for f in dirp.glob('*.csv'):
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        # find date and value columns
        cols = [c.lower() for c in df.columns]
        date_col = None
        val_col = None
        for c in df.columns:
            lc = c.lower()
            if 'fecha' in lc:
                date_col = c
            if 'venta' in lc and 'estim' in lc or 'venta'==lc or 'ventas'==lc or 'valor' in lc:
                # prefer columna con 'estim' in name
                val_col = c
        # fallback heuristics
        if date_col is None:
            # try first col
            date_col = df.columns[0]
        if val_col is None:
            # try second col
            if len(df.columns) > 1:
                val_col = df.columns[1]
            else:
                val_col = df.columns[0]
        for _, row in df.iterrows():
            raw = row[date_col]
            d = parse_spanish_date(raw)
            if d is None:
                # try pandas parse
                try:
                    dtmp = pd.to_datetime(raw, dayfirst=True, errors='coerce')
                    if not pd.isna(dtmp):
                        d = dtmp.date()
                except Exception:
                    d = None
            if d is None:
                continue
            try:
                val = float(row[val_col])
            except Exception:
                try:
                    s = str(row[val_col]).replace(',', '.')
                    val = float(re.sub(r'[^0-9\.-]','', s))
                except Exception:
                    continue
            mapping[d] = val
    return mapping


def summarize_range(base: Path, start: date, end: date):
    real = load_real_sales(base)
    estim = load_estimated_sales(base)
    # ensure start <= end
    if start > end:
        start, end = end, start
    current = start
    per_day = []
    total_real = 0.0
    total_estim_used = 0.0
    while current <= end:
        if current in real:
            val = float(real[current])
            per_day.append((current, 'real', val))
            total_real += val
        elif current in estim:
            val = float(estim[current])
            per_day.append((current, 'estimada', val))
            total_estim_used += val
        else:
            per_day.append((current, 'missing', 0.0))
        current = current + timedelta(days=1)
    total = total_real + total_estim_used
    return {
        'per_day': per_day,
        'total_real': total_real,
        'total_estim_used': total_estim_used,
        'total': total
    }
