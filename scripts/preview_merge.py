import pandas as pd
from pathlib import Path

from app import _load_items_from_folder

for folder in ['fresco','congelado','seco']:
    print('===', folder)
    rows = _load_items_from_folder(Path(folder))
    for i, r in enumerate(rows[:20]):
        print(i, r)
    print('Total rows parsed:', len(rows))
