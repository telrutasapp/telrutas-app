import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.distance import geodesic
import urllib.parse
import os

# --- 1. CONFIGURACIÓN ÚNICA DE PÁGINA (CRÍTICO: Solo una vez al inicio) ---
st.set_page_config(page_title="TelRuta Barinas", layout="wide", initial_sidebar_state="collapsed")
st.markdown('<meta name="referrer" content="no-referrer">', unsafe_allow_html=True)

# --- 2. OPTIMIZACIÓN DE ESPACIOS Y ESTILOS CSS ---
st.markdown("""
<style>
    /* Eliminar espacios superiores y barras de Streamlit */
    .block-container { padding-top: 0px !important; padding-bottom: 0px !important; margin-top: -30px !important; }
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    
    /* Botón de Menú Circular */
    div.stButton > button[key="btn_principal"] {
        background-color: #00569E !important; color: white !important;
        width: 60px !important; height: 60px !important; border-radius: 50% !important; font-size: 25px !important;
    }

    /* Botones Azules de la App */
    div.stButton > button:first-child {
        background-color: #002D62 !important; color: white !important;
        border-radius: 12px !important; font-weight: bold !important; width: 100% !important;
        height: 3em !important; transition: all 0.3s ease !important;
    }
    div.stButton > button:first-child:hover { background-color: #FF7F00 !important; border-color: #FF7F00 !important; }

    /* Cajas de Cotización y Tasa */
    .cotizacion-box { background-color: #f0f4f8; padding: 20px; border-radius: 15px; border-left: 8px solid #FF7F00; text-align: center; border: 1px solid #002D62; }
    .tasa-display { background-color: #e8f4fd; border: 1px solid #002D62; border-radius: 10px; padding: 10px; text-align: center; font-weight: bold; color: #002D62; }
</style>
""", unsafe_allow_html=True)

# --- 3. LÓGICA DEL MENÚ SUPERIOR ---
if "menu_abierto" not in st.session_state: st.session_state.menu_abierto = False

if st.button("☰", key="btn_principal"):
    st.session_state.menu_abierto = not st.session_state.menu_abierto

if st.session_state.menu_abierto:
    with st.container(border=True):
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if st.button("🔄 Actualizar", use_container_width=True):
                st.cache_data.clear(); st.cache_resource.clear(); st.rerun()
        with col_m2:
            if st.button("📥 Descargar", use_container_width=True):
                st.session_state.ver_qr = not st.session_state.get("ver_qr", False)
        with col_m3:
            if st.button("❓ Ayuda", use_container_width=True):
                st.session_state.ver_ayuda = not st.session_state.get("ver_ayuda", False)

        if st.session_state.get("ver_qr", False):
            st.markdown("---")
            try:
                with open("telrutas.apk", "rb") as f:
                    st.download_button("🚀 INSTALAR APK", data=f, file_name="telrutas.apk", mime="application/vnd.android.package-archive")
            except: st.error("Archivo APK no encontrado.")
            st.image("qr_descarga.png", width=200)

# --- 4. CONFIGURACIÓN DE TARIFAS Y TASA ---
tasa_fija = float(st.secrets.get("TASA_DIA", 450.45))
def f_ve(m): return "{:,.2f}".format(m).replace(",", "X").replace(".", ",").replace("X", ".")

config = {
    "tarifa_base": 3.00, "precio_km": 0.80, "recargo_ligero": 1.00,
    "recargo_mediano": 3.00, "recargo_pesado": 6.00, "whatsapp": "584264741485"
}

# --- 5. ENCABEZADO Y REGISTRO ---
st.image("logo.png", width=350)
st.markdown(f'<div class="tasa-display">🏛️ Tasa Oficial BCV: {f_ve(tasa_fija)} Bs.</div>', unsafe_allow_html=True)

st.subheader("👤 Registro Cliente")
c_nom, c_tel = st.columns(2)
nombre_cliente = c_nom.text_input("Nombre y Apellido *", placeholder="Su nombre")
telefono_input = c_tel.text_input("Teléfono *", placeholder="Ej: 04141234567")
telefono_cliente = "".join(filter(str.isdigit, telefono_input))

if not nombre_cliente or not telefono_cliente:
    st.markdown("<p style='color:#FF0000; font-weight:bold;'>⚠️ Complete su Nombre y Teléfono para solicitar el servicio.</p>", unsafe_allow_html=True)

# --- 6. SELECCIÓN DE SERVICIO ---
st.subheader("Seleccione el servicio:")
c1, c2 = st.columns(2)
if 'tipo' not in st.session_state: st.session_state.tipo = "Traslado"
if c1.button("🚗 TRASLADO PERSONA"): st.session_state.tipo = "Traslado"
if c2.button("📦 ENVIAR ENCOMIENDA"): st.session_state.tipo = "Encomienda"

recargo_fijo = 0.0
detalle_serv = ""

if st.session_state.tipo == "Encomienda":
    desc_prod = st.text_input("¿Qué producto envía?")
    opcion = st.selectbox("Peso:", ["Ligero (+1$)", "Mediano (+3$)", "Pesado (+6$)"])
    recargo_fijo = config["recargo_ligero"] if "Ligero" in opcion else (config["recargo_mediano"] if "Mediano" in opcion else config["recargo_pesado"])
    detalle_serv = f"{desc_prod} ({opcion})"
else:
    n_p = st.number_input("¿Cuántas personas?", min_value=1, value=1)
    recargo_fijo = (n_p - 2) * 1.50 if n_p > 2 else 0.0
    detalle_serv = f"{n_p} Pasajeros"

# --- 7. RUTA Y MAPA (GPS + MANUAL) ---
st.subheader("📍 Definir Ruta")
if 'modo_manual' not in st.session_state: st.session_state.modo_manual = False
if 'punto_a' not in st.session_state: st.session_state.punto_a = None
if 'punto_b' not in st.session_state: st.session_state.punto_b = None

cg, cm = st.columns(2)
if cg.button("📡 USAR MI GPS"): 
    st.session_state.modo_manual = False; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()
if cm.button("📍 MARCAR EN MAPA"): 
    st.session_state.modo_manual = True; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()

centro = [8.6226, -70.2039]
loc = None
if not st.session_state.modo_manual:
    loc = get_geolocation()
    if loc: 
        st.session_state.punto_a = [loc['coords']['latitude'], loc['coords']['longitude']]
        centro = st.session_state.punto_a

m = folium.Map(location=centro, zoom_start=14)
if st.session_state.punto_a: folium.Marker(st.session_state.punto_a, tooltip="Origen", icon=folium.Icon(color='blue')).add_to(m)
if st.session_state.punto_b: folium.Marker(st.session_state.punto_b, tooltip="Destino", icon=folium.Icon(color='red')).add_to(m)

map_res = st_folium(m, width=700, height=350)

if map_res and map_res["last_clicked"]:
    click = [map_res["last_clicked"]["lat"], map_res["last_clicked"]["lng"]]
    if st.session_state.modo_manual and st.session_state.punto_a is None:
        st.session_state.punto_a = click; st.rerun()
    elif st.session_state.punto_b is None:
        st.session_state.punto_b = click; st.rerun()

# --- 8. CÁLCULO Y WHATSAPP ---
if st.session_state.punto_a and st.session_state.punto_b:
    dist = geodesic(st.session_state.punto_a, st.session_state.punto_b).km
    total_usd = (config["tarifa_base"] + (max(0, dist-1) * config["precio_km"])) + recargo_fijo
    total_bs = total_usd * tasa_fija

    st.markdown(f'''
        <div class="cotizacion-box">
            <h1>Bs. {f_ve(total_bs)}</h1>
            <h2>$ {f_ve(total_usd)} USD</h2>
            <p>{dist:.2f} km | {st.session_state.tipo}</p>
        </div>
    ''', unsafe_allow_html=True)

    if nombre_cliente and telefono_cliente:
        msg = (f"¡Hola TelRuta! 👋\n👤 *CLIENTE:* {nombre_cliente}\n📞 *TEL:* {telefono_cliente}\n"
               f"🛠️ *SERV:* {st.session_state.tipo.upper()}\n📦 *DETALLE:* {detalle_serv}\n"
               f"📍 *Origen:* http://maps.google.com/maps?q={st.session_state.punto_a[0]},{st.session_state.punto_a[1]}\n"
               f"🏁 *Destino:* http://maps.google.com/maps?q={st.session_state.punto_b[0]},{st.session_state.punto_b[1]}\n"
               f"💰 *TOTAL:* ${f_ve(total_usd)} / Bs. {f_ve(total_bs)}")
        
        url_wa = f"https://wa.me/{config['whatsapp']}?text={urllib.parse.quote(msg)}"
        st.markdown(f'''
            <a href="{url_wa}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#FF7F00; color:white; padding:18px; text-align:center; border-radius:12px; font-weight:bold; font-size:22px; margin-top:20px;">
                    🚀 SOLICITAR {st.session_state.tipo.upper()} AHORA
                </div>
            </a>
        ''', unsafe_allow_html=True)
    
    if st.button("🔄 Reiniciar Ruta"):
        st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()