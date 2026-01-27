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
file = files[0]
print('Processing', file)
date, table = parse_xls(file)
if date is None:
    print('NO DATE FOUND')
    sys.exit(0)
if table is None or table.empty:
    print('NO PRODUCTS FOUND')
    sys.exit(0)
# choose consumo column
cons_col = None
for cand in ['Col_10', 'Col_9', 'Col_11', 'Col_8', 'Col_12']:
    if cand in table.columns:
        cons_col = cand
        break
if cons_col is None:
    for col in table.columns:
        if col not in ('Codigo','Articulo','Unidad_de_Medida'):
            cons_col = col
            break
if cons_col is None:
    print('No consumption column found')
    sys.exit(1)
save_df = table[['Codigo','Articulo','Unidad_de_Medida',cons_col]].rename(columns={cons_col:'Consumo'})
fname = date.strftime('%d-%m-%y') + '.csv'
target = dst / fname
if target.exists():
    target.unlink()
save_df.to_csv(target, index=False, encoding='utf-8')
print('Saved', target)
