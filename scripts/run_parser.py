import sys
from pathlib import Path
base = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base))
from scripts.parser import parse_xls
p=Path(base)/'ficheros_a_convertir'
files=list(p.glob('*.xls'))+list(p.glob('*.xlsx'))
print('FOUND', len(files))
if files:
    dt, df = parse_xls(files[0])
    print('DATE', dt)
    print('DF', None if df is None else df.shape)
    if df is not None:
        print(df.head().to_string())
else:
    print('No files')
