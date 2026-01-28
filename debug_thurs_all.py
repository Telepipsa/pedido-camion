from pathlib import Path
from datetime import datetime as _dt, date, timedelta
from scripts.sales_utils import load_real_sales, load_estimated_sales

base = Path('.')
consumo_dir = base / 'consumo_teorico'
start_sel = date(2026,2,1)
end_sel = date(2026,2,12)

# compute thursdays in range
cur = start_sel
thursdays = []
while cur <= end_sel:
    if cur.weekday() == 3:
        thursdays.append(cur)
    cur = cur + timedelta(days=1)
print('Range:', start_sel, 'to', end_sel)
print('Thursdays in range:', thursdays)

real_sales = load_real_sales(base)
ests_map = load_estimated_sales(base)

if not consumo_dir.exists():
    print('No consumo_teorico dir')
    exit(1)

files = sorted(consumo_dir.glob('*.csv'))

print('\nFound files:', len(files))

def parse_fname_dates(p: Path):
    stem = p.stem
    if '_' in stem:
        parts = stem.split('_')
        if len(parts) >= 2:
            try:
                start = _dt.strptime(parts[0], '%d-%m-%y').date()
                end = _dt.strptime(parts[1], '%d-%m-%y').date()
                return (start, end)
            except Exception:
                return None
    try:
        return _dt.strptime(stem, '%d-%m-%y').date()
    except Exception:
        return None

print('\nFiles with their thursday counts (in file range):')
for f in files:
    parsed = parse_fname_dates(f)
    if parsed is None:
        continue
    if isinstance(parsed, tuple):
        s,e = parsed
        cur = s
        th_count = 0
        while cur <= e:
            if cur.weekday() == 3:
                th_count += 1
            cur = cur + timedelta(days=1)
        label = f"{s.isoformat()}_{e.isoformat()}"
    else:
        d = parsed
        th_count = 1 if d.weekday() == 3 else 0
        label = d.isoformat()
    print(f.name, '|', label, '| th_count_in_file=', th_count)

print('\nDone')
