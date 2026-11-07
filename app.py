# -*- coding: utf-8 -*-
"""
===============================================================================
 CONTROL DE INVENTARIO FÍSICO  |  SMITH & NEPHEW  ·  TECNITRAUMA   (versión web)
-------------------------------------------------------------------------------
 Dos perfiles:
   • PAREJAS DE CONTEO (ingresan con PIN): conteo a ciegas. Pistolean o digitan
     referencias, seleccionan/cierran seriales. NO ven cantidades del sistema,
     costos ni diferencias.
   • ADMINISTRADOR (contraseña): ve todo. Carga maestros, crea parejas, cruces,
     seriales pendientes, dashboard y reportes Excel.

 Datos: se guardan en una base de datos.
   • En línea (Streamlit Cloud + Supabase): defina DB_URL en los "Secrets".
   • Local (sin internet): se crea sola en datos_conteo/inventario.db
 Ningún registro se pierde al cerrar el navegador o recargar la página.

 Ejecutar local:  streamlit run app.py
===============================================================================
"""

import base64
import gzip
import hashlib
import io
import os
import random
import re
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import (Column, Float, Integer, LargeBinary, MetaData, String, Table, Text, create_engine,
                        delete, insert, select, update)

st.set_page_config(
    page_title="Inventario Smith & Nephew | Tecnitrauma",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="auto",
)
pd.set_option("styler.render.max_elements", 5_000_000)

BODEGAS_SMITH = [58, 59, 81, 82, 83, 84]
BODEGAS_SERENA = [66, 67]
BODEGAS_SIN_SERIALES_VALREF = [10, 20, 27]   # bodegas propietarias cuyos seriales NO se suman por la regla Valref
ZONAS = {
    "Smith & Nephew": "SMITH",
    "Serena del Mar · Bod. 66": "SERENA",
    "Serena del Mar · Bod. 67": "SERENA",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIR_DATOS = os.path.join(BASE_DIR, "datos_conteo")
CLAVE_ADMIN_INICIAL = "Tecnitrauma2026"
TZ_COL = timezone(timedelta(hours=-5))   # hora de Colombia (el servidor en la nube usa UTC)


def ahora() -> datetime:
    return datetime.now(TZ_COL).replace(tzinfo=None)



LOGO_TECNITRAUMA_B64 = "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"


C = dict(
    navy="#0B2545", navy2="#13315C", teal="#2A88C9", rojo="#D64545", ambar="#F2A541",
    gris="#8D99AE", azul="#0E7490", verde="#2A9D8F", fondo="#F4F6FA",
)


CSS = f"""
<style>
.block-container {{padding-top: 1.1rem; padding-bottom: 2rem;}}
.banner {{background: linear-gradient(90deg, {C['navy']} 0%, {C['navy2']} 55%, {C['teal']} 100%);
  color:#fff; padding:18px 26px; border-radius:14px; margin-bottom:12px;
  box-shadow:0 4px 18px rgba(11,37,69,.18);}}
.banner h1 {{color:#fff; font-size:1.55rem; margin:0; font-weight:800; letter-spacing:.01em;}}
.banner p {{margin:3px 0 0 0; opacity:.88; font-size:.92rem;}}
.kpi {{background:#FFFFFF; border-radius:14px; padding:14px 16px 12px 16px;
  box-shadow:0 2px 12px rgba(11,37,69,.08); border-left:6px solid var(--c); min-height:112px;}}
.kpi .t {{font-size:.72rem; color:#5A6B85; text-transform:uppercase; letter-spacing:.07em; font-weight:700;}}
.kpi .v {{font-size:1.65rem; font-weight:800; color:{C['navy']}; line-height:1.25; margin-top:4px;}}
.kpi .s {{font-size:.78rem; color:#7A8AA0; margin-top:2px;}}
.kpi .bar {{height:6px; background:#E6EAF1; border-radius:4px; margin-top:8px; overflow:hidden;}}
.kpi .bar > div {{height:6px; background:var(--c); border-radius:4px;}}
.alerta {{padding:9px 14px; border-radius:10px; margin:5px 0; font-size:.88rem;}}
.alerta.roja  {{background:#FDECEC; border-left:5px solid {C['rojo']};  color:#7A1F1F;}}
.alerta.ambar {{background:#FFF5E6; border-left:5px solid {C['ambar']}; color:#7A4B00;}}
.alerta.verde {{background:#E8F6F3; border-left:5px solid {C['verde']}; color:#145A50;}}
.alerta.azul  {{background:#EAF3FA; border-left:5px solid {C['azul']};  color:#14425A;}}
.seccion {{font-size:1.05rem; font-weight:800; color:{C['navy']}; border-bottom:2px solid {C['teal']};
  padding-bottom:4px; margin:16px 0 10px 0;}}
.logo-box {{background:#fff; border-radius:12px; padding:12px 10px; text-align:center; box-shadow:0 2px 10px rgba(11,37,69,.10); margin-bottom:8px;}}
.logo-box img {{max-width:100%; height:auto;}}
.logo-ph {{border:2px dashed {C['teal']}; border-radius:12px; padding:16px 10px; text-align:center;
  color:{C['navy']}; font-weight:900; font-size:1.25rem; letter-spacing:.04em; background:#fff;}}
.logo-ph small {{display:block; font-weight:500; font-size:.7rem; color:#7A8AA0; letter-spacing:0;}}
.chip {{display:inline-block; padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:700; margin:2px 4px 2px 0;}}
.chip.ok {{background:#E8F6F3; color:#145A50;}}
.chip.no {{background:#FDECEC; color:#7A1F1F;}}
.chip.info {{background:#EAF3FA; color:#14425A;}}
div[data-testid="stTabs"] button p {{font-weight:700;}}
</style>
"""


def norm(s) -> str:
    """Normaliza texto para comparar nombres de columnas (sin tildes, espacios ni signos)."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def find_col(df: pd.DataFrame, *cands, parcial: bool = True):
    """Busca una columna por varios nombres posibles (exacto primero, luego parcial)."""
    mapa = {norm(c): c for c in df.columns}
    for c in cands:
        if norm(c) in mapa:
            return mapa[norm(c)]
    if parcial:
        for c in cands:
            k = norm(c)
            if len(k) < 4:
                continue
            for nk, orig in mapa.items():
                if nk.startswith(k):
                    return orig
    return None


def to_num(s) -> pd.Series:
    """Convierte textos tipo '$1,367,400.00', '.00', '68.32 %' a número."""
    s = pd.Series(s)
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").astype("float64")
    t = s.astype("string").str.strip()
    t = t.str.replace(r"[\$\s%]", "", regex=True).str.replace(",", "", regex=False)
    t = t.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA, "NaN": pd.NA, "-": pd.NA})
    return pd.to_numeric(t, errors="coerce").astype("float64")


def limpiar_codigo(s) -> pd.Series:
    """Referencia limpia: mayúsculas, sin espacios, sin '.0' de Excel."""
    t = pd.Series(s).astype("string").fillna("").str.upper().str.strip()
    t = t.str.replace(r"\s+", "", regex=True)
    t = t.str.replace(r"^(\d+)\.0+$", r"\1", regex=True)
    t = t.replace({"NAN": "", "NONE": "", "<NA>": "", "NAT": ""})
    return t.astype(str)


def limpiar_lote(s) -> pd.Series:
    """Lote limpio (conserva el '*' para poder detectarlo)."""
    t = limpiar_codigo(s)
    t = t.str.replace(r"^[^A-Z0-9\*]+", "", regex=True).str.replace(r"[^A-Z0-9\*]+$", "", regex=True)
    return t


def clave(s: pd.Series, es_lote: bool = False) -> pd.Series:
    """Llave de cruce: sin asteriscos, sin ceros a la izquierda."""
    t = pd.Series(s).astype(str).str.replace("*", "", regex=False).str.strip()
    t2 = t.str.lstrip("0")
    t = t2.where(t2 != "", t)
    if es_lote:
        t = t.where(~t.isin(["", "NOBATCH", "SINLOTE", "NA", "N/A", "0"]), "SIN LOTE")
    return t


def tiene_asterisco(s) -> pd.Series:
    return pd.Series(s).astype("string").fillna("").str.contains(r"\*", regex=True)


def tipo_asterisco(s) -> pd.Series:
    t = pd.Series(s).astype("string").fillna("")
    return np.where(t.str.contains(r"\*\*", regex=True), "**", np.where(t.str.contains(r"\*", regex=True), "*", ""))


def _una_fecha(v):
    try:
        if v is None or (not isinstance(v, str) and pd.isna(v)):
            return None
        if isinstance(v, (pd.Timestamp, datetime, date)):
            ts = pd.Timestamp(v)
        else:
            t = str(v).strip()
            if not t or t in ("nan", "NaT", "None", "<NA>"):
                return None
            m = re.match(r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", t)
            if m:
                ts = pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            elif re.match(r"^\d{5}(\.0+)?$", t):
                ts = pd.Timestamp("1899-12-30") + pd.Timedelta(days=int(float(t)))
            else:
                ts = pd.to_datetime(t, dayfirst=True, errors="coerce")
        if pd.isna(ts) or ts.year < 1950 or ts.year > 2200:
            return None
        return pd.Timestamp(ts.year, ts.month, ts.day)
    except Exception:
        return None


def parse_fecha(s) -> pd.Series:
    """Convierte fechas mixtas (datetime de Excel, 'YYYY/MM/DD', 'DD/MM/YYYY', seriales de Excel)."""
    s = pd.Series(s, dtype="object")
    cache = {}
    vals = []
    for v in s:
        k = v if isinstance(v, (str, int, float)) else repr(v)
        if k not in cache:
            cache[k] = _una_fecha(v)
        vals.append(cache[k])
    return pd.Series(pd.to_datetime(pd.Series(vals, dtype="object"), errors="coerce"), dtype="datetime64[ns]").set_axis(s.index)


def estado_venc(fechas: pd.Series, dias_alerta: int):
    hoy = pd.Timestamp(date.today())
    dias = (fechas - hoy).dt.days
    est = np.select(
        [fechas.isna(), dias < 0, dias <= dias_alerta],
        ["SIN FECHA", "VENCIDO", "PRÓXIMO A VENCER"],
        "VIGENTE",
    )
    return dias, est


def leer_csv_flexible(data: bytes, sep=None, header="infer") -> pd.DataFrame:
    for enc in ("utf-8-sig", "latin-1"):
        try:
            txt = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if sep is None:
        primera = txt.splitlines()[0] if txt else ""
        sep = ";" if primera.count(";") >= primera.count(",") else ","
    return pd.read_csv(io.StringIO(txt), sep=sep, dtype=str, header=0 if header == "infer" else header,
                       index_col=False, keep_default_na=True, on_bad_lines="skip")


def detectar_encabezado(raw: pd.DataFrame, obligatorios, alguno) -> int | None:
    for i in range(min(40, len(raw))):
        vals = {norm(v) for v in raw.iloc[i].tolist() if v is not None and str(v) != "nan"}
        if any(o in vals for o in obligatorios) and any(a in vals for a in alguno):
            return i
    return None


def unicos(cols):
    vistos, out = {}, []
    for c in cols:
        c = "COL" if c is None or str(c) == "nan" else str(c).strip()
        if c in vistos:
            vistos[c] += 1
            c = f"{c}_{vistos[c]}"
        else:
            vistos[c] = 0
        out.append(c)
    return out


def parse_gs1(codigo: str) -> dict:
    """Interpreta un código GS1-128 / DataMatrix: (01) GTIN, (17) vencimiento, (10) lote, (21) serial."""
    s = str(codigo).strip().replace("\x1d", "|").replace("]C1", "").replace("]d2", "")
    res = {}
    if "(" in s:
        for ai, val in re.findall(r"\((\d{2,4})\)([^(]*)", s):
            res[ai] = val.strip("|").strip()
        return res
    if not (s[:2] == "01" and len(s) >= 16 and s[2:16].isdigit()):
        return res
    i = 0
    while i < len(s):
        ai = s[i:i + 2]
        if ai == "01" and len(s) >= i + 16:
            res["01"] = s[i + 2:i + 16]; i += 16
        elif ai in ("11", "15", "17") and len(s) >= i + 8:
            res[ai] = s[i + 2:i + 8]; i += 8
        elif ai in ("10", "21"):
            j = s.find("|", i + 2)
            j = len(s) if j < 0 else j
            res[ai] = s[i + 2:j]; i = j + 1
        else:
            break
    return res


def gs1_fecha(yymmdd: str):
    try:
        yy, mm, dd = int(yymmdd[:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
        if dd == 0:
            dd = 28
        return pd.Timestamp(year=2000 + yy, month=mm, day=dd)
    except Exception:
        return pd.NaT


def fmt_num(x, dec=0) -> str:
    try:
        if round(float(x), dec) == 0:
            x = 0.0
        return f"{x:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def fmt_cop(x) -> str:
    try:
        signo = "-" if x < 0 else ""
        return f"{signo}$ {fmt_num(abs(x))}"
    except Exception:
        return "$ 0"


def pct(a, b) -> float:
    return float(a) / float(b) * 100 if b else 0.0


@st.cache_data(show_spinner=False)
def hojas_excel(data: bytes) -> list:
    return pd.ExcelFile(io.BytesIO(data)).sheet_names


@st.cache_data(show_spinner="Leyendo Templete / Kardex…")
def leer_templete(data: bytes, nombre: str, hoja=None) -> pd.DataFrame:
    if nombre.lower().endswith((".csv", ".txt")):
        raw = leer_csv_flexible(data, header=None)
    else:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=hoja if hoja is not None else 0, header=None, dtype=object)
    h = detectar_encabezado(raw, {"ITEMNUMBER", "REFERENCIA", "CODIGO"}, {"BATCHNUMBER", "LOTE", "BATCH"})
    if h is None:
        raise ValueError("No se encontró la fila de encabezados (Item number / Batch number) en el Templete.")
    df = raw.iloc[h + 1:].copy()
    df.columns = unicos(raw.iloc[h].tolist())
    c_ref = find_col(df, "Item number", "Referencia", "Codigo")
    c_lot = find_col(df, "Batch number", "Lote", "Batch")
    c_qty = find_col(df, "Physical inventory", "Cantidad", "Existencia", "Total available")
    c_des = find_col(df, "Product name", "Descripcion", "Nombre")
    c_exp = find_col(df, "Expiration date", "Vencimiento", "Fecha vencimiento")
    c_loc = find_col(df, "Location", "Ubicacion")
    c_wh = find_col(df, "Warehouse", "Bodega")
    out = pd.DataFrame({
        "REFERENCIA": limpiar_codigo(df[c_ref]),
        "DESCRIPCION": df[c_des].astype("string").fillna("").str.strip().astype(str) if c_des else "",
        "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
        "CANTIDAD": to_num(df[c_qty]).fillna(0) if c_qty else 1,
        "VENCE": parse_fecha(df[c_exp]) if c_exp else pd.NaT,
        "UBICACION": df[c_loc].astype("string").fillna("").astype(str) if c_loc else "",
        "BODEGA_SMITH": df[c_wh].astype("string").fillna("").astype(str) if c_wh else "",
    })
    out = out[(out["REFERENCIA"] != "") & (out["REFERENCIA"].map(norm) != "ITEMNUMBER")].copy()
    out["K_REF"] = clave(out["REFERENCIA"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True)
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Procesando archivo NAL (inventario nacional)…")
def leer_nal(data: bytes) -> pd.DataFrame:
    df = leer_csv_flexible(data, sep=";")
    df.columns = [str(c).strip() for c in df.columns]
    c_tip = find_col(df, "TIP", parcial=False)
    if c_tip is None:
        raise ValueError("El archivo NAL no tiene la columna 'TIP'.")
    df = df[df[c_tip].astype("string").str.strip().str.upper().isin(["REF", "COM", "LOT", "SET"])].copy()
    c_bp = find_col(df, "BODEGA PROPIE.", "BODEGA PROPIETARIA")
    c_be = find_col(df, "BOD-EXISTENCIA", "BODEGA EXISTENCIA")
    c_cod = find_col(df, "CODIGO", parcial=False)
    c_ser = find_col(df, "SERIAL", parcial=False)
    c_nom = find_col(df, "NOMBRE", parcial=False)
    c_lot = find_col(df, "COD. CLIENTE", parcial=False)
    c_fec = find_col(df, "FEC. CRE", parcial=False)
    c_qty = find_col(df, "CANT. ACTUAL SER", parcial=False)
    c_cmp = find_col(df, "CANT. COMPO-SER", parcial=False)
    c_cos = find_col(df, "COS. SER. ACTUAL", parcial=False)
    c_set = find_col(df, "NOMBRE  SET", "NOMBRE SET", parcial=False)
    c_lin = find_col(df, "LINEA", parcial=False)
    tip = df[c_tip].astype("string").str.strip().str.upper()
    es_rl = tip.isin(["REF", "LOT"])
    out = pd.DataFrame({
        "TIP": tip.astype(str),
        "BOD_PROP": pd.to_numeric(df[c_bp].astype("string").str.extract(r"^\s*(\d+)")[0], errors="coerce").astype("float64"),
        "BOD_PROP_NOM": df[c_bp].astype("string").fillna("").str.strip().astype(str),
        "BOD_EXIST": pd.to_numeric(df[c_be].astype("string").str.extract(r"^\s*(\d+)")[0], errors="coerce").astype("float64") if c_be else np.nan,
        "BOD_EXIST_NOM": df[c_be].astype("string").fillna("").str.strip().astype(str) if c_be else "",
        "CODIGO": limpiar_codigo(df[c_cod]),
        "SERIAL": limpiar_codigo(df[c_ser]) if c_ser else "",
        "NOMBRE": df[c_nom].astype("string").fillna("").str.strip().astype(str) if c_nom else "",
        "LOTE": np.where(es_rl, limpiar_lote(df[c_lot]) if c_lot else "", ""),
        "VENCE": parse_fecha(df[c_fec].where(es_rl)) if c_fec else pd.NaT,
        "CANT": to_num(df[c_qty]).fillna(0) if c_qty else 0,
        "CANT_COMPO": to_num(df[c_cmp]).fillna(0) if c_cmp else 0,
        "COSTO_SER": to_num(df[c_cos]).fillna(0) if c_cos else 0,
        "NOMBRE_SET": df[c_set].astype("string").fillna("").str.strip().astype(str) if c_set else "",
        "LINEA": df[c_lin].astype("string").fillna("").str.strip().astype(str) if c_lin else "",
    })
    # Nombre del set para todas las filas a partir de la fila 'SET'
    sets = out[out["TIP"] == "SET"].drop_duplicates("SERIAL").set_index("SERIAL")["NOMBRE"]
    out["SET_NOMBRE"] = out["SERIAL"].map(sets).fillna(out["NOMBRE_SET"]).fillna("")
    out["K_REF"] = clave(out["CODIGO"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True)
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Leyendo Valref (validación de referencias y lotes)…")
def leer_valref(data: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(io.BytesIO(data), dtype=str)
    else:
        df = leer_csv_flexible(data)
    df.columns = [str(c).strip() for c in df.columns]
    c_ref = find_col(df, "COD. RELACION", "Item number", "Referencia proveedor", parcial=False)
    c_int = find_col(df, "R E F E R E N C I A", "REFERENCIA", parcial=False)
    if c_ref is None:
        c_ref = c_int
    if c_ref is None:
        raise ValueError("Valref: no se encontró la columna de referencia (COD. RELACION / REFERENCIA).")
    df = df[df[c_ref].astype("string").fillna("").map(norm) != norm(c_ref)].copy()   # quita encabezados repetidos
    c_nom = find_col(df, "N O M B R E", "NOMBRE", "DESCRIPCION")
    c_ean = find_col(df, "REFER-PROVEED.", "EAN", "GTIN")
    c_cos = find_col(df, "COSTO PROMEDIO", "COSTO")
    c_pre = find_col(df, "PRECIO VENTA", "PRECIO")
    c_lot = None
    for cand in ("LOTE", "LOT", "BATCH NUMBER", "NUMERO DE LOTE", "NRO LOTE", "NO LOTE", "LOTES"):
        c_lot = find_col(df, cand, parcial=False)
        if c_lot:
            break
    eval_cols = [c_lot] if c_lot else [c for c in (c_ref, c_int) if c]
    texto_eval = df[eval_cols].astype("string").fillna("").agg(" ".join, axis=1)
    out = pd.DataFrame({
        "REFERENCIA": limpiar_codigo(df[c_ref]),
        "COD_INTERNO": df[c_int].astype("string").fillna("").str.strip().astype(str) if c_int else "",
        "DESCRIPCION": df[c_nom].astype("string").fillna("").str.strip().astype(str) if c_nom else "",
        "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
        "EAN": df[c_ean].astype("string").fillna("").str.replace(r"\D", "", regex=True).astype(str) if c_ean else "",
        "COSTO": to_num(df[c_cos]).fillna(0) if c_cos else 0,
        "PRECIO": to_num(df[c_pre]).fillna(0) if c_pre else 0,
        "ASTERISCO": tipo_asterisco(texto_eval),
    })
    out = out[out["REFERENCIA"] != ""].copy()
    out["VALIDA"] = out["ASTERISCO"] == ""
    out["K_REF"] = clave(out["REFERENCIA"])
    out["K_LOTE"] = clave(out["LOTE"], es_lote=True) if c_lot else "SIN LOTE"
    out.attrs["col_lote"] = c_lot or "(sin columna de lote: se evaluó la referencia)"
    return out.reset_index(drop=True)


@st.cache_data(show_spinner="Leyendo archivo de pistoleo…")
def leer_pistoleo(data: bytes, nombre: str) -> pd.DataFrame:
    if nombre.lower().endswith((".csv", ".txt")):
        candidatos = {"CSV": leer_csv_flexible(data, header=None)}
    else:
        xls = pd.ExcelFile(io.BytesIO(data))
        orden = sorted(xls.sheet_names, key=lambda n: (0 if norm(n) in ("INVENTARIO", "PISTOLEO", "CONTEO") else 1))
        orden = [n for n in orden if norm(n) not in ("MAESTRO", "BATCHMAESTRO", "RESUMEN")]
        candidatos = {n: pd.read_excel(xls, sheet_name=n, header=None, dtype=object) for n in orden[:4]}
    for hoja, raw in candidatos.items():
        h = detectar_encabezado(raw, {"REFERENCIA", "EAN", "ITEMNUMBER", "CODIGO"}, {"LOTE", "CANTIDAD", "BATCHNUMBER"})
        if h is None:
            continue
        df = raw.iloc[h + 1:].copy()
        df.columns = unicos(raw.iloc[h].tolist())
        df = df.dropna(how="all")
        c_ean = find_col(df, "EAN", "GTIN", "CODIGO BARRAS", parcial=False)
        c_ref = find_col(df, "REFERENCIA", "Item number", "CODIGO", parcial=False)
        c_lot = find_col(df, "LOTE", "Batch number", parcial=False)
        c_qty = find_col(df, "CANTIDAD", "CANT", "QTY", parcial=False)
        c_des = find_col(df, "DESCRIPCION", "Product name", "NOMBRE", parcial=False)
        c_ven = find_col(df, "VENCIMIENTO", "Expiration date", "FECHA VENCIMIENTO", parcial=False)
        c_gon = find_col(df, "GONDOLA", "UBICACION", "ZONA", parcial=False)
        c_niv = find_col(df, "NIVEL", parcial=False)
        c_fh = find_col(df, "FECHA_HORA REGISTRO", "FECHA HORA REGISTRO", "FECHA", parcial=True)
        c_ser = find_col(df, "SERIAL", parcial=False)
        out = pd.DataFrame({
            "EAN": df[c_ean].astype("string").fillna("").str.strip().astype(str) if c_ean else "",
            "GONDOLA": df[c_gon].astype("string").fillna("").str.strip().astype(str) if c_gon else "",
            "NIVEL": df[c_niv].astype("string").fillna("").str.strip().astype(str) if c_niv else "",
            "REFERENCIA": limpiar_codigo(df[c_ref]) if c_ref else "",
            "DESCRIPCION": df[c_des].astype("string").fillna("").str.strip().astype(str) if c_des else "",
            "LOTE": limpiar_lote(df[c_lot]) if c_lot else "",
            "VENCE": parse_fecha(df[c_ven]) if c_ven else pd.NaT,
            "CANTIDAD": to_num(df[c_qty]) if c_qty else np.nan,
            "SERIAL": limpiar_codigo(df[c_ser]) if c_ser else "",
            "FECHA_REG": df[c_fh].astype("string").fillna("").astype(str) if c_fh else "",
        })
        out = out[(out["REFERENCIA"] != "") | (out["EAN"] != "")].copy()
        out["CANTIDAD"] = out["CANTIDAD"].fillna(1)
        out["ARCHIVO"] = nombre
        out["HOJA"] = hoja
        return out.reset_index(drop=True)
    return pd.DataFrame(columns=["EAN", "GONDOLA", "NIVEL", "REFERENCIA", "DESCRIPCION", "LOTE", "VENCE",
                                 "CANTIDAD", "SERIAL", "FECHA_REG", "ARCHIVO", "HOJA"])


@st.cache_data(show_spinner="Cargando maestros Smith (GTIN y lotes) del archivo de pistoleo…")
def leer_maestros_tpn(data: bytes):
    """Devuelve (mapa GTIN->referencia, DataFrame de lotes Smith) si el archivo trae esas hojas."""
    try:
        xls = pd.ExcelFile(io.BytesIO(data))
    except Exception:
        return {}, pd.DataFrame()
    nombres = {norm(n): n for n in xls.sheet_names}
    gtin = {}
    if "MAESTRO" in nombres:
        m = pd.read_excel(xls, sheet_name=nombres["MAESTRO"], dtype=str)
        c_it = find_col(m, "Item number", "REFERENCIA")
        for cg in [find_col(m, "GTIN", parcial=False), find_col(m, "EAN/UPC", "EAN", parcial=False)]:
            if cg and c_it:
                k = m[cg].astype("string").fillna("").str.replace(r"\D", "", regex=True).str.lstrip("0")
                v = limpiar_codigo(m[c_it])
                gtin.update({a: b for a, b in zip(k, v) if a and b})
    lotes = pd.DataFrame()
    if "BATCHMAESTRO" in nombres:
        b = pd.read_excel(xls, sheet_name=nombres["BATCHMAESTRO"], dtype=str)
        c_b = find_col(b, "Batch number", "LOTE")
        c_i = find_col(b, "Item number", "REFERENCIA")
        c_s = find_col(b, "Batch disposition status", "Estado")
        if c_b and c_i:
            lotes = pd.DataFrame({
                "K_REF": clave(limpiar_codigo(b[c_i])),
                "K_LOTE": clave(limpiar_lote(b[c_b]), es_lote=True),
                "ESTADO_LOTE": b[c_s].astype("string").fillna("").astype(str) if c_s else "",
            }).drop_duplicates(["K_REF", "K_LOTE"])
    return gtin, lotes


def conciliar_com_lot(nal_f: pd.DataFrame) -> pd.DataFrame:
    """COM = total del componente en el serial; debe ser igual a la suma de sus filas LOT."""
    com = nal_f[nal_f["TIP"] == "COM"].groupby(["SERIAL", "K_REF"], as_index=False).agg(
        BODEGA=("BOD_PROP", "first"), SET=("SET_NOMBRE", "first"), REFERENCIA=("CODIGO", "first"),
        DESCRIPCION=("NOMBRE", "first"), CANT_COM=("CANT", "sum"))
    lot = nal_f[nal_f["TIP"] == "LOT"].groupby(["SERIAL", "K_REF"], as_index=False).agg(
        BODEGA_L=("BOD_PROP", "first"), SET_L=("SET_NOMBRE", "first"), REFERENCIA_L=("CODIGO", "first"),
        DESCRIPCION_L=("NOMBRE", "first"), SUMA_LOT=("CANT", "sum"), N_LOTES=("K_LOTE", "nunique"))
    m = com.merge(lot, on=["SERIAL", "K_REF"], how="outer")
    for a, b in [("BODEGA", "BODEGA_L"), ("SET", "SET_L"), ("REFERENCIA", "REFERENCIA_L"), ("DESCRIPCION", "DESCRIPCION_L")]:
        m[a] = m[a].fillna(m[b])
    m = m.drop(columns=["BODEGA_L", "SET_L", "REFERENCIA_L", "DESCRIPCION_L"])
    m[["CANT_COM", "SUMA_LOT", "N_LOTES"]] = m[["CANT_COM", "SUMA_LOT", "N_LOTES"]].fillna(0)
    m["DIF_COM_LOT"] = m["SUMA_LOT"] - m["CANT_COM"]
    m["CUADRA"] = np.where(m["DIF_COM_LOT"] == 0, "Sí", "No")
    return m


def para_excel(df: pd.DataFrame, quitar=("K_REF", "K_LOTE", "ID", "REVISADA")) -> pd.DataFrame:
    d = df.drop(columns=[c for c in quitar if c in df.columns]).copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.tz_localize(None) if getattr(d[c].dt, "tz", None) else d[c]
        elif d[c].dtype == "object" or str(d[c].dtype).startswith("string") or str(d[c].dtype) == "str":
            d[c] = d[c].astype("object").where(d[c].notna(), "")
            d[c] = d[c].map(lambda x: EMOJI.sub("", x).strip() if isinstance(x, str) else x)
    d = d.rename(columns=NOMBRES)
    d.columns = unicos(list(d.columns))
    return d


def a_excel(hojas: dict, titulo: str, subtitulo: str = "") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter", datetime_format="dd/mm/yyyy", date_format="dd/mm/yyyy") as xw:
        wb = xw.book
        f_tit = wb.add_format({"bold": True, "font_size": 15, "font_color": C["navy"]})
        f_sub = wb.add_format({"italic": True, "font_size": 9, "font_color": "#5A6B85"})
        f_hdr = wb.add_format({"bold": True, "bg_color": C["navy"], "font_color": "#FFFFFF", "border": 1,
                               "text_wrap": True, "valign": "vcenter", "align": "center"})
        f_money = wb.add_format({"num_format": '"$" #,##0;[Red]-"$" #,##0'})
        f_int = wb.add_format({"num_format": "#,##0;[Red]-#,##0"})
        f_dec = wb.add_format({"num_format": "#,##0.0"})
        f_rojo = wb.add_format({"bg_color": "#F8D7DA", "font_color": "#842029"})
        f_ambar = wb.add_format({"bg_color": "#FFE8C2", "font_color": "#7A4B00"})
        f_verde = wb.add_format({"bg_color": "#D7F0EA", "font_color": "#145A50"})
        f_neg = wb.add_format({"font_color": "#C0392B", "bold": True})
        f_pos = wb.add_format({"font_color": "#1F5FA8", "bold": True})
        for nombre, df in hojas.items():
            hoja = re.sub(r"[\[\]\:\*\?\/\\]", "", nombre)[:31]
            if df is None or len(df) == 0:
                df = pd.DataFrame({"MENSAJE": ["Sin registros para esta sección"]})
            df = df.reset_index(drop=True)
            df.to_excel(xw, sheet_name=hoja, startrow=3, index=False)
            ws = xw.sheets[hoja]
            ws.write(0, 0, titulo, f_tit)
            ws.write(1, 0, f"{subtitulo}   ·   Generado: {ahora():%d/%m/%Y %H:%M}", f_sub)
            n, cols = len(df), list(df.columns)
            for j, c in enumerate(cols):
                ws.write(3, j, c, f_hdr)
                muestra = df[c].astype(str).head(400)
                ancho = min(max(len(str(c)) * 0.9, muestra.str.len().quantile(0.9) if n else 8) + 3, 55)
                fmt = None
                if any(k in str(c) for k in ("VALOR", "COSTO", "$")):
                    fmt = f_money
                elif pd.api.types.is_numeric_dtype(df[c]):
                    fmt = f_dec if str(c).startswith("%") or "AVANCE" in str(c) else f_int
                ws.set_column(j, j, ancho, fmt)
            ws.set_row(3, 32)
            ws.freeze_panes(4, 1 if len(cols) > 3 else 0)
            ws.autofilter(3, 0, 3 + n, len(cols) - 1)
            from xlsxwriter.utility import xl_col_to_name
            if "ESTADO VENC." in cols and n:
                L = xl_col_to_name(cols.index("ESTADO VENC."))
                ws.conditional_format(4, 0, 3 + n, len(cols) - 1,
                                      {"type": "formula", "criteria": f'=${L}5="VENCIDO"', "format": f_rojo})
                ws.conditional_format(4, 0, 3 + n, len(cols) - 1,
                                      {"type": "formula", "criteria": f'=${L}5="PRÓXIMO A VENCER"', "format": f_ambar})
            if "ESTADO" in cols and n:
                j = cols.index("ESTADO")
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "FALTANTE", "format": f_rojo})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "SOBRANTE", "format": f_ambar})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "CUADRADO", "format": f_verde})
                ws.conditional_format(4, j, 3 + n, j, {"type": "text", "criteria": "containing", "value": "NO", "format": f_ambar})
            for nom_dif in ("DIFERENCIA", "DIF. (LOT - COM)"):
                if nom_dif in cols and n:
                    j = cols.index(nom_dif)
                    ws.conditional_format(4, j, 3 + n, j, {"type": "cell", "criteria": "<", "value": 0, "format": f_neg})
                    ws.conditional_format(4, j, 3 + n, j, {"type": "cell", "criteria": ">", "value": 0, "format": f_pos})
    return buf.getvalue()


def kpi(col, titulo, valor, sub="", color=C["teal"], barra=None):
    barra_html = ""
    if barra is not None:
        b = max(0.0, min(100.0, float(barra)))
        barra_html = f'<div class="bar"><div style="width:{b:.1f}%"></div></div>'
    col.markdown(f'<div class="kpi" style="--c:{color}"><div class="t">{titulo}</div>'
                 f'<div class="v">{valor}</div><div class="s">{sub}</div>{barra_html}</div>',
                 unsafe_allow_html=True)


def alerta(texto, tipo="azul"):
    st.markdown(f'<div class="alerta {tipo}">{texto}</div>', unsafe_allow_html=True)


def seccion(texto):
    st.markdown(f'<div class="seccion">{texto}</div>', unsafe_allow_html=True)


def estilo_filas(df: pd.DataFrame):
    """Resalta en rojo lo vencido y en ámbar lo próximo a vencer; colorea estados."""
    def fila(r):
        ev = r.get("ESTADO VENC.", r.get("ESTADO_VENC", ""))
        if ev == "VENCIDO":
            return ["background-color:#F8D7DA;color:#842029;font-weight:600"] * len(r)
        if ev == "PRÓXIMO A VENCER":
            return ["background-color:#FFE8C2;color:#7A4B00"] * len(r)
        return [""] * len(r)
    sty = df.style.apply(fila, axis=1)
    if "ESTADO" in df.columns:
        def est(v):
            v = str(v)
            if "FALTANTE" in v:
                return "color:#B42318;font-weight:700"
            if "SOBRANTE" in v or "NO COINCIDE" in v or "NO ESTÁ" in v:
                return "color:#B54708;font-weight:700"
            if "CUADRADO" in v:
                return "color:#067647;font-weight:700"
            return ""
        sty = sty.map(est, subset=["ESTADO"])
    fmt = {}
    for c in df.columns:
        if any(k in c for k in ("VALOR", "COSTO")):
            fmt[c] = lambda x: fmt_cop(x) if pd.notna(x) else ""
        elif c in ("VENCIMIENTO", "VENCE"):
            fmt[c] = lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else ""
        elif pd.api.types.is_float_dtype(df[c]):
            fmt[c] = lambda x: fmt_num(x) if pd.notna(x) else ""
    return sty.format(fmt)


def mostrar_tabla(df: pd.DataFrame, alto=460, limite=6000):
    if df is None or df.empty:
        st.info("Sin registros para mostrar con los filtros actuales.")
        return
    d = para_excel(df)
    if len(d) > limite:
        st.caption(f"Mostrando las primeras {fmt_num(limite)} de {fmt_num(len(d))} filas (el Excel exportado contiene todo).")
        d = d.head(limite)
    st.dataframe(estilo_filas(d), height=alto, hide_index=True)


def layout_fig(fig, alto=340, titulo=None):
    fig.update_layout(
        height=alto, margin=dict(l=10, r=10, t=50 if titulo else 20, b=10),
        title=dict(text=titulo, font=dict(size=15, color=C["navy"])) if titulo else None,
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial", color="#33415C"),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    return fig


def logo_html() -> str:
    logo_dir = os.path.join(DIR_DATOS, "logo")
    logo = None
    for n in LOGOS_LOCALES:
        if os.path.exists(os.path.join(BASE_DIR, n)):
            logo = os.path.join(BASE_DIR, n)
            break
    if logo is None and os.path.isdir(logo_dir) and os.listdir(logo_dir):
        logo = os.path.join(logo_dir, sorted(os.listdir(logo_dir))[0])
    if logo:
        with open(logo, "rb") as fh:
            b64, mime = base64.b64encode(fh.read()).decode(), "image/jpeg" if logo.lower().endswith(("jpg", "jpeg")) else "image/png"
    else:
        b64, mime = LOGO_TECNITRAUMA_B64, "image/png"
    return f'<div class="logo-box"><img src="data:{mime};base64,{b64}" alt="Tecnitrauma"></div>'


EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200d\u2139\u23F0-\u23FA\u2194-\u21FF]")


NOMBRES = {
    "REFERENCIA": "REFERENCIA", "DESCRIPCION": "DESCRIPCIÓN", "LOTE": "LOTE", "VENCE": "VENCIMIENTO",
    "DIAS_VENCE": "DÍAS PARA VENCER", "ESTADO_VENC": "ESTADO VENC.", "TEORICO": "TEÓRICO (TEMPLETE)",
    "CONTADO": "CONTADO", "DIFERENCIA": "DIFERENCIA", "ESTADO": "ESTADO", "COSTO_UNIT": "COSTO UNIT.",
    "VALOR_TEORICO": "VALOR TEÓRICO", "VALOR_CONTADO": "VALOR CONTADO", "VALOR_DIF": "VALOR DIFERENCIA",
    "LOTE_EN_TEMPLETE": "LOTE EN TEMPLETE", "REF_EN_TEMPLETE": "REF. EN TEMPLETE",
    "LOTE_EN_MAESTRO_SMITH": "LOTE EN MAESTRO SMITH", "VALREF": "VALREF", "NAL_SUELTAS": "NAL SUELTAS (REF)",
    "NAL_SERIALES": "NAL EN SERIALES (LOT)", "NAL_TOTAL": "NAL TOTAL (INFORMATIVO)",
    "NAL_SERIALES_ID": "SERIALES NAL", "GONDOLAS": "GÓNDOLAS", "UBICACION": "UBICACIÓN SMITH",
    "LOTES": "N° LOTES", "LOTES_CON_DIF": "LOTES CON DIFERENCIA", "VENCIDOS": "LOTES VENCIDOS",
    "BODEGA": "BODEGA", "TIPO": "TIPO", "SERIAL": "SERIAL", "SET": "NOMBRE SET", "SISTEMA": "SISTEMA (NAL)",
    "OBSERVACION": "OBSERVACIÓN", "CONTADO_POR": "CONTADO POR", "CANT_COM": "CANT. COM",
    "SUMA_LOT": "SUMA LOT", "VALOR_SISTEMA": "VALOR SISTEMA", "LECTURAS": "LECTURAS", "MANUAL": "REG. MANUALES",
    "PAREJAS": "PAREJAS", "BODEGAS": "BODEGAS", "ORIGEN": "ORIGEN", "TEMPLETE": "TEMPLETE", "NAL": "NAL (SISTEMA)",
    "UNIDADES": "UNIDADES SISTEMA", "BODEGA_NOM": "NOMBRE BODEGA", "ORIGEN_BOD": "ORIGEN BODEGA", "CERRADO_POR": "CERRADO POR",
    "CERRADO_TS": "CERRADO", "ULTIMA": "ÚLTIMA LECTURA", "LINEAS": "LÍNEAS", "N_LOTES": "N° LOTES", "DIF_COM_LOT": "DIF. (LOT - COM)", "CUADRA": "CUADRA",
}



def logo_html() -> str:
    return f'<div class="logo-box"><img src="data:image/png;base64,{LOGO_TECNITRAUMA_B64}" alt="Tecnitrauma"></div>'


CSS_EXTRA = """
<style>
.pareja-head {background:#fff; border-radius:14px; padding:12px 18px; box-shadow:0 2px 12px rgba(11,37,69,.08);
  border-left:6px solid #2A88C9; margin-bottom:10px;}
.pareja-head b {color:#0B2545; font-size:1.15rem;}
.ok-scan {background:#E8F6F3; border-left:6px solid #2A9D8F; padding:12px 16px; border-radius:10px; font-size:1.05rem; color:#145A50;}
.no-scan {background:#FDECEC; border-left:6px solid #D64545; padding:12px 16px; border-radius:10px; font-size:1.05rem; color:#7A1F1F;}
div[data-testid="stForm"] {background:#FFFFFF; border-radius:14px;}
</style>
"""

# =============================================================================
# BASE DE DATOS (Supabase/PostgreSQL en la nube  ·  SQLite en local)
# =============================================================================
META = MetaData()
T_LECT = Table(
    "lecturas", META,
    Column("id", String(24), primary_key=True), Column("ts", String(19)), Column("pareja", String(80)),
    Column("auxiliares", String(200)), Column("modo", String(12)), Column("grupo", String(10)),
    Column("zona", String(60)), Column("gondola", String(40)), Column("nivel", String(20)),
    Column("serial", String(60)), Column("codigo_leido", String(300)), Column("referencia", String(80)),
    Column("descripcion", String(250)), Column("lote", String(80)), Column("vence", String(10)),
    Column("cantidad", Float), Column("observacion", String(400)), Column("origen", String(120)),
    Column("anulada", Integer, default=0), Column("anulada_por", String(80)), Column("anulada_ts", String(19)))
T_PAR = Table(
    "parejas", META,
    Column("id", String(12), primary_key=True), Column("nombre", String(80)), Column("aux1", String(80)),
    Column("aux2", String(80)), Column("pin", String(8)), Column("zona", String(60)), Column("gondolas", String(200)),
    Column("estado", String(12)), Column("inicio", String(19)), Column("fin", String(19)))
T_SER = Table(
    "seriales_estado", META,
    Column("serial", String(60), primary_key=True), Column("grupo", String(10)), Column("estado", String(12)),
    Column("pareja", String(80)), Column("ts", String(19)))
T_MAE = Table(
    "maestros", META,
    Column("tipo", String(20), primary_key=True), Column("nombre", String(200)), Column("sha", String(64)),
    Column("ts", String(19)), Column("tam", Integer), Column("datos", LargeBinary))
T_CFG = Table("config", META, Column("k", String(60), primary_key=True), Column("v", Text))


def _secreto(nombre: str, defecto: str = "") -> str:
    try:
        return str(st.secrets.get(nombre, defecto) or defecto)
    except Exception:
        return defecto


@st.cache_resource(show_spinner="Conectando con la base de datos…")
def motor():
    url = _secreto("DB_URL")
    if url:
        url = re.sub(r"^postgres(ql)?://", "postgresql+psycopg2://", url)
        eng = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=3, pool_recycle=280)
        modo = "nube"
    else:
        os.makedirs(DIR_DATOS, exist_ok=True)
        eng = create_engine("sqlite:///" + os.path.join(DIR_DATOS, "inventario.db"),
                            connect_args={"check_same_thread": False, "timeout": 30})
        with eng.begin() as c:
            c.exec_driver_sql("PRAGMA journal_mode=WAL")
        modo = "local"
    META.create_all(eng)
    return eng, modo


def bd():
    return motor()[0]


def ejecutar(stmt, filas=None):
    with bd().begin() as c:
        if filas is None:
            c.execute(stmt)
        else:
            c.execute(stmt, filas)


def consultar(stmt) -> pd.DataFrame:
    with bd().connect() as c:
        return pd.read_sql(stmt, c)


@st.cache_data(ttl=10, show_spinner=False)
def config_todo() -> dict:
    df = consultar(select(T_CFG))
    return dict(zip(df["k"], df["v"]))


def cfg(k, defecto=None):
    return config_todo().get(k, defecto)


def cfg_set(k, v):
    with bd().begin() as c:
        c.execute(delete(T_CFG).where(T_CFG.c.k == k))
        c.execute(insert(T_CFG).values(k=k, v=str(v)))
    config_todo.clear()


@st.cache_data(ttl=4, show_spinner=False)
def leer_lecturas() -> pd.DataFrame:
    df = consultar(select(T_LECT))
    if df.empty:
        return df
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0)
    df["anulada"] = pd.to_numeric(df["anulada"], errors="coerce").fillna(0).astype(int)
    for c in df.columns:
        if df[c].dtype == object or str(df[c].dtype).startswith(("str", "string")):
            df[c] = df[c].fillna("").astype(str)
    return df


@st.cache_data(ttl=4, show_spinner=False)
def leer_parejas() -> pd.DataFrame:
    return consultar(select(T_PAR)).fillna("")


@st.cache_data(ttl=4, show_spinner=False)
def leer_estado_seriales() -> pd.DataFrame:
    return consultar(select(T_SER)).fillna("")


@st.cache_data(ttl=30, show_spinner=False)
def maestros_meta() -> pd.DataFrame:
    return consultar(select(T_MAE.c.tipo, T_MAE.c.nombre, T_MAE.c.sha, T_MAE.c.ts, T_MAE.c.tam))


@st.cache_data(max_entries=8, show_spinner="Descargando archivo maestro…")
def bytes_maestro(tipo: str, sha: str) -> bytes:
    df = consultar(select(T_MAE.c.datos).where(T_MAE.c.tipo == tipo))
    return gzip.decompress(bytes(df["datos"].iloc[0])) if len(df) else b""


def guardar_maestro(tipo: str, nombre: str, data: bytes):
    sha = hashlib.sha256(data).hexdigest()
    with bd().begin() as c:
        c.execute(delete(T_MAE).where(T_MAE.c.tipo == tipo))
        c.execute(insert(T_MAE).values(tipo=tipo, nombre=nombre, sha=sha, ts=ahora().strftime("%Y-%m-%d %H:%M:%S"),
                                       tam=len(data), datos=gzip.compress(data, 6)))
    maestros_meta.clear()


def limpiar_caches_conteo():
    leer_lecturas.clear()
    leer_parejas.clear()
    leer_estado_seriales.clear()


def registrar_lectura(**kw):
    fila = {c.name: "" for c in T_LECT.columns}
    fila.update(id=uuid.uuid4().hex[:16], ts=ahora().strftime("%Y-%m-%d %H:%M:%S"), anulada=0, cantidad=1.0)
    fila.update({k: v for k, v in kw.items() if k in fila})
    fila["cantidad"] = float(fila["cantidad"] or 0)
    ejecutar(insert(T_LECT).values(**fila))
    leer_lecturas.clear()
    return fila


def anular_lecturas(ids, por: str):
    if not ids:
        return
    ejecutar(update(T_LECT).where(T_LECT.c.id.in_(list(ids))).values(
        anulada=1, anulada_por=por, anulada_ts=ahora().strftime("%Y-%m-%d %H:%M:%S")))
    leer_lecturas.clear()


def fijar_estado_serial(serial: str, grupo: str, estado: str | None, pareja: str = ""):
    with bd().begin() as c:
        c.execute(delete(T_SER).where(T_SER.c.serial == serial))
        if estado:
            c.execute(insert(T_SER).values(serial=serial, grupo=grupo, estado=estado, pareja=pareja,
                                           ts=ahora().strftime("%Y-%m-%d %H:%M:%S")))
    leer_estado_seriales.clear()

# =============================================================================
# CLAVES
# =============================================================================

def _hash(clave: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal.encode("utf-8"), 100_000).hex()


def verificar_admin(clave: str) -> bool:
    h, sal = cfg("admin_hash"), cfg("admin_sal")
    if h and sal:
        return _hash(clave, sal) == h
    return clave == _secreto("CLAVE_ADMIN", CLAVE_ADMIN_INICIAL)


def cambiar_clave_admin(nueva: str):
    sal = uuid.uuid4().hex
    cfg_set("admin_sal", sal)
    cfg_set("admin_hash", _hash(nueva, sal))

# =============================================================================
# PARÁMETROS
# =============================================================================

def parametros() -> dict:
    return dict(
        criterio=cfg("criterio", "Propietaria (BODEGA PROPIE.)"),
        incluir_otras=cfg("incluir_otras", "1") == "1",
        dias=int(cfg("dias", "90")),
        base_valor=cfg("base_valor", "Costo promedio (Valref)"),
        cliente=cfg("cliente", "Smith & Nephew"),
        responsable=cfg("responsable", ""),
        hoja_tpl=cfg("hoja_tpl", ""),
        avisos_pareja=cfg("avisos_pareja", "0") == "1",
    )

# =============================================================================
# UNIVERSO A CONTAR (desde el NAL)
# =============================================================================

def sha_de(tipo: str) -> str:
    m = maestros_meta()
    r = m[m["tipo"] == tipo]
    return r["sha"].iloc[0] if len(r) else ""


def nombre_de(tipo: str) -> str:
    m = maestros_meta()
    r = m[m["tipo"] == tipo]
    return r["nombre"].iloc[0] if len(r) else ""


@st.cache_data(max_entries=3, show_spinner="Leyendo Valref…")
def valref_df(sha: str):
    if not sha:
        return None
    return leer_valref(bytes_maestro("valref", sha), nombre_de("valref") or "valref.csv")


@st.cache_data(max_entries=3, show_spinner="Leyendo Templete…")
def templete_df(sha: str, hoja: str):
    if not sha:
        return None
    return leer_templete(bytes_maestro("templete", sha), nombre_de("templete") or "templete.xlsx", hoja or None)


@st.cache_data(max_entries=3, show_spinner="Leyendo maestros GTIN y lotes Smith…")
def maestros_smith(sha_tpn: str, sha_val: str):
    gtin, lotes = ({}, pd.DataFrame())
    if sha_tpn:
        gtin, lotes = leer_maestros_tpn(bytes_maestro("tpn", sha_tpn))
        gtin = dict(gtin)
    v = valref_df(sha_val)
    if v is not None:
        for ean, ref in zip(v["EAN"], v["REFERENCIA"]):
            if ean and ref:
                gtin.setdefault(ean.lstrip("0"), ref)
    return gtin, lotes


@st.cache_data(max_entries=3, show_spinner="Preparando el inventario a contar (NAL)…")
def construir_universo(sha_nal: str, sha_val: str, criterio: str, incluir_otras: bool, dias: int):
    """Devuelve líneas a contar (stock y seriales), seriales, excluidos por asterisco y conciliación Com/Lot."""
    vacio = dict(U=pd.DataFrame(), S=pd.DataFrame(), excl=pd.DataFrame(), conc=pd.DataFrame(), info={}, neg=pd.DataFrame())
    if not sha_nal:
        return vacio
    nal = leer_nal(bytes_maestro("nal", sha_nal)).copy()
    val = valref_df(sha_val)
    col = "BOD_PROP" if criterio.startswith("Propietaria") else "BOD_EXIST"
    col_nom = "BOD_PROP_NOM" if col == "BOD_PROP" else "BOD_EXIST_NOM"
    b = nal[col]
    es_smith, es_serena = b.isin(BODEGAS_SMITH), b.isin(BODEGAS_SERENA)
    validas = set(val.loc[val["VALIDA"], "K_REF"]) if val is not None else set()
    asteriscos = tiene_asterisco(nal["CODIGO"]) | tiene_asterisco(nal["LOTE"])
    # Regla Valref: SOLO seriales (Com/Lot) de las bodegas de las demás ciudades, mirando la BODEGA PROPIETARIA,
    # sin las bodegas 10, 20 y 27, cuya referencia esté en Valref y cuyo código/lote no tenga * ni **.
    bp = nal["BOD_PROP"]
    candidata = (~es_smith & ~es_serena & ~bp.isin(BODEGAS_SMITH + BODEGAS_SERENA + BODEGAS_SIN_SERIALES_VALREF)
                 & nal["TIP"].isin(["COM", "LOT"]) & (nal["SERIAL"] != "") & nal["K_REF"].isin(validas))
    if not incluir_otras:
        candidata = candidata & False
    otras = candidata & ~asteriscos
    nal["GRUPO"] = np.select([es_serena, es_smith, otras], ["SERENA", "SMITH", "SMITH"], "")
    nal["ORIGEN_BOD"] = np.select([es_serena, es_smith, otras], ["Bodega Serena", "Bodega Smith", "Serial otra ciudad (Valref)"], "")
    nal["BODEGA"] = np.where(otras, bp, b)
    nal["BODEGA_NOM"] = np.where(otras, nal["BOD_PROP_NOM"], nal[col_nom])
    excl = nal[candidata & asteriscos].copy()
    excl["GRUPO"] = "SMITH"
    excl["ORIGEN_BOD"] = "Serial otra ciudad (excluido * / **)"
    base = nal[nal["GRUPO"] != ""].copy()
    # Un serial pertenece al grupo de su fila SET (si existe) para no partir kits
    grupo_serial = base[base["SERIAL"] != ""].groupby("SERIAL")["GRUPO"].first()
    ref = base[base["TIP"] == "REF"]
    lot = base[base["TIP"] == "LOT"]
    partes = [
        pd.DataFrame({"GRUPO": ref["GRUPO"], "ORIGEN_BOD": ref["ORIGEN_BOD"], "BODEGA": ref["BODEGA"],
                      "BODEGA_NOM": ref["BODEGA_NOM"], "TIPO": "STOCK", "SERIAL": "", "SET": "",
                      "REFERENCIA": ref["CODIGO"], "DESCRIPCION": ref["NOMBRE"], "LOTE": ref["LOTE"],
                      "VENCE": ref["VENCE"], "SISTEMA": ref["CANT"], "K_REF": ref["K_REF"]}),
        pd.DataFrame({"GRUPO": lot["GRUPO"], "ORIGEN_BOD": lot["ORIGEN_BOD"], "BODEGA": lot["BODEGA"],
                      "BODEGA_NOM": lot["BODEGA_NOM"], "TIPO": "SERIAL", "SERIAL": lot["SERIAL"],
                      "SET": lot["SET_NOMBRE"], "REFERENCIA": lot["CODIGO"], "DESCRIPCION": lot["NOMBRE"],
                      "LOTE": lot["LOTE"], "VENCE": lot["VENCE"], "SISTEMA": lot["CANT"], "K_REF": lot["K_REF"]}),
    ]
    conc = conciliar_com_lot(base)
    if not conc.empty:
        info_ser = base[base["SERIAL"] != ""].groupby("SERIAL").agg(
            GRUPO=("GRUPO", "first"), ORIGEN_BOD=("ORIGEN_BOD", "first"), BODEGA_X=("BODEGA", "first"),
            BODEGA_NOM=("BODEGA_NOM", "first"))
        conc = conc.merge(info_ser, left_on="SERIAL", right_index=True, how="left")
        sin_lote = conc[conc["CANT_COM"] > conc["SUMA_LOT"]]
        if not sin_lote.empty:
            partes.append(pd.DataFrame({
                "GRUPO": sin_lote["GRUPO"], "ORIGEN_BOD": sin_lote["ORIGEN_BOD"], "BODEGA": sin_lote["BODEGA_X"],
                "BODEGA_NOM": sin_lote["BODEGA_NOM"], "TIPO": "SERIAL", "SERIAL": sin_lote["SERIAL"],
                "SET": sin_lote["SET"], "REFERENCIA": sin_lote["REFERENCIA"], "DESCRIPCION": sin_lote["DESCRIPCION"],
                "LOTE": "SIN LOTE", "VENCE": pd.NaT, "SISTEMA": sin_lote["CANT_COM"] - sin_lote["SUMA_LOT"],
                "K_REF": sin_lote["K_REF"]}))
    U = pd.concat(partes, ignore_index=True)
    U["SERIAL"] = U["SERIAL"].fillna("").astype(str)
    U.loc[U["SERIAL"] != "", "GRUPO"] = U.loc[U["SERIAL"] != "", "SERIAL"].map(grupo_serial).fillna(U["GRUPO"])
    U["LOTE"] = U["LOTE"].fillna("").astype(str).replace("", "SIN LOTE")
    U["K_LOTE"] = clave(U["LOTE"], es_lote=True)
    U["BODEGA"] = pd.to_numeric(U["BODEGA"], errors="coerce").fillna(0).astype(int)
    U["VENCE"] = pd.to_datetime(U["VENCE"])
    U["SISTEMA"] = pd.to_numeric(U["SISTEMA"], errors="coerce").fillna(0)
    negativos = U[U["SISTEMA"] < 0].copy()
    U = U[U["SISTEMA"] > 0].copy()
    if val is not None:
        v = val.drop_duplicates("K_REF").set_index("K_REF")
        U["COSTO"] = U["K_REF"].map(v["COSTO"]).fillna(0)
        U["PRECIO"] = U["K_REF"].map(v["PRECIO"]).fillna(0)
    else:
        U["COSTO"], U["PRECIO"] = 0.0, 0.0
    U["DIAS_VENCE"], U["ESTADO_VENC"] = estado_venc(U["VENCE"], dias)
    sets = base[base["TIP"] == "SET"].drop_duplicates("SERIAL").set_index("SERIAL")
    S = U[U["TIPO"] == "SERIAL"].groupby("SERIAL", as_index=False).agg(
        GRUPO=("GRUPO", "first"), SET=("SET", "first"), BODEGA=("BODEGA", "first"), BODEGA_NOM=("BODEGA_NOM", "first"),
        ORIGEN_BOD=("ORIGEN_BOD", "first"), LINEAS=("REFERENCIA", "count"), UNIDADES=("SISTEMA", "sum"),
        REFERENCIAS=("K_REF", "nunique"))
    S["SET"] = S["SET"].where(S["SET"] != "", S["SERIAL"].map(sets["NOMBRE"]).fillna(""))
    info = {
        "lineas": len(U), "seriales": len(S),
        "stock_smith": float(U.loc[(U["GRUPO"] == "SMITH") & (U["TIPO"] == "STOCK"), "SISTEMA"].sum()),
        "excluidos_ast": len(excl), "otras_bodegas": int((U["ORIGEN_BOD"] == "Serial otra ciudad (Valref)").sum()),
        "seriales_otras": int(U.loc[U["ORIGEN_BOD"] == "Serial otra ciudad (Valref)", "SERIAL"].nunique()),
        "descuadres_com_lot": int((conc["CUADRA"] == "No").sum()) if not conc.empty else 0,
        "negativos": len(negativos),
    }
    excl_v = excl[["GRUPO", "ORIGEN_BOD", "BODEGA_NOM", "TIP", "SERIAL", "CODIGO", "NOMBRE", "LOTE", "CANT"]]
    return dict(U=U.reset_index(drop=True), S=S, excl=excl_v, conc=conc, info=info,
                neg=negativos[["GRUPO", "BODEGA_NOM", "TIPO", "SERIAL", "REFERENCIA", "DESCRIPCION", "LOTE", "SISTEMA"]])


def lecturas_validas(gtin=None) -> pd.DataFrame:
    L = leer_lecturas()
    if L.empty:
        return pd.DataFrame(columns=["id", "ts", "pareja", "grupo", "serial", "referencia", "lote", "cantidad",
                                     "K_REF", "K_LOTE", "SERIAL", "VENCE_L"])
    L = L[L["anulada"] == 0].copy()
    L["SERIAL"] = limpiar_codigo(L["serial"])
    L["K_REF"] = clave(limpiar_codigo(L["referencia"]))
    L["K_LOTE"] = clave(limpiar_lote(L["lote"]), es_lote=True)
    L["VENCE_L"] = parse_fecha(L["vence"])
    return L


def estado_seriales(S: pd.DataFrame, L: pd.DataFrame) -> pd.DataFrame:
    E = leer_estado_seriales()
    cerr = dict(zip(E["serial"], E["estado"])) if not E.empty else {}
    quien = dict(zip(E["serial"], E["pareja"])) if not E.empty else {}
    cuando = dict(zip(E["serial"], E["ts"])) if not E.empty else {}
    if S.empty:
        return S
    S = S.copy()
    Ls = L[L["SERIAL"] != ""]
    if not Ls.empty:
        g = Ls.groupby("SERIAL").agg(LECTURAS=("id", "count"), CONTADO=("cantidad", "sum"),
                                    PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s)))), ULTIMA=("ts", "max"))
        S = S.merge(g, left_on="SERIAL", right_index=True, how="left")
    else:
        S["LECTURAS"], S["CONTADO"], S["PAREJAS"], S["ULTIMA"] = 0, 0.0, "", ""
    S[["LECTURAS", "CONTADO"]] = S[["LECTURAS", "CONTADO"]].fillna(0)
    S[["PAREJAS", "ULTIMA"]] = S[["PAREJAS", "ULTIMA"]].fillna("")
    S["ESTADO"] = np.where(S["SERIAL"].map(cerr).fillna("") == "CERRADO", "✅ CERRADO",
                           np.where(S["LECTURAS"] > 0, "🔄 EN CONTEO", "⏳ PENDIENTE"))
    S["CERRADO_POR"] = S["SERIAL"].map(quien).fillna("")
    S["CERRADO_TS"] = S["SERIAL"].map(cuando).fillna("")
    return S


def comparar(U: pd.DataFrame, L: pd.DataFrame, grupo: str, base_valor: str, Sest: pd.DataFrame | None = None):
    """Sistema (NAL) vs contado, por serial + referencia + lote, para un grupo (SMITH / SERENA)."""
    llaves = ["SERIAL", "K_REF", "K_LOTE"]
    u = U[U["GRUPO"] == grupo] if not U.empty else U
    l = L[L["grupo"] == grupo] if not L.empty else L
    col_v = "COSTO" if base_valor.startswith("Costo") else "PRECIO"
    if u.empty and l.empty:
        return pd.DataFrame()
    if not u.empty:
        Ug = u.groupby(llaves, as_index=False).agg(
            TIPO=("TIPO", "first"), SET=("SET", "first"), REF_U=("REFERENCIA", "first"), DES_U=("DESCRIPCION", "first"),
            LOTE_U=("LOTE", "first"), VENCE_U=("VENCE", "min"), SISTEMA=("SISTEMA", "sum"), COSTO_UNIT=(col_v, "max"),
            BODEGAS=("BODEGA_NOM", lambda s: ", ".join(sorted(set(map(str, s))))),
            ORIGEN=("ORIGEN_BOD", lambda s: ", ".join(sorted(set(map(str, s))))))
    else:
        Ug = pd.DataFrame(columns=llaves + ["TIPO", "SET", "REF_U", "DES_U", "LOTE_U", "VENCE_U", "SISTEMA",
                                            "COSTO_UNIT", "BODEGAS", "ORIGEN"])
    if not l.empty:
        Lg = l.groupby(llaves, as_index=False).agg(
            REF_L=("referencia", "first"), DES_L=("descripcion", "first"), LOTE_L=("lote", "first"),
            VENCE_L=("VENCE_L", "min"), CONTADO=("cantidad", "sum"), LECTURAS=("id", "count"),
            PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s)))),
            GONDOLAS=("gondola", lambda s: ", ".join(sorted({x for x in s if x}))),
            MANUAL=("modo", lambda s: int((s == "MANUAL").sum())))
    else:
        Lg = pd.DataFrame(columns=llaves + ["REF_L", "DES_L", "LOTE_L", "VENCE_L", "CONTADO", "LECTURAS",
                                            "PAREJAS", "GONDOLAS", "MANUAL"])
    M = Ug.merge(Lg, on=llaves, how="outer")
    for a, b_ in [("REF_U", "REF_L"), ("DES_U", "DES_L"), ("LOTE_U", "LOTE_L")]:
        M[a] = M[a].where(M[a].notna() & (M[a].astype(str) != ""), M[b_])
    M = M.rename(columns={"REF_U": "REFERENCIA", "DES_U": "DESCRIPCION", "LOTE_U": "LOTE"})
    M["VENCE"] = pd.to_datetime(M["VENCE_U"]).fillna(pd.to_datetime(M["VENCE_L"]))
    for c in ["SISTEMA", "CONTADO", "LECTURAS", "MANUAL"]:
        M[c] = pd.to_numeric(M[c], errors="coerce").fillna(0)
    for c in ["TIPO", "SET", "BODEGAS", "ORIGEN", "PAREJAS", "GONDOLAS", "REFERENCIA", "DESCRIPCION", "LOTE"]:
        M[c] = M[c].fillna("").astype(str)
    M["TIPO"] = np.where(M["TIPO"] == "", np.where(M["SERIAL"] != "", "SERIAL", "STOCK"), M["TIPO"])
    if not u.empty:
        cmap = u.drop_duplicates("K_REF").set_index("K_REF")[col_v]
        M["COSTO_UNIT"] = pd.to_numeric(M["COSTO_UNIT"], errors="coerce").fillna(M["K_REF"].map(cmap)).fillna(0)
    else:
        M["COSTO_UNIT"] = 0.0
    M["DIFERENCIA"] = M["CONTADO"] - M["SISTEMA"]
    est_ser = {}
    if Sest is not None and not Sest.empty:
        est_ser = dict(zip(Sest["SERIAL"], Sest["ESTADO"]))
    ser_pend = M["SERIAL"].map(est_ser).fillna("") == "⏳ PENDIENTE"
    refs_grupo = set(u["K_REF"]) if not u.empty else set()
    seriales_grupo = set(u["SERIAL"]) if not u.empty else set()
    cond = [
        (M["SISTEMA"] == 0) & (M["SERIAL"] != "") & ~M["SERIAL"].isin(seriales_grupo),
        (M["SISTEMA"] == 0) & M["K_REF"].isin(refs_grupo),
        (M["SISTEMA"] == 0),
        M["DIFERENCIA"] == 0,
        (M["CONTADO"] == 0) & ser_pend,
        (M["CONTADO"] == 0),
        M["DIFERENCIA"] < 0,
    ]
    elec = ["🆕 SERIAL NO LISTADO", "⚠️ LOTE / UBICACIÓN NO COINCIDE", "🆕 REFERENCIA NO LISTADA", "✅ CUADRADO",
            "⏳ SERIAL PENDIENTE", "🔻 FALTANTE (NO ENCONTRADO)", "🔻 FALTANTE"]
    M["ESTADO"] = np.select(cond, elec, "🔺 SOBRANTE")
    M["VALOR_SISTEMA"] = M["SISTEMA"] * M["COSTO_UNIT"]
    M["VALOR_DIF"] = M["DIFERENCIA"] * M["COSTO_UNIT"]
    M["DIAS_VENCE"], M["ESTADO_VENC"] = estado_venc(M["VENCE"], int(cfg("dias", "90")))
    M["DIAS_VENCE"] = M["DIAS_VENCE"].astype("Int64")
    cols = ["TIPO", "SERIAL", "SET", "REFERENCIA", "DESCRIPCION", "LOTE", "VENCE", "DIAS_VENCE", "ESTADO_VENC",
            "SISTEMA", "CONTADO", "DIFERENCIA", "ESTADO", "COSTO_UNIT", "VALOR_SISTEMA", "VALOR_DIF", "LECTURAS",
            "MANUAL", "PAREJAS", "GONDOLAS", "BODEGAS", "ORIGEN", "K_REF", "K_LOTE"]
    return M[cols].sort_values(["TIPO", "SERIAL", "REFERENCIA", "LOTE"]).reset_index(drop=True)


def totales_ref(M: pd.DataFrame) -> pd.DataFrame:
    if M.empty:
        return M
    g = M.groupby("K_REF", as_index=False).agg(
        REFERENCIA=("REFERENCIA", "first"), DESCRIPCION=("DESCRIPCION", "first"), SISTEMA=("SISTEMA", "sum"),
        CONTADO=("CONTADO", "sum"), COSTO_UNIT=("COSTO_UNIT", "max"), LOTES=("K_LOTE", "nunique"),
        SERIALES=("SERIAL", lambda s: int((s != "").sum())))
    g["DIFERENCIA"] = g["CONTADO"] - g["SISTEMA"]
    g["VALOR_DIF"] = g["DIFERENCIA"] * g["COSTO_UNIT"]
    g["ESTADO"] = np.select([g["DIFERENCIA"] == 0, g["DIFERENCIA"] < 0], ["✅ CUADRADO", "🔻 FALTANTE"], "🔺 SOBRANTE")
    return g[["REFERENCIA", "DESCRIPCION", "LOTES", "SERIALES", "SISTEMA", "CONTADO", "DIFERENCIA", "ESTADO",
              "COSTO_UNIT", "VALOR_DIF"]].sort_values("REFERENCIA")


def templete_vs_conteo(T: pd.DataFrame, L: pd.DataFrame, U: pd.DataFrame, base_valor, lotes_smith) -> pd.DataFrame:
    if T is None or T.empty:
        return pd.DataFrame()
    llaves = ["K_REF", "K_LOTE"]
    Tg = T.groupby(llaves, as_index=False).agg(REFERENCIA=("REFERENCIA", "first"), DESCRIPCION=("DESCRIPCION", "first"),
                                               LOTE=("LOTE", "first"), VENCE=("VENCE", "min"), TEMPLETE=("CANTIDAD", "sum"))
    l = L[L["grupo"] == "SMITH"] if not L.empty else L
    Lg = l.groupby(llaves, as_index=False).agg(CONTADO=("cantidad", "sum"), REF_L=("referencia", "first"),
                                               LOTE_L=("lote", "first")) if not l.empty else pd.DataFrame(columns=llaves + ["CONTADO", "REF_L", "LOTE_L"])
    u = U[U["GRUPO"] == "SMITH"] if not U.empty else U
    Ng = u.groupby(llaves, as_index=False).agg(NAL=("SISTEMA", "sum")) if not u.empty else pd.DataFrame(columns=llaves + ["NAL"])
    M = Tg.merge(Lg, on=llaves, how="outer").merge(Ng, on=llaves, how="left")
    M["REFERENCIA"] = M["REFERENCIA"].fillna(M["REF_L"]).fillna("")
    M["LOTE"] = M["LOTE"].fillna(M["LOTE_L"]).fillna("")
    M["DESCRIPCION"] = M["DESCRIPCION"].fillna("")
    for c in ["TEMPLETE", "CONTADO", "NAL"]:
        M[c] = pd.to_numeric(M[c], errors="coerce").fillna(0)
    M["DIFERENCIA"] = M["CONTADO"] - M["TEMPLETE"]
    M["ESTADO"] = np.select([M["TEMPLETE"] == 0, M["DIFERENCIA"] == 0, M["DIFERENCIA"] < 0],
                            ["⚠️ NO ESTÁ EN TEMPLETE", "✅ CUADRADO", "🔻 FALTANTE"], "🔺 SOBRANTE")
    if lotes_smith is not None and not lotes_smith.empty:
        par = set(zip(lotes_smith["K_REF"], lotes_smith["K_LOTE"]))
        M["LOTE_EN_MAESTRO_SMITH"] = ["Sí" if (a, b) in par else "No" for a, b in zip(M["K_REF"], M["K_LOTE"])]
    else:
        M["LOTE_EN_MAESTRO_SMITH"] = "N/D"
    M["DIAS_VENCE"], M["ESTADO_VENC"] = estado_venc(pd.to_datetime(M["VENCE"]), int(cfg("dias", "90")))
    M["DIAS_VENCE"] = M["DIAS_VENCE"].astype("Int64")
    return M[["REFERENCIA", "DESCRIPCION", "LOTE", "VENCE", "DIAS_VENCE", "ESTADO_VENC", "TEMPLETE", "NAL", "CONTADO",
              "DIFERENCIA", "ESTADO", "LOTE_EN_MAESTRO_SMITH"]].sort_values(["REFERENCIA", "LOTE"])


def resolver_codigo(codigo: str, gtin_map: dict):
    """(referencia, lote, vencimiento, ean) a partir de lo leído por la pistola o digitado."""
    codigo = str(codigo or "").strip()
    if not codigo:
        return "", "", pd.NaT, ""
    gs = parse_gs1(codigo)
    if gs.get("01"):
        ean = gs["01"]
        return gtin_map.get(ean.lstrip("0"), ""), gs.get("10", ""), gs1_fecha(gs["17"]) if "17" in gs else pd.NaT, ean
    solo = re.sub(r"\D", "", codigo)
    if len(codigo) in (12, 13, 14) and solo == codigo:
        return gtin_map.get(codigo.lstrip("0"), ""), "", pd.NaT, codigo
    return limpiar_codigo(pd.Series([codigo])).iloc[0], "", pd.NaT, ""

# =============================================================================
# CONTEXTO COMPARTIDO
# =============================================================================

def contexto():
    p = parametros()
    sha_nal, sha_val, sha_tpl, sha_tpn = sha_de("nal"), sha_de("valref"), sha_de("templete"), sha_de("tpn")
    UV = construir_universo(sha_nal, sha_val, p["criterio"], p["incluir_otras"], p["dias"])
    gtin, lotes = maestros_smith(sha_tpn, sha_val)
    return dict(p=p, UV=UV, U=UV["U"], S=UV["S"], gtin=gtin, lotes=lotes, sha_tpl=sha_tpl, sha_val=sha_val)


def enfocar(etiqueta: str):
    """Deja el cursor en el campo del código para que la pistola escriba allí sin hacer clic."""
    html = (
        "<script>const f=()=>{const el=window.parent.document.querySelector('input[aria-label=\"" + etiqueta +
        "\"]');if(el){el.focus();return true}return false};let n=0;const t=setInterval(()=>{if(f()||++n>20)clearInterval(t)},150);</script>")
    if hasattr(st, "iframe"):
        st.iframe(html, height=1)
    else:
        import streamlit.components.v1 as components
        components.html(html, height=0)

# =============================================================================
# PANTALLA DE CONTEO (parejas · conteo a ciegas)
# =============================================================================
ETQ_CODIGO = "Código (pistola o digitado)"


def pantalla_conteo(par: dict, ctx: dict, es_admin: bool = False):
    pid = par["nombre"]
    U, S, gtin = ctx["U"], ctx["S"], ctx["gtin"]
    st.markdown(f'<div class="pareja-head"><b>👥 {pid}</b> &nbsp; {par.get("aux1", "")} / {par.get("aux2", "")}'
                f' &nbsp;·&nbsp; 📍 {par.get("zona", "")}'
                + (f' &nbsp;·&nbsp; 🗄️ {par.get("gondolas")}' if par.get("gondolas") else "") + '</div>',
                unsafe_allow_html=True)
    if U.empty:
        alerta("⏳ El administrador aún no ha cargado el archivo NAL. Puede registrar lecturas igualmente.", "ambar")
    z1, z2, z3 = st.columns([2, 1, 1])
    zonas = list(ZONAS)
    zona = z1.selectbox("Zona", zonas, index=zonas.index(par["zona"]) if par.get("zona") in zonas else 0, key=f"zona_{pid}")
    grupo = ZONAS[zona]
    gon = z2.text_input("Góndola / ubicación", key=f"gon_{pid}")
    niv = z3.text_input("Nivel", key=f"niv_{pid}")
    modo = st.radio("¿Qué está contando?", ["📦 Stock de seguridad (sin serial)", "🧰 Serial / Kit"], horizontal=True,
                    key=f"modo_{pid}")
    L = lecturas_validas()
    serial = ""
    if modo.startswith("🧰"):
        Sest = estado_seriales(S[S["GRUPO"] == grupo], L) if not S.empty else pd.DataFrame()
        if zona.endswith("66") or zona.endswith("67"):
            bod = int(zona[-2:])
            if not Sest.empty:
                Sest = Sest[Sest["BODEGA"] == bod]
        s1, s2 = st.columns([3, 2])
        opciones = ["— seleccione un serial —"]
        etiquetas = {}
        if not Sest.empty:
            vista = Sest.sort_values(["ESTADO", "SERIAL"], key=lambda c: c.map({"⏳ PENDIENTE": 0, "🔄 EN CONTEO": 1, "✅ CERRADO": 2}) if c.name == "ESTADO" else c)
            for _, r in vista.iterrows():
                e = f'{r["ESTADO"]} · {r["SERIAL"]} · {r["SET"][:45]} · {r["BODEGA_NOM"][:22]}'
                opciones.append(e)
                etiquetas[e] = r["SERIAL"]
        sel = s1.selectbox("Serial pendiente (puede escribir para buscar)", opciones, key=f"selser_{pid}")
        escrito = s2.text_input("…o escanee / digite el número de serial", key=f"txtser_{pid}")
        serial = limpiar_codigo(pd.Series([escrito])).iloc[0] if escrito.strip() else etiquetas.get(sel, "")
        if not Sest.empty:
            pend = (Sest["ESTADO"] == "⏳ PENDIENTE").sum()
            enc = (Sest["ESTADO"] == "🔄 EN CONTEO").sum()
            cer = (Sest["ESTADO"] == "✅ CERRADO").sum()
            st.markdown(f'<span class="chip no">⏳ {pend} pendientes</span><span class="chip info">🔄 {enc} en conteo</span>'
                        f'<span class="chip ok">✅ {cer} cerrados</span>', unsafe_allow_html=True)
        if serial:
            fila = Sest[Sest["SERIAL"] == serial] if not Sest.empty else pd.DataFrame()
            if fila.empty:
                alerta(f"🆕 El serial <b>{serial}</b> no está en el listado de esta zona: se registrará como novedad.", "ambar")
            else:
                r = fila.iloc[0]
                alerta(f"🧰 Contando serial <b>{serial}</b> · {r['SET']} · {r['BODEGA_NOM']} · Estado: <b>{r['ESTADO']}</b>"
                       + (f" (por {r['CERRADO_POR']})" if r["ESTADO"] == "✅ CERRADO" else ""),
                       "verde" if r["ESTADO"] != "✅ CERRADO" else "azul")
                if r["ESTADO"] == "✅ CERRADO" and not es_admin:
                    st.warning("Este serial ya fue cerrado. Si necesita volver a contarlo, pida al administrador que lo reabra.")
            c1, c2 = st.columns(2)

            def _cerrar(s_=serial, g_=grupo, p_=pid):
                fijar_estado_serial(s_, g_, "CERRADO", p_)
                st.session_state[f"txtser_{p_}"] = ""
                st.session_state[f"selser_{p_}"] = "— seleccione un serial —"
                st.session_state[f"ult_{p_}"] = ("ok", f"✅ Serial {s_} cerrado.")
            c1.button("✅ Cerrar serial (terminé de contarlo)", type="primary", width="stretch", key=f"cerrar_{pid}",
                      on_click=_cerrar)
            if es_admin and c2.button("↩️ Reabrir serial", width="stretch", key=f"reabrir_{pid}"):
                fijar_estado_serial(serial, grupo, None)
                st.rerun()
        else:
            st.info("Seleccione o escanee el serial antes de pistolear su contenido.")

    bloqueado = modo.startswith("🧰") and not serial
    # ---- Pistolear
    with st.form(f"form_pist_{pid}", clear_on_submit=True):
        f1, f2, f3 = st.columns([3, 1.4, 0.8])
        cod = f1.text_input(ETQ_CODIGO, key=f"cod_{pid}", placeholder="Escanee aquí y la pistola dará Enter")
        lote = f2.text_input("Lote (si el código no lo trae)", key=f"lote_{pid}")
        cant = f3.number_input("Cantidad", min_value=1, value=1, step=1, key=f"cant_{pid}")
        enviar = st.form_submit_button("📥 Registrar", type="primary", width="stretch", disabled=bloqueado)
    if enviar and cod.strip():
        ref, lote_c, ven, ean = resolver_codigo(cod, gtin)
        lote_f = limpiar_lote(pd.Series([lote or lote_c])).iloc[0]
        if not ref:
            st.session_state[f"ult_{pid}"] = ("no", f"No se reconoce el código «{cod}». Use <b>✍️ Registro manual</b> y digite la referencia.")
        else:
            desc = ""
            if not U.empty:
                m = U[U["K_REF"] == clave(pd.Series([ref])).iloc[0]]
                desc = m["DESCRIPCION"].iloc[0] if len(m) else ""
            registrar_lectura(pareja=pid, auxiliares=f'{par.get("aux1", "")} / {par.get("aux2", "")}', modo="PISTOLA",
                              grupo=grupo, zona=zona, gondola=gon.strip(), nivel=niv.strip(), serial=serial,
                              codigo_leido=cod.strip(), referencia=ref, descripcion=desc, lote=lote_f,
                              vence=ven.strftime("%Y-%m-%d") if not pd.isna(ven) else "", cantidad=cant,
                              origen="Admin" if es_admin else "Pareja")
            msg = f"✔ {ref} · lote {lote_f or 'SIN LOTE'} × {int(cant)}" + (f" · serial {serial}" if serial else "")
            if ctx["p"]["avisos_pareja"] or es_admin:
                u = U[U["GRUPO"] == grupo] if not U.empty else U
                kr, kl = clave(pd.Series([ref])).iloc[0], clave(pd.Series([lote_f]), True).iloc[0]
                if not u.empty and not ((u["K_REF"] == kr) & (u["K_LOTE"] == kl)).any():
                    msg += " · ⚠️ verifique el lote: no figura en el listado"
            st.session_state[f"ult_{pid}"] = ("ok", msg)
    elif enviar:
        st.session_state[f"ult_{pid}"] = ("no", "El código está vacío.")
    if f"ult_{pid}" in st.session_state:
        t, m = st.session_state[f"ult_{pid}"]
        st.markdown(f'<div class="{"ok-scan" if t == "ok" else "no-scan"}">{m}</div>', unsafe_allow_html=True)
    if not bloqueado and not es_admin:
        enfocar(ETQ_CODIGO)

    # ---- Registro manual (referencias que no se pueden pistolear)
    with st.expander("✍️ Registro manual · la etiqueta no se puede leer / referencia sin código", expanded=False):
        with st.form(f"form_man_{pid}", clear_on_submit=True):
            m1, m2, m3, m4 = st.columns([1.6, 1.4, 1.2, 0.8])
            m_ref = m1.text_input("Referencia *")
            m_lot = m2.text_input("Lote")
            m_ven = m3.date_input("Vencimiento", value=None, format="DD/MM/YYYY")
            m_can = m4.number_input("Cantidad *", min_value=1, value=1, step=1)
            m5, m6 = st.columns([2, 2])
            m_des = m5.text_input("Descripción (opcional)")
            m_obs = m6.text_input("Observación (ej. etiqueta borrosa)")
            if st.form_submit_button("💾 Guardar registro manual", type="primary", disabled=bloqueado):
                if not m_ref.strip():
                    st.error("La referencia es obligatoria.")
                else:
                    ref = limpiar_codigo(pd.Series([m_ref])).iloc[0]
                    lote_f = limpiar_lote(pd.Series([m_lot])).iloc[0]
                    desc = m_des.strip()
                    if not desc and not U.empty:
                        mm = U[U["K_REF"] == clave(pd.Series([ref])).iloc[0]]
                        desc = mm["DESCRIPCION"].iloc[0] if len(mm) else ""
                    registrar_lectura(pareja=pid, auxiliares=f'{par.get("aux1", "")} / {par.get("aux2", "")}',
                                      modo="MANUAL", grupo=grupo, zona=zona, gondola=gon.strip(), nivel=niv.strip(),
                                      serial=serial, codigo_leido="", referencia=ref, descripcion=desc, lote=lote_f,
                                      vence=m_ven.isoformat() if m_ven else "", cantidad=m_can, observacion=m_obs.strip(),
                                      origen="Admin" if es_admin else "Pareja")
                    st.session_state[f"ult_{pid}"] = ("ok", f"✍️ Manual: {ref} · lote {lote_f or 'SIN LOTE'} × {int(m_can)}")
                    st.rerun()

    # ---- Mis lecturas
    Lp = leer_lecturas()
    Lp = Lp[(Lp["pareja"] == pid) & (Lp["anulada"] == 0)] if not Lp.empty else Lp
    k = st.columns(3)
    kpi(k[0], "Mis lecturas", fmt_num(len(Lp)), "registros activos", C["teal"])
    kpi(k[1], "Mis unidades", fmt_num(Lp["cantidad"].sum() if not Lp.empty else 0), "contadas por esta pareja", C["navy"])
    E = leer_estado_seriales()
    kpi(k[2], "Seriales cerrados", fmt_num((E["pareja"] == pid).sum() if not E.empty else 0), "por esta pareja", C["verde"])
    if not Lp.empty:
        st.markdown("**Mis últimas lecturas** · marque y anule si se equivocó")
        v = Lp.sort_values("ts", ascending=False).head(60)
        if serial:
            v = v[v["serial"] == serial] if (v["serial"] == serial).any() else v
        v = v[["id", "ts", "modo", "zona", "gondola", "serial", "referencia", "descripcion", "lote", "cantidad"]].copy()
        v.insert(0, "ANULAR", False)
        ed = st.data_editor(v.set_index("id"), hide_index=True, height=300, key=f"mis_{pid}_{len(Lp)}",
                            disabled=[c for c in v.columns if c not in ("ANULAR", "id")],
                            column_config={"cantidad": st.column_config.NumberColumn(format="%d")})
        marcadas = list(ed.index[ed["ANULAR"]])
        if marcadas and st.button(f"🗑️ Anular {len(marcadas)} lectura(s) marcada(s)", key=f"anular_{pid}"):
            anular_lecturas(marcadas, pid)
            st.rerun()

# =============================================================================
# ADMINISTRADOR
# =============================================================================

def admin_maestros(ctx):
    seccion("📂 Archivos maestros (se guardan en la base de datos para todos)")
    st.caption("Cargue cada archivo y pulse **Guardar**. Las parejas no necesitan cargar nada.")
    c = st.columns(4)
    specs = [("templete", "Templete / Kardex Smith", ["xlsx", "xlsm", "xls", "csv"]),
             ("nal", "Archivo Nacional (NAL)", ["csv", "txt"]),
             ("valref", "Referencias Valref", ["csv", "txt", "xlsx"]),
             ("tpn", "Archivo TPN (hojas MAESTRO / BATCH-MAESTRO)", ["xlsm", "xlsx"])]
    for col, (tipo, etq, tipos) in zip(c, specs):
        with col:
            up = st.file_uploader(etq, type=tipos, key=f"up_{tipo}")
            if up is not None and st.button(f"💾 Guardar {tipo.upper()}", key=f"g_{tipo}", type="primary", width="stretch"):
                with st.spinner("Guardando…"):
                    guardar_maestro(tipo, up.name, up.getvalue())
                st.success("Guardado.")
                st.rerun()
    m = maestros_meta()
    if not m.empty:
        mm = m.copy()
        mm["tam"] = (mm["tam"] / 1_048_576).round(2).astype(str) + " MB"
        st.dataframe(mm.rename(columns={"tipo": "TIPO", "nombre": "ARCHIVO", "ts": "CARGADO", "tam": "TAMAÑO"}).drop(columns=["sha"]),
                     hide_index=True)
    if sha_de("templete"):
        try:
            hs = hojas_excel(bytes_maestro("templete", sha_de("templete"))) if not nombre_de("templete").lower().endswith(".csv") else []
        except Exception:
            hs = []
        if len(hs) > 1:
            actual = ctx["p"]["hoja_tpl"] or hs[0]
            h = st.selectbox("Hoja del templete a usar", hs, index=hs.index(actual) if actual in hs else 0)
            if h != ctx["p"]["hoja_tpl"]:
                cfg_set("hoja_tpl", h)
                st.rerun()
    UV = ctx["UV"]
    if UV["info"]:
        i = UV["info"]
        alerta(f"🧾 Inventario a contar: <b>{fmt_num(i['lineas'])}</b> líneas · <b>{fmt_num(i['seriales'])}</b> seriales · "
               f"<b>{fmt_num(i['seriales_otras'])}</b> seriales de otras ciudades ({fmt_num(i['otras_bodegas'])} líneas, referencias Valref) · "
               f"<b>{fmt_num(i['excluidos_ast'])}</b> registros excluidos por * / ** · "
               f"<b>{fmt_num(i['descuadres_com_lot'])}</b> descuadres Com vs Lot · "
               f"<b>{fmt_num(i.get('negativos', 0))}</b> líneas con saldo negativo en el NAL (no se cuentan)", "azul")

    seccion("⚙️ Parámetros")
    p = ctx["p"]
    with st.form("form_param"):
        a, b, c3 = st.columns(3)
        cliente = a.text_input("Cliente / proveedor", p["cliente"])
        resp = b.text_input("Responsable del conteo", p["responsable"])
        dias = c3.number_input("Alerta 'próximo a vencer' (días)", 15, 365, p["dias"], step=15)
        d, e, f = st.columns(3)
        opc_c = ["Propietaria (BODEGA PROPIE.)", "Existencia (BOD-EXISTENCIA)"]
        criterio = d.radio("Filtrar bodegas del NAL por", opc_c, index=opc_c.index(p["criterio"]) if p["criterio"] in opc_c else 0)
        opc_v = ["Costo promedio (Valref)", "Precio de venta (Valref)"]
        base_valor = e.radio("Valorizar con", opc_v, index=opc_v.index(p["base_valor"]) if p["base_valor"] in opc_v else 0)
        incl = f.toggle("Incluir seriales de otras ciudades (bodega propietaria, sin 10·20·27, ref. Valref sin * / **)",
                        value=p["incluir_otras"])
        avisos = f.toggle("Avisar a las parejas si el lote no figura en el listado", value=p["avisos_pareja"],
                          help="Apagado = conteo 100 % a ciegas.")
        if st.form_submit_button("Guardar parámetros", type="primary"):
            for k_, v_ in [("cliente", cliente), ("responsable", resp), ("dias", int(dias)), ("criterio", criterio),
                           ("base_valor", base_valor), ("incluir_otras", "1" if incl else "0"), ("avisos_pareja", "1" if avisos else "0")]:
                cfg_set(k_, v_)
            st.success("Parámetros guardados.")
            st.rerun()

    seccion("🔑 Seguridad")
    with st.form("form_clave"):
        n1, n2 = st.columns(2)
        c1_ = n1.text_input("Nueva contraseña de administrador", type="password")
        c2_ = n2.text_input("Repita la contraseña", type="password")
        if st.form_submit_button("Cambiar contraseña"):
            if len(c1_) < 6 or c1_ != c2_:
                st.error("La contraseña debe tener al menos 6 caracteres y coincidir.")
            else:
                cambiar_clave_admin(c1_)
                st.success("Contraseña actualizada.")
    if not cfg("admin_hash"):
        alerta("⚠️ Está usando la contraseña inicial. Cámbiela antes del conteo.", "ambar")

    seccion("🧹 Reinicio del conteo")
    st.caption("Use esto solo para empezar un inventario nuevo. Descargue antes los reportes.")
    conf = st.text_input("Escriba BORRAR para habilitar")
    if st.button("Borrar TODAS las lecturas y estados de seriales", disabled=conf.strip().upper() != "BORRAR"):
        ejecutar(delete(T_LECT))
        ejecutar(delete(T_SER))
        limpiar_caches_conteo()
        st.success("Conteo reiniciado.")
        st.rerun()


def nuevo_pin(existentes) -> str:
    while True:
        p = f"{random.randint(0, 9999):04d}"
        if p not in existentes:
            return p


def admin_parejas(ctx):
    seccion("👥 Parejas de conteo")
    P = leer_parejas()
    with st.form("form_pareja", clear_on_submit=True):
        p1, p2, p3, p4 = st.columns([1.2, 2, 2, 2])
        nombre = p1.text_input("Nombre pareja", placeholder=f"Pareja {len(P) + 1}")
        aux1 = p2.text_input("Auxiliar 1 *")
        aux2 = p3.text_input("Auxiliar 2 *")
        zona = p4.selectbox("Zona asignada", list(ZONAS))
        gond = st.text_input("Góndolas / ubicaciones asignadas")
        if st.form_submit_button("➕ Crear pareja (genera PIN)", type="primary"):
            nom = nombre.strip() or f"Pareja {len(P) + 1}"
            if not aux1.strip() or not aux2.strip():
                st.error("Indique los dos auxiliares.")
            elif not P.empty and nom in set(P["nombre"]):
                st.error("Ya existe una pareja con ese nombre.")
            else:
                pin = nuevo_pin(set(P["pin"]) if not P.empty else set())
                ejecutar(insert(T_PAR).values(id=uuid.uuid4().hex[:10], nombre=nom, aux1=aux1.strip(), aux2=aux2.strip(),
                                              pin=pin, zona=zona, gondolas=gond.strip(), estado="Activa",
                                              inicio=ahora().strftime("%Y-%m-%d %H:%M:%S"), fin=""))
                leer_parejas.clear()
                st.success(f"Pareja **{nom}** creada. PIN: **{pin}** (entrégueselo a la pareja).")
    P = leer_parejas()
    if not P.empty:
        st.caption("Puede editar auxiliares, zona, góndolas, PIN y estado directamente en la tabla.")
        v = P.set_index("id")[["nombre", "aux1", "aux2", "pin", "zona", "gondolas", "estado", "inicio", "fin"]]
        ed = st.data_editor(v, hide_index=True, key=f"ed_par_{len(P)}", disabled=["nombre", "inicio", "fin"],
                            column_config={"estado": st.column_config.SelectboxColumn("estado", options=["Activa", "Finalizada"]),
                                           "zona": st.column_config.SelectboxColumn("zona", options=list(ZONAS)),
                                           "pin": st.column_config.TextColumn("PIN", max_chars=4)})
        for pid_, r in ed.iterrows():
            o = v.loc[pid_]
            cambios = {c: str(r[c]) for c in ["aux1", "aux2", "pin", "zona", "gondolas", "estado"] if str(r[c]) != str(o[c])}
            if cambios:
                if cambios.get("estado") == "Finalizada":
                    cambios["fin"] = ahora().strftime("%Y-%m-%d %H:%M:%S")
                elif cambios.get("estado") == "Activa":
                    cambios["fin"] = ""
                ejecutar(update(T_PAR).where(T_PAR.c.id == pid_).values(**cambios))
                leer_parejas.clear()
                st.rerun()

    seccion("📥 Importar archivo de pistoleo (lector descargado / TPN)")
    with st.form("form_import"):
        i1, i2, i3 = st.columns([2, 1.2, 1.2])
        f = i1.file_uploader("Archivo de pistoleo", type=["xlsx", "xlsm", "csv"])
        par_opc = list(P["nombre"]) if not P.empty else []
        par_sel = i2.selectbox("Pareja que lo contó", ["(sin asignar)"] + par_opc)
        zona_sel = i3.selectbox("Zona", list(ZONAS))
        if st.form_submit_button("Importar lecturas", type="primary") and f is not None:
            data = f.getvalue()
            sha = hashlib.sha256(data).hexdigest()[:20]
            if cfg(f"import_{sha}"):
                st.warning("Ese archivo ya fue importado antes; no se duplicaron lecturas.")
            else:
                pis = leer_pistoleo(data, f.name)
                filas = []
                for _, r in pis.iterrows():
                    ref, lote = r["REFERENCIA"], r["LOTE"]
                    if not ref and r["EAN"]:
                        ref, lc, _, _ = resolver_codigo(r["EAN"], ctx["gtin"])
                        lote = lote or lc
                    filas.append({c.name: "" for c in T_LECT.columns} | dict(
                        id=uuid.uuid4().hex[:16], ts=ahora().strftime("%Y-%m-%d %H:%M:%S"), pareja=par_sel,
                        modo="ARCHIVO", grupo=ZONAS[zona_sel], zona=zona_sel, gondola=str(r["GONDOLA"]),
                        nivel=str(r["NIVEL"]), serial=str(r["SERIAL"]), codigo_leido=str(r["EAN"]), referencia=ref,
                        descripcion=str(r["DESCRIPCION"]), lote=lote,
                        vence=r["VENCE"].strftime("%Y-%m-%d") if not pd.isna(r["VENCE"]) else "",
                        cantidad=float(r["CANTIDAD"]), origen=f"Archivo {f.name}"[:120], anulada=0))
                if filas:
                    ejecutar(insert(T_LECT), filas)
                    cfg_set(f"import_{sha}", f.name)
                    leer_lecturas.clear()
                st.success(f"{len(filas)} lecturas importadas.")

    seccion("📡 Monitor de lecturas en vivo")
    L = leer_lecturas()
    if L.empty:
        st.info("Aún no hay lecturas.")
    else:
        f1, f2, f3 = st.columns([1.5, 1.5, 2])
        fp = f1.multiselect("Pareja", sorted(L["pareja"].unique()), placeholder="Todas")
        fm = f2.multiselect("Modo", sorted(L["modo"].unique()), placeholder="Todos")
        fb = f3.text_input("Buscar referencia / lote / serial")
        d = L
        if fp:
            d = d[d["pareja"].isin(fp)]
        if fm:
            d = d[d["modo"].isin(fm)]
        if fb:
            b_ = fb.strip().upper()
            d = d[d["referencia"].str.upper().str.contains(b_, regex=False) | d["lote"].str.upper().str.contains(b_, regex=False)
                  | d["serial"].str.upper().str.contains(b_, regex=False)]
        d = d.sort_values("ts", ascending=False).head(2000)
        v = d[["id", "ts", "pareja", "modo", "zona", "gondola", "nivel", "serial", "referencia", "descripcion", "lote",
               "vence", "cantidad", "observacion", "anulada", "anulada_por"]].copy()
        v.insert(0, "ANULAR", False)
        ed = st.data_editor(v.set_index("id"), hide_index=True, height=380, key=f"mon_{len(L)}_{hash((tuple(fp), tuple(fm), fb)) % 10**6}",
                            disabled=[c for c in v.columns if c not in ("ANULAR", "id")])
        marc = list(ed.index[ed["ANULAR"] & (ed["anulada"] == 0)])
        if marc and st.button(f"🗑️ Anular {len(marc)} lectura(s)"):
            anular_lecturas(marc, "Administrador")
            st.rerun()

    seccion("🧭 Trazabilidad por pareja")
    traz, det = trazabilidad()
    if not traz.empty:
        st.dataframe(traz, hide_index=True, column_config={
            "% DEL TOTAL": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%")})
    st.download_button("⬇️ Informe de Trazabilidad por Parejas (.xlsx)", data=lambda: a_excel(
        excel_traz(traz, det), "INFORME DE TRAZABILIDAD POR PAREJAS DE CONTEO", f"Responsable: {ctx['p']['responsable'] or '—'}"),
        file_name=f"Trazabilidad_Parejas_{ahora():%Y%m%d_%H%M}.xlsx", type="primary", width="stretch",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def trazabilidad():
    L = leer_lecturas()
    if L.empty:
        return pd.DataFrame(), pd.DataFrame()
    Lv = L[L["anulada"] == 0]
    P = leer_parejas()
    aux = dict(zip(P["nombre"], P["aux1"] + " / " + P["aux2"])) if not P.empty else {}
    E = leer_estado_seriales()
    ser_c = E.groupby("pareja")["serial"].count() if not E.empty else pd.Series(dtype=int)
    t = Lv.groupby("pareja", as_index=False).agg(
        ZONAS=("zona", lambda s: ", ".join(sorted(set(s)))), LECTURAS=("id", "count"), UNIDADES=("cantidad", "sum"),
        MANUALES=("modo", lambda s: int((s == "MANUAL").sum())), REFERENCIAS=("referencia", "nunique"),
        SERIALES=("serial", lambda s: len({x for x in s if x})),
        GONDOLAS=("gondola", lambda s: ", ".join(sorted({x for x in s if x}))),
        PRIMER_REGISTRO=("ts", "min"), ULTIMO_REGISTRO=("ts", "max"))
    t.insert(1, "AUXILIARES", t["pareja"].map(aux).fillna("—"))
    t["SERIALES_CERRADOS"] = t["pareja"].map(ser_c).fillna(0).astype(int)
    t["ANULADAS"] = t["pareja"].map(L[L["anulada"] == 1].groupby("pareja")["id"].count()).fillna(0).astype(int)
    t["% DEL TOTAL"] = (t["UNIDADES"] / max(t["UNIDADES"].sum(), 1) * 100).round(1)
    return t.rename(columns={"pareja": "PAREJA"}).sort_values("UNIDADES", ascending=False), L


def excel_traz(traz, L) -> dict:
    P = leer_parejas().drop(columns=["pin", "id"], errors="ignore")
    E = leer_estado_seriales()
    hojas = {"Resumen_por_Pareja": traz, "Parejas": P, "Lecturas_Todas": L.drop(columns=["id"], errors="ignore") if not L.empty else L,
             "Seriales_Cerrados": E}
    if not L.empty:
        Lv = L[L["anulada"] == 0]
        hojas["Pareja_x_Gondola"] = Lv.pivot_table(index=["pareja", "zona", "gondola"], values="cantidad", aggfunc="sum").reset_index()
    return hojas


def admin_seriales(ctx):
    S, U = ctx["S"], ctx["U"]
    if S.empty:
        st.info("Cargue el NAL para ver los seriales.")
        return
    L = lecturas_validas()
    Se = estado_seriales(S, L)
    g1, g2, g3 = st.columns([1, 1, 2])
    gr = g1.selectbox("Grupo", ["SMITH", "SERENA"], key="ser_grupo")
    est = g2.multiselect("Estado", ["⏳ PENDIENTE", "🔄 EN CONTEO", "✅ CERRADO"], placeholder="Todos")
    bus = g3.text_input("Buscar serial / set", key="ser_bus")
    d = Se[Se["GRUPO"] == gr]
    tot = len(d)
    k = st.columns(4)
    for col, (e, colr) in zip(k, [("⏳ PENDIENTE", C["rojo"]), ("🔄 EN CONTEO", C["ambar"]), ("✅ CERRADO", C["verde"])]):
        n = int((d["ESTADO"] == e).sum())
        kpi(col, e, fmt_num(n), f"{pct(n, tot):.1f}% de {fmt_num(tot)} seriales", colr, pct(n, tot))
    kpi(k[3], "Unidades en seriales", fmt_num(d["UNIDADES"].sum()), f"contadas: {fmt_num(d['CONTADO'].sum())}", C["navy"])
    if est:
        d = d[d["ESTADO"].isin(est)]
    if bus:
        b_ = bus.strip().upper()
        d = d[d["SERIAL"].str.contains(b_, regex=False) | d["SET"].str.upper().str.contains(b_, regex=False)]
    d = d.assign(DIFERENCIA=d["CONTADO"] - d["UNIDADES"])
    st.dataframe(d[["SERIAL", "SET", "BODEGA_NOM", "ORIGEN_BOD", "ESTADO", "LINEAS", "UNIDADES", "CONTADO", "DIFERENCIA",
                    "PAREJAS", "CERRADO_POR", "CERRADO_TS", "ULTIMA"]], hide_index=True, height=360)
    ser_det = st.selectbox("Ver detalle de un serial", ["—"] + list(d["SERIAL"]), key="ser_det")
    if ser_det != "—":
        M = comparar(U[U["SERIAL"] == ser_det], L[L["SERIAL"] == ser_det], gr, ctx["p"]["base_valor"], Se)
        mostrar_tabla(M.drop(columns=["TIPO", "BODEGAS", "ORIGEN"]), alto=320)
        r = Se[Se["SERIAL"] == ser_det].iloc[0]
        if r["ESTADO"] == "✅ CERRADO" and st.button("↩️ Reabrir este serial"):
            fijar_estado_serial(ser_det, gr, None)
            st.rerun()
    no_list = L[(L["SERIAL"] != "") & ~L["SERIAL"].isin(set(S["SERIAL"]))]
    if not no_list.empty:
        seccion("🆕 Seriales escaneados que no están en el NAL")
        st.dataframe(no_list.groupby("SERIAL", as_index=False).agg(LECTURAS=("id", "count"), UNIDADES=("cantidad", "sum"),
                                                                   PAREJAS=("pareja", lambda s: ", ".join(sorted(set(s))))),
                     hide_index=True)


def admin_grupo(ctx, grupo: str):
    U, S, p = ctx["U"], ctx["S"], ctx["p"]
    L = lecturas_validas()
    if U.empty and L.empty:
        alerta("ℹ️ Cargue el NAL (y Valref) en <b>⚙️ Maestros</b> para generar el inventario a contar.", "azul")
        return None
    Se = estado_seriales(S, L) if not S.empty else S
    M = comparar(U, L, grupo, p["base_valor"], Se)
    if M.empty:
        st.info("Sin datos para este grupo.")
        return M
    nolist = M["ESTADO"].str.startswith("🆕") | M["ESTADO"].str.startswith("⚠️")
    Ms = M[~nolist]
    sis, con = Ms["SISTEMA"].sum(), M["CONTADO"].sum()
    cob = np.minimum(Ms["CONTADO"], Ms["SISTEMA"]).sum()
    k = st.columns(5)
    kpi(k[0], "Avance (cobertura)", f"{pct(cob, sis):.1f}%", f"{fmt_num(cob)} de {fmt_num(sis)} und", C["teal"], pct(cob, sis))
    stk = Ms[Ms["TIPO"] == "STOCK"]
    kpi(k[1], "Stock de seguridad", f"{pct(np.minimum(stk['CONTADO'], stk['SISTEMA']).sum(), stk['SISTEMA'].sum()):.1f}%",
        f"{fmt_num(stk['SISTEMA'].sum())} und en sistema", C["azul"])
    sg = Se[Se["GRUPO"] == grupo] if not Se.empty else Se
    cerr = int((sg["ESTADO"] == "✅ CERRADO").sum()) if not sg.empty else 0
    kpi(k[2], "Seriales cerrados", f"{fmt_num(cerr)} / {fmt_num(len(sg))}",
        f"{fmt_num((sg['ESTADO'] == '⏳ PENDIENTE').sum() if not sg.empty else 0)} pendientes", C["navy"], pct(cerr, len(sg)))
    Mf = Ms[(Ms["DIFERENCIA"] < 0) & (Ms["ESTADO"] != "⏳ SERIAL PENDIENTE")]
    kpi(k[3], "Faltantes", fmt_num(-Mf["DIFERENCIA"].sum()),
        f"{fmt_cop(Mf['VALOR_DIF'].sum())} · sin seriales pendientes", C["rojo"])
    kpi(k[4], "Sobrantes / novedades", fmt_num(M.loc[M["DIFERENCIA"] > 0, "DIFERENCIA"].sum()),
        f"{fmt_num(nolist.sum())} líneas no listadas · {fmt_cop(M.loc[M['DIFERENCIA'] > 0, 'VALOR_DIF'].sum())}", C["ambar"])
    venc = int((Ms["ESTADO_VENC"] == "VENCIDO").sum())
    if venc:
        alerta(f"⛔ <b>{fmt_num(venc)}</b> líneas con lote VENCIDO y <b>{fmt_num((Ms['ESTADO_VENC'] == 'PRÓXIMO A VENCER').sum())}</b> "
               f"próximas a vencer (≤ {p['dias']} días) · resaltadas en rojo / ámbar", "roja")
    st.write("")
    nombres = ["📋 Sistema vs conteo (serial · ref · lote)", "Σ Totales por referencia", "⏰ Vencimientos", "🆕 Novedades / no listadas"]
    if grupo == "SMITH":
        nombres += ["📑 Templete vs conteo", "✳️ Excluidos por * / **", "🧮 Com vs Lot"]
    tabs = st.tabs(nombres)
    with tabs[0]:
        f1, f2, f3, f4 = st.columns([2, 1.3, 1.2, 2])
        se = f1.multiselect("Estado", sorted(M["ESTADO"].unique()), placeholder="Todos", key=f"fe_{grupo}")
        ti = f2.multiselect("Tipo", ["STOCK", "SERIAL"], placeholder="Ambos", key=f"ft_{grupo}")
        sd = f3.toggle("Solo diferencias", key=f"sd_{grupo}")
        bu = f4.text_input("Buscar referencia / lote / serial", key=f"bu_{grupo}")
        d = M
        if se:
            d = d[d["ESTADO"].isin(se)]
        if ti:
            d = d[d["TIPO"].isin(ti)]
        if sd:
            d = d[d["DIFERENCIA"] != 0]
        if bu:
            b_ = bu.strip().upper()
            d = d[d["REFERENCIA"].str.upper().str.contains(b_, regex=False) | d["LOTE"].str.upper().str.contains(b_, regex=False)
                  | d["SERIAL"].str.contains(b_, regex=False) | d["DESCRIPCION"].str.upper().str.contains(b_, regex=False)]
        st.caption(f"{fmt_num(len(d))} líneas · sistema {fmt_num(d['SISTEMA'].sum())} · contado {fmt_num(d['CONTADO'].sum())} · "
                   f"diferencia {fmt_num(d['DIFERENCIA'].sum())} · {fmt_cop(d['VALOR_DIF'].sum())}")
        mostrar_tabla(d)
    with tabs[1]:
        mostrar_tabla(totales_ref(Ms))
    with tabs[2]:
        vv = Ms[Ms["ESTADO_VENC"].isin(["VENCIDO", "PRÓXIMO A VENCER"])].sort_values("VENCE")
        mostrar_tabla(vv, alto=380)
    with tabs[3]:
        nv = M[nolist | (M["MANUAL"] > 0)]
        st.caption("Incluye referencias / lotes / seriales encontrados que no están en el listado y todos los registros manuales.")
        mostrar_tabla(nv, alto=380)
    T = None
    if grupo == "SMITH":
        T = templete_df(ctx["sha_tpl"], p["hoja_tpl"])
        with tabs[4]:
            if T is None:
                st.info("Cargue el Templete/Kardex en ⚙️ Maestros.")
            else:
                mostrar_tabla(templete_vs_conteo(T, L, U, p["base_valor"], ctx["lotes"]))
        with tabs[5]:
            ex = ctx["UV"]["excl"]
            st.caption("Componentes de seriales de otras ciudades cuya referencia está en Valref pero su código o lote tiene * o **: no entran al conteo.")
            st.dataframe(ex, hide_index=True, height=320)
        with tabs[6]:
            cc = ctx["UV"]["conc"]
            mostrar_tabla(cc[cc["CUADRA"] == "No"][["SERIAL", "SET", "REFERENCIA", "DESCRIPCION", "CANT_COM", "SUMA_LOT",
                                                    "N_LOTES", "DIF_COM_LOT", "CUADRA"]] if not cc.empty else cc, alto=320)
    seccion("📥 Exportación")
    titulo = "CONSOLIDADO GENERAL CRUZADO · SMITH & NEPHEW" if grupo == "SMITH" else "REPORTE DE NOVEDADES · SERENA DEL MAR"
    nombre = "Consolidado_General_Smith" if grupo == "SMITH" else "Novedades_Serena_del_Mar"
    st.download_button(f"⬇️ Descargar {titulo.title()} (.xlsx)", data=lambda: a_excel(
        excel_grupo(ctx, grupo, M, Ms, Se, L, T), titulo,
        f"{p['cliente']} · Responsable: {p['responsable'] or '—'} · Criterio: {p['criterio']}"),
        file_name=f"{nombre}_{ahora():%Y%m%d_%H%M}.xlsx", type="primary", width="stretch",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{grupo}")
    return M


def excel_grupo(ctx, grupo, M, Ms, Se, L, T) -> dict:
    p = ctx["p"]
    sis = Ms["SISTEMA"].sum()
    sg = Se[Se["GRUPO"] == grupo] if not Se.empty else Se
    res = pd.DataFrame([
        ("Fecha de generación", ahora().strftime("%d/%m/%Y %H:%M")), ("Cliente", p["cliente"]), ("Responsable", p["responsable"]),
        ("Bodegas", ", ".join(map(str, BODEGAS_SMITH if grupo == "SMITH" else BODEGAS_SERENA))
         + (" + seriales de otras ciudades por bodega propietaria (sin 10, 20, 27) con referencias Valref sin * / **"
            if grupo == "SMITH" and p["incluir_otras"] else "")),
        ("Criterio de bodega", p["criterio"]), ("Archivo NAL", nombre_de("nal")), ("Archivo Valref", nombre_de("valref")),
        ("Unidades en sistema", sis), ("Unidades contadas", M["CONTADO"].sum()),
        ("Avance (cobertura) %", round(pct(np.minimum(Ms["CONTADO"], Ms["SISTEMA"]).sum(), sis), 2)),
        ("Seriales totales", len(sg)), ("Seriales cerrados", int((sg["ESTADO"] == "✅ CERRADO").sum()) if not sg.empty else 0),
        ("Seriales pendientes", int((sg["ESTADO"] == "⏳ PENDIENTE").sum()) if not sg.empty else 0),
        ("Unidades faltantes", -Ms.loc[Ms["DIFERENCIA"] < 0, "DIFERENCIA"].sum()),
        ("Unidades sobrantes / novedades", M.loc[M["DIFERENCIA"] > 0, "DIFERENCIA"].sum()),
        ("Valor en sistema $", Ms["VALOR_SISTEMA"].sum()), ("Valor faltante $", Ms.loc[Ms["DIFERENCIA"] < 0, "VALOR_DIF"].sum()),
        ("Valor sobrante $", M.loc[M["DIFERENCIA"] > 0, "VALOR_DIF"].sum()), ("Diferencia neta $", M["VALOR_DIF"].sum()),
        ("Lotes vencidos", int((Ms["ESTADO_VENC"] == "VENCIDO").sum())),
        ("Registros excluidos por * / **", len(ctx["UV"]["excl"]) if grupo == "SMITH" else ""),
    ], columns=["INDICADOR", "VALOR"])
    res["VALOR"] = res["VALOR"].astype(str)
    sg_x = sg.assign(DIFERENCIA=sg["CONTADO"] - sg["UNIDADES"]) if not sg.empty else sg
    lg = L[L["grupo"] == grupo].drop(columns=["K_REF", "K_LOTE", "SERIAL", "VENCE_L"], errors="ignore") if not L.empty else L
    h = {
        "Resumen": res,
        "Sistema_vs_Conteo": para_excel(M),
        "Totales_Referencia": para_excel(totales_ref(Ms)),
        "Seriales": para_excel(sg_x),
        "Faltantes": para_excel(Ms[Ms["DIFERENCIA"] < 0]),
        "Sobrantes_y_Novedades": para_excel(M[(M["DIFERENCIA"] > 0) | (M["MANUAL"] > 0)]),
        "Stock_Seguridad": para_excel(M[M["TIPO"] == "STOCK"]),
        "Vencimientos": para_excel(Ms[Ms["ESTADO_VENC"].isin(["VENCIDO", "PRÓXIMO A VENCER"])].sort_values("VENCE")),
        "Lecturas": lg,
    }
    if grupo == "SMITH":
        if T is not None:
            h["Templete_vs_Conteo"] = para_excel(templete_vs_conteo(T, L, ctx["U"], p["base_valor"], ctx["lotes"]))
        h["Excluidos_Asterisco"] = ctx["UV"]["excl"]
        h["Saldos_Negativos_NAL"] = ctx["UV"]["neg"]
        h["Conciliacion_Com_Lot"] = para_excel(ctx["UV"]["conc"]) if not ctx["UV"]["conc"].empty else pd.DataFrame()
    return h


def admin_dashboard(ctx):
    U, S, p = ctx["U"], ctx["S"], ctx["p"]
    L = lecturas_validas()
    if U.empty and L.empty:
        alerta("ℹ️ El tablero se llena cuando se cargan los maestros y empiezan las lecturas.", "azul")
        return
    Se = estado_seriales(S, L) if not S.empty else S
    res = {}
    for g in ["SMITH", "SERENA"]:
        M = comparar(U, L, g, p["base_valor"], Se)
        if M.empty:
            res[g] = dict(sis=0, con=0, cob=0, falt=0, sobr=0, vf=0, vs=0, vsis=0, M=M, exa=0, n=0, pend=0)
            continue
        nol = M["ESTADO"].str.startswith("🆕") | M["ESTADO"].str.startswith("⚠️")
        Ms = M[~nol]
        Mf = Ms[(Ms["DIFERENCIA"] < 0) & (Ms["ESTADO"] != "⏳ SERIAL PENDIENTE")]
        res[g] = dict(sis=Ms["SISTEMA"].sum(), con=M["CONTADO"].sum(), cob=np.minimum(Ms["CONTADO"], Ms["SISTEMA"]).sum(),
                      falt=-Mf["DIFERENCIA"].sum(), sobr=M.loc[M["DIFERENCIA"] > 0, "DIFERENCIA"].sum(),
                      vf=Mf["VALOR_DIF"].sum(), vs=M.loc[M["DIFERENCIA"] > 0, "VALOR_DIF"].sum(),
                      vsis=Ms["VALOR_SISTEMA"].sum(), M=M, exa=int((Ms["DIFERENCIA"] == 0).sum()), n=len(Ms),
                      pend=Ms.loc[Ms["ESTADO"] == "⏳ SERIAL PENDIENTE", "SISTEMA"].sum())
    sm, se = res["SMITH"], res["SERENA"]
    tot = {k: sm[k] + se[k] for k in ["sis", "con", "cob", "falt", "sobr", "vf", "vs", "vsis", "exa", "n", "pend"]}
    st.markdown(f"#### Resumen ejecutivo · {p['cliente']} · corte {ahora():%d/%m/%Y %H:%M}")
    r1 = st.columns(4)
    av = pct(tot["cob"], tot["sis"])
    kpi(r1[0], "Avance global", f"{av:.1f}%", f"{fmt_num(tot['cob'])} de {fmt_num(tot['sis'])} und", C["teal"], av)
    kpi(r1[1], "Smith & Nephew", f"{pct(sm['cob'], sm['sis']):.1f}%", "bod. 58·59·81·82·83·84 + seriales Valref", C["navy"], pct(sm["cob"], sm["sis"]))
    kpi(r1[2], "Serena del Mar", f"{pct(se['cob'], se['sis']):.1f}%", "bodegas 66 · 67", C["azul"], pct(se["cob"], se["sis"]))
    n_ser = len(Se) if not Se.empty else 0
    n_cer = int((Se["ESTADO"] == "✅ CERRADO").sum()) if n_ser else 0
    kpi(r1[3], "Seriales cerrados", f"{pct(n_cer, n_ser):.1f}%", f"{fmt_num(n_cer)} de {fmt_num(n_ser)}", C["verde"], pct(n_cer, n_ser))
    st.write("")
    r2 = st.columns(4)
    kpi(r2[0], "Valor en sistema", fmt_cop(tot["vsis"]), p["base_valor"], C["navy"])
    kpi(r2[1], "Valor faltante", fmt_cop(tot["vf"]), f"{fmt_num(tot['falt'])} und · sin contar {fmt_num(tot['pend'])} und en seriales pendientes", C["rojo"])
    kpi(r2[2], "Valor sobrante / novedades", fmt_cop(tot["vs"]), f"{fmt_num(tot['sobr'])} und", C["ambar"])
    neto = tot["vf"] + tot["vs"]
    kpi(r2[3], "Diferencia neta", fmt_cop(neto), f"Exactitud por línea: {pct(tot['exa'], tot['n']):.1f}%",
        C["rojo"] if neto < 0 else C["verde"])
    st.write("")
    g1, g2 = st.columns([1, 1.6])
    with g1:
        fig = go.Figure(go.Pie(labels=["Contado", "Pendiente"], values=[tot["cob"], max(tot["sis"] - tot["cob"], 0)], hole=.68,
                               marker=dict(colors=[C["teal"], "#DDE3EC"]), sort=False, textinfo="percent"))
        fig.add_annotation(text=f"<b>{av:.1f}%</b><br>avance", showarrow=False, font=dict(size=22, color=C["navy"]))
        st.plotly_chart(layout_fig(fig, 330, "Ítems contados vs pendientes"), key="d_donut")
    with g2:
        fig = go.Figure()
        for nm, k_, colr in [("Sistema", "sis", C["gris"]), ("Contado", "con", C["teal"]), ("Serial pendiente", "pend", "#C9D3E0"),
                             ("Faltante", "falt", C["rojo"]), ("Sobrante", "sobr", C["ambar"])]:
            fig.add_bar(name=nm, x=["Smith & Nephew", "Serena del Mar"], y=[sm[k_], se[k_]], marker_color=colr,
                        text=[fmt_num(sm[k_]), fmt_num(se[k_])], textposition="outside")
        fig.update_layout(barmode="group")
        st.plotly_chart(layout_fig(fig, 330, "Unidades por sección"), key="d_bar")
    g3, g4 = st.columns([1.6, 1])
    with g3:
        top = pd.concat([sm["M"].assign(SEC="Smith"), se["M"].assign(SEC="Serena")]) if not (sm["M"].empty and se["M"].empty) else pd.DataFrame()
        top = top[top["VALOR_DIF"] != 0] if not top.empty else top
        if top.empty:
            st.info("Sin diferencias valorizadas todavía.")
        else:
            top = top.groupby(["SEC", "REFERENCIA"], as_index=False).agg(DES=("DESCRIPCION", "first"), V=("VALOR_DIF", "sum"))
            top = top.reindex(top["V"].abs().sort_values(ascending=False).index).head(12).iloc[::-1]
            fig = go.Figure(go.Bar(x=top["V"], y=top["REFERENCIA"] + " · " + top["DES"].str[:26], orientation="h",
                                   marker_color=np.where(top["V"] < 0, C["rojo"], C["ambar"]),
                                   text=[fmt_cop(v) for v in top["V"]], textposition="auto"))
            st.plotly_chart(layout_fig(fig, 420, "Top 12 diferencias valorizadas"), key="d_top")
    with g4:
        if n_ser:
            cnt = Se.groupby(["GRUPO", "ESTADO"]).size().reset_index(name="N")
            fig = px.bar(cnt, x="GRUPO", y="N", color="ESTADO", text="N",
                         color_discrete_map={"⏳ PENDIENTE": C["rojo"], "🔄 EN CONTEO": C["ambar"], "✅ CERRADO": C["verde"]})
            st.plotly_chart(layout_fig(fig, 420, "Estado de seriales"), key="d_ser")
    traz, det = trazabilidad()
    if not traz.empty:
        g5, g6 = st.columns(2)
        with g5:
            fig = px.bar(traz.sort_values("UNIDADES"), x="UNIDADES", y="PAREJA", orientation="h", text="UNIDADES",
                         color_discrete_sequence=[C["navy"]])
            st.plotly_chart(layout_fig(fig, 320, "Productividad por pareja"), key="d_par")
        with g6:
            d = det[det["anulada"] == 0].copy()
            d["HORA"] = pd.to_datetime(d["ts"], errors="coerce").dt.floor("h")
            d = d.dropna(subset=["HORA"]).groupby("HORA", as_index=False)["cantidad"].sum()
            if not d.empty:
                d["ACUM"] = d["cantidad"].cumsum()
                fig = go.Figure(go.Scatter(x=d["HORA"], y=d["ACUM"], mode="lines+markers", fill="tozeroy",
                                           line=dict(color=C["teal"], width=3)))
                st.plotly_chart(layout_fig(fig, 320, "Ritmo del conteo (unidades acumuladas)"), key="d_ritmo")
    tabla = pd.DataFrame([{"SECCIÓN": n, "UND. SISTEMA": d_["sis"], "UND. CONTADAS": d_["con"],
                           "AVANCE %": round(pct(d_["cob"], d_["sis"]), 1), "FALTANTES": d_["falt"], "SOBRANTES": d_["sobr"],
                           "VALOR SISTEMA": d_["vsis"], "VALOR FALTANTE": d_["vf"], "VALOR SOBRANTE": d_["vs"],
                           "DIF. NETA": d_["vf"] + d_["vs"]}
                          for n, d_ in [("Smith & Nephew", sm), ("Serena del Mar", se), ("TOTAL", tot)]])
    seccion("📌 Tabla resumen para la gerencia")
    st.dataframe(tabla, hide_index=True)
    st.download_button("⬇️ Resumen gerencial (.xlsx)", data=lambda: a_excel({"Resumen_Gerencial": tabla}, "RESUMEN GERENCIAL DEL INVENTARIO",
                                                                    p["cliente"]),
                       file_name=f"Resumen_Gerencial_{ahora():%Y%m%d_%H%M}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# =============================================================================
# INGRESO Y NAVEGACIÓN
# =============================================================================

def pantalla_login():
    st.markdown("<style>section[data-testid='stSidebar']{display:none;}</style>", unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 1.5, 1])
    with centro:
        st.markdown(logo_html(), unsafe_allow_html=True)
        st.markdown('<div class="banner" style="text-align:center"><h1>Control de Inventario Físico</h1>'
                    '<p>Smith &amp; Nephew · Tecnitrauma</p></div>', unsafe_allow_html=True)
        if st.session_state.get("intentos", 0) >= 8:
            st.error("Demasiados intentos fallidos. Cierre y vuelva a abrir el navegador.")
            return
        t1, t2 = st.tabs(["👥 Pareja de conteo", "🔐 Administrador"])
        with t1:
            P = leer_parejas()
            act = P[P["estado"] == "Activa"] if not P.empty else P
            if act.empty:
                st.info("El administrador aún no ha creado parejas de conteo.")
            else:
                with st.form("login_par"):
                    nom = st.selectbox("Su pareja", list(act["nombre"]))
                    pin = st.text_input("PIN de 4 dígitos", type="password", max_chars=4)
                    if st.form_submit_button("Ingresar a contar", type="primary", width="stretch"):
                        r = act[act["nombre"] == nom].iloc[0]
                        if pin.strip() and pin.strip() == str(r["pin"]).strip():
                            st.session_state.update(rol="pareja", pareja_id=r["id"], intentos=0)
                            st.rerun()
                        else:
                            st.session_state.intentos = st.session_state.get("intentos", 0) + 1
                            st.error("PIN incorrecto.")
        with t2:
            with st.form("login_adm"):
                clave_ = st.text_input("Contraseña de administrador", type="password")
                if st.form_submit_button("Ingresar", type="primary", width="stretch"):
                    if verificar_admin(clave_):
                        st.session_state.update(rol="admin", intentos=0)
                        st.rerun()
                    else:
                        st.session_state.intentos = st.session_state.get("intentos", 0) + 1
                        st.error("Contraseña incorrecta.")
        modo = motor()[1]
        st.caption("🟢 Datos guardados en la nube" if modo == "nube" else "💾 Datos guardados en este computador (modo local)")


def barra(rol: str, nombre: str):
    sb = st.sidebar
    sb.markdown(logo_html(), unsafe_allow_html=True)
    sb.markdown(f"**Sesión:** {'🔐 Administrador' if rol == 'admin' else '👥 ' + nombre}")
    sb.caption(f"🕒 {ahora():%d/%m/%Y %H:%M}  ·  " + ("🟢 nube" if motor()[1] == "nube" else "💾 local"))
    if sb.button("🔄 Actualizar datos", width="stretch"):
        limpiar_caches_conteo()
        st.rerun()
    if sb.button("🚪 Cerrar sesión", width="stretch"):
        for k in ("rol", "pareja_id"):
            st.session_state.pop(k, None)
        st.rerun()


def main():
    st.markdown(CSS + CSS_EXTRA, unsafe_allow_html=True)
    try:
        motor()
    except Exception as e:
        st.error(f"No fue posible conectar con la base de datos: {e}")
        st.stop()
    rol = st.session_state.get("rol")
    if not rol:
        pantalla_login()
        return
    if rol == "pareja":
        P = leer_parejas()
        fila = P[P["id"] == st.session_state.get("pareja_id")]
        if fila.empty or fila.iloc[0]["estado"] != "Activa":
            st.session_state.pop("rol", None)
            st.warning("Su pareja fue finalizada o eliminada. Ingrese de nuevo.")
            st.rerun()
        par = fila.iloc[0].to_dict()
        barra("pareja", par["nombre"])
        ctx = contexto()
        st.markdown(f'<div class="banner"><h1>📡 Conteo · {par["nombre"]}</h1><p>Pistolee o digite. '
                    'Los registros se guardan al instante.</p></div>', unsafe_allow_html=True)
        pantalla_conteo(par, ctx)
        return
    # ---- Administrador
    barra("admin", "")
    ctx = contexto()
    st.markdown(f'<div class="banner"><h1>📦 Control de Inventario Físico · Smith & Nephew</h1>'
                f'<p>Tecnitrauma · Panel del administrador · {ahora():%d/%m/%Y %H:%M}</p></div>', unsafe_allow_html=True)
    if ctx["U"].empty:
        alerta("👉 Empiece en <b>⚙️ Maestros y configuración</b>: cargue NAL, Valref, Templete y TPN; luego cree las parejas.", "ambar")
    t = st.tabs(["📊 Dashboard", "🏭 Smith & Nephew", "🌊 Serena del Mar", "🧰 Seriales", "👥 Parejas y trazabilidad",
                 "📡 Pistolear", "⚙️ Maestros y configuración"])
    with t[0]:
        admin_dashboard(ctx)
    with t[1]:
        admin_grupo(ctx, "SMITH")
    with t[2]:
        admin_grupo(ctx, "SERENA")
    with t[3]:
        admin_seriales(ctx)
    with t[4]:
        admin_parejas(ctx)
    with t[5]:
        P = leer_parejas()
        opciones = ["Administrador"] + (list(P["nombre"]) if not P.empty else [])
        quien = st.selectbox("Registrar a nombre de", opciones, key="adm_quien")
        if quien == "Administrador":
            par = dict(nombre="Administrador", aux1="", aux2="", zona=list(ZONAS)[0], gondolas="")
        else:
            par = P[P["nombre"] == quien].iloc[0].to_dict()
        pantalla_conteo(par, ctx, es_admin=True)
    with t[6]:
        admin_maestros(ctx)


if __name__ == "__main__":
    main()
