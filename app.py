# Aplicación Streamlit inicial con botón de extracción de tabla desde XLS
import streamlit as st
import pandas as pd
from pathlib import Path

from scripts.parser import parse_xls

st.set_page_config(page_title="Pedido Camión", page_icon="🚚", layout="wide")

st.title("🚚 Pedido Camión")
# Toggle to avoid using files that contain Thursdays when selecting
avoid_thurs = st.checkbox("Evitar usar ficheros con jueves en su rango (cuando sea posible)", value=False)

# Helper: render saved results (so toggles/re-runs don't lose the last calculation)
def render_saved_results(res):
	if not res:
		return
	# Mostrar resumen de ventas (permanente mientras haya resultados guardados)
	summary = res.get('summary')
	if summary:
		st.markdown('### Resumen de ventas')
		st.write(f"Total ventas reales (disponibles en venta.xlsx): {summary.get('total_real', 0):,.2f}")
		st.write(f"Total ventas estimadas usadas (venta_estimada): {summary.get('total_estim_used', 0):,.2f}")
		st.write(f"Total combinado: {summary.get('total', 0):,.2f}")
		# mostrar ventas asociadas a ficheros si están disponibles
		if 'chosen_sales_total' in res:
			st.write(f"Total ventas asociadas a ficheros usados: {res.get('chosen_sales_total', 0):,.2f}")
			st.write(f"Diferencia con total combinado: {res.get('diff_sales', 0):,.2f}")

	st.markdown('### Cantidad a pedir')
	st.write(f"Ficheros usados: {', '.join(res.get('chosen_files', []))}")
	st.info('''**Ajustes aplicados**

	- Colchon 20%
	- Desperdicio -4%
	- Masas descongelación: 4 días''')
	order_df = res.get('order_df')
	if order_df is None:
		st.info('No hay tabla `Cantidad a pedir` disponible.')
	else:
		# checkbox solo cuando existe la tabla
		hide_zero_local = st.checkbox("Ocultar cantidad 0", value=True, key='hide_zero_order')
		df_disp = order_df.copy()
		if hide_zero_local and 'Cantidad_a_pedir' in df_disp.columns:
			df_disp = df_disp.loc[df_disp['Cantidad_a_pedir'] != 0].reset_index(drop=True)
		st.dataframe(df_disp)

	prod_revisar = res.get('prod_revisar')
	if prod_revisar is not None and not prod_revisar.empty:
		st.markdown('### Productos a Revisar')
		st.dataframe(prod_revisar.reset_index(drop=True))
	else:
		st.info('No hay productos a revisar.')

	agg = res.get('agg')
	if agg is not None:
		st.markdown('### Consumo agregado (archivos seleccionados)')
		st.dataframe(agg)

	df_inv = res.get('df_inv')
	if df_inv is not None:
		st.markdown('### Inventario actual guardado')
		st.dataframe(df_inv)

# Sidebar: botón para convertir todos los .xls/.xlsx en `ficheros_a_convertir`
src_dir = Path("ficheros_a_convertir")
dst_dir = Path("consumo_teorico")
dst_dir.mkdir(parents=True, exist_ok=True)

# carpeta bulk (nombres con sufijo segundo jueves)
bulk_dir = Path("ficheros_a_convertir_bulk")

if st.sidebar.button("Convertir todos los XLS"):
	if not src_dir.exists():
		st.error(f"No existe la carpeta {src_dir}")
	else:
		files = list(src_dir.glob('*.xls')) + list(src_dir.glob('*.xlsx'))
		if not files:
			st.info("No se han encontrado ficheros .xls/.xlsx en ficheros_a_convertir")
		else:
			results = []
			for file in files:
				try:
					date, table = parse_xls(file)
				except Exception as e:
					results.append((file.name, 'ERROR', str(e)))
					continue

				if date is None:
					results.append((file.name, 'NO_DATE', 'No se encontró fecha interna'))
					continue
				if table is None or table.empty:
					results.append((file.name, 'NO_PRODUCTS', 'No se extrajeron líneas de producto'))
					continue

				# select consumption column
				cons_col = None
				for cand in ['Col_10', 'Col_9', 'Col_11', 'Col_8', 'Col_12']:
					if cand in table.columns:
						cons_col = cand
						break
				if cons_col is None:
					for coln in table.columns:
						if coln not in ('Codigo', 'Articulo', 'Unidad_de_Medida'):
							cons_col = coln
							break

				if cons_col is None:
					results.append((file.name, 'NO_CONS_COL', 'No se localizó columna Consumo'))
					continue

				save_df = table[['Codigo', 'Articulo', 'Unidad_de_Medida', cons_col]].rename(columns={cons_col: 'Consumo'})
				fname = date.strftime('%d-%m-%y') + '.csv'
				target = dst_dir / fname
				try:
					if target.exists():
						target.unlink()
					save_df.to_csv(target, index=False, encoding='utf-8')
					results.append((file.name, 'SAVED', fname))
				except Exception as e:
					results.append((file.name, 'ERROR_SAVE', str(e)))

			st.markdown('### Resultados de la conversión en lote')
			for r in results:
				st.write(f"- {r[0]}: {r[1]} {r[2] if len(r) > 2 else ''}")

# Botón para convertir/procesar inventario actual (junto a los botones de conversión)
if st.sidebar.button("Convertir inventario actual"):
	file = Path("inventario_actual.xls")
	if not file.exists():
		st.error(f"No se encontró el fichero {file}. Debe situarse en la raíz del proyecto.")
	else:
		st.write(f"Procesando: {file.name}")
		try:
			date, table = parse_xls(file)
		except Exception as e:
			st.error(f"Error leyendo {file.name}: {e}")
			table = None
			date = None

		title = date.strftime('%d/%m/%Y %H:%M:%S') if date else file.name

		if table is None or table.empty:
			st.warning("No se han extraído líneas de producto según el patrón especificado.")
		else:
			# No mostrar la tabla al usuario; solo guardar el CSV con la columna 'Real'
			dest_dir = Path('inventario_actual')
			dest_dir.mkdir(parents=True, exist_ok=True)
			if 'Col_16' not in table.columns:
				st.error('No se encontró la columna Col_16 necesaria para "Real".')
			else:
				out = table[['Codigo', 'Articulo', 'Unidad_de_Medida', 'Col_16']].rename(columns={'Col_16': 'Real'})
				target = dest_dir / 'inventario_real.csv'
				try:
					if target.exists():
						target.unlink()
					out.to_csv(target, index=False, encoding='utf-8')
					st.success(f"CSV guardado en {target}")
				except Exception as e:
					st.error(f"Error guardando inventario_real.csv: {e}")
 

# --- Botón para convertir ficheros desde la carpeta bulk y añadir sufijo segundo jueves
if bulk_dir.exists() and st.sidebar.button("Convertir bulk XLS (añadir segundo jueves)"):
	files = list(bulk_dir.glob('*.xls')) + list(bulk_dir.glob('*.xlsx'))
	if not files:
		st.info(f"No se han encontrado ficheros .xls/.xlsx en {bulk_dir}")
	else:
		results = []
		from datetime import timedelta

		def second_thursday_from(d):
			# Thursday weekday() == 3; find first Thursday >= d, then add 7 days
			delta = (3 - d.weekday()) % 7
			first = d + timedelta(days=delta)
			second = first + timedelta(days=7)
			return second

		for file in files:
			try:
				date, table = parse_xls(file)
			except Exception as e:
				results.append((file.name, 'ERROR', str(e)))
				continue

			if date is None:
				results.append((file.name, 'NO_DATE', 'No se encontró fecha interna'))
				continue
			if table is None or table.empty:
				results.append((file.name, 'NO_PRODUCTS', 'No se extrajeron líneas de producto'))
				continue

			# select consumption column
			cons_col = None
			for cand in ['Col_10', 'Col_9', 'Col_11', 'Col_8', 'Col_12']:
				if cand in table.columns:
					cons_col = cand
					break
			if cons_col is None:
				for coln in table.columns:
					if coln not in ('Codigo', 'Articulo', 'Unidad_de_Medida'):
						cons_col = coln
						break

			if cons_col is None:
				results.append((file.name, 'NO_CONS_COL', 'No se localizó columna Consumo'))
				continue

			save_df = table[['Codigo', 'Articulo', 'Unidad_de_Medida', cons_col]].rename(columns={cons_col: 'Consumo'})
			# nombre base por fecha interna
			base_name = date.strftime('%d-%m-%y')
			# calcular segundo jueves relativo a la fecha interna
			second = second_thursday_from(date)
			suffix = second.strftime('%d-%m-%y')
			fname = f"{base_name}_{suffix}.csv"
			target = dst_dir / fname
			try:
				if target.exists():
					target.unlink()
				save_df.to_csv(target, index=False, encoding='utf-8')
				results.append((file.name, 'SAVED', fname))
			except Exception as e:
				results.append((file.name, 'ERROR_SAVE', str(e)))

		st.markdown('### Resultados de la conversión bulk')
		for r in results:
			st.write(f"- {r[0]}: {r[1]} {r[2] if len(r) > 2 else ''}")

st.sidebar.markdown("---")

# --- Uploaders en la barra lateral
st.sidebar.markdown('### Subir ficheros (.xls/.xlsx)')

# 1) Inventario actual (un único fichero). Se guarda siempre como inventario_actual.xls
inv_upload = st.sidebar.file_uploader("1) Subir inventario actual (se guardará como inventario_actual.xls)", type=['xls', 'xlsx'], accept_multiple_files=False, key='inv_uploader')
if inv_upload is not None:
	try:
		target = Path('inventario_actual.xls')
		with open(target, 'wb') as fh:
			fh.write(inv_upload.getvalue())
		st.sidebar.success(f"Inventario guardado como {target.name}")
	except Exception as e:
		st.sidebar.error(f"Error guardando inventario: {e}")

# 2) Ficheros consumo días sueltos -> carpeta ficheros_a_convertir (múltiples)
src_dir = Path('ficheros_a_convertir')
src_dir.mkdir(parents=True, exist_ok=True)
cons_uploads = st.sidebar.file_uploader("2) Subir ficheros consumo (días sueltos) - varios permitidos", type=['xls', 'xlsx'], accept_multiple_files=True, key='cons_uploader')
if cons_uploads:
	saved = []
	for up in cons_uploads:
		try:
			fn = up.name
			target = src_dir / fn
			with open(target, 'wb') as fh:
				fh.write(up.getvalue())
			saved.append(fn)
		except Exception as e:
			st.sidebar.error(f"Error guardando {up.name}: {e}")
	if saved:
		st.sidebar.success(f"Guardados en ficheros_a_convertir: {', '.join(saved)}")

# 3) Ficheros consumo bulk -> carpeta ficheros_a_convertir_bulk (múltiples)
bulk_dir = Path('ficheros_a_convertir_bulk')
bulk_dir.mkdir(parents=True, exist_ok=True)
bulk_uploads = st.sidebar.file_uploader("3) Subir ficheros consumo bulk - varios permitidos", type=['xls', 'xlsx'], accept_multiple_files=True, key='bulk_uploader')
if bulk_uploads:
	saved_b = []
	for up in bulk_uploads:
		try:
			fn = up.name
			target = bulk_dir / fn
			with open(target, 'wb') as fh:
				fh.write(up.getvalue())
			saved_b.append(fn)
		except Exception as e:
			st.sidebar.error(f"Error guardando {up.name}: {e}")
	if saved_b:
		st.sidebar.success(f"Guardados en ficheros_a_convertir_bulk: {', '.join(saved_b)}")
# --- Selector de rango de fechas en la página principal
from datetime import date, timedelta
from scripts.sales_utils import summarize_range

today = date.today()
default_start = today - timedelta(days=7)
start_end = st.date_input("Selecciona rango de fechas", value=(default_start, today))
if isinstance(start_end, tuple) and len(start_end) == 2:
	start_sel, end_sel = start_end
else:
	start_sel = default_start
	end_sel = today

# (Los resultados guardados se mostrarán debajo del botón "Calcular ventas"
# para que los toggles no oculten el propio botón.)

if st.button("Calcular ventas"):
	base = Path('.')
	res = summarize_range(base, start_sel, end_sel)
	# alert if there are missing days without real or estimated data
	missing = [d for d, src, v in res['per_day'] if src == 'missing']
	if missing:
		missing_str = ', '.join([d.strftime('%Y-%m-%d') for d in missing])
		st.error(f"Faltan datos (ni real ni estimada) para las siguientes fechas: {missing_str}")

	# --- Mapear cada fichero de consumo_teorico a su venta real y buscar la mejor combinación
	consumo_dir = Path('consumo_teorico')
	if consumo_dir.exists():
		files = sorted(consumo_dir.glob('*.csv'))
		from datetime import datetime as _dt
		def fname_to_date(p: Path):
			try:
				return _dt.strptime(p.stem, '%d-%m-%y').date()
			except Exception:
				return None

		# cargar ventas reales y estimadas globalmente
		from scripts.sales_utils import load_real_sales, load_estimated_sales
		real_sales = load_real_sales(Path('.'))
		ests_map = load_estimated_sales(Path('.'))

		# construir lista de candidatos: (file, date_or_range, sale_value)
		candidates = []
		from datetime import timedelta

		def parse_fname_dates(p: Path):
			stem = p.stem
			# range like DD-MM-YY_DD-MM-YY
			if '_' in stem:
				parts = stem.split('_')
				if len(parts) >= 2:
					try:
						start = _dt.strptime(parts[0], '%d-%m-%y').date()
						end = _dt.strptime(parts[1], '%d-%m-%y').date()
						return (start, end)
					except Exception:
						return None
			# single date
			try:
				return _dt.strptime(stem, '%d-%m-%y').date()
			except Exception:
				return None

		for f in files:
			parsed = parse_fname_dates(f)
			if parsed is None:
				continue
			# if parsed is a tuple -> range
			# determine if file contains any Thursday (weekday==3)
			has_thursday = False
			if isinstance(parsed, tuple):
				start, end = parsed
				# sum ventas for days in inclusive range, prefer real then estim
				t = start
				sumv = 0.0
				while t <= end:
					if t.weekday() == 3:
						has_thursday = True
					if t in real_sales:
						sumv += float(real_sales[t])
					elif t in ests_map:
						sumv += float(ests_map[t])
					# else add 0
					t = t + timedelta(days=1)
				candidates.append((f, (start, end), sumv, has_thursday))
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



		if not candidates:
			st.info('No hay ficheros en consumo_teorico con venta real asociada.')
		else:
			# objetivo: seleccionar combinación de ficheros cuya suma de ventas reales se aproxime a res['total']
			target = int(round(res['total'] * 100))
			# seleccionar candidatos activos según toggle (evitar jueves cuando sea posible)
			thursday_files = [c[0].name for c in candidates if c[3]]
			non_thurs = [c for c in candidates if not c[3]]
			if avoid_thurs:
				# mostrar solo una línea con los ficheros a evitar (si existen) y usar alternativas sin jueves
				if thursday_files and non_thurs:
					st.info(f"Se evitarán los siguientes ficheros porque contienen jueves: {', '.join(thursday_files)}")
					active_candidates = non_thurs
				elif thursday_files and not non_thurs:
					st.info("No hay alternativas sin jueves; se usarán todos los ficheros disponibles.")
					active_candidates = candidates
				else:
					# no hay ficheros con jueves, usar todos
					active_candidates = candidates
			else:
				# modo desactivado -> usar todos los ficheros (no mostrar mensaje)
				active_candidates = candidates

			vals = [int(round(c[2] * 100)) for c in active_candidates]

			# subset sum search (meet-in-the-middle for performance)
			def subset_sums(items):
				n = len(items)
				res = []
				for mask in range(1 << n):
					s = 0
					idxs = []
					for i in range(n):
						if mask >> i & 1:
							s += items[i]
							idxs.append(i)
					res.append((s, idxs))
				return res

			n = len(vals)
			best_idxs = []
			if n <= 20:
				subsets = subset_sums(vals)
				best = min(subsets, key=lambda x: abs(x[0] - target))
				best_idxs = best[1]
			else:
				# split
				h = n // 2
				A = vals[:h]
				B = vals[h:]
				sa = subset_sums(A)
				sb = subset_sums(B)
				sa_sorted = sorted(sa, key=lambda x: x[0])
				sb_sorted = sorted(sb, key=lambda x: x[0])
				import bisect
				b_sums = [x[0] for x in sb_sorted]
				best_diff = None
				for s_a, idxs_a in sa_sorted:
					need = target - s_a
					i = bisect.bisect_left(b_sums, need)
					for j in (i-1, i, i+1):
						if 0 <= j < len(b_sums):
							s_b, idxs_b = sb_sorted[j]
							total = s_a + s_b
							diff = abs(total - target)
							if best_diff is None or diff < best_diff:
								best_diff = diff
								best_idxs = idxs_a + [i + h for i in idxs_b]

			# archivos elegidos (map indices back to active candidates)
			chosen_candidates = [active_candidates[i] for i in best_idxs]
			# convert to (file, date_or_range, value) tuples for downstream code
			chosen = [(c[0], c[1], c[2]) for c in chosen_candidates]
			if not chosen:
				st.info('No se encontró una combinación útil de ficheros.')
			else:
				chosen_files = [c[0] for c in chosen]
				# suma de ventas reales asociadas a los ficheros elegidos
				chosen_sales_total = sum(c[2] for c in chosen)
				diff_sales = chosen_sales_total - res['total'] 
				# leer y agregar consumos
				def read_cons_df(pth: Path):
					try:
						df = pd.read_csv(pth, encoding='utf-8')
					except Exception:
						df = pd.read_csv(pth, encoding='latin-1')
					if 'Consumo' in df.columns:
						cons_col = 'Consumo'
					else:
						cands = [c for c in df.columns if c not in ('Codigo', 'Articulo', 'Unidad_de_Medida')]
						cons_col = cands[-1] if cands else None
					if cons_col is None:
						return None
					out = df[['Codigo', 'Articulo', 'Unidad_de_Medida', cons_col]].rename(columns={cons_col: 'Consumo'})
					out['Consumo'] = pd.to_numeric(out['Consumo'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
					return out

				dfs = [read_cons_df(p) for p in chosen_files]
				dfs = [d for d in dfs if d is not None]
				if not dfs:
					st.info('No se pudieron leer los ficheros elegidos.')
				else:
					agg = pd.concat(dfs).groupby(['Codigo', 'Articulo', 'Unidad_de_Medida'], as_index=False)['Consumo'].sum()

					# --- Ajuste para masas (BF, BM, BP): añadir 4 días extra al rango solo para estos códigos
					MASAS = set(['BF', 'BM', 'BP'])
					extra_days = 4
					per_product_extra_days = extra_days
					from datetime import timedelta as _td
					extra_start = end_sel + _td(days=1)
					extra_dates = [extra_start + _td(days=i) for i in range(extra_days)]

					# helper: parse all consumo_teorico files and find consumption for given product and dates
					def consumo_for_product_on_dates(code, dates):
						total = 0.0
						found = False
						for p in files:
							parsed = parse_fname_dates(p)
							if parsed is None:
								continue
							# determine if p covers any of the dates
							covers = set()
							if isinstance(parsed, tuple):
								s, e = parsed
								cur = s
								while cur <= e:
									covers.add(cur)
									cur = cur + _td(days=1)
							else:
								covers.add(parsed)
							if not any(d in covers for d in dates):
								continue
							# read file and sum code
							try:
								df = pd.read_csv(p, encoding='utf-8')
							except Exception:
								df = pd.read_csv(p, encoding='latin-1')
							cols = [c for c in df.columns if c not in ('Codigo', 'Articulo', 'Unidad_de_Medida')]
							cons_col = 'Consumo' if 'Consumo' in df.columns else (cols[-1] if cols else None)
							if cons_col is None:
								continue
							df['Consumo'] = pd.to_numeric(df[cons_col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
							# sum rows where Codigo matches
							if 'Codigo' in df.columns:
								mask = df['Codigo'].astype(str).str.strip() == str(code)
								sval = df.loc[mask, 'Consumo'].sum()
								if sval > 0:
									found = True
								total += float(sval)
						return total, found

					# compute days covered by chosen files for average calculation
					days_covered = 0
					for _f, _d, _v in chosen:
						if isinstance(_d, tuple):
							days_covered += (_d[1] - _d[0]).days + 1
						else:
							days_covered += 1
					days_covered = max(1, days_covered)

					# for summary
					masas_added_days = 0  # total days summed across all masas (e.g., 4*3 = 12)
					masas_added_sales = 0.0
					masas_added_consumption = 0.0

					# ensure agg has Codigo as string
					agg['Codigo'] = agg['Codigo'].astype(str)

					# Recalcular usando solo venta estimada de los 4 días siguientes
					ests_extra_total = 0.0
					for d in extra_dates:
						if d in ests_map:
							ests_extra_total += float(ests_map[d])

					# masa consumo actual (antes de añadir extras)
					masa_current_total = agg.loc[agg['Codigo'].isin(MASAS)]['Consumo'].sum()
					# evitar división por cero
					if res['total'] and res['total'] > 0:
						masa_per_euro = masa_current_total / float(res['total'])
					else:
						masa_per_euro = 0.0

					# masa necesaria para los días extra según venta estimada
					masa_needed_total = ests_extra_total * masa_per_euro

					# distribuir masa_needed_total entre códigos según su participación actual, o igual si 0
					if masa_current_total > 0:
						shares = {}
						masas_added_detail = {}
						for code in MASAS:
							cval = float(agg.loc[agg['Codigo'] == code, 'Consumo'].sum()) if not agg.loc[agg['Codigo'] == code].empty else 0.0
							shares[code] = cval / masa_current_total
					else:
						shares = {code: 1.0/len(MASAS) for code in MASAS}

					for code in MASAS:
						added = masa_needed_total * shares.get(code, 0)
						if any(agg['Codigo'] == code):
							agg.loc[agg['Codigo'] == code, 'Consumo'] += added
						else:
							agg = pd.concat([agg, pd.DataFrame([{'Codigo': code, 'Articulo': '', 'Unidad_de_Medida': '', 'Consumo': added}])], ignore_index=True)
						masas_added_consumption += added
						masas_added_detail[code] = round(added, 2)

					masas_added_days = per_product_extra_days
					masas_added_sales = ests_extra_total

					# notas para el resumen de ventas
					summary_masas = None
					if masas_added_days > 0:
						summary_masas = {
							'total_days': masas_added_days,
							'per_product_days': per_product_extra_days,
							'sales': masas_added_sales,
							'consumo_added': masas_added_consumption
						}
					# Intentar leer inventario guardado
					inv_path = Path('inventario_actual') / 'inventario_real.csv'
					if inv_path.exists():
						try:
							df_inv = pd.read_csv(inv_path, encoding='utf-8')
						except Exception:
							df_inv = pd.read_csv(inv_path, encoding='latin-1')
						# normalizar columna 'Real'
						if 'Real' in df_inv.columns:
							df_inv['Real'] = pd.to_numeric(df_inv['Real'].astype(str).str.replace(',', '.'), errors='coerce').fillna(0)
						else:
							# si no existe, crear columna Real a 0
							df_inv['Real'] = 0.0
					else:
						df_inv = pd.DataFrame(columns=['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real'])

					# unir consumo agregado con inventario por claves
					merged = agg.merge(df_inv[['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real']], on=['Codigo', 'Articulo', 'Unidad_de_Medida'], how='left')
					merged['Real'] = merged['Real'].fillna(0)
					merged['Consumo'] = merged['Consumo'].fillna(0)
					# Aplicar porcentajes solo para el cálculo de 'Cantidad a pedir'
					# Inventario: aplicar desperdicio del 4% (disponible = Real * 0.96)
					# Consumo: añadir 20% extra al consumo (Consumo * 1.20)
					INV_WASTE = 0.04
					CONSUMO_EXTRA = 0.20
					inv_multiplier = 1.0 - INV_WASTE
					cons_multiplier = 1.0 + CONSUMO_EXTRA
					consumo_adj = merged['Consumo'] * cons_multiplier
					real_adj = merged['Real'] * inv_multiplier
					# Ajuste porcentual según diferencia entre Total combinado y ventas asociadas
					adj_pct = 0.0
					try:
						total_combined = float(res['total'])
						chosen_total = float(chosen_sales_total)
						if total_combined != 0:
							adj_pct = (total_combined - chosen_total) / total_combined
					except Exception:
						adj_pct = 0.0
					merged['Cantidad_a_pedir'] = ((consumo_adj - real_adj) * (1.0 + adj_pct)).clip(lower=0).round(2)

					order_df = merged[['Codigo', 'Articulo', 'Unidad_de_Medida', 'Cantidad_a_pedir']]
					# Eliminar de 'Cantidad a pedir' los productos cuyo nombre empiece por ZZ o YY (case-insensitive)
					if 'Articulo' in order_df.columns:
						mask_drop = order_df['Articulo'].astype(str).str.upper().str.startswith(('ZZ', 'YY'), na=False)
						if mask_drop.any():
							order_df = order_df.loc[~mask_drop].reset_index(drop=True)

					# Mostrar: Cantidad a pedir encima, luego Consumo agregado y finalmente Inventario
					# Mostrar resumen adicional para masas si procede
					# No mostramos aquí; guardamos los resultados en session_state para que
					# los toggles (checkboxes) no reinicien la página y permitan filtrar sin
					# volver a recalcular.

					# Productos en inventario que no aparecen en el consumo agregado -> Productos a Revisar
					try:
						# normalizar Codigo como string
						inv_codes = df_inv['Codigo'].astype(str).str.strip()
						agg_codes = agg['Codigo'].astype(str).str.strip()
						missing_mask = ~inv_codes.isin(agg_codes)
						prod_revisar = df_inv.loc[missing_mask, ['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real']]
						# buscar también los productos que están en consumo agregado pero no en inventario
						agg_only_mask = ~agg_codes.isin(inv_codes)
						agg_only = agg.loc[agg_only_mask, ['Codigo', 'Articulo', 'Unidad_de_Medida', 'Consumo']].copy()
						# preparar DataFrame combinado con columna Fuente
						inv_part = prod_revisar.copy()
						if not inv_part.empty:
							inv_part = inv_part.rename(columns={'Real': 'Real'})
							inv_part['Consumo'] = 0.0
							inv_part['Fuente'] = 'Inventario'
						else:
							inv_part = pd.DataFrame(columns=['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real', 'Consumo', 'Fuente'])
						if not agg_only.empty:
							agg_only = agg_only.rename(columns={'Consumo': 'Consumo'})
							agg_only['Real'] = 0.0
							agg_only['Fuente'] = 'Consumo agregado'
						else:
							agg_only = pd.DataFrame(columns=['Codigo', 'Articulo', 'Unidad_de_Medida', 'Consumo', 'Real', 'Fuente'])
						# alinear columnas y concatenar
						cols = ['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real', 'Consumo', 'Fuente']
						prod_revisar = pd.concat([inv_part[cols], agg_only[cols]], ignore_index=True, sort=False)
						# eliminar productos cuyo nombre empiece por ZZ o YY
						if 'Articulo' in prod_revisar.columns:
							mask_drop_rev = prod_revisar['Articulo'].astype(str).str.upper().str.startswith(('ZZ', 'YY'), na=False)
							if mask_drop_rev.any():
								prod_revisar = prod_revisar.loc[~mask_drop_rev].reset_index(drop=True)
						# además, añadir todos los productos cuyo Consumo sea 0 (si no están ya en la tabla)
						try:
							zeros = merged.loc[merged['Consumo'] == 0, ['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real', 'Consumo']].copy()
							if not zeros.empty:
								zeros['Fuente'] = 'Consumo 0'
								# evitar duplicados por Codigo (normalizando a str)
								existing = prod_revisar['Codigo'].astype(str).str.strip().unique().tolist() if not prod_revisar.empty else []
								zeros = zeros[~zeros['Codigo'].astype(str).str.strip().isin(existing)]
								if not zeros.empty:
									prod_revisar = pd.concat([prod_revisar, zeros[cols]], ignore_index=True, sort=False)
									# volver a aplicar filtro ZZ/YY por si las nuevas filas deben eliminarse
									if 'Articulo' in prod_revisar.columns:
										mask_drop_rev = prod_revisar['Articulo'].astype(str).str.upper().str.startswith(('ZZ', 'YY'), na=False)
										if mask_drop_rev.any():
											prod_revisar = prod_revisar.loc[~mask_drop_rev].reset_index(drop=True)
						except Exception:
							pass
					except Exception:
						prod_revisar = pd.DataFrame(columns=['Codigo', 'Articulo', 'Unidad_de_Medida', 'Real'])

					# guardar resultados en session_state para persistencia entre reruns
					saved = {
						'order_df': order_df,
						'prod_revisar': prod_revisar,
						'agg': agg,
						'df_inv': df_inv,
						'chosen_files': [p.name for p in chosen_files],
						'summary_masas': summary_masas,
						# incluir resumen de ventas para mostrar en render_saved_results
						'summary': {
							'total_real': res['total_real'] if 'total_real' in res else 0.0,
							'total_estim_used': res['total_estim_used'] if 'total_estim_used' in res else 0.0,
							'total': res['total'] if 'total' in res else 0.0,
						},
						'per_day': res.get('per_day'),
						'chosen_sales_total': chosen_sales_total,
						'diff_sales': diff_sales
					}
					st.session_state['last_results'] = saved
					# resultados guardados en session_state; la visualización persistente
					# se renderiza una sola vez más abajo para evitar duplicados de widgets

					# (Estas vistas se muestran vía session_state para permitir toggles sin recálculo)

			# --- (Oculto) Construyo internamente las tablas solicitadas pero no las muestro
			# Tabla 1: días de la consulta con venta real/estimada/missing (no mostrada)
			per_day = None
			if 'last_results' in st.session_state:
				per_day = st.session_state['last_results'].get('per_day')
			if per_day:
				days_df = pd.DataFrame([{'Fecha': d, 'Fuente': src, 'Venta': v} for d, src, v in per_day])
			else:
				days_df = pd.DataFrame()
			# Tabla 2: ficheros usados y la venta asociada a cada uno (real si existe, si no estimada) (no mostrada)
			from scripts.sales_utils import load_estimated_sales
			ests_map = load_estimated_sales(Path('.'))
			file_rows = []
			for f, d, v in chosen:
				# d puede ser una fecha o un rango (start, end); usamos la venta ya calculada en v
				if isinstance(d, tuple):
					start, end = d
					fecha_label = f"{start.strftime('%Y-%m-%d')}_{end.strftime('%Y-%m-%d')}"
				else:
					fecha_label = d.strftime('%Y-%m-%d') if d else ''
				sale_used = v
				file_rows.append({'Fichero': f.name, 'Fecha': fecha_label, 'Venta_asociada': sale_used})
			files_df = pd.DataFrame(file_rows)
	else:
		st.info('No existe la carpeta consumo_teorico')

# Mostrar resultados guardados (debajo del botón) si existen
if 'last_results' in st.session_state:
    render_saved_results(st.session_state.get('last_results'))


