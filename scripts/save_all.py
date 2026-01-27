import sys
from pathlib import Path
base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base))
from scripts.parser import parse_xls

src = base / 'ficheros_a_convertir'
dst = base / 'consumo_teorico'
dst.mkdir(parents=True, exist_ok=True)
files = list(src.glob('*.xls')) + list(src.glob('*.xlsx'))
if not files:
    print('NO_EXCEL_FOUND')
    sys.exit(0)

results = []
for file in files:
    try:
        date, table = parse_xls(file)
    except Exception as e:
        results.append((file.name, 'ERROR', str(e)))
        continue
    if date is None:
        results.append((file.name, 'NO_DATE', 'No se encontró fecha interna'))
        continue
    if table is None or table.empty:
        results.append((file.name, 'NO_PRODUCTS', 'No se extrajeron líneas de producto'))
        continue
    cons_col = None
    for cand in ['Col_10', 'Col_9', 'Col_11', 'Col_8', 'Col_12']:
        if cand in table.columns:
            cons_col = cand
            break
    if cons_col is None:
        for coln in table.columns:
            if coln not in ('Codigo','Articulo','Unidad_de_Medida'):
                cons_col = coln
                break
    if cons_col is None:
        results.append((file.name, 'NO_CONS_COL', 'No se localizó columna Consumo'))
        continue
    save_df = table[['Codigo','Articulo','Unidad_de_Medida',cons_col]].rename(columns={cons_col:'Consumo'})
    fname = date.strftime('%d-%m-%y') + '.csv'
    target = dst / fname
    try:
        if target.exists():
            target.unlink()
        save_df.to_csv(target, index=False, encoding='utf-8')
        results.append((file.name, 'SAVED', str(target)))
    except Exception as e:
        results.append((file.name, 'ERROR_SAVE', str(e)))

for r in results:
    print(r)
