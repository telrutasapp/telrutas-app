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

# --- CONFIGURACIÓN DE PERSISTENCIA (SECRETS + LOCAL) ---
CONFIG_FILE = "config_tarifas.json"

def cargar_config():
    # 1. Intentar cargar desde Streamlit Secrets (Nube)
    try:
        if "tarifas" in st.secrets:
            return dict(st.secrets["tarifas"])
    except:
        # Si da error en tu PC, simplemente ignoramos st.secrets y seguimos
        pass
    
    # 2. Intentar cargar desde archivo local JSON
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: pass
        
    # 3. Valores por defecto (Lo que usará tu PC al fallar lo anterior)
    return {
        "tarifa_base": 3.00, 
        "precio_km": 0.80, 
        "recargo_ligero": 1.00,
        "recargo_mediano": 3.00,
        "recargo_pesado": 6.00,
        "whatsapp": "584264741485",
        "clave_admin": "appadmintelr#2026"
    }

def guardar_config(nueva_config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(nueva_config, f)

config = cargar_config()

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="TelRutas - Cotizador", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #ffffff; }
    h1, h2, h3, h4 { color: #002D62 !important; }
    .header-info { border-left: 5px solid #FF7F00; padding-left: 20px; margin-left: 10px; }
    .header-title { font-size: 32px; font-weight: bold; margin: 0; color: #002D62; }
    .header-text { font-size: 18px; color: #444; margin: 5px 0; }
    .stButton>button { background-color: #002D62; color: white; border-radius: 10px; border: 2px solid #002D62; font-weight: bold; }
    .stButton>button:hover { background-color: #FF7F00; border-color: #FF7F00; color: white; }
    .cotizacion-box { background-color: #f0f4f8; padding: 20px; border-radius: 15px; border-left: 8px solid #FF7F00; border-right: 1px solid #002D62; border-top: 1px solid #002D62; border-bottom: 1px solid #002D62; text-align: center; }
    .tasa-display { background-color: #e8f4fd; border: 1px solid #002D62; border-radius: 10px; padding: 10px; text-align: center; margin-top: 10px; font-weight: bold; color: #002D62; }
    .btn-disabled { background-color: #cccccc !important; color: #666; padding: 18px; text-align: center; border-radius: 12px; font-weight: bold; font-size: 22px; margin-top: 20px; border: 1px solid #999; }
    </style>
    """, unsafe_allow_html=True)

# --- PANEL DE ADMINISTRACIÓN ---
if 'admin_logged' not in st.session_state: st.session_state.admin_logged = False

with st.sidebar:
    st.header("⚙️ TelRutas")
    if not st.session_state.admin_logged:
        pwd_input = st.text_input("Clave de Acceso", type="password")
        if pwd_input == config["clave_admin"]:
            st.session_state.admin_logged = True
            st.rerun()
        else: st.info("🔒 Panel Protegido")
    else:
        st.success("✅ Modo Administrador")
        st.subheader("🚗 Tarifas Traslado")
        n_base = st.number_input("Tarifa Mínima ($)", value=float(config["tarifa_base"]), step=0.50)
        n_km = st.number_input("Precio por Km ($)", value=float(config["precio_km"]), step=0.10)
        
        st.subheader("📦 Tarifas Encomienda")
        n_lig = st.number_input("Recargo Ligero ($)", value=float(config["recargo_ligero"]), step=0.50)
        n_med = st.number_input("Recargo Mediano ($)", value=float(config["recargo_mediano"]), step=0.50)
        n_pes = st.number_input("Recargo Pesado ($)", value=float(config["recargo_pesado"]), step=0.50)
        
        st.subheader("📱 Contacto")
        n_wa = st.text_input("WhatsApp (sin +)", value=config["whatsapp"])

        col_save, col_exit = st.columns(2)
        if col_save.button("💾 GUARDAR"):
            config.update({"tarifa_base": n_base, "precio_km": n_km, "recargo_ligero": n_lig, "recargo_mediano": n_med, "recargo_pesado": n_pes, "whatsapp": n_wa})
            guardar_config(config)
            st.toast("Cambios guardados localmente")
            st.rerun()
        
        if col_exit.button("🚪 SALIR"):
            st.session_state.admin_logged = False
            st.rerun()

# --- LÓGICA DE TASA ---
@st.cache_data(ttl=300)
def obtener_tasa():
    try:
        url = "https://www.monitordedivisavenezuela.com/"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        elementos = soup.find_all(['h3', 'p', 'span'])
        for el in elementos:
            texto = el.get_text().strip()
            if "Bs." in texto and "," in texto:
                limpio = texto.replace('Bs.', '').replace(' ', '').replace('.', '').replace(',', '.')
                return float(limpio)
        return 417.36
    except: return 417.36

tasa_fija = obtener_tasa()
def f_ve(m): return "{:,.2f}".format(m).replace(",", "X").replace(".", ",").replace("X", ".")

# --- 2. ENCABEZADO ---
col_logo, col_desc = st.columns([1.2, 2])
with col_logo:
    if os.path.exists("logo.jpg"): st.image("logo.jpg", use_container_width=True)
with col_desc:
    st.markdown(f'<div class="header-info"><p class="header-title">TelRutas Barinas</p><p class="header-text"><b>🚗 Traslados:</b> Mínima ${config["tarifa_base"]:.2f}<br><b>📦 Encomiendas:</b> Tarifas fijas.</p></div>', unsafe_allow_html=True)
    st.markdown(f'<div class="tasa-display">📊 Cotización del día: {f_ve(tasa_fija)} Bs.</div>', unsafe_allow_html=True)

st.divider()

# --- 3. REGISTRO ---
st.subheader("👤 Registro Cliente:")
col_nom, col_tel = st.columns(2)
nombre_cliente = col_nom.text_input("Nombre y Apellido *", placeholder="Nombre y Apellido")
telefono_cliente = col_tel.text_input("Teléfono de contacto *", placeholder="Teléfono de contacto")

if not nombre_cliente or not telefono_cliente:
    st.error("⚠️ Para poder solicitar el servicio, debe completar su Nombre y Teléfono.")

st.divider()

# --- 4. SERVICIO ---
st.subheader("Seleccione el servicio:")
c1, c2 = st.columns(2)
if 'tipo' not in st.session_state: st.session_state.tipo = "Traslado"
if c1.button("🚗 TRASLADO PERSONA", use_container_width=True): st.session_state.tipo = "Traslado"
if c2.button("📦 ENVIAR ENCOMIENDA", use_container_width=True): st.session_state.tipo = "Encomienda"

recargo_fijo = 0.0
detalle_paquete = ""
if st.session_state.tipo == "Encomienda":
    st.markdown("<p style='color:#FF7F00; font-weight:bold;'>📦 DETALLES DE ENCOMIENDA</p>", unsafe_allow_html=True)
    desc_prod = st.text_input("¿Qué producto envía?", placeholder="Ej: Repuestos, Comida...")
    opcion = st.selectbox("Peso:", [f"Ligero (Hasta 2kg) +${config['recargo_ligero']}", f"Mediano (2kg a 10kg) +${config['recargo_mediano']}", f"Pesado (10kg a 25kg) +${config['recargo_pesado']}"])
    if "Ligero" in opcion: recargo_fijo = config["recargo_ligero"]
    elif "Mediano" in opcion: recargo_fijo = config["recargo_mediano"]
    elif "Pesado" in opcion: recargo_fijo = config["recargo_pesado"]
    detalle_paquete = opcion

# --- 5. RUTA ---
st.subheader("📍 Definir Ruta")
if 'modo_manual' not in st.session_state: st.session_state.modo_manual = False
if 'punto_a' not in st.session_state: st.session_state.punto_a = None
if 'punto_b' not in st.session_state: st.session_state.punto_b = None

cg, cm = st.columns(2)
if cg.button("📡 USAR MI GPS ACTUAL"): st.session_state.modo_manual = False; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()
if cm.button("📍 MARCAR EN EL MAPA"): st.session_state.modo_manual = True; st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()

# --- 6. MAPA ---
centro = [8.6226, -70.2039]
loc = None
if not st.session_state.modo_manual:
    loc = get_geolocation()
    if loc: st.session_state.punto_a = [loc['coords']['latitude'], loc['coords']['longitude']]; centro = st.session_state.punto_a

m = folium.Map(location=centro, zoom_start=14)
if st.session_state.punto_a: folium.Marker(st.session_state.punto_a, tooltip="Origen", icon=folium.Icon(color='blue', icon='home')).add_to(m)
if st.session_state.punto_b: folium.Marker(st.session_state.punto_b, tooltip="Destino", icon=folium.Icon(color='red', icon='flag')).add_to(m)

map_data = st_folium(m, width=700, height=350)
if map_data and map_data["last_clicked"]:
    click = [map_data["last_clicked"]["lat"], map_data["last_clicked"]["lng"]]
    if st.session_state.modo_manual and st.session_state.punto_a is None: st.session_state.punto_a = click; st.rerun()
    elif st.session_state.punto_b is None: st.session_state.punto_b = click; st.rerun()

# --- 7. CÁLCULO ---
if st.session_state.punto_a and st.session_state.punto_b:
    dist = geodesic(st.session_state.punto_a, st.session_state.punto_b).km
    costo_base = config["tarifa_base"]
    costo_km = config["precio_km"]
    
    costo_ruta = costo_base if dist <= 1.0 else costo_base + ((dist - 1.0) * costo_km)
    total_usd = costo_ruta + recargo_fijo
    total_bs = total_usd * tasa_fija
    
    st.markdown(f'<div class="cotizacion-box"><h4>COTIZACIÓN ESTIMADA</h4><h1>Bs. {f_ve(total_bs)}</h1><h2>$ {f_ve(total_usd)} USD</h2><p>Distancia: {dist:.2f} km</p></div>', unsafe_allow_html=True)
    
    if st.button("🔄 Reiniciar Ruta"): st.session_state.punto_a = st.session_state.punto_b = None; st.rerun()

    if nombre_cliente and telefono_cliente:
        l_orig = f"https://www.google.com/maps?q={st.session_state.punto_a[0]},{st.session_state.punto_a[1]}"
        l_dest = f"https://www.google.com/maps?q={st.session_state.punto_b[0]},{st.session_state.punto_b[1]}"
        srv = f"📦 *ENCOMIENDA* ({detalle_paquete})" if st.session_state.tipo == "Encomienda" else "🚗 *TRASLADO*"
        msg = f"¡Hola TelRutas! 👋\n👤 *CLIENTE:* {nombre_cliente}\n📞 *TEL:* {telefono_cliente}\n{srv}\n📍 *Origen:* {l_orig}\n🏁 *Destino:* {l_dest}\n💰 *TOTAL:* ${f_ve(total_usd)} / Bs. {f_ve(total_bs)}"
        url_wa = f"https://wa.me/{config['whatsapp']}?text={urllib.parse.quote(msg)}"
        st.markdown(f'<a href="{url_wa}" target="_blank" style="text-decoration:none;"><div style="background-color:#FF7F00; color:white; padding:18px; text-align:center; border-radius:12px; font-weight:bold; font-size:22px; margin-top:20px;">✅ SOLICITAR AHORA</div></a>', unsafe_allow_html=True)
    else: st.markdown('<div class="btn-disabled">❌ COMPLETE SU NOMBRE Y TELÉFONO ARRIBA</div>', unsafe_allow_html=True)
elif not st.session_state.modo_manual and not loc:
    st.info("📡 Obteniendo señal GPS...")