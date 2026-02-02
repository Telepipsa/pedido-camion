# Aplicación Streamlit inicial con botón de extracción de tabla desde XLS
import streamlit as st
import pandas as pd
from pathlib import Path

from scripts.parser import parse_xls

st.set_page_config(page_title="Pedido Camión", page_icon="🚚", layout="wide")

st.title("🚚 Pedido Camión")
# Toggle to avoid using files that contain Thursdays when selecting
avoid_thurs = st.checkbox("Evitar usar ficheros con jueves en su rango (cuando sea posible)", value=False)

# --- Mostrar inventario/maestro por carpeta (congelado / fresco / seco)
def _load_items_from_folder(folder: Path):
	out_rows = []
	if not folder.exists():
		return []
	files = list(folder.glob('*.xls')) + list(folder.glob('*.xlsx'))
	for f in files:
		# read without header to detect where real header sits
		try:
			raw = pd.read_excel(f, header=None, engine='xlrd' if f.suffix.lower()=='.xls' else 'openpyxl')
		except Exception:
			try:
				raw = pd.read_excel(f, header=None)
			except Exception:
				continue

		# try to detect header row by looking for known keywords
		header_keywords = ['articulo', 'artículo', 'codigo', 'código', 'unid', 'unid. totales', 'unid. totales', 'medida', 'embalaje', 'nombre']
		header_row = None
		max_search = min(40, len(raw))
		for i in range(max_search):
			row_vals = [str(x).strip().lower() if pd.notna(x) else '' for x in raw.iloc[i].tolist()]
			# count matches
			matches = sum(1 for h in header_keywords if any(h in v for v in row_vals))
			if matches >= 2:
				header_row = i
				break

		if header_row is None:
			# fallback: assume header at row 0
			header_row = 0

		# create df with proper header
		header = raw.iloc[header_row].astype(str).tolist()
		df = raw.iloc[header_row+1:].copy()
		df.columns = [str(c).strip() for c in header]

		# candidate column names for each target (case-insensitive)
		def find_col(dfcols, candidates):
			lower_map = {str(c).strip().lower(): c for c in dfcols}
			for cand in candidates:
				if cand.lower() in lower_map:
					return lower_map[cand.lower()]
			# try partial contains
			for cand in candidates:
				for lc, orig in lower_map.items():
					if cand.lower() in lc or lc in cand.lower():
						return orig
			return None

		name_col = find_col(df.columns, ['Articulo', 'Artículo', 'Nombre'])
		code_col = find_col(df.columns, ['Codigo', 'Código', 'Cod'])
		units_col = find_col(df.columns, ['Unid. Totales', 'Unid Totales', 'Unidades totales', 'Unidades', 'Total'])
		measure_col = find_col(df.columns, ['Medida', 'Unidad_de_Medida', 'Unidad'])
		pack_col = find_col(df.columns, ['Embalaje', 'Packaging', 'Envase'])

		# merge rows where product name and its metrics are split across two rows
		i = 0
		n = len(df)
		while i < n:
			row = df.iloc[i]
			name_val = row.get(name_col) if name_col is not None else None
			code_val = row.get(code_col) if code_col is not None else None
			units_val = row.get(units_col) if units_col is not None else None
			measure_val = row.get(measure_col) if measure_col is not None else None
			pack_val = row.get(pack_col) if pack_col is not None else None

			# if this row appears to contain only the name and next row has details, merge them
			merged = False
			if (pd.isna(code_val) or code_val == '' or str(code_val).strip().lower() in ('nan', 'none')) and name_val and (i + 1) < n:
				row2 = df.iloc[i+1]
				code2 = row2.get(code_col) if code_col is not None else None
				units2 = row2.get(units_col) if units_col is not None else None
				measure2 = row2.get(measure_col) if measure_col is not None else None
				pack2 = row2.get(pack_col) if pack_col is not None else None
				# if next row contains a code or units, treat as the companion row
				if (pd.notna(code2) and str(code2).strip() not in ('', 'nan', 'None')) or (pd.notna(units2) and str(units2).strip() not in ('', 'nan', 'None')):
					out_rows.append({
						'Nombre': name_val,
						'Codigo': code2,
						'Unidades totales': units2,
						'Medida': measure2,
						'Embalaje': pack2,
						'Origen fichero': f.name
					})
					merged = True

			if not merged:
				out_rows.append({
					'Nombre': name_val,
					'Codigo': code_val,
					'Unidades totales': units_val,
					'Medida': measure_val,
					'Embalaje': pack_val,
					'Origen fichero': f.name
				})
			i += 2 if merged else 1

	return out_rows


# Mostrar tabla maestra de productos por carpeta
# Cargar maestro en background (oculto). No mostrar selector ni cabecera.
folder_choice = 'Todos'

def _collect_for(choice: str):
	rows = []
	base = Path('.')
	if choice in ('congelado', 'Todos'):
		rows += _load_items_from_folder(base / 'congelado')
	if choice in ('fresco', 'Todos'):
		rows += _load_items_from_folder(base / 'fresco')
	if choice in ('seco', 'Todos'):
		rows += _load_items_from_folder(base / 'seco')
	return rows

col_rows = _collect_for(folder_choice)
if col_rows:
	df_master = pd.DataFrame(col_rows)
	# normalizar nombres de columnas al pedido del usuario
	# mostrar sólo las columnas solicitadas (ocultar 'Origen fichero')
	display_cols = ['Nombre', 'Codigo', 'Unidades totales', 'Medida', 'Embalaje']
	for c in display_cols:
		if c not in df_master.columns:
			df_master[c] = None

	# Filtrar filas sin Código (no mostrar filas que carezcan de código válido)
	try:
		df_master['Codigo'] = df_master['Codigo'].astype(object)
		mask_has_code = df_master['Codigo'].notna() & (df_master['Codigo'].astype(str).str.strip() != '')
		df_master = df_master.loc[mask_has_code].reset_index(drop=True)
	except Exception:
		# en caso de error, no romper la UI; mostrar lo que haya
		pass

	# Normalizar números en 'Unidades totales' y 'Embalaje' y calcular unidades por embalaje
	try:
		# limpiar comas y convertir a float
		df_master['Unidades totales'] = pd.to_numeric(df_master['Unidades totales'].astype(str).str.replace(',', '.'), errors='coerce')
		df_master['Embalaje'] = pd.to_numeric(df_master['Embalaje'].astype(str).str.replace(',', '.'), errors='coerce')
		def compute_upack(row):
			try:
				u = float(row['Unidades totales'])
				e = float(row['Embalaje'])
				if pd.isna(u) or pd.isna(e) or e == 0:
					return None
				val = u / e
				# mostrar entero cuando es casi entero
				if abs(val - round(val)) < 1e-8:
					return int(round(val))
				return round(val, 4)
			except Exception:
				return None
		df_master['Unidades_por_embalaje'] = df_master.apply(compute_upack, axis=1)
	except Exception:
		df_master['Unidades_por_embalaje'] = None

	# Guardar maestro en session_state (oculto)
	try:
		st.session_state['df_master'] = df_master
	except Exception:
		pass
else:
	# Diagnóstico: mostrar contenido de las carpetas y errores de lectura
	base = Path('.')
	folders = ['congelado', 'fresco', 'seco']
	st.warning('No se han encontrado ficheros válidos en la(s) carpeta(s) seleccionadas. Mostrando diagnóstico:')
	for fld in folders:
		p = base / fld
		exists = p.exists()
		files = []
		if exists:
			files = sorted([x.name for x in p.iterdir() if x.is_file()])
		st.write(f"Carpeta `{fld}` — existe: {exists} — archivos encontrados: {len(files)}")
		if files:
			st.write(', '.join(files[:50]))

	# Intentar leer el primer .xls/.xlsx de cada carpeta y mostrar excepción (útil en deploy)
	for fld in folders:
		p = base / fld
		if not p.exists():
			continue
		for f in sorted(p.iterdir()):
			if not f.is_file():
				continue
			if f.suffix.lower() not in ('.xls', '.xlsx'):
				continue
			try:
				pd.read_excel(f, header=None, nrows=1)
				st.write(f"Lectura de prueba OK para: {f.name}")
			except Exception as e:
				st.write(f"Error de lectura para {f.name}: {e}")
			break

# Helper: render saved results (so toggles/re-runs don't lose the last calculation)
def render_saved_results(res):
	if not res:
		return
	# Mostrar resumen de ventas (permanente mientras haya resultados guardados)
	summary = res.get('summary')
	if summary:
		# Toggle button to show/hide resumen
		if 'show_summary_details' not in st.session_state:
			st.session_state['show_summary_details'] = False
		btn_label = f"Resumen de ventas {'🙈' if st.session_state.get('show_summary_details') else '👁️'}"
		if st.button(btn_label, key='toggle_summary'):
			st.session_state['show_summary_details'] = not st.session_state.get('show_summary_details', False)
		# mostrar detalles solo si está activo
		if st.session_state.get('show_summary_details'):
			st.write(f"Total ventas reales (disponibles en venta.xlsx): {summary.get('total_real', 0):,.2f}")
			st.write(f"Total ventas estimadas usadas (venta_estimada): {summary.get('total_estim_used', 0):,.2f}")
			st.write(f"Total combinado: {summary.get('total', 0):,.2f}")
			# mostrar ventas asociadas a ficheros si están disponibles
			if 'chosen_sales_total' in res:
				st.write(f"Total ventas asociadas a ficheros usados: {res.get('chosen_sales_total', 0):,.2f}")
				st.write(f"Diferencia con total combinado: {res.get('diff_sales', 0):,.2f}")

			# Mostrar ficheros usados y recuento de jueves (si hay)
			st.write(f"Ficheros usados: {', '.join(res.get('chosen_files', []))}")
			thurs_used = res.get('chosen_thurs', [])
			if thurs_used:
				# calcular total de jueves representados por los nombres de fichero (contando duplicados)
				def _count_thurs_in_name(nm):
					from datetime import datetime, timedelta
					s = str(nm)
					if s.lower().endswith('.csv'):
						s = s[:-4]
					# rango como DD-MM-YY_DD-MM-YY
					if '_' in s:
						parts = s.split('_')
						if len(parts) >= 2:
							try:
								start = datetime.strptime(parts[0], '%d-%m-%y').date()
								end = datetime.strptime(parts[1], '%d-%m-%y').date()
							except Exception:
								return 0
							cnt = 0
							cur = start
							while cur <= end:
								if cur.weekday() == 3:
									cnt += 1
								cur = cur + timedelta(days=1)
							return cnt
						return 0
					else:
						try:
							d = datetime.strptime(s, '%d-%m-%y').date()
							return 1 if d.weekday() == 3 else 0
						except Exception:
							return 0
				total_th = sum(_count_thurs_in_name(n) for n in thurs_used)
				st.write(f"Ficheros jueves usados: {', '.join(thurs_used)} ({total_th} jueves)")
		# (Ficheros usados y conteo de jueves se muestran dentro del toggle 'Resumen de ventas')
	st.markdown('### Cantidad a pedir')
	
	# Mostrar ajustes aplicados y, si procede, el +/- aplicado al colchón
	colchon_base_pct = 20
	colchon_extra_str = ""
	try:
		total_for_summary = summary.get('total', 0) if summary else 0
		chosen_sales_for_summary = res.get('chosen_sales_total', 0)
		if total_for_summary:
			raw_pct = (float(total_for_summary) - float(chosen_sales_for_summary or 0)) / float(total_for_summary)
			if abs(raw_pct) >= 0.01:
				sign_pct = int(round(raw_pct * 100))
				colchon_extra_str = f" ({'+' if sign_pct>0 else ''}{sign_pct}%)"
	except Exception:
		colchon_extra_str = ""
	st.info(f"""**Ajustes aplicados**

	- Colchon {colchon_base_pct}%{colchon_extra_str}
	- Desperdicio -4%
	- Masas descongelación: 4 días""")
	order_df = res.get('order_df')
	if order_df is None:
		st.info('No hay tabla `Cantidad a pedir` disponible.')
	else:
		# --- Tablas por tipo: Congelado / Fresco / Seco (productos con Cantidad_a_pedir > 0)
		try:
			odf = order_df.copy()
			# asegurar columnas necesarias
			if 'Cantidad_a_pedir' in odf.columns and 'Codigo' in odf.columns:
				# normalizar codigo para comparar
				odf['__COD__'] = odf['Codigo'].astype(str).str.strip().str.upper().str.replace(' ', '')
				# cargar listas de códigos desde los csv de congelado/fresco (si existen)
				cong_path = Path('congelado.csv')
				fres_path = Path('fresco.csv')
				cong_codes = set()
				fres_codes = set()
				if cong_path.exists():
					try:
						df_cong = pd.read_csv(cong_path, encoding='utf-8')
					except Exception:
						df_cong = pd.read_csv(cong_path, encoding='latin-1')
					if 'Codigo' in df_cong.columns:
						cong_codes = set(df_cong['Codigo'].astype(str).str.strip().str.upper().str.replace(' ', ''))
				if fres_path.exists():
					try:
						df_fres = pd.read_csv(fres_path, encoding='utf-8')
					except Exception:
						df_fres = pd.read_csv(fres_path, encoding='latin-1')
					if 'Codigo' in df_fres.columns:
						fres_codes = set(df_fres['Codigo'].astype(str).str.strip().str.upper().str.replace(' ', ''))
				# filtros
				mask_positive = pd.to_numeric(odf['Cantidad_a_pedir'], errors='coerce').fillna(0) > 0
				mask_cong = odf['__COD__'].isin(cong_codes)
				mask_fres = odf['__COD__'].isin(fres_codes)
				congelado_tbl = odf.loc[mask_positive & mask_cong].drop(columns=['__COD__']).reset_index(drop=True)
				fresco_tbl = odf.loc[mask_positive & mask_fres].drop(columns=['__COD__']).reset_index(drop=True)
				seco_tbl = odf.loc[mask_positive & ~(mask_cong | mask_fres)].drop(columns=['__COD__']).reset_index(drop=True)
				# calcular 'Embalajes_a_pedir' = ceil(Cantidad_a_pedir / Unidades_por_embalaje) cuando sea posible
				# checkbox para mostrar Unidades_por_embalaje en las tablas (oculto por defecto)
				show_upe = st.checkbox("Mostrar 'Unidades_por_embalaje' en tablas (congelado/fresco/seco)", value=False, key='show_upe')
				def _compute_embalajes(df):
					import math
					if 'Cantidad_a_pedir' not in df.columns:
						return df
					# asegurar columna Unidades_por_embalaje si no existe
					if 'Unidades_por_embalaje' not in df.columns:
						df['Unidades_por_embalaje'] = None
					def _calc(row):
						try:
							q = float(row['Cantidad_a_pedir'])
							upe = row['Unidades_por_embalaje']
							if pd.isna(upe) or upe is None:
								return None
							up = float(upe)
							if up == 0:
								return None
							val = math.ceil(q / up)
							return int(val)
						except Exception:
							return None
					df['Embalajes_a_pedir'] = df.apply(_calc, axis=1)
					return df

				congelado_tbl = _compute_embalajes(congelado_tbl)
				fresco_tbl = _compute_embalajes(fresco_tbl)
				seco_tbl = _compute_embalajes(seco_tbl)

				# mostrar solo si tienen filas; ocultar columna Unidades_por_embalaje por defecto
				if not congelado_tbl.empty:
					st.markdown("<h3 style='color:#88DDEE'>Congelado</h3>", unsafe_allow_html=True)
					display_cols = [c for c in congelado_tbl.columns if c != 'Unidades_por_embalaje' or show_upe]
					st.dataframe(congelado_tbl[display_cols])
				if not fresco_tbl.empty:
					st.markdown("<h3 style='color:#CFFFD6'>Fresco</h3>", unsafe_allow_html=True)
					display_cols = [c for c in fresco_tbl.columns if c != 'Unidades_por_embalaje' or show_upe]
					st.dataframe(fresco_tbl[display_cols])
				if not seco_tbl.empty:
					st.markdown("<h3 style='color:#FFB347'>Seco</h3>", unsafe_allow_html=True)
					display_cols = [c for c in seco_tbl.columns if c != 'Unidades_por_embalaje' or show_upe]
					st.dataframe(seco_tbl[display_cols])
		except Exception:
			# no bloquear la interfaz si hay un error mostrando estas tablas
			pass

		prod_revisar = res.get('prod_revisar')
		if prod_revisar is not None and not prod_revisar.empty:
			st.markdown("<h3 style='color:#FFB6B6'>Productos a Revisar</h3>", unsafe_allow_html=True)
			st.dataframe(prod_revisar.reset_index(drop=True))
		else:
			st.info('No hay productos a revisar.')

		# checkbox solo cuando existe la tabla
		hide_zero_local = st.checkbox("Ocultar cantidad 0", value=True, key='hide_zero_order')
		df_disp = order_df.copy()
		if hide_zero_local and 'Cantidad_a_pedir' in df_disp.columns:
			df_disp = df_disp.loc[df_disp['Cantidad_a_pedir'] != 0].reset_index(drop=True)
		st.dataframe(df_disp)

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
			# determinar base_name y sufijo final
			# Preferimos usar la primera y segunda "Fecha de grabación" dentro del fichero
			from scripts.parser import _read_excel_fallback
			raw_df = None
			try:
				raw_df = _read_excel_fallback(file)
			except Exception:
				raw_df = None

			def _extract_all_dates(df):
				import re
				from datetime import datetime
				if df is None:
					return []
				res = []
				def norm(s):
					try:
						return re.sub(r'\s+', ' ', str(s)).strip()
					except Exception:
						return ''
				# pattern for full datetime and date
				patterns = [re.compile(r'(\d{1,2}/\d{1,2}/\d{4}\s*\d{1,2}:\d{2}:\d{2})'), re.compile(r'(\d{1,2}/\d{1,2}/\d{4})')]
				rows, cols = df.shape
				for r in range(rows):
					for c in range(cols):
						cell = norm(df.iat[r, c])
						if not cell:
							continue
						# direct match
						for p in patterns:
							m = p.search(cell)
							if m:
								found = m.group(1)
								for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y'):
									try:
										res.append(datetime.strptime(found, fmt))
										break
									except Exception:
										continue
				# also look for label 'fecha de grabaci' and check right-side cells
				for r in range(rows):
					for c in range(cols):
						cell = norm(df.iat[r, c]).strip("'\"")
						if 'fecha de grabaci' in cell.lower():
							for c2 in range(c+1, min(cols, c+6)):
								v = df.iat[r, c2]
								if v is None or (isinstance(v, float) and pd.isna(v)):
									continue
								# numeric excel serial
								try:
									if isinstance(v, (int, float)):
										dt = pd.to_datetime(v, unit='d', origin='1899-12-30', errors='coerce')
										if not pd.isna(dt):
											res.append(dt.to_pydatetime())
										continue
								except Exception:
									pass
								s2 = norm(v).strip("'\"")
								for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S'):
									try:
										res.append(datetime.strptime(s2, fmt))
										break
									except Exception:
										continue
				# remove duplicates while preserving order
				seen = set()
				out = []
				for d in res:
					key = d.strftime('%Y-%m-%d %H:%M:%S')
					if key not in seen:
						seen.add(key)
						out.append(d)
				return out

			all_dates = _extract_all_dates(raw_df)
			if len(all_dates) >= 2:
				base_dt = all_dates[0]
				end_dt = all_dates[1] - timedelta(days=1)
				base_name = base_dt.strftime('%d-%m-%y')
				suffix = end_dt.strftime('%d-%m-%y')
				fname = f"{base_name}_{suffix}.csv"
			else:
				# fallback to previous behavior (use the single internal date and compute second thursday)
				if date is None:
					results.append((file.name, 'NO_DATE', 'No se encontró fecha interna'))
					continue
				base_name = date.strftime('%d-%m-%y')
				second = second_thursday_from(date)
				suffix = second.strftime('%d-%m-%y')
				fname = f"{base_name}_{suffix}.csv"

			# guardar fichero resultante (aplicable en ambos casos)
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
# --- Uploaders para ficheros maestros de secciones (congelado, fresco, seco)
st.sidebar.markdown("---")
st.sidebar.write("Subir ficheros maestros para las secciones (opcional). Se guardarán en las carpetas `congelado/`, `fresco/`, `seco/`.")

# congelado
congelado_dir = Path('congelado')
congelado_dir.mkdir(parents=True, exist_ok=True)
congelado_uploads = st.sidebar.file_uploader("Subir ficheros para 'congelado' - varios permitidos", type=['xls', 'xlsx'], accept_multiple_files=True, key='congelado_uploader')
if congelado_uploads:
	saved_c = []
	for up in congelado_uploads:
		try:
			fn = up.name
			target = congelado_dir / fn
			with open(target, 'wb') as fh:
				fh.write(up.getvalue())
			saved_c.append(fn)
		except Exception as e:
			st.sidebar.error(f"Error guardando {up.name} en congelado/: {e}")
	if saved_c:
		st.sidebar.success(f"Guardados en congelado/: {', '.join(saved_c)}")

# fresco
fresco_dir = Path('fresco')
fresco_dir.mkdir(parents=True, exist_ok=True)
fresco_uploads = st.sidebar.file_uploader("Subir ficheros para 'fresco' - varios permitidos", type=['xls', 'xlsx'], accept_multiple_files=True, key='fresco_uploader')
if fresco_uploads:
	saved_f = []
	for up in fresco_uploads:
		try:
			fn = up.name
			target = fresco_dir / fn
			with open(target, 'wb') as fh:
				fh.write(up.getvalue())
			saved_f.append(fn)
		except Exception as e:
			st.sidebar.error(f"Error guardando {up.name} en fresco/: {e}")
	if saved_f:
		st.sidebar.success(f"Guardados en fresco/: {', '.join(saved_f)}")

# seco
seco_dir = Path('seco')
seco_dir.mkdir(parents=True, exist_ok=True)
seco_uploads = st.sidebar.file_uploader("Subir ficheros para 'seco' - varios permitidos", type=['xls', 'xlsx'], accept_multiple_files=True, key='seco_uploader')
if seco_uploads:
	saved_s = []
	for up in seco_uploads:
		try:
			fn = up.name
			target = seco_dir / fn
			with open(target, 'wb') as fh:
				fh.write(up.getvalue())
			saved_s.append(fn)
		except Exception as e:
			st.sidebar.error(f"Error guardando {up.name} en seco/: {e}")
	if saved_s:
		st.sidebar.success(f"Guardados en seco/: {', '.join(saved_s)}")
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

if st.button("Calcular Pedido"):
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
			from datetime import timedelta as _td
			# calcular lista de jueves en el rango solicitado
			curd = start_sel
			thursdays = []
			while curd <= end_sel:
				if curd.weekday() == 3:
					thursdays.append(curd)
				curd = curd + _td(days=1)
			required_thurs = len(thursdays)

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
				# modo desactivado -> debemos asegurar que la selección final contenga
				# el mismo número de jueves que el rango. Construimos una lista de
				# items donde los ficheros de día único con jueves pueden duplicarse
				# (para permitir usar el mismo jueves varias veces). Los ficheros bulk
				# (rangos) no se duplican.
				item_entries = []
				for c in candidates:
					f, d_or_r, v, has_th = c
					# contar jueves dentro del propio fichero (no limitado al rango seleccionado)
					if isinstance(d_or_r, tuple):
						s, e = d_or_r
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
						# añadir entrada única
						item_entries.append((f, d_or_r, v, th_count, False))
					# tras construir item_entries, comprobar si la suma total de jueves
					# entre todos los items ya alcanza required_thurs; si no, duplicar
					# ficheros de jueves de un solo día prefiriendo archivos distintos.
					current_th_total = sum(it[3] for it in item_entries)
					if current_th_total < required_thurs:
						need = required_thurs - current_th_total
						# listar índices de ficheros de jueves de un solo día (no bulk)
						single_th_idxs = [i for i, it in enumerate(item_entries) if (not it[4]) and it[3] == 1]
						if single_th_idxs:
							# añadir duplicados prefiriendo distintos archivos (round-robin)
							idx_cycle = 0
							while need > 0:
								src_idx = single_th_idxs[idx_cycle % len(single_th_idxs)]
								item_entries.append(item_entries[src_idx])
								need -= 1
								idx_cycle += 1
						# si no hay single_th_idxs no hacemos nada (no hay ficheros jueves de un día)
					active_candidates = item_entries

			# construir arrays de valores y contador de jueves por item
			vals = [int(round(c[2] * 100)) for c in active_candidates]
			th_counts = [c[3] for c in active_candidates]

			# subset sum search (meet-in-the-middle) que además preserva el conteo de jueves
			def subset_sums_with_th(items_vals, items_th):
				n = len(items_vals)
				res = []
				for mask in range(1 << n):
					s = 0
					idxs = []
					th = 0
					for i in range(n):
						if mask >> i & 1:
							s += items_vals[i]
							idxs.append(i)
							th += items_th[i]
					res.append((s, idxs, th))
				return res

			n = len(vals)
			best_idxs = []
			# función auxiliar para elegir el mejor subconjunto priorizando primero
			# la cercanía en número de jueves respecto a required_thurs y luego
			# la diferencia absoluta respecto al objetivo de ventas
			def pick_best(subsets):
				# calcular la distancia mínima en número de jueves
				min_th_diff = min(abs(required_thurs - s[2]) for s in subsets)
				candidates = [s for s in subsets if abs(required_thurs - s[2]) == min_th_diff]
				# entre los candidatos, seleccionar el que minimice la diferencia de ventas
				best = min(candidates, key=lambda x: abs(x[0] - target))
				return best[1], best[2]

			if n <= 20:
				subsets = subset_sums_with_th(vals, th_counts)
				best_idxs, best_th = pick_best(subsets)
			else:
				# split
				h = n // 2
				A_vals = vals[:h]
				B_vals = vals[h:]
				A_th = th_counts[:h]
				B_th = th_counts[h:]
				sa = subset_sums_with_th(A_vals, A_th)
				sb = subset_sums_with_th(B_vals, B_th)
				sa_sorted = sorted(sa, key=lambda x: x[0])
				sb_sorted = sorted(sb, key=lambda x: x[0])
				import bisect
				b_sums = [x[0] for x in sb_sorted]
				best_diff = None
				best_combo = None
				# intentamos combinar; priorizamos minimizar (abs(required_thurs - th_total), abs(total-target))
				for s_a, idxs_a, th_a in sa_sorted:
					need = target - s_a
					i = bisect.bisect_left(b_sums, need)
					# revisar un rango razonable de vecinos alrededor de i para encontrar buenas combinaciones
					for j in range(max(0, i-5), min(len(b_sums), i+6)):
						s_b, idxs_b, th_b = sb_sorted[j]
						total = s_a + s_b
						diff = abs(total - target)
						th_total = th_a + th_b
						metric = (abs(required_thurs - th_total), diff)
						if best_combo is None:
							best_combo = (idxs_a, idxs_b, th_total, metric)
						else:
							# comparar por métrica lexicográfica: primero distancia en jueves, después diff
							if metric < best_combo[3]:
								best_combo = (idxs_a, idxs_b, th_total, metric)
				# convertir indices de B ajustando offset
				if best_combo:
					idxs_a, idxs_b, best_th, _ = best_combo
					best_idxs = idxs_a + [i + h for i in idxs_b]

			# archivos elegidos (map indices back to active candidates)
			chosen_candidates = [active_candidates[i] for i in best_idxs]
			# convert to (file, date_or_range, value) tuples for downstream code
			chosen = [(c[0], c[1], c[2]) for c in chosen_candidates]
			# si el toggle evita jueves está desactivado, comprobar que la selección
			# contiene el número de jueves requerido. Si no, avisar en rojo.
			if not avoid_thurs:
				try:
					chosen_th_count = sum([c[3] for c in chosen_candidates])
					if chosen_th_count < required_thurs:
						if chosen_th_count == 0:
							st.error(f"Los ficheros consultados solo contienen 0 jueves mientras que el rango requiere {required_thurs} jueves.")
						else:
							st.warning(f"Los ficheros consultados contienen {chosen_th_count} jueves mientras que el rango requiere {required_thurs} jueves. Se usarán datos disponibles.")
				except Exception:
					pass
			if not chosen:
				st.info('No se encontró una combinación útil de ficheros.')
			else:
				chosen_files = [c[0] for c in chosen]
				# construir lista de ficheros jueves usados (incluye duplicados si el mismo fichero aparece varias veces)
				chosen_thurs_files = []
				for c in chosen_candidates:
					try:
						# si el candidato tiene cuenta de jueves en la posición 3 (item_entries), úsala
						if len(c) >= 4 and isinstance(c[3], int):
							thc = int(c[3])
						else:
							# fallback: parsear nombre y calcular si es jueves o rango con jueves
							parsed = parse_fname_dates(c[0])
							thc = 0
							if isinstance(parsed, tuple):
								s_, e_ = parsed
								cur_ = s_
								while cur_ <= e_:
									if cur_.weekday() == 3:
										thc += 1
									cur_ = cur_ + _td(days=1)
							else:
								if parsed.weekday() == 3:
									thc = 1
						# si este candidato aporta al menos un jueves, añadir su nombre (una vez por aparición)
						if thc > 0:
							chosen_thurs_files.append(c[0].name)
					except Exception:
						pass
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
					# Aplicar solo si la diferencia relativa es al menos 1% (0.01).
					adj_pct = 0.0
					try:
						total_combined = float(res.get('total', 0) or 0)
						chosen_total = float(chosen_sales_total or 0)
						if total_combined != 0:
							raw_pct = (total_combined - chosen_total) / total_combined
							# solo aplicar si la diferencia es >= 1%
							if abs(raw_pct) >= 0.01:
								adj_pct = raw_pct
							else:
								adj_pct = 0.0
					except Exception:
						adj_pct = 0.0

					merged['Cantidad_a_pedir'] = ((consumo_adj - real_adj) * (1.0 + adj_pct)).clip(lower=0).round(2)

					order_df = merged[['Codigo', 'Articulo', 'Unidad_de_Medida', 'Cantidad_a_pedir']]

					# Añadir columna `Unidades_por_embalaje` tomando los valores del maestro (congelado/fresco/seco)
					try:
						# recolectar maestro combinado
						master_rows = _collect_for('Todos')
						if master_rows:
							df_master_all = pd.DataFrame(master_rows)
						else:
							df_master_all = pd.DataFrame(columns=['Nombre', 'Codigo', 'Unidades totales', 'Medida', 'Embalaje', 'Origen fichero'])

						# normalizar y calcular Unidades_por_embalaje en el maestro
						try:
							df_master_all['Unidades totales'] = pd.to_numeric(df_master_all['Unidades totales'].astype(str).str.replace(',', '.'), errors='coerce')
							df_master_all['Embalaje'] = pd.to_numeric(df_master_all['Embalaje'].astype(str).str.replace(',', '.'), errors='coerce')
							def _calc_upe(r):
								try:
									u = float(r['Unidades totales'])
									e = float(r['Embalaje'])
									if pd.isna(u) or pd.isna(e) or e == 0:
										return None
									val = u / e
									if abs(val - round(val)) < 1e-8:
										return int(round(val))
									return round(val, 4)
								except Exception:
									return None
							df_master_all['Unidades_por_embalaje'] = df_master_all.apply(_calc_upe, axis=1)
						except Exception:
							df_master_all['Unidades_por_embalaje'] = None

						# construir mapping por codigo (normalizado)
						df_master_all['__COD__'] = df_master_all['Codigo'].astype(str).str.strip().str.upper()
						mapping = df_master_all.set_index('__COD__')['Unidades_por_embalaje'].to_dict()

						# aplicar al order_df
						order_df['Unidades_por_embalaje'] = order_df['Codigo'].astype(str).str.strip().str.upper().map(mapping)
					except Exception:
						order_df['Unidades_por_embalaje'] = None
					# Redondear a enteros (0.5 hacia arriba) cuando Unidad_de_Medida sea 'Bola' o 'Unidad'
					try:
						if 'Unidad_de_Medida' in order_df.columns and 'Cantidad_a_pedir' in order_df.columns:
							mask_round = order_df['Unidad_de_Medida'].astype(str).str.strip().str.lower().isin(['bola', 'unidad'])
							if mask_round.any():
								import math
								def _round_half_up(x):
									try:
										f = float(x)
									except Exception:
										return x
									# usar floor/ceil para garantizar .5 -> arriba
									if f - math.floor(f) >= 0.5:
										return int(math.ceil(f))
									else:
										return int(math.floor(f))
								order_df.loc[mask_round, 'Cantidad_a_pedir'] = order_df.loc[mask_round, 'Cantidad_a_pedir'].apply(_round_half_up)
					except Exception:
						pass
					# Eliminar de 'Cantidad a pedir' los productos cuyo nombre empiece por ZZ o YY (case-insensitive)
					if 'Articulo' in order_df.columns:
						# excluir artículos que empiecen por ZZ o YY, excepto el producto con código GAMBC
						mask_drop = order_df['Articulo'].astype(str).str.upper().str.startswith(('ZZ', 'YY'), na=False)
						mask_exception = order_df['Codigo'].astype(str).str.strip().str.upper() == 'GAMBC'
						mask_drop = mask_drop & (~mask_exception)
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
							# excluir artículos que empiecen por ZZ o YY, excepto el producto con código GAMBC
							mask_drop_rev = prod_revisar['Articulo'].astype(str).str.upper().str.startswith(('ZZ', 'YY'), na=False)
							mask_exception_rev = prod_revisar['Codigo'].astype(str).str.strip().str.upper() == 'GAMBC'
							mask_drop_rev = mask_drop_rev & (~mask_exception_rev)
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
							'chosen_thurs': chosen_thurs_files,
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


