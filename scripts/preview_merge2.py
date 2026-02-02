import pandas as pd
from pathlib import Path

def parse_and_merge(path: Path):
    try:
        raw = pd.read_excel(path, header=None, engine='xlrd' if path.suffix.lower()=='.xls' else 'openpyxl')
    except Exception:
        raw = pd.read_excel(path, header=None)

    header_keywords = ['articulo', 'artículo', 'codigo', 'código', 'unid', 'unid. totales', 'medida', 'embalaje', 'nombre']
    header_row = None
    max_search = min(40, len(raw))
    for i in range(max_search):
        row_vals = [str(x).strip().lower() if pd.notna(x) else '' for x in raw.iloc[i].tolist()]
        matches = sum(1 for h in header_keywords if any(h in v for v in row_vals))
        if matches >= 2:
            header_row = i
            break
    if header_row is None:
        header_row = 0

    header = raw.iloc[header_row].astype(str).tolist()
    df = raw.iloc[header_row+1:].copy()
    df.columns = [str(c).strip() for c in header]

    def find_col(dfcols, candidates):
        lower_map = {str(c).strip().lower(): c for c in dfcols}
        for cand in candidates:
            if cand.lower() in lower_map:
                return lower_map[cand.lower()]
        for cand in candidates:
            for lc, orig in lower_map.items():
                if cand.lower() in lc or lc in cand.lower():
                    return orig
        return None

    name_col = find_col(df.columns, ['Articulo', 'Artículo', 'Nombre'])
    code_col = find_col(df.columns, ['Codigo', 'Código', 'Cod'])
    units_col = find_col(df.columns, ['Unid. Totales', 'Unid Totales', 'Unidades totales', 'Unidades', 'Total'])
    measure_col = find_col(df.columns, ['Medida', 'Unidad_de_Medida', 'Unidad'])
    pack_col = find_col(df.columns, ['Embalaje', 'Packaging', 'Envase'])

    out = []
    i = 0
    n = len(df)
    while i < n:
        row = df.iloc[i]
        name_val = row.get(name_col) if name_col is not None else None
        code_val = row.get(code_col) if code_col is not None else None
        units_val = row.get(units_col) if units_col is not None else None
        measure_val = row.get(measure_col) if measure_col is not None else None
        pack_val = row.get(pack_col) if pack_col is not None else None

        merged = False
        if (pd.isna(code_val) or str(code_val).strip() == '' or str(code_val).strip().lower() in ('nan','none')) and name_val and (i+1) < n:
            row2 = df.iloc[i+1]
            code2 = row2.get(code_col) if code_col is not None else None
            units2 = row2.get(units_col) if units_col is not None else None
            measure2 = row2.get(measure_col) if measure_col is not None else None
            pack2 = row2.get(pack_col) if pack_col is not None else None
            if (pd.notna(code2) and str(code2).strip() not in ('','nan','None')) or (pd.notna(units2) and str(units2).strip() not in ('','nan','None')):
                out.append({'Nombre': name_val, 'Codigo': code2, 'Unidades totales': units2, 'Medida': measure2, 'Embalaje': pack2})
                merged = True

        if not merged:
            out.append({'Nombre': name_val, 'Codigo': code_val, 'Unidades totales': units_val, 'Medida': measure_val, 'Embalaje': pack_val})
        i += 2 if merged else 1

    return out


if __name__ == '__main__':
    for folder in ['fresco','congelado','seco']:
        print('---', folder)
        p = Path(folder)
        files = list(p.glob('*.xls')) + list(p.glob('*.xlsx'))
        for f in files:
            print('FILE:', f)
            rows = parse_and_merge(f)
            for r in rows[:15]:
                print(r)
            print('Total parsed:', len(rows))
            print()
