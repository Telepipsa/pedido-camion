from pathlib import Path
import pandas as pd
base = Path(__file__).resolve().parent.parent
venta_xls = base / 'venta.xlsx'
estim_dir = base / 'venta_estimada'
print('venta.xlsx exists:', venta_xls.exists())
if venta_xls.exists():
    try:
        df = pd.read_excel(venta_xls)
        print('venta.xlsx columns:', df.columns.tolist())
        print('venta.xlsx sample:')
        print(df.head(10).to_string())
    except Exception as e:
        print('Error reading venta.xlsx:', e)

if estim_dir.exists():
    for f in estim_dir.glob('*.csv'):
        try:
            dfe = pd.read_csv(f)
            print('\nestim file:', f.name)
            print('columns:', dfe.columns.tolist())
            print(dfe.head(10).to_string())
        except Exception as e:
            print('Error reading', f.name, e)
else:
    print('No estimations folder')
