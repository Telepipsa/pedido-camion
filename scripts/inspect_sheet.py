from pathlib import Path
import sys

base = Path(__file__).resolve().parent.parent
src = base / 'ficheros_a_convertir'
files = list(src.glob('*.xls')) + list(src.glob('*.xlsx'))
if not files:
    print('NO_EXCEL_FOUND')
    sys.exit(0)
file = files[0]
print('FILE:', file)

try:
    import xlrd
    wb = xlrd.open_workbook(file)
    sheet = wb.sheet_by_index(0)
except Exception as e:
    print('XL_READ_ERROR', e)
    sys.exit(1)

def norm(v):
    try:
        return repr(v)
    except Exception:
        return str(v)

print('\n--- First 80 rows, cols A-H (0-7) ---')
for r in range(min(80, sheet.nrows)):
    row = [norm(sheet.cell_value(r, c)) for c in range(min(8, sheet.ncols))]
    joined = ' '.join(row)
    if 'Fecha' in joined or 'grabaci' in joined.lower() or any(u in joined for u in ['Kilogramo','Bola','Litro','Gramo','Unidad','Unidad de']):
        print(f'Row {r}:', row)

print('\n--- All cells containing Fecha or date-like patterns ---')
import re
pat = re.compile(r'\d{1,2}/\d{1,2}/\d{4}')
for r in range(min(200, sheet.nrows)):
    for c in range(min(20, sheet.ncols)):
        v = sheet.cell_value(r,c)
        s = '' if v is None else str(v)
        if 'Fecha' in s or pat.search(s):
            print(f'Cell R{r}C{c}:', repr(v))

print('\nDONE')
