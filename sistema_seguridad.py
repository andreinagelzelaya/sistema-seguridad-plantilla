"""
============================================================
SISTEMA DE SEGURIDAD INTELIGENTE CON IA
============================================================
Programa principal. Corre todo junto:

  - CAMARA + IA (Teachable Machine), 3 clases:
        Vacio   -> nada
        Dueno   -> mensaje de bienvenida
        Externo -> foto + Telegram con botones (conocido / desconocido)
                   si respondes "desconocido" -> graba video de evidencia
    Con capa de verificacion: confianza minima + confirmacion por
    varios frames seguidos + cooldown entre alertas.

  - MONITOR DE RED WIFI (solo en tus redes): avisa cuando un
    dispositivo se conecta o desconecta.

  - CONTROL POR TELEGRAM: comandos y botones.

  - RESUMEN diario y semanal automatico.

Toda la configuracion (credenciales, clases, red) esta en config.py.
La camara corre en segundo plano (sin ventana). Ctrl+C para detener.
============================================================
"""

import os
import sys

os.environ["TF_USE_LEGACY_KERAS"] = "1"

# ---------- Cargar configuracion ----------
try:
    import config as cfg
except ImportError:
    print("ERROR: no existe config.py")
    print("Copia config.example.py, renombra la copia a config.py y llena tus datos.")
    sys.exit(1)

if "PON_AQUI" in cfg.TOKEN or "PON_AQUI" in str(cfg.CHAT_ID):
    print("ERROR: falta poner tu TOKEN y CHAT_ID de Telegram en config.py")
    sys.exit(1)

for archivo in (cfg.ARCHIVO_MODELO, cfg.ARCHIVO_LABELS):
    if not os.path.exists(archivo):
        print(f"ERROR: no se encontro '{archivo}'.")
        print("Entrena tu modelo en Teachable Machine, exportalo (Tensorflow -> Keras)")
        print("y copia keras_model.h5 y labels.txt a esta carpeta.")
        sys.exit(1)

import subprocess
import socket
import time
import threading
import json
import platform
from datetime import datetime, date, timedelta
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import requests
from tf_keras.models import load_model
from tf_keras.layers import DepthwiseConv2D

ES_WINDOWS = platform.system() == "Windows"
CREATE_NO_WINDOW = 0x08000000 if ES_WINDOWS else 0
BACKEND_CAM = cv2.CAP_DSHOW if ES_WINDOWS else cv2.CAP_ANY

API = f"https://api.telegram.org/bot{cfg.TOKEN}"
CHAT_ID = str(cfg.CHAT_ID)
CONOCIDOS = {k.lower(): v for k, v in cfg.CONOCIDOS.items()}

CARPETA = "evidencia"
os.makedirs(CARPETA, exist_ok=True)
ARCHIVO_HISTORIAL = "historial.csv"
ARCHIVO_CONOCIDOS = "conocidos.json"
ARCHIVO_DIARIO = "diario.json"

lock = threading.Lock()
lock_frame = threading.Lock()
armado = True
historial = []
rastreo = {}
diario = {}
offset_tg = 0
silencio_hasta = 0.0
ultimo_frame = None


# ==================== Modelo ====================
class DepthwiseConv2DCompat(DepthwiseConv2D):
    """Parche: los modelos de Teachable Machine traen un argumento 'groups'
    que Keras rechaza. Lo ignoramos."""
    def __init__(self, *args, **kwargs):
        kwargs.pop("groups", None)
        super().__init__(*args, **kwargs)


print("Cargando modelo de Teachable Machine...")
modelo = load_model(cfg.ARCHIVO_MODELO, compile=False,
                    custom_objects={"DepthwiseConv2D": DepthwiseConv2DCompat})
with open(cfg.ARCHIVO_LABELS, encoding="utf-8") as f:
    clases = [l.strip() for l in f if l.strip()]
clases = [c.split(" ", 1)[1] if " " in c else c for c in clases]
print("Clases del modelo:", clases)

TIPO_POR_CLASE = {
    cfg.CLASE_VACIO.lower(): "vacio",
    cfg.CLASE_DUENO.lower(): "dueno",
    cfg.CLASE_EXTERNO.lower(): "externo",
}
for c in clases:
    if c.lower() not in TIPO_POR_CLASE:
        print(f"AVISO: la clase '{c}' del modelo no coincide con config.py "
              f"(CLASE_VACIO / CLASE_DUENO / CLASE_EXTERNO). Revisa los nombres.")


# ==================== Telegram ====================
def telegram(texto):
    try:
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": texto}, timeout=10)
    except Exception as e:
        print("Error Telegram:", e)


def teclado():
    return {"keyboard": [
        ["📸 Foto", "🎥 Video"],
        ["📊 Estado", "📖 Diario", "📅 Resumen"],
        ["🔔 Armar", "🔇 Desarmar", "🔕 Silencio 1h"],
        ["❓ Ayuda"],
    ], "resize_keyboard": True}


def telegram_menu(texto):
    try:
        requests.post(f"{API}/sendMessage",
                      json={"chat_id": CHAT_ID, "text": texto, "reply_markup": teclado()},
                      timeout=10)
    except Exception as e:
        print("Error Telegram:", e)


BOTONES = {
    "📸 Foto": "/foto", "🎥 Video": "/video", "📊 Estado": "/estado",
    "📖 Diario": "/diario", "📅 Resumen": "/resumen", "🔔 Armar": "/armar",
    "🔇 Desarmar": "/desarmar", "🔕 Silencio 1h": "/silencio 1h", "❓ Ayuda": "/ayuda",
}


def enviar_foto(ruta, caption=""):
    try:
        with open(ruta, "rb") as f:
            requests.post(f"{API}/sendPhoto",
                          data={"chat_id": CHAT_ID, "caption": caption},
                          files={"photo": f}, timeout=20)
    except Exception as e:
        print("Error foto:", e)


def enviar_foto_botones(ruta, caption):
    botones = {"inline_keyboard": [[
        {"text": "✅ Es conocido", "callback_data": "ok"},
        {"text": "🚨 Desconocido", "callback_data": "no"},
    ]]}
    try:
        with open(ruta, "rb") as f:
            requests.post(f"{API}/sendPhoto",
                          data={"chat_id": CHAT_ID, "caption": caption,
                                "reply_markup": json.dumps(botones)},
                          files={"photo": f}, timeout=20)
    except Exception as e:
        print("Error foto:", e)


def enviar_video(ruta, caption=""):
    try:
        with open(ruta, "rb") as f:
            requests.post(f"{API}/sendVideo",
                          data={"chat_id": CHAT_ID, "caption": caption},
                          files={"video": f}, timeout=60)
    except Exception as e:
        print("Error video:", e)


def enviar_documento(ruta):
    try:
        with open(ruta, "rb") as f:
            requests.post(f"{API}/sendDocument",
                          data={"chat_id": CHAT_ID}, files={"document": f}, timeout=30)
    except Exception:
        telegram("No pude exportar el historial (¿aun no hay eventos?).")


# ==================== Utilidades ====================
def log(tipo, detalle):
    ahora = datetime.now()
    with lock:
        historial.append({"t": ahora, "tipo": tipo, "detalle": detalle})
    try:
        with open(ARCHIVO_HISTORIAL, "a", encoding="utf-8") as f:
            f.write(f"{ahora.strftime('%Y-%m-%d %H:%M:%S')},{tipo},{detalle}\n")
    except Exception:
        pass


def resumen_texto():
    with lock:
        hoy = [h for h in historial if h["t"].date() == date.today()]
    conex = sum(1 for h in hoy if h["tipo"] == "conexion")
    desc = sum(1 for h in hoy if h["tipo"] == "desconexion")
    cam = sum(1 for h in hoy if h["tipo"] == "camara")
    return (f"📊 Resumen del dia\nConexiones: {conex}\nDesconexiones: {desc}\n"
            f"Eventos de camara: {cam}\nEventos totales: {len(hoy)}")


def resumen_semanal_texto():
    limite = datetime.now() - timedelta(days=7)
    eventos = []
    try:
        with open(ARCHIVO_HISTORIAL, encoding="utf-8") as f:
            for linea in f:
                p = linea.strip().split(",", 2)
                if len(p) >= 2:
                    try:
                        t = datetime.strptime(p[0], "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        continue
                    if t >= limite:
                        eventos.append(p[1])
    except Exception:
        pass
    return (f"📅 Resumen semanal (7 dias)\n"
            f"Conexiones: {eventos.count('conexion')}\n"
            f"Desconexiones: {eventos.count('desconexion')}\n"
            f"Eventos de camara: {eventos.count('camara')}\n"
            f"Eventos totales: {len(eventos)}")


def cargar_json(archivo, destino):
    try:
        with open(archivo, encoding="utf-8") as f:
            destino.update(json.load(f))
    except Exception:
        pass


def guardar_json(archivo, datos):
    try:
        with open(archivo, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False)
    except Exception:
        pass


def duracion(delta):
    seg = int(delta.total_seconds())
    h, m = seg // 3600, (seg % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def parse_tiempo(s):
    s = s.lower().strip()
    try:
        if s.endswith("h"):
            return int(float(s[:-1]) * 60)
        if s.endswith("m"):
            return int(s[:-1])
        return int(s)
    except Exception:
        return 0


def en_silencio():
    return time.time() < silencio_hasta


def avisos_activos():
    return armado and not en_silencio()


# ==================== Red ====================
def ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()


def ping(ip):
    cmd = (["ping", "-n", "1", "-w", "1000", ip] if ES_WINDOWS
           else ["ping", "-c", "1", "-W", "1", ip])
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   creationflags=CREATE_NO_WINDOW)


def barrer_red(subred):
    ips = [f"{subred}.{i}" for i in range(1, 255)]
    with ThreadPoolExecutor(max_workers=64) as ex:
        list(ex.map(ping, ips))


def leer_arp(subred):
    """Devuelve {mac: ip} solo de equipos de tu red (ignora VirtualBox, IPv6, etc.)."""
    disp = {}
    prefijo = subred + "."
    if ES_WINDOWS:
        out = subprocess.run(["arp", "-a"], capture_output=True, text=True,
                             creationflags=CREATE_NO_WINDOW).stdout
        for linea in out.splitlines():
            p = linea.split()
            if len(p) >= 2 and p[1].count("-") == 5 and p[0].startswith(prefijo):
                mac = p[1].replace("-", ":").lower()
                try:
                    if int(mac.split(":")[0], 16) & 0x01:
                        continue
                except Exception:
                    continue
                disp[mac] = p[0]
    else:
        out = subprocess.run(["ip", "neigh", "show"], capture_output=True, text=True).stdout
        for linea in out.splitlines():
            p = linea.split()
            if ("lladdr" in p and p[-1] in ("REACHABLE", "DELAY", "PROBE")
                    and p[0].startswith(prefijo)):
                disp[p[p.index("lladdr") + 1].lower()] = p[0]
    return disp


def fabricante(mac):
    try:
        if int(mac.split(":")[0], 16) & 0x02:
            return "MAC aleatoria"
        r = requests.get(f"https://api.macvendors.com/{mac}", timeout=5)
        return r.text.strip() if (r.status_code == 200 and r.text.strip()) else "desconocido"
    except Exception:
        return "desconocido"


def hostname(ip):
    try:
        socket.setdefaulttimeout(2)
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return ""
    finally:
        socket.setdefaulttimeout(None)


# ==================== Camara ====================
def clasificar(frame):
    img = cv2.resize(frame, (224, 224))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)
    arr = np.expand_dims((img / 127.5) - 1.0, axis=0)
    pred = modelo.predict(arr, verbose=0)[0]
    idx = int(np.argmax(pred))
    return clases[idx], float(pred[idx])


def guardar_foto(frame, nota=""):
    f = frame.copy()
    cv2.putText(f, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    if nota:
        cv2.putText(f, nota, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    ruta = os.path.join(CARPETA, datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg")
    cv2.imwrite(ruta, f)
    return ruta


def frame_actual():
    with lock_frame:
        return None if ultimo_frame is None else ultimo_frame.copy()


def grabar_video(segundos):
    frame = frame_actual()
    if frame is None:
        return None
    h, w = frame.shape[:2]
    ruta = os.path.join(CARPETA, datetime.now().strftime("%Y%m%d_%H%M%S") + ".mp4")
    out = cv2.VideoWriter(ruta, cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
    fin = time.time() + segundos
    while time.time() < fin:
        f = frame_actual()
        if f is not None:
            out.write(f)
        time.sleep(0.1)
    out.release()
    return ruta


# ==================== Comandos de Telegram ====================
def manejar_comando(texto):
    global armado, silencio_hasta
    partes = texto.strip().split()
    if not partes:
        return
    cmd = partes[0].lower().split("@")[0]
    args = partes[1:]

    if cmd in ("/ayuda", "/start", "/help", "/menu"):
        telegram_menu("Comandos:\n/foto  /video  /estado  /diario\n"
                      "/armar  /desarmar  /silencio 2h\n"
                      "/historial  /resumen  /semana  /exportar\n"
                      "/agregar MAC nombre  /quitar MAC  /conocidos")
    elif cmd == "/armar":
        armado = True
        telegram("🔔 Sistema ARMADO (red + camara).")
    elif cmd == "/desarmar":
        armado = False
        telegram("🔕 Sistema DESARMADO.")
    elif cmd == "/foto":
        frame = frame_actual()
        if frame is not None:
            enviar_foto(guardar_foto(frame, "Foto por comando"), "Foto en vivo")
        else:
            telegram("No hay imagen de la camara.")
    elif cmd == "/video":
        telegram("🎥 Grabando 5 segundos...")
        ruta = grabar_video(5)
        if ruta:
            enviar_video(ruta, "Video en vivo")
        else:
            telegram("No hay imagen de la camara.")
    elif cmd == "/estado":
        with lock:
            actuales = dict(rastreo)
        if not actuales:
            telegram("No hay datos de red (¿estas en una de tus redes?).")
        else:
            lineas = ["📡 Conectados ahora:"]
            for mac, info in actuales.items():
                lineas.append(f"• {CONOCIDOS.get(mac, info.get('fab', 'desconocido'))} ({mac})")
            telegram("\n".join(lineas))
    elif cmd == "/diario":
        if not diario:
            telegram("Aun no hay registro de entradas/salidas.")
        else:
            lineas = ["📖 Diario:"]
            for mac, d in diario.items():
                lleg = d.get("llegada", "")[11:16] or "-"
                sal = d.get("salida", "")[11:16] or "-"
                lineas.append(f"• {CONOCIDOS.get(mac, mac)}: llegada {lleg} | salida {sal}")
            telegram("\n".join(lineas))
    elif cmd == "/historial":
        with lock:
            ultimos = historial[-10:]
        if not ultimos:
            telegram("Sin eventos aun.")
        else:
            telegram("🗒️ Ultimos eventos:\n" + "\n".join(
                f"• {h['t'].strftime('%H:%M')} {h['tipo']}: {h['detalle']}" for h in ultimos))
    elif cmd == "/resumen":
        telegram(resumen_texto())
    elif cmd == "/semana":
        telegram(resumen_semanal_texto())
    elif cmd == "/exportar":
        enviar_documento(ARCHIVO_HISTORIAL)
    elif cmd == "/silencio":
        minutos = parse_tiempo(args[0]) if args else 0
        if minutos > 0:
            silencio_hasta = time.time() + minutos * 60
            telegram(f"🔕 Avisos silenciados por {minutos} min.")
        else:
            telegram("Uso: /silencio 2h   o   /silencio 30m")
    elif cmd == "/agregar":
        if len(args) >= 2:
            mac, nombre = args[0].lower(), " ".join(args[1:])
            CONOCIDOS[mac] = nombre
            guardar_json(ARCHIVO_CONOCIDOS, CONOCIDOS)
            telegram(f"✅ Agregado: {nombre} ({mac})")
        else:
            telegram("Uso: /agregar MAC nombre")
    elif cmd == "/quitar":
        if args and CONOCIDOS.pop(args[0].lower(), None) is not None:
            guardar_json(ARCHIVO_CONOCIDOS, CONOCIDOS)
            telegram(f"🗑️ Quitado: {args[0].lower()}")
        else:
            telegram("Esa MAC no estaba en la lista (uso: /quitar MAC).")
    elif cmd == "/conocidos":
        if not CONOCIDOS:
            telegram("No hay conocidos registrados.")
        else:
            telegram("👥 Conocidos:\n" + "\n".join(f"• {n} ({m})" for m, n in CONOCIDOS.items()))
    else:
        telegram("No conozco ese comando. Usa /ayuda")


# ==================== Hilos ====================
def hilo_telegram():
    """Escucha comandos, botones del menu y respuestas a las alertas."""
    global offset_tg
    try:
        r = requests.get(f"{API}/getUpdates", timeout=10).json()
        if r.get("result"):
            offset_tg = r["result"][-1]["update_id"] + 1
    except Exception:
        pass
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"offset": offset_tg, "timeout": 20}, timeout=30).json()
        except Exception:
            time.sleep(2)
            continue
        for upd in r.get("result", []):
            offset_tg = upd["update_id"] + 1

            # Seguridad: solo obedece a TU chat (cualquiera puede escribirle al bot)
            origen = (upd.get("callback_query", {}).get("message", {}).get("chat", {}).get("id")
                      or upd.get("message", {}).get("chat", {}).get("id"))
            if str(origen) != CHAT_ID:
                print(f"Mensaje ignorado de un chat ajeno: {origen}")
                continue

            if "callback_query" in upd:
                cq = upd["callback_query"]
                try:
                    requests.post(f"{API}/answerCallbackQuery",
                                  json={"callback_query_id": cq["id"]}, timeout=10)
                except Exception:
                    pass
                if cq.get("data") == "ok":
                    telegram("✅ Marcado como conocido. Sin alarma.")
                    log("respuesta", "conocido")
                elif cq.get("data") == "no":
                    telegram("🚨 DESCONOCIDO confirmado. Grabando evidencia...")
                    log("respuesta", "DESCONOCIDO")
                    ruta = grabar_video(cfg.SEGUNDOS_VIDEO_EVIDENCIA)
                    if ruta:
                        enviar_video(ruta, "📹 Evidencia del desconocido")
                    else:
                        telegram("No pude grabar el video (¿camara activa?).")
                continue
            texto = upd.get("message", {}).get("text", "")
            if texto in BOTONES:
                manejar_comando(BOTONES[texto])
            elif texto.startswith("/"):
                manejar_comando(texto)


def hilo_red():
    """Vigila conexiones y desconexiones en tus redes."""
    if not cfg.VIGILAR_RED:
        print("Monitor de red desactivado (VIGILAR_RED = False).")
        return
    try:
        subred = ".".join(ip_local().split(".")[:3])
    except Exception:
        print("Sin conexion a la red. Monitor de red DESACTIVADO.")
        return
    if subred not in cfg.REDES_CASA:
        print(f"Red actual ({subred}.x) no esta en REDES_CASA. Monitor de red DESACTIVADO.")
        return
    print(f"Monitor de red ACTIVO en {subred}.0/24")

    local = {}
    primera = True
    while True:
        try:
            barrer_red(subred)
            disp = leer_arp(subred)
        except Exception:
            time.sleep(cfg.INTERVALO_S)
            continue
        actuales = set(disp)

        if primera:  # primer escaneo: base sin avisar
            for mac in actuales:
                local[mac] = {"ip": disp[mac], "fab": fabricante(mac), "misses": 0}
            primera = False
            with lock:
                rastreo.clear(); rastreo.update(local)
            time.sleep(cfg.INTERVALO_S)
            continue

        # Conexiones
        for mac in actuales:
            if mac not in local:
                fab = fabricante(mac)
                local[mac] = {"ip": disp[mac], "fab": fab, "misses": 0}
                hora = datetime.now().strftime("%H:%M:%S")
                nombre = CONOCIDOS.get(mac)
                if nombre:
                    ahora = datetime.now()
                    d = diario.get(mac, {})
                    txt = f"👋 ¡Bienvenido {nombre}! Llegaste a casa."
                    if d.get("salida"):
                        try:
                            txt += f"\nEstuviste fuera: {duracion(ahora - datetime.fromisoformat(d['salida']))}"
                        except Exception:
                            pass
                    d["llegada"] = ahora.isoformat()
                    diario[mac] = d
                    guardar_json(ARCHIVO_DIARIO, diario)
                    txt += f"\nHora: {hora}"
                    log("conexion", nombre)
                else:
                    host = hostname(disp[mac])
                    extra = f"\nNombre: {host}" if host else ""
                    txt = (f"🟢 Dispositivo CONECTADO\nFabricante: {fab}{extra}\n"
                           f"MAC: {mac}\nIP: {disp[mac]}\nHora: {hora}")
                    log("conexion", f"{fab} {mac}")
                if avisos_activos():
                    telegram(txt)
            else:
                local[mac]["misses"] = 0
                local[mac]["ip"] = disp[mac]

        # Desconexiones
        for mac in list(local):
            if mac not in actuales:
                local[mac]["misses"] += 1
                if local[mac]["misses"] >= cfg.UMBRAL_AUSENCIA:
                    info = local.pop(mac)
                    hora = datetime.now().strftime("%H:%M:%S")
                    nombre = CONOCIDOS.get(mac)
                    if nombre:
                        ahora = datetime.now()
                        d = diario.get(mac, {})
                        txt = f"👋 Hasta luego {nombre}, que te vaya bien."
                        if d.get("llegada"):
                            try:
                                txt += f"\nEstuvo en casa: {duracion(ahora - datetime.fromisoformat(d['llegada']))}"
                            except Exception:
                                pass
                        d["salida"] = ahora.isoformat()
                        diario[mac] = d
                        guardar_json(ARCHIVO_DIARIO, diario)
                        txt += f"\nHora: {hora}"
                        log("desconexion", nombre)
                    else:
                        txt = (f"🔴 Dispositivo DESCONECTADO\nFabricante: {info['fab']}\n"
                               f"MAC: {mac}\nHora: {hora}")
                        log("desconexion", f"{info['fab']} {mac}")
                    if avisos_activos():
                        telegram(txt)

        with lock:
            rastreo.clear(); rastreo.update(local)
        time.sleep(cfg.INTERVALO_S)


def hilo_resumen():
    ultimo_dia = ultimo_sem = None
    while True:
        ahora = datetime.now()
        if ahora.hour == cfg.HORA_RESUMEN:
            if ultimo_dia != date.today():
                telegram(resumen_texto())
                ultimo_dia = date.today()
            if ahora.weekday() == 6 and ultimo_sem != date.today():  # domingo
                telegram(resumen_semanal_texto())
                ultimo_sem = date.today()
        time.sleep(30)


# ==================== Camara (hilo principal) ====================
def actuar_camara(tipo, frame):
    if not avisos_activos():
        return
    if tipo == "dueno":
        telegram(f"👋 ¡Bienvenido {cfg.NOMBRE_DUENO}! (camara)")
        log("camara", cfg.NOMBRE_DUENO)
        print(f"CAMARA: {cfg.NOMBRE_DUENO}")
    elif tipo == "externo":
        ruta = guardar_foto(frame, "Externo detectado")
        enviar_foto_botones(ruta, "⚠️ Persona detectada en la entrada. ¿La reconoces?")
        log("camara", "Externo")
        print("CAMARA: Externo -> foto + botones")


def bucle_camara():
    """Corre en segundo plano, sin ventana."""
    global ultimo_frame
    cap = cv2.VideoCapture(cfg.CAMARA, BACKEND_CAM)
    if not cap.isOpened():
        print("ERROR: no se pudo abrir la camara. Revisa CAMARA en config.py.")
        return
    for _ in range(5):  # calentar la camara
        cap.read()
        time.sleep(0.1)

    contador = 0
    clase_prev = None
    ultima_confirmada = None
    ultima_alerta = 0.0

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
            continue
        with lock_frame:
            ultimo_frame = frame.copy()

        clase, conf = clasificar(frame)
        tipo = TIPO_POR_CLASE.get(clase.lower(), "desconocida")

        # Capa de verificacion: misma clase en varios frames seguidos
        contador = contador + 1 if clase == clase_prev else 1
        clase_prev = clase
        confirmada = contador >= cfg.FRAMES_CONFIRMA and conf >= cfg.UMBRAL_CONFIANZA

        if confirmada and clase != ultima_confirmada:
            if tipo == "vacio" or (time.time() - ultima_alerta > cfg.COOLDOWN_CAM_S):
                actuar_camara(tipo, frame)
                ultima_confirmada = clase
                if tipo != "vacio":
                    ultima_alerta = time.time()

        time.sleep(0.03)


# ==================== Arranque ====================
print("Iniciando sistema...")
cargar_json(ARCHIVO_CONOCIDOS, CONOCIDOS)
cargar_json(ARCHIVO_DIARIO, diario)
telegram_menu("✅ Sistema de seguridad iniciado (red + camara). Usa los botones o /ayuda.")

threading.Thread(target=hilo_telegram, daemon=True).start()
threading.Thread(target=hilo_red, daemon=True).start()
threading.Thread(target=hilo_resumen, daemon=True).start()

print("Sistema corriendo en segundo plano. Ctrl+C para detener.")
try:
    bucle_camara()
except KeyboardInterrupt:
    pass
print("Sistema detenido.")
