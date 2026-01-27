from scripts.parser import parse_xls
from pathlib import Path
p=Path('ficheros_a_convertir')
files=list(p.glob('*.xls'))+list(p.glob('*.xlsx'))
print('FOUND', len(files))
if files:
    dt, df = parse_xls(files[0])
    print('DATE', dt)
    print('DF', None if df is None else df.shape)
    print(df.head())
else:
    print('No files')
