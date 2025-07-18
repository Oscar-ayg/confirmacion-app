import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(page_title="CONFIRMACIONES A&G", layout="wide")

# --- CONFIGURAR GOOGLE SHEETS ---
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", SCOPE)
CLIENT = gspread.authorize(CREDS)
SHEET_ID = "1M9kT7zy2VcBt0j_1iHmWw1bV2mSA2Q1lMoxxRwQMe6k"

# --- LOCALIDADES DE INTERÉS ---
LOCALIDADES_VALIDAS = ["FUNZA", "MADRID", "MOSQUERA", "FACATATIVA", "COTA", "VILLETA", "ANAPOIMA", "LA MESA"]

# --- CARGAR DATOS DE GOOGLE SHEETS ---
def cargar_datos():
    sheet = CLIENT.open_by_key(SHEET_ID)

    columnas_confirmaciones = [
        "Técnico", "Estado de la orden", "Número de petición",
        "Dias", "Dirección", "Localidad", "Teléfono móvil", "Confirmación"
    ]
    columnas_pendientes = columnas_confirmaciones[:-1] + ["Fecha de carga"]

    confirmaciones_raw = sheet.worksheet("confirmaciones").get_all_records()
    pendientes_raw = sheet.worksheet("pendientes").get_all_records()

    confirmaciones = pd.DataFrame(confirmaciones_raw)
    if confirmaciones.empty:
        confirmaciones = pd.DataFrame(columns=columnas_confirmaciones)

    pendientes = pd.DataFrame(pendientes_raw)
    if pendientes.empty:
        pendientes = pd.DataFrame(columns=columnas_pendientes)

    return confirmaciones, pendientes

# --- GUARDAR CONFIRMACIONES EN GOOGLE SHEETS ---
def guardar_confirmaciones(df):
    sheet = CLIENT.open_by_key(SHEET_ID).worksheet("confirmaciones")
    valores = [df.columns.tolist()] + df.astype(str).values.tolist()
    sheet.clear()
    sheet.update("A1", valores)

# --- GUARDAR PENDIENTES NUEVOS ---
def guardar_pendientes_nuevos(df_nuevos):
    sheet = CLIENT.open_by_key(SHEET_ID).worksheet("pendientes")
    existentes = pd.DataFrame(sheet.get_all_records())
    df_final = pd.concat([existentes, df_nuevos], ignore_index=True)
    valores = [df_final.columns.tolist()] + df_final.astype(str).values.tolist()
    sheet.clear()
    sheet.update("A1", valores)

# --- ELIMINAR PENDIENTES POR FECHA DE CARGA ---
def eliminar_pendientes_por_fecha(fecha_str):
    sheet = CLIENT.open_by_key(SHEET_ID).worksheet("pendientes")
    pendientes = pd.DataFrame(sheet.get_all_records())
    pendientes = pendientes[pendientes["Fecha de carga"] != fecha_str]
    valores = [pendientes.columns.tolist()] + pendientes.astype(str).values.tolist()
    sheet.clear()
    sheet.update("A1", valores)

# --- EXPORTAR A EXCEL LAS ÓRDENES CONFIRMADAS (ESTADO ≠ COMPLETADO) ---
def exportar_confirmadas(df):
    df_export = df[(df["Estado de la orden"].str.upper() != "COMPLETADO") & (df["Confirmación"] != "")]
    return df_export

# --- CARGAR NUEVOS PENDIENTES DESDE ARCHIVO ---
def procesar_archivos_pendientes(files):
    dataframes = []
    for file in files:
        df = pd.read_excel(file)
        columnas = [
            "Técnico", "Estado de la orden", "Número de petición",
            "Dias", "Dirección", "Localidad", "Teléfono móvil"
        ]
        df = df[columnas]
        df["Localidad"] = df["Localidad"].str.upper()
        df = df[df["Localidad"].isin(LOCALIDADES_VALIDAS)]
        df["Fecha de carga"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        df["Teléfono móvil"] = df["Teléfono móvil"].apply(lambda x: str(int(x)) if pd.notnull(x) else "")
        dataframes.append(df)
    return pd.concat(dataframes, ignore_index=True)

# --- INTERFAZ PRINCIPAL ---
st.title("📋 CONFIRMACIONES A&G")

st.sidebar.markdown("### 📤 Cargar pendientes")
archivos = st.sidebar.file_uploader("Selecciona uno o varios archivos Excel", type=["xlsx"], accept_multiple_files=True)

if archivos:
    nuevos_pendientes = procesar_archivos_pendientes(archivos)

    confirmaciones_exist, pendientes_exist = cargar_datos()

    if "Número de petición" in confirmaciones_exist.columns:
        ids_confirmados = set(confirmaciones_exist["Número de petición"])
    else:
        ids_confirmados = set()

    nuevos_sin_repetir = nuevos_pendientes[~nuevos_pendientes["Número de petición"].isin(ids_confirmados)]

    guardar_pendientes_nuevos(nuevos_sin_repetir)
    st.sidebar.success("✅ Pendientes cargados exitosamente.")

# --- MOSTRAR DATOS EN PESTAÑAS ---
confirmaciones, pendientes = cargar_datos()

if "Número de petición" in confirmaciones.columns:
    ids_confirmados = set(confirmaciones["Número de petición"])
else:
    ids_confirmados = set()

if "Número de petición" in pendientes.columns:
    ids_pendientes = set(pendientes["Número de petición"])
else:
    ids_pendientes = set()

df_base = pendientes.copy()

df_base["Confirmación"] = df_base["Número de petición"].map(
    dict(zip(confirmaciones["Número de petición"], confirmaciones["Confirmación"]))
) if "Número de petición" in confirmaciones.columns else ""

df_base["Técnico"] = df_base["Número de petición"].map(
    dict(zip(confirmaciones["Número de petición"], confirmaciones["Técnico"]))
).combine_first(df_base["Técnico"]) if "Número de petición" in confirmaciones.columns else df_base["Técnico"]

# Aplicar filtros de localidad
st.subheader("📍 Filtro por localidad")
localidades_seleccionadas = st.multiselect("Selecciona localidades", LOCALIDADES_VALIDAS, default=LOCALIDADES_VALIDAS)
df_base = df_base[df_base["Localidad"].isin(localidades_seleccionadas)]

tab1, tab2, tab3 = st.tabs(["✅ ÓRDENES COMPLETADAS", "🕓 PENDIENTE POR CONFIRMACIÓN", "📝 ÓRDENES CONFIRMADAS"])

with tab1:
    st.subheader("✅ ÓRDENES COMPLETADAS")
    df_completadas = df_base[df_base["Estado de la orden"].str.upper() == "COMPLETADO"]
    st.dataframe(df_completadas, use_container_width=True)

with tab2:
    st.subheader("🕓 PENDIENTE POR CONFIRMACIÓN")
    df_pendientes = df_base[(df_base["Estado de la orden"].str.upper() != "COMPLETADO") & (df_base["Confirmación"].isna())]
    for i, row in df_pendientes.iterrows():
        st.markdown(f"**Número de orden:** {row['Número de petición']}  |  **Técnico:** {row['Técnico']}")
        st.text_input("Ingresa confirmación", key=f"confirm_{i}")

    if st.button("💾 GUARDAR CONFIRMACIONES"):
        nuevas_confirmaciones = []
        for i, row in df_pendientes.iterrows():
            valor = st.session_state.get(f"confirm_{i}", "").strip()
            if valor:
                nuevas_confirmaciones.append({
                    "Técnico": row["Técnico"],
                    "Estado de la orden": row["Estado de la orden"],
                    "Número de petición": row["Número de petición"],
                    "Días": row["Dias"],
                    "Dirección": row["Dirección"],
                    "Localidad": row["Localidad"],
                    "Teléfono móvil": row["Teléfono móvil"],
                    "Confirmación": valor
                })
        if nuevas_confirmaciones:
            df_nuevas = pd.DataFrame(nuevas_confirmaciones)
            df_actualizado = pd.concat([confirmaciones, df_nuevas], ignore_index=True)
            guardar_confirmaciones(df_actualizado)
            st.success("✔️ Confirmaciones guardadas correctamente.")
            st.experimental_rerun()

with tab3:
    st.subheader("📝 ÓRDENES CONFIRMADAS")
    df_confirmadas = df_base[(df_base["Estado de la orden"].str.upper() != "COMPLETADO") & (df_base["Confirmación"].notna())]
    for i, row in df_confirmadas.iterrows():
        new_value = st.text_input(f"Editar confirmación ({row['Número de petición']})", value=row["Confirmación"], key=f"edit_{i}")
        df_confirmadas.at[i, "Confirmación"] = new_value.strip()

    if st.button("💾 GUARDAR CAMBIOS DE CONFIRMADAS"):
        df_final = pd.concat([
            confirmaciones[~confirmaciones["Número de petición"].isin(df_confirmadas["Número de petición"])],
            df_confirmadas
        ])
        guardar_confirmaciones(df_final)
        st.success("✔️ Confirmaciones actualizadas.")
        st.experimental_rerun()

# --- EXPORTAR CONFIRMADAS ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 📥 Exportar confirmadas")
if st.sidebar.button("Descargar Excel"):
    df_export = exportar_confirmadas(confirmaciones)
    st.sidebar.download_button(
        label="📄 Descargar órdenes confirmadas",
        data=df_export.to_excel(index=False, engine='openpyxl'),
        file_name="confirmadas_ag.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- ELIMINAR PENDIENTES POR FECHA ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 🗑️ Eliminar pendientes por fecha")
if not pendientes.empty:
    fechas_unicas = pendientes["Fecha de carga"].unique().tolist()
    fecha_sel = st.sidebar.selectbox("Selecciona fecha de carga", fechas_unicas)
    if st.sidebar.button("Eliminar pendientes de esta fecha"):
        eliminar_pendientes_por_fecha(fecha_sel)
        st.sidebar.success("✅ Pendientes eliminados.")
        st.experimental_rerun()
