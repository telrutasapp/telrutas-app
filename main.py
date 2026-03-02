import streamlit as st
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation
from geopy.distance import geodesic
import urllib.parse
import os
import requests
import json
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN PARA FORZAR EL ICONO NUEVO ---
st.markdown("""
    <head>
        <link rel="icon" href="./logo.png" type="image/png">
        <link rel="apple-touch-icon" href="./logo.png">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta name="theme-color" content="#002D62">
    </head>
""", unsafe_allow_html=True)

# --- CARGA DE TARIFAS (DESDE STREAMLIT SECRETS) ---
def cargar_config():
    try:
        if "tarifas" in st.secrets:
            return dict(st.secrets["tarifas"])
    except: pass
    
    # Valores por defecto si no hay Secrets configurados
    return {
        "tarifa_base": 3.00, 
        "precio_km": 0.80, 
        "recargo_ligero": 1.00,
        "recargo_mediano": 3.00,
        "recargo_pesado": 6.00,
        "whatsapp": "584264741485"
    }

config = cargar_config()

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILO CSS ---
st.set_page_config(page_title="TelRutas - Cotizador", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
  /* --- ESTO ELIMINA EL BOTÓN NEGRO Y BARRAS DE UNA VEZ --- */
    #MainMenu {visibility: hidden !important;}
    header {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    /* Selector específico para el botón de Manage App */
    .stAppDeployButton {display:none !important;}
    [data-testid="stStatusWidget"] {display:none !important;}
    [data-testid="stSidebar"] {display: none !important;}
    
    /* Quita el espacio en blanco que deja la barra superior */
    .stAppHeader {display: none !important;}

    /* Estilos Generales que ya tenías... */
    .stApp { background-color: #ffffff; }
    h1, h2, h3, h4 { color: #002D62 !important; }
    .stButton>button { background-color: #002D62; color: white; border-radius: 10px; border: 2px solid #002D62; font-weight: bold; }
    .stButton>button:hover { background-color: #FF7F00; border-color: #FF7F00; color: white; }
    .cotizacion-box { background-color: #f0f4f8; padding: 20px; border-radius: 15px; border-left: 8px solid #FF7F00; border-right: 1px solid #002D62; border-top: 1px solid #002D62; border-bottom: 1px solid #002D62; text-align: center; }
    .tasa-display { background-color: #e8f4fd; border: 1px solid #002D62; border-radius: 10px; padding: 10px; text-align: center; margin-top: 10px; font-weight: bold; color: #002D62; }
    .btn-disabled { background-color: #cccccc !important; color: #666; padding: 18px; text-align: center; border-radius: 12px; font-weight: bold; font-size: 22px; margin-top: 20px; border: 1px solid #999; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ENCABEZADO: LOGO Y TEXTO ---
st.image("logo.png", width=350)
st.markdown("<br>", unsafe_allow_html=True)

st.markdown(f"""
    <div style="border-left: 6px solid #FF7F00; padding-left: 20px; margin-left: 5px;">
        <h1 style="margin: 0; color: #002D62; font-size: 36px;">TelRutas Barinas</h1>
        <p style="font-size: 20px; color: #444; margin: 5px 0;">🚗 <b>Traslados:</b> Mínima ${config["tarifa_base"]:.2f}</p>
        <p style="font-size: 20px; color: #444; margin: 5px 0;">📦 <b>Encomiendas:</b> Tarifas fijas.</p>
    </div>
""", unsafe_allow_html=True)

# --- 3. LÓGICA DE ACTUALIZACIÓN AUTOMÁTICA BCV ---
# ttl=300 hace que la app revise la página cada 5 minutos por cambios
@st.cache_data(ttl=300)
def obtener_tasa():
    url = "https://exchangemonitor.net/dolar-venezuela/bcv"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            import re
            # Captura el primer número con coma que aparezca después de la palabra USD
            # Esto garantiza que tome el Dólar y no el Euro de tu imagen
            match = re.search(r'USD.*?(\d+,\d+)', response.text, re.DOTALL)
            if match:
                # Extrae el número, quita la coma y lo hace funcional
                return float(match.group(1).replace(',', '.'))
    except: pass
    return 419.98 # Valor de respaldo si la web cae

tasa_fija = obtener_tasa()

# Formato de salida: Siempre con coma decimal (Ej: 419,98)
def f_ve(m): 
    return "{:,.2f}".format(m).replace(",", "X").replace(".", ",").replace("X", ".")

st.markdown(f'<div class="tasa-display">🏛️ Tasa Oficial BCV: {f_ve(tasa_fija)} Bs.</div>', unsafe_allow_html=True)
st.markdown("<br>", unsafe_allow_html=True)

# --- 4. REGISTRO CLIENTE (CON ETIQUETAS DENTRO) ---
st.subheader("👤 Registro Cliente:")
col_nom, col_tel = st.columns(2)
# Agregamos 'placeholder' para que el texto aparezca dentro de la casilla
nombre_cliente = col_nom.text_input("Nombre y Apellido *", placeholder="Escriba su Nombre y Apellido")
telefono_cliente = col_tel.text_input("Teléfono de contacto *", placeholder="Ej: 04141234567")

if not nombre_cliente or not telefono_cliente:
    st.error("⚠️ Complete su Nombre y Teléfono para solicitar el servicio.")

# --- 5. SELECCIÓN DE SERVICIO ---
st.subheader("Seleccione el servicio:")
c1, c2 = st.columns(2)
if 'tipo' not in st.session_state: st.session_state.tipo = "Traslado"
if c1.button("🚗 TRASLADO PERSONA", use_container_width=True): st.session_state.tipo = "Traslado"
if c2.button("📦 ENVIAR ENCOMIENDA", use_container_width=True): st.session_state.tipo = "Encomienda"

recargo_fijo = 0.0
detalle_paquete = ""
if st.session_state.tipo == "Encomienda":
    st.markdown("<p style='color:#FF7F00; font-weight:bold;'>📦 DETALLES DE ENCOMIENDA</p>", unsafe_allow_html=True)
    desc_prod = st.text_input("¿Qué producto envía?")
    opcion = st.selectbox("Peso:", [f"Ligero +${config['recargo_ligero']}", f"Mediano +${config['recargo_mediano']}", f"Pesado +${config['recargo_pesado']}"])
    recargo_fijo = config["recargo_ligero"] if "Ligero" in opcion else config["recargo_mediano"] if "Mediano" in opcion else config["recargo_pesado"]
    detalle_paquete = opcion

# --- 6. RUTA Y MAPA ---
st.subheader("📍 Definir Ruta")
if 'modo_manual' not in st.session_state: st.session_state.modo_manual = False
if 'punto_a' not in st.session_state: st.session_state.punto_a = None
if 'punto_b' not in st.session_state: st.session_state.punto_b = None

cg, cm = st.columns(2)
if cg.button("📡 USAR MI GPS"): st.session_state.modo_manual = False; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()
if cm.button("📍 MARCAR EN MAPA"): st.session_state.modo_manual = True; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()

centro = [8.6226, -70.2039]
loc = None
if not st.session_state.modo_manual:
    loc = get_geolocation()
    if loc: st.session_state.punto_a = [loc['coords']['latitude'], loc['coords']['longitude']]; centro = st.session_state.punto_a

m = folium.Map(location=centro, zoom_start=14)
if st.session_state.punto_a: folium.Marker(st.session_state.punto_a, icon=folium.Icon(color='blue')).add_to(m)
if st.session_state.punto_b: folium.Marker(st.session_state.punto_b, icon=folium.Icon(color='red')).add_to(m)

map_data = st_folium(m, width=700, height=350)
if map_data and map_data["last_clicked"]:
    click = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    if st.session_state.modo_manual and st.session_state.punto_a is None: st.session_state.punto_a = click; st.rerun()
    elif st.session_state.punto_b is None: st.session_state.punto_b = click; st.rerun()

# --- 7. CÁLCULO FINAL Y WHATSAPP ---
if st.session_state.punto_a and st.session_state.punto_b:
    dist = geodesic(st.session_state.punto_a, st.session_state.punto_b).km
    costo_ruta = config["tarifa_base"] if dist <= 1.0 else config["tarifa_base"] + ((dist - 1.0) * config["precio_km"])
    total_usd = costo_ruta + recargo_fijo
    total_bs = total_usd * tasa_fija
    
    st.markdown(f'<div class="cotizacion-box"><h4>COTIZACIÓN ESTIMADA</h4><h1>Bs. {f_ve(total_bs)}</h1><h2>$ {f_ve(total_usd)} USD</h2><p>Distancia: {dist:.2f} km</p></div>', unsafe_allow_html=True)
    
    if st.button("🔄 Reiniciar Ruta"): st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()

    if nombre_cliente and telefono_cliente:
        msg = f"¡Hola TelRutas! 👋\n👤 *CLIENTE:* {nombre_cliente}\n📞 *TEL:* {telefono_cliente}\n📍 *Origen:* https://www.google.com/maps?q={st.session_state.punto_a[0]},{st.session_state.punto_a[1]}\n🏁 *Destino:* https://www.google.com/maps?q={st.session_state.punto_b[0]},{st.session_state.punto_b[1]}\n💰 *TOTAL:* ${f_ve(total_usd)} / Bs. {f_ve(total_bs)}"
        url_wa = f"https://wa.me/{config['whatsapp']}?text={urllib.parse.quote(msg)}"
        st.markdown(f'<a href="{url_wa}" target="_blank" style="text-decoration:none;"><div style="background-color:#FF7F00; color:white; padding:18px; text-align:center; border-radius:12px; font-weight:bold; font-size:22px; margin-top:20px;">✅ SOLICITAR AHORA</div></a>', unsafe_allow_html=True)
elif not st.session_state.modo_manual and not loc:
    st.info("📡 Obteniendo señal GPS...")

# --- SECCIÓN: GUÍA DE INSTALACIÓN REAL ---
st.divider()

st.markdown("""
    <div style="background-color: #002D62; padding: 20px; border-radius: 15px; text-align: center; color: white;">
        <h3 style="margin:0;">📲 ¡Instala TelRutas en tu Telefono!</h3>
        <p style="font-size: 0.9em; opacity: 0.9;">Accede más rápido sin usar el navegador.</p>
        <div style="background-color: white; color: #333; padding: 10px; border-radius: 10px; text-align: left; margin-top: 10px;">
            <b>1.</b> Toca los <b>3 puntos (⋮)</b> o <b>Compartir (↑)</b>.<br>
            <b>2.</b> Elige <b>"Añadir a pantalla de inicio"</b> o <b>"Instalar"</b>.
        </div>
    </div>
""", unsafe_allow_html=True)