import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.distance import geodesic
import urllib.parse
import os
from PIL import Image

# --- 1. CONFIGURACIÓN ÚNICA (DEBE SER LA PRIMERA) ---
st.set_page_config(page_title="TelRutas Barinas", layout="wide", initial_sidebar_state="collapsed")

# --- 2. FUNCIONES DE CACHÉ (PARA EVITAR ERROR 500) ---
@st.cache_data
def cargar_imagen(ruta, ancho=None):
    try:
        img = Image.open(ruta)
        return img
    except:
        return None

@st.cache_resource
def obtener_apk():
    try:
        with open("telrutas.apk", "rb") as file:
            return file.read()
    except:
        return None

# --- ESTILOS CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 0px !important; margin-top: -30px !important; }
    header {visibility: hidden;}
    div.stButton > button[key="btn_principal"] {
        background-color: #00569E !important; color: white !important;
        width: 60px !important; height: 60px !important; border-radius: 50% !important; font-size: 25px !important;
    }
    div.stButton > button:first-child {
        background-color: #002D62 !important; color: white !important;
        border-radius: 12px !important; font-weight: bold !important; width: 100% !important;
    }
    div.stButton > button:first-child:hover { background-color: #FF7F00 !important; }
    .cotizacion-box { background-color: #f0f4f8; padding: 20px; border-radius: 15px; border-left: 8px solid #FF7F00; border: 1px solid #002D62; text-align: center; }
    .tasa-display { background-color: #e8f4fd; border: 1px solid #002D62; border-radius: 10px; padding: 10px; text-align: center; font-weight: bold; color: #002D62; }
</style>
""", unsafe_allow_html=True)

# --- LÓGICA DEL MENÚ ---
if "menu_abierto" not in st.session_state: st.session_state.menu_abierto = False

if st.button("☰", key="btn_principal"):
    st.session_state.menu_abierto = not st.session_state.menu_abierto

if st.session_state.menu_abierto:
    with st.container(border=True):
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if st.button("🔄 Actualizar", use_container_width=True):
                st.cache_data.clear()
                st.cache_resource.clear()
                st.rerun()
        with col_m2:
            if st.button("📥 Descargar", use_container_width=True):
                st.session_state.ver_qr = not st.session_state.get("ver_qr", False)
        with col_m3:
            if st.button("❓ Ayuda", use_container_width=True):
                st.session_state.ver_ayuda = not st.session_state.get("ver_ayuda", False)

        if st.session_state.get("ver_qr", False):
            apk_bytes = obtener_apk()
            if apk_bytes:
                st.download_button(label="🚀 CLIC AQUÍ PARA INSTALAR APK", data=apk_bytes, file_name="telrutas.apk", mime="application/vnd.android.package-archive")
            qr_img = cargar_imagen("qr_descarga.png")
            if qr_img: st.image(qr_img, use_container_width=True)

# --- CARGA DE CONFIGURACIÓN ---
def cargar_config():
    try: return dict(st.secrets["tarifas"])
    except: return {"tarifa_base": 3.00, "precio_km": 0.80, "recargo_ligero": 1.00, "recargo_mediano": 3.00, "recargo_pesado": 6.00, "whatsapp": "584264741485"}

config = cargar_config()

# --- ENCABEZADO ---
logo = cargar_imagen("logo.png")
if logo: st.image(logo, width=350)

st.markdown(f"""
    <div style="border-left: 6px solid #FF7F00; padding-left: 20px;">
        <h1 style="color: #002D62;">TelRutas Barinas</h1>
        <p>🚗 <b>Traslados:</b> Mínima ${config["tarifa_base"]:.2f} | 📦 <b>Encomiendas:</b> Tarifas fijas.</p>
    </div>
""", unsafe_allow_html=True)

# --- TASA BCV ---
tasa_fija = float(st.secrets.get("TASA_DIA", 450.45))
def f_ve(m): return "{:,.2f}".format(m).replace(",", "X").replace(".", ",").replace("X", ".")
st.markdown(f'<div class="tasa-display">🏛️ Tasa Oficial BCV: {f_ve(tasa_fija)} Bs.</div>', unsafe_allow_html=True)

# --- REGISTRO ---
st.subheader("👤 Registro Cliente")
c_nom, c_tel = st.columns(2)
nombre_cliente = c_nom.text_input("Nombre y Apellido *")
telefono_input = c_tel.text_input("Teléfono de contacto *")
telefono_cliente = "".join(filter(str.isdigit, telefono_input))

# --- SERVICIOS ---
if 'tipo' not in st.session_state: st.session_state.tipo = "Traslado"
c1, c2 = st.columns(2)
if c1.button("🚗 TRASLADO PERSONA"): st.session_state.tipo = "Traslado"
if c2.button("📦 ENVIAR ENCOMIENDA"): st.session_state.tipo = "Encomienda"

recargo_fijo = 0.0
detalle_paquete = ""
detalle_personas = "0"

if st.session_state.tipo == "Encomienda":
    desc_prod = st.text_input("¿Qué producto envía?")
    opcion = st.selectbox("Seleccione el Peso:", [f"Ligero (+${config['recargo_ligero']:.2f})", f"Mediano (+${config['recargo_mediano']:.2f})", f"Pesado (+${config['recargo_pesado']:.2f})"])
    recargo_fijo = config["recargo_ligero"] if "Ligero" in opcion else (config["recargo_mediano"] if "Mediano" in opcion else config["recargo_pesado"])
    detalle_paquete = f"{desc_prod} ({opcion})"
else:
    num_p = st.number_input("¿Cuántas personas?", min_value=1, value=1)
    recargo_fijo = (num_p - 2) * 1.50 if num_p > 2 else 0.0
    detalle_personas = str(num_p)

# --- MAPA ---
st.subheader("📍 Definir Ruta")
if 'p_a' not in st.session_state: st.session_state.p_a = None
if 'p_b' not in st.session_state: st.session_state.p_b = None

m = folium.Map(location=[8.6226, -70.2039], zoom_start=14)
if st.session_state.p_a: folium.Marker(st.session_state.p_a, icon=folium.Icon(color='blue')).add_to(m)
if st.session_state.p_b: folium.Marker(st.session_state.p_b, icon=folium.Icon(color='red')).add_to(m)

map_data = st_folium(m, width=700, height=350)
if map_data and map_data["last_clicked"]:
    click = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    if st.session_state.p_a is None: st.session_state.p_a = click; st.rerun()
    elif st.session_state.p_b is None: st.session_state.p_b = click; st.rerun()

# --- CÁLCULO Y WHATSAPP ---
if st.session_state.p_a and st.session_state.p_b:
    dist = geodesic(st.session_state.p_a, st.session_state.p_b).km
    total_usd = (config["tarifa_base"] + (max(0, dist-1) * config["precio_km"])) + recargo_fijo
    total_bs = total_usd * tasa_fija

    st.markdown(f'<div class="cotizacion-box"><h1>Bs. {f_ve(total_bs)}</h1><h2>$ {f_ve(total_usd)} USD</h2><p>{dist:.2f} km</p></div>', unsafe_allow_html=True)

    if nombre_cliente and telefono_cliente:
        msg = f"¡Hola TelRutas! 👋\n👤 *CLIENTE:* {nombre_cliente}\n🛠️ *SERVICIO:* {st.session_state.tipo.upper()}\n"
        msg += f"📦 *DETALLE:* {detalle_paquete if st.session_state.tipo == 'Encomienda' else detalle_personas}\n"
        msg += f"💰 *TOTAL:* ${f_ve(total_usd)} / Bs. {f_ve(total_bs)}"
        url_wa = f"https://wa.me/{config['whatsapp']}?text={urllib.parse.quote(msg)}"
        st.markdown(f'<a href="{url_wa}" target="_blank" style="text-decoration:none;"><div style="background-color:#FF7F00; color:white; padding:18px; text-align:center; border-radius:12px; font-weight:bold; font-size:22px;">🚀 SOLICITAR AHORA</div></a>', unsafe_allow_html=True)
    
    if st.button("🔄 Reiniciar Ruta"):
        st.session_state.p_a = st.session_state.p_b = None
        st.rerun()