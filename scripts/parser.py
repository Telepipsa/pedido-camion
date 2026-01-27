from pathlib import Path
import re
from datetime import datetime
import pandas as pd


UNIT_WORDS = ['Kilogramo', 'Bola', 'Litro', 'Gramo', 'Unidad']
UNIT_RE = r"\b(" + "|".join(UNIT_WORDS) + r")\b"


def _read_excel_fallback(path: Path):
    try:
        return pd.read_excel(path, header=None, dtype=object)
    except Exception:
        try:
            import xlrd
            wb = xlrd.open_workbook(path)
            sheet = wb.sheet_by_index(0)
            data = []
            for r in range(sheet.nrows):
                row = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
                data.append(row)
            return pd.DataFrame(data)
        except Exception:
            raise


def extract_date(df: pd.DataFrame):
    """Buscar la fecha de grabación en el DataFrame. Devuelve datetime o None."""
    patterns = [
        re.compile(r'Fecha de grabaci[oó]n\s*[:\-]?\s*(\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}:\d{2})', re.IGNORECASE),
        re.compile(r'(\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}:\d{2})'),
        re.compile(r'(\d{1,2}/\d{1,2}/\d{4})'),
    ]

    def norm(s):
        try:
            return re.sub(r'\s+', ' ', str(s)).strip()
        except Exception:
            return ''

    # scan all cells generally for direct text dates
    for val in df.values.flatten():
        s = norm(val)
        if not s:
            continue
        for p in patterns:
            m = p.search(s)
            if m:
                found = m.group(1)
                # try to parse
                for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y'):
                    try:
                        return datetime.strptime(found, fmt)
                    except Exception:
                        continue

    # if not found, look for label cell 'Fecha de grabación' and check neighbors (e.g., excel serial in column D)
    rows, cols = df.shape
    for r in range(rows):
        for c in range(cols):
            cell = norm(df.iat[r, c]).strip("'\"")
            if 'fecha de grabaci' in cell.lower():
                # check right cells for date-like values or numeric excel serial
                for c2 in range(c + 1, min(cols, c + 6)):
                    v = df.iat[r, c2]
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        continue
                    # numeric serial
                    try:
                        if isinstance(v, (int, float)):
                            dt = pd.to_datetime(v, unit='d', origin='1899-12-30', errors='coerce')
                            if not pd.isna(dt):
                                return dt.to_pydatetime()
                    except Exception:
                        pass
                    s2 = norm(v)
                    # remove surrounding quotes
                    s2 = s2.strip("'\"")
                    # try direct parse
                    for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S'):
                        try:
                            return datetime.strptime(s2, fmt)
                        except Exception:
                            continue
    return None


def parse_products(df: pd.DataFrame):
    """Extrae filas de productos buscando el código al inicio en mayúsculas
    y la unidad entre las palabras definidas. Devuelve lista de dicts.
    """
    rows = []

    # regex: code at start (uppercase letters/digits and optional -), then text, then unit word
    code_re = re.compile(r'^([A-Z0-9\-]+)\s+(.+?)\s+' + UNIT_RE, re.IGNORECASE)

    def norm(s):
        try:
            return re.sub(r'\s+', ' ', str(s)).strip()
        except Exception:
            return ''

    nrows, ncols = df.shape
    for r in range(nrows):
        # prefer explicit columns: Codigo in col 0, Articulo in col 2, Unidad in col 7 (based on sample)
        raw_code = norm(df.iat[r, 0]) if ncols > 0 else ''
        raw_article = None
        if ncols > 2:
            raw_article = norm(df.iat[r, 2])
        # try to find first non-empty article to the right if col2 empty
        if not raw_article:
            for c in range(1, min(ncols, 6)):
                v = norm(df.iat[r, c])
                if v:
                    raw_article = v
                    break
        # unit: search up to column 10 for known unit words
        unit_found = ''
        for c in range(min(ncols, 12)):
            v = norm(df.iat[r, c])
            for uw in UNIT_WORDS:
                if uw.lower() in v.lower():
                    unit_found = uw
                    break
            if unit_found:
                break

        # normalize code and article
        code = raw_code.strip("'\"")
        article = (raw_article or '').strip("'\"")
        # remove leading '*' or other markers from article
        article = re.sub(r'^\*+\s*', '', article).strip()

        # match code pattern
        if code and re.match(r'^[A-Z0-9\-]+$', code):
            extras = {}
            col_index = 1
            # collect numeric/other cols from column 3 onwards
            for c2 in range(3, ncols):
                val = df.iat[r, c2]
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    v = ''
                else:
                    v = val
                extras[f'Col_{col_index}'] = v
                col_index += 1

            row = {
                'Codigo': code,
                'Articulo': article,
                'Unidad_de_Medida': unit_found or ''
            }
            row.update(extras)
            rows.append(row)

    return rows


def parse_xls(path: Path):
    """Lee el archivo y devuelve (fecha_datetime, pandas.DataFrame) o (None, None) si falla."""
    df = _read_excel_fallback(path)
    date = extract_date(df)
    products = parse_products(df)
    if not products:
        return date, None
    # build DataFrame, ensure consistent columns
    all_cols = set()
    for p in products:
        all_cols.update(p.keys())
    cols = ['Codigo', 'Articulo', 'Unidad_de_Medida'] + sorted([c for c in all_cols if c.startswith('Col_')], key=lambda x: int(x.split('_')[1]))
    out_rows = []
    for p in products:
        out_rows.append([p.get(col, '') for col in cols])
    out_df = pd.DataFrame(out_rows, columns=cols)

    # Helper to transform values: empty -> 0; if contains comma as decimal separator keep one digit after comma
    def transform_cell(v):
        if v is None:
            return 0
        # pandas NA
        try:
            if isinstance(v, float) and pd.isna(v):
                return 0
        except Exception:
            pass
        s = str(v).strip()
        if s == '' or s.lower() == "nan":
            return 0
        # If cell contains a comma as decimal separator, keep only first digit after comma
        # e.g. '1.305,00' -> '1.305,0'
        if ',' in s:
            # split at last comma to preserve thousands separators with dots
            left, right = s.rsplit(',', 1)
            # take first two digits of right (pad with zeros if needed)
            two = (right + '00')[:2]
            return left + ',' + two
        # If cell contains a dot decimal separator, keep only first digit after dot
        if '.' in s:
            # ensure this is numeric-like
            parts = s.split('.')
            if len(parts) >= 2 and parts[-1].replace('\n','').strip().isdigit():
                left = '.'.join(parts[:-1])
                right = parts[-1]
                two = (right + '00')[:2]
                return left + '.' + two
        return s

    # Apply transformation to all columns except identifiers
    for col in out_df.columns:
        if col in ('Codigo', 'Articulo', 'Unidad_de_Medida'):
            # still replace empty strings with '' trimmed
            out_df[col] = out_df[col].fillna('').astype(str).apply(lambda x: x.strip().strip("'\"") if x and x.lower() != 'nan' else '')
        else:
            out_df[col] = out_df[col].apply(transform_cell)

    return date, out_df
