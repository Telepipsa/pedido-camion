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

candidates = []
for f in files:
    parsed = parse_fname_dates(f)
    if parsed is None:
        continue
    has_thursday = False
    th_count = 0
    if isinstance(parsed, tuple):
        s, e = parsed
        t = s
        sumv = 0.0
        while t <= e:
            if t.weekday() == 3:
                has_thursday = True
                if t in thursdays:
                    th_count += 1
            if t in real_sales:
                sumv += float(real_sales[t])
            elif t in ests_map:
                sumv += float(ests_map[t])
            t = t + timedelta(days=1)
        candidates.append((f, (s,e), sumv, has_thursday, th_count))
    else:
        d = parsed
        v = 0.0
        if d in real_sales:
            v = float(real_sales[d])
        elif d in ests_map:
            v = float(ests_map[d])
        if d.weekday() == 3:
            has_thursday = True
            if d in thursdays:
                th_count = 1
        candidates.append((f, d, v, has_thursday, th_count))

print('\nCandidates:')
for c in candidates:
    f, d_or_r, v, has_th, th_count = c
    if isinstance(d_or_r, tuple):
        s,e = d_or_r
        label = f"{s.isoformat()}_{e.isoformat()}"
    else:
        label = d_or_r.isoformat()
    print('-', f.name, '|', label, '| has_thursday=', has_th, '| th_count_in_range=', th_count, '| sales_value=', v)

# Summary counts
total_th_in_candidates = sum(c[4] for c in candidates)
print('\nTotal th_count in candidates (sum of thursdays inside range across all files):', total_th_in_candidates)

# Also list files that actually fall on Thursdays (single-day files)
print('\nSingle-day files that are on Thursdays in the range:')
for c in candidates:
    f, d_or_r, v, has_th, th_count = c
    if not isinstance(d_or_r, tuple) and th_count == 1:
        print('-', f.name, d_or_r)

print('\nDone')
