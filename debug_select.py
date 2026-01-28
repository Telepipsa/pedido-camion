from pathlib import Path
from datetime import datetime as _dt, date, timedelta
from scripts.sales_utils import load_real_sales, load_estimated_sales, summarize_range

base = Path('.')
start_sel = date(2026,2,1)
end_sel = date(2026,2,12)
res = summarize_range(base, start_sel, end_sel)
print('Range total combined:', res['total'])

consumo_dir = base / 'consumo_teorico'
files = sorted(consumo_dir.glob('*.csv'))

from datetime import timedelta as _td
from datetime import datetime as _dt

# parse filenames
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

real_sales = load_real_sales(base)
ests_map = load_estimated_sales(base)

candidates = []
for f in files:
    parsed = parse_fname_dates(f)
    if parsed is None:
        continue
    has_thursday = False
    if isinstance(parsed, tuple):
        s,e = parsed
        t = s
        sumv = 0.0
        while t <= e:
            if t.weekday() == 3:
                has_thursday = True
            if t in real_sales:
                sumv += float(real_sales[t])
            elif t in ests_map:
                sumv += float(ests_map[t])
            t = t + timedelta(days=1)
        candidates.append((f, (s,e), sumv, has_thursday))
    else:
        d = parsed
        v = 0.0
        if d in real_sales:
            v = float(real_sales[d])
        elif d in ests_map:
            v = float(ests_map[d])
        if d.weekday() == 3:
            has_thursday = True
        candidates.append((f, d, v, has_thursday))

print('Candidates with has_thursday:')
for c in candidates:
    print(c[0].name, c[1], c[3])

# determine required thursdays in range
cur = start_sel
req_th = 0
while cur <= end_sel:
    if cur.weekday() == 3:
        req_th += 1
    cur = cur + _td(days=1)
print('Required Thursdays:', req_th)

# build item_entries per app logic (counting th in file ranges irrespective of range)
item_entries = []
for c in candidates:
    f, d_or_r, v, has_th = c
    if isinstance(d_or_r, tuple):
        s,e = d_or_r
        cur = s
        th_count = 0
        while cur <= e:
            if cur.weekday() == 3:
                th_count += 1
            cur = cur + _td(days=1)
        item_entries.append((f, d_or_r, v, th_count, True))
    else:
        d = d_or_r
        th_count = 1 if d.weekday() == 3 else 0
        item_entries.append((f, d_or_r, v, th_count, False))

# controlled duplication: if total th_count across items < req_th, duplicate single-day th files round-robin
current_th_total = sum(it[3] for it in item_entries)
if current_th_total < req_th:
    need = req_th - current_th_total
    single_th_idxs = [i for i, it in enumerate(item_entries) if (not it[4]) and it[3] == 1]
    idx_cycle = 0
    while need > 0 and single_th_idxs:
        src_idx = single_th_idxs[idx_cycle % len(single_th_idxs)]
        item_entries.append(item_entries[src_idx])
        need -= 1
        idx_cycle += 1

print('\nItem entries (including duplicates for single-day Thursdays):')
for ie in item_entries:
    print(ie[0].name, ie[1], 'v=', ie[2], 'th_count=', ie[3], 'is_bulk=', ie[4])

# now run subset sum with th counts
vals = [int(round(c[2]*100)) for c in item_entries]
th_counts = [c[3] for c in item_entries]
from itertools import combinations
n = len(vals)
best = None
best_metric = None
target = int(round(res['total']*100))
for r in range(1, n+1):
    for idxs in combinations(range(n), r):
        s = sum(vals[i] for i in idxs)
        th = sum(th_counts[i] for i in idxs)
        metric = (abs(req_th - th), abs(s - target))
        if best is None or metric < best_metric:
            best = idxs
            best_metric = metric

print('\nBest selection indices:', best)
print('Best metric (th_diff, sales_diff):', best_metric)
print('Chosen files:')
for i in best:
    print(item_entries[i][0].name, item_entries[i][1], 'th_count=', item_entries[i][3])

