import pandas as pd
from pathlib import Path
files = [
    Path('congelado/1_2_2026_233329_infProveedor.xls'),
    Path('fresco/1_2_2026_233335_infProveedor.xls'),
    Path('seco/1_2_2026_233322_infProveedor.xls'),
]
for f in files:
    print('---', f)
    try:
        df = pd.read_excel(f, engine='xlrd')
    except Exception as e:
        try:
            df = pd.read_excel(f)
        except Exception as e2:
            print('ERROR reading', f, e, e2)
            continue
    print('Columns:', list(df.columns))
    # print first 20 rows to inspect where header may sit
    for i in range(min(20, len(df))):
        row = df.iloc[i].fillna('')
        # join truncated preview
        preview = ' | '.join([str(x)[:40] for x in row.tolist()])
        print(f'ROW {i}:', preview)

    # try to auto-detect header row: look for cells containing common header names
    header_candidates = ['codigo', 'codigo', 'articulo', 'artículo', 'unidad', 'embalaje', 'nombre']
    found = None
    for i in range(min(30, len(df))):
        row_vals = [str(x).lower() for x in df.iloc[i].tolist()]
        if any(any(h in v for v in row_vals) for h in header_candidates):
            found = i
            break
    if found is not None:
        print('Detected header row at index', found, '->', df.iloc[found].tolist())
    else:
        print('No obvious header row detected in first 30 rows')
