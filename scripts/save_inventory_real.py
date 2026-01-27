import sys
from pathlib import Path
base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base))
from scripts.parser import parse_xls

file = base / 'inventario_actual.xls'
if not file.exists():
    print('No inventario_actual.xls in project root')
    sys.exit(1)

date, table = parse_xls(file)
if table is None or table.empty:
    print('No product rows extracted')
    sys.exit(1)

if 'Col_16' not in table.columns:
    print('Col_16 not found')
    sys.exit(1)

out = table[['Codigo','Articulo','Unidad_de_Medida','Col_16']].rename(columns={'Col_16':'Real'})
dest = base / 'inventario_actual'
dest.mkdir(exist_ok=True)
target = dest / 'inventario_real.csv'
if target.exists():
    target.unlink()
out.to_csv(target, index=False, encoding='utf-8')
print('Saved', target)
