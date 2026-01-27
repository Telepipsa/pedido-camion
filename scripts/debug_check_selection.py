from pathlib import Path
import pandas as pd
from datetime import date, datetime
from scripts.sales_utils import summarize_range, load_real_sales, load_estimated_sales

base = Path('.')
start = date(2026,2,1)
end = date(2026,2,12)
res = summarize_range(base, start, end)
print('Per-day:')
for d, src, v in res['per_day']:
    print(d, src, v)
print('total_real', res['total_real'])
print('total_estim_used', res['total_estim_used'])
print('total', res['total'])

# load sales maps
real = load_real_sales(base)
estim = load_estimated_sales(base)
print('\nReal sales count:', len(real))
print('Estimated sales count:', len(estim))

# map consumo_teorico files to dates and their sales (real if available else estimated)
consumo_dir = base / 'consumo_teorico'
files = sorted(consumo_dir.glob('*.csv'))

def fname_to_date(p: Path):
    try:
        return datetime.strptime(p.stem, '%d-%m-%y').date()
    except Exception:
        return None

candidates = []
for f in files:
    d = fname_to_date(f)
    if d is None:
        continue
    v_real = real.get(d)
    v_estim = estim.get(d)
    candidates.append((f.name, d, v_real, v_estim))

print('\nCandidates (file, date, real, estim):')
for c in candidates:
    print(c)

# For app selection we only used files with real sales; but the user wants to compare estimadas and chosen files' sales.
# Let's compute sum of estimadas used in res vs sum of sales for files that have estim values matching dates in res 'estimada' days.
estim_days = [d for d, src, v in res['per_day'] if src == 'estimada']
print('\nEstim days from res:', estim_days)
# sum estim values for those days
sum_estim_for_days = sum(estim.get(d, 0.0) for d in estim_days)
print('Sum estim for days:', sum_estim_for_days)

# Now find which files were chosen by the app logic: map files with real sales only and subset-sum to res['total']
# replicate app logic
real_sales = real
candidates_real = [(f, d, float(real_sales[d])) for (f, d, vr, ve) in candidates if d in real_sales]
print('\nCandidates with real sales:')
for f,d,v in candidates_real:
    print(f.name, d, v)

if not candidates_real:
    print('\nNo candidates with real sales. The app should have shown info accordingly.')
else:
    target = int(round(res['total'] * 100))
    vals = [int(round(v*100)) for (_f,_d,v) in candidates_real]
    n = len(vals)
    best_idxs = []
    def subset_sums(items):
        res = []
        n = len(items)
        for mask in range(1 << n):
            s = 0
            idxs = []
            for i in range(n):
                if mask >> i & 1:
                    s += items[i]
                    idxs.append(i)
            res.append((s, idxs))
        return res
    if n <= 20:
        subsets = subset_sums(vals)
        best = min(subsets, key=lambda x: abs(x[0] - target))
        best_idxs = best[1]
    else:
        # not expected
        best_idxs = []
    chosen = [candidates_real[i] for i in best_idxs]
    print('\nChosen files and associated real sales:')
    for f,d,v in chosen:
        print(f.name, d, v)
    chosen_sales_total = sum(c[2] for c in chosen)
    print('Chosen sales total:', chosen_sales_total)

print('\nDone')
