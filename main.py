import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.distance import geodesic
import urllib.parse
import os

# --- 1. CONFIGURACIÓN ÚNICA Y FUERZA BRUTA PARA MODO CLARO ---
st.set_page_config(page_title="TelRuta Barinas", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Forzar fondo blanco en toda la app */
    .stApp { background-color: white !important; color: #002D62 !important; }
    
    /* Eliminar franjas negras y menús de Streamlit */
    header {visibility: hidden !important; height: 0px !important;}
    footer {visibility: hidden !important;}
    .stAppDeployButton {display:none !important;}
    [data-testid="stStatusWidget"] {display:none !important;}

    /* Compactar espacios para que todo suba */
    .block-container { padding-top: 0px !important; padding-bottom: 0px !important; margin-top: -50px !important; }
    
    /* Botón de Menú Flotante */
    div.stButton > button[key="btn_principal"] {
        background-color: #00569E !important; color: white !important;
        width: 50px !important; height: 50px !important; border-radius: 50% !important;
        position: fixed; top: 10px; left: 10px; z-index: 9999;
    }

    /* Estilo de los inputs para que resalten en fondo blanco */
    .stTextInput>div>div>input { background-color: #f0f2f6 !important; color: black !important; }
    
    /* Caja de cotización compacta */
    .cotizacion-box { 
        background-color: #f8f9fa; padding: 15px; border-radius: 12px; 
        border: 2px solid #002D62; text-align: center; margin-top: 0px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. LÓGICA DE ACTUALIZACIÓN REAL ---
def reiniciar_todo():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.cache_data.clear()
    st.cache_resource.clear()
    st.rerun()

# --- 3. MENÚ SUPERIOR ---
if "menu_abierto" not in st.session_state: st.session_state.menu_abierto = False

if st.button("☰", key="btn_principal"):
    st.session_state.menu_abierto = not st.session_state.menu_abierto

if st.session_state.menu_abierto:
    with st.container(border=True):
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            if st.button("🔄 ACTUALIZAR APP", use_container_width=True):
                reiniciar_todo()
        with col_m2:
            if st.button("📥 APK", use_container_width=True):
                st.session_state.ver_qr = not st.session_state.get("ver_qr", False)

# --- 4. ENCABEZADO (LOGO PEQUEÑO PARA SUBIR TODO) ---
st.image("logo.png", width=220)

tasa_fija = float(st.secrets.get("TASA_DIA", 450.45))
def f_ve(m): return "{:,.2f}".format(m).replace(",", "X").replace(".", ",").replace("X", ".")

st.markdown(f'<div class="tasa-display" style="text-align:center; font-weight:bold; background:#e8f4fd; padding:5px; border-radius:10px;">🏛️ Tasa BCV: {f_ve(tasa_fija)} Bs.</div>', unsafe_allow_html=True)

# --- 5. REGISTRO (COMPACTO) ---
st.subheader("👤 Registro Cliente")
c_nom, c_tel = st.columns(2)
nombre_cliente = c_nom.text_input("Nombre", placeholder="Su nombre")
telefono_input = c_tel.text_input("Teléfono", placeholder="0414...")
telefono_cliente = "".join(filter(str.isdigit, telefono_input))

# --- 6. SERVICIO ---
st.write("¿Qué necesitas?")
c1, c2 = st.columns(2)
if 'tipo' not in st.session_state: st.session_state.tipo = "Traslado"
if c1.button("🚗 TRASLADO"): st.session_state.tipo = "Traslado"
if c2.button("📦 ENCOMIENDA"): st.session_state.tipo = "Encomienda"

recargo_fijo = 0.0
detalle_serv = ""

if st.session_state.tipo == "Encomienda":
    desc_prod = st.text_input("Producto:")
    opcion = st.selectbox("Peso:", ["Ligero (+1$)", "Mediano (+3$)", "Pesado (+6$)"])
    recargo_fijo = 1.0 if "Ligero" in opcion else (3.0 if "Mediano" in opcion else 6.0)
    detalle_serv = f"{desc_prod} ({opcion})"
else:
    n_p = st.number_input("Personas:", min_value=1, value=1)
    recargo_fijo = (n_p - 2) * 1.50 if n_p > 2 else 0.0
    detalle_serv = f"{n_p} Pasajeros"

# --- 7. RUTA Y MAPA (CON BOTÓN DE REINICIO ARRIBA) ---
st.subheader("📍 Definir Ruta")
if 'modo_manual' not in st.session_state: st.session_state.modo_manual = False
if 'punto_a' not in st.session_state: st.session_state.punto_a = None
if 'punto_b' not in st.session_state: st.session_state.punto_b = None

# Fila de botones de control
col_gps, col_mapa, col_reset = st.columns(3)

if col_gps.button("📡 GPS"): 
    st.session_state.modo_manual = False
    st.session_state.punto_a = st.session_state.punto_b = None
    st.rerun()

if col_mapa.button("📍 MAPA"): 
    st.session_state.modo_manual = True
    st.session_state.punto_a = st.session_state.punto_b = None
    st.rerun()

# AQUÍ SUBIMOS EL BOTÓN PARA QUE NO CHOQUE ABAJO
if col_reset.button("🔄 LIMPIAR"):
    st.session_state.punto_a = st.session_state.punto_b = None
    st.rerun()

# Configuración del mapa
centro = [8.6226, -70.2039]
if not st.session_state.modo_manual:
    loc = get_geolocation()
    if loc: 
        st.session_state.punto_a = [loc['coords']['latitude'], loc['coords']['longitude']]
        centro = st.session_state.punto_a

m = folium.Map(location=centro, zoom_start=14)
if st.session_state.punto_a: 
    folium.Marker(st.session_state.punto_a, icon=folium.Icon(color='blue', icon='info-sign')).add_to(m)
if st.session_state.punto_b: 
    folium.Marker(st.session_state.punto_b, icon=folium.Icon(color='red', icon='flag')).add_to(m)

# Mapa más compacto para que el botón de WhatsApp también suba
map_res = st_folium(m, width=700, height=280)

if map_res and map_res["last_clicked"]:
    click = [map_res["last_clicked"]["lat"], map_res["last_clicked"]["lng"]]
    if st.session_state.modo_manual and st.session_state.punto_a is None:
        st.session_state.punto_a = click; st.rerun()
    elif st.session_state.punto_b is None:
        st.session_state.punto_b = click; st.rerun()

# --- 8. CÁLCULO FINAL Y WHATSAPP ---
if st.session_state.punto_a and st.session_state.punto_b:
    dist = geodesic(st.session_state.punto_a, st.session_state.punto_b).km
    total_usd = (3.00 + (max(0, dist-1) * 0.80)) + recargo_fijo
    total_bs = total_usd * tasa_fija

    st.markdown(f'''
        <div class="cotizacion-box">
            <h2 style="margin:0;">Bs. {f_ve(total_bs)}</h2>
            <p style="margin:0;"><b>$ {f_ve(total_usd)} USD</b> ({dist:.2f} km)</p>
        </div>
    ''', unsafe_allow_html=True)

    if nombre_cliente and telefono_cliente:
        msg = (f"¡Hola TelRuta! 👋\n👤 *CLIENTE:* {nombre_cliente}\n📞 *TEL:* {telefono_cliente}\n"
               f"🛠️ *SERV:* {st.session_state.tipo.upper()}\n📦 *DETALLE:* {detalle_serv}\n"
               f"📍 *Origen:* http://maps.google.com/?q={st.session_state.punto_a[0]},{st.session_state.punto_a[1]}\n"
               f"🏁 *Destino:* http://maps.google.com/?q={st.session_state.punto_b[0]},{st.session_state.punto_b[1]}\n"
               f"💰 *TOTAL:* ${f_ve(total_usd)} / Bs. {f_ve(total_bs)}")
        
        url_wa = f"https://wa.me/584264741485?text={urllib.parse.quote(msg)}"
        st.markdown(f'''
            <a href="{url_wa}" target="_blank" style="text-decoration:none;">
                <div style="background-color:#FF7F00; color:white; padding:15px; text-align:center; border-radius:12px; font-weight:bold; font-size:20px; margin-top:10px;">
                    🚀 SOLICITAR AHORA
                </div>
            </a>
        ''', unsafe_allow_html=True)
    
    if st.button("🔄 Reiniciar Ruta", use_container_width=True):
        st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()