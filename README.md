# 🏠 Sistema de Seguridad Inteligente con IA (Teachable Machine + Telegram)

Plantilla para armar en tu casa un sistema de seguridad con:

- **Cámara + IA** (modelo de Teachable Machine) que reconoce si en tu entrada hay **nadie**, **tú** o **alguien externo**.
- **Alertas por Telegram** con foto y botones *Conocido / Desconocido*.
- **Video de evidencia** automático si marcas a la persona como *Desconocido*.
- **Monitor de tu red WiFi**: avisa cada vez que un dispositivo se conecta o desconecta.
- **Comandos y botones en Telegram**: foto en vivo, video, estado, historial, resúmenes diarios y semanales.

> ⚠️ Este repositorio **no trae credenciales ni modelo**.
> Cada persona pone **su propio bot de Telegram** y **entrena su propio modelo** con su puerta y su gente.

---

## 📑 Índice

1. [Cómo funciona](#1-cómo-funciona)
2. [Qué necesitas](#2-qué-necesitas)
3. [Instalar Python y VS Code](#3-instalar-python-y-vs-code)
4. [Descargar este proyecto](#4-descargar-este-proyecto)
5. [Crear el entorno e instalar librerías](#5-crear-el-entorno-e-instalar-librerías)
6. [Crear tu bot de Telegram](#6-crear-tu-bot-de-telegram)
7. [Entrenar tu modelo en Teachable Machine](#7-entrenar-tu-modelo-en-teachable-machine)
8. [Configurar config.py](#8-configurar-configpy)
9. [Probar cámara y Telegram](#9-probar-cámara-y-telegram)
10. [Ejecutar el sistema](#10-ejecutar-el-sistema)
11. [Comandos de Telegram](#11-comandos-de-telegram)
12. [Ajustes finos](#12-ajustes-finos)
13. [Problemas comunes](#13-problemas-comunes)
14. [Privacidad y uso responsable](#14-privacidad-y-uso-responsable)
15. [Estructura del proyecto](#15-estructura-del-proyecto)

---

## 1. Cómo funciona

```
 Webcam ──► Modelo Teachable Machine ──► Capa de verificación ──► Telegram
                (Vacío / Dueño / Externo)   (90% + 10 frames)        │
                                                                    ├─ Dueño   → "Bienvenido"
                                                                    └─ Externo → Foto + botones
                                                                                  └─ Desconocido → Video evidencia

 Red WiFi ──► Escaneo (ping + tabla ARP) ──► Conexión / desconexión ──► Telegram
```

**Cámara:**

- Corre en segundo plano (no abre ninguna ventana).
- Cada imagen pasa por tu modelo.
- Solo se confirma una detección si:
  - la confianza es ≥ 90 %, y
  - la misma clase sale en 10 frames seguidos.
- Solo avisa cuando la clase confirmada **cambia** (no manda spam).
- Entre alertas hay un tiempo mínimo (90 s por defecto).

**Red:**

- Cada pocos segundos hace ping a toda tu red y lee la tabla ARP.
- El primer escaneo se guarda en silencio (son los que ya estaban).
- Después avisa cada conexión y desconexión, incluso de equipos conocidos.
- Muestra el nombre (si lo registraste), el fabricante y el nombre del equipo.
- Solo vigila en las redes que tú pongas en `REDES_CASA`.

**Funciona en Windows y Linux.**

---

## 2. Qué necesitas

| Cosa | Detalle |
|---|---|
| Computadora | Windows 10/11 o Linux (Ubuntu) |
| Webcam | La de la laptop o una USB apuntando a tu entrada |
| Python | **3.11 o 3.12** (⚠️ 3.13 y 3.14 **no** funcionan con TensorFlow) |
| Telegram | En tu celular |
| Internet | La PC conectada al WiFi de tu casa |
| Cuenta Google | Opcional, para guardar tu proyecto de Teachable Machine |

---

## 3. Instalar Python y VS Code

### Windows

1. Abre **PowerShell** (tecla Windows → escribe `PowerShell`).
2. Instala Python 3.12:
   ```powershell
   winget install -e --id Python.Python.3.12
   ```
3. Instala Git (para clonar el proyecto):
   ```powershell
   winget install -e --id Git.Git
   ```
4. Descarga e instala **VS Code**: https://code.visualstudio.com
5. Cierra y vuelve a abrir PowerShell.
6. Verifica:
   ```powershell
   py -3.12 --version
   ```
   Debe decir `Python 3.12.x`.

> Si instalas desde python.org, marca la casilla **"Add Python to PATH"**.

### Linux (Ubuntu)

```bash
sudo apt update
sudo apt install -y software-properties-common git
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv
python3.11 --version
```

VS Code:

```bash
sudo snap install code --classic
```

### Extensión de Python en VS Code

1. Abre VS Code.
2. Ve a **Extensiones** (icono de cuadritos a la izquierda o `Ctrl+Shift+X`).
3. Busca **Python** (de Microsoft) → **Install**.

---

## 4. Descargar este proyecto

**Opción A — Sin Git (más fácil):**

1. En esta página de GitHub, botón verde **Code** → **Download ZIP**.
2. Descomprime la carpeta (por ejemplo en `Documentos`).

**Opción B — Con Git:**

```bash
git clone https://github.com/andreinagelzelaya/sistema-seguridad-plantilla.git
cd sistema-seguridad-plantilla
```

Luego en VS Code: **File → Open Folder** → elige la carpeta del proyecto.

Abre la terminal dentro de VS Code: **Terminal → New Terminal** (o `` Ctrl+` ``).
Todos los comandos siguientes se escriben **en esa terminal**.

---

## 5. Crear el entorno e instalar librerías

El entorno virtual (`venv`) es una carpeta con su propio Python solo para este proyecto.

### Windows

```powershell
py -3.12 -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Linux

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

La instalación tarda unos minutos (TensorFlow pesa ~500 MB).

**Qué se instala:**

- `opencv-python` → leer la cámara.
- `numpy` → manejar las imágenes como números.
- `requests` → hablar con Telegram.
- `tensorflow` → correr el modelo.
- `tf_keras` → cargar modelos de Teachable Machine (con Keras 3 normal **no** cargan).

> 💡 En VS Code, abajo a la derecha, elige el intérprete del `venv`
> (`Ctrl+Shift+P` → **Python: Select Interpreter** → el que dice `venv`).

---

## 6. Crear tu bot de Telegram

### 6.1 Crear el bot y sacar el TOKEN

1. En Telegram busca **@BotFather** (con check azul).
2. Escríbele `/newbot`.
3. Ponle un nombre (ej. `Seguridad de mi casa`).
4. Ponle un usuario que termine en `bot` (ej. `seguridad_micasa_bot`).
5. Te devuelve un **TOKEN** como este:
   ```
   1234567890:AAH-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. Guárdalo. **No lo compartas con nadie** (quien lo tenga controla tu bot).

### 6.2 Activar tu bot

1. Busca tu bot por su usuario.
2. Ábrelo y presiona **Start** (o escribe `/start`).

> Sin este paso el bot **no puede** escribirte (error 400).

### 6.3 Sacar tu CHAT_ID

1. Busca **@userinfobot** en Telegram.
2. Escríbele cualquier cosa.
3. Te responde con tu **Id** (un número, ej. `987654321`).
4. Ese número es tu `CHAT_ID`.

---

## 7. Entrenar tu modelo en Teachable Machine

Teachable Machine: https://teachablemachine.withgoogle.com/train/image

### 7.1 Crear el proyecto

1. Entra al link → **Image Project** → **Standard image model**.
2. Crea **3 clases** con estos nombres (o los que quieras, pero luego los pones igual en `config.py`):

| Clase | Qué fotos van |
|---|---|
| `Vacio` | Tu entrada **sin nadie** |
| `Dueno` | **Tú** entrando/parado en la entrada |
| `Externo` | **Otras personas** (amigos, familia, fotos de gente) |

> Evita tildes y ñ en los nombres para no tener problemas (`Dueno`, no `Dueño`).

### 7.2 Tomar las fotos (lo más importante)

- Pon la webcam **en el mismo lugar** donde va a vigilar. No la muevas después.
- Toma las fotos con **esa misma cámara**.
- Usa **Webcam** → mantén presionado **Hold to Record**.
- **300 a 500 fotos por clase**, más o menos la misma cantidad en las 3.
- Varía:
  - distancia (cerca, lejos),
  - posición (de frente, de lado, de espaldas),
  - luz (día, noche, foco prendido/apagado),
  - **ropa** (si no, el modelo aprende tu polera y no tu cara).
- Para `Externo`:
  - pide a 2-3 personas que posen, y/o
  - usa **Upload** para subir fotos de otras personas.
- Para `Vacio`: graba la entrada vacía con distintas luces y con la puerta abierta/cerrada.

### 7.3 Entrenar y probar

1. Presiona **Train Model** y espera (no cierres la pestaña).
2. En **Preview**, prueba con la webcam:
   - Tú → `Dueno` con barra alta.
   - Otra persona → `Externo`.
   - Nadie → `Vacio`.
3. Si se confunde, agrega más fotos variadas a la clase que falla y vuelve a entrenar.

### 7.4 Exportar

1. **Export Model** → pestaña **Tensorflow**.
2. Elige **Keras** → **Download my model**.
3. Te baja un `.zip` con:
   - `keras_model.h5`
   - `labels.txt`
4. Descomprime y **copia esos 2 archivos a la carpeta del proyecto** (al lado de `sistema_seguridad.py`).

> 💾 Opcional: **Save project to Drive** para poder reentrenar después.

---

## 8. Configurar `config.py`

Aquí van **tus** datos. Este archivo **nunca** se sube a GitHub (está en `.gitignore`).

### 8.1 Crear el archivo

Copia `config.example.py` y nombra la copia `config.py`.

**Windows:**

```powershell
copy config.example.py config.py
```

**Linux:**

```bash
cp config.example.py config.py
```

(O en VS Code: clic derecho → Copy → Paste → renombrar.)

### 8.2 Llenar los datos

Abre `config.py` y cambia:

| Variable | Qué poner | Ejemplo |
|---|---|---|
| `TOKEN` | El token de @BotFather | `"1234567890:AAH-xxxx"` |
| `CHAT_ID` | Tu Id de @userinfobot | `"987654321"` |
| `CLASE_VACIO` | Nombre exacto de tu clase vacía | `"Vacio"` |
| `CLASE_DUENO` | Nombre exacto de tu clase | `"Dueno"` |
| `CLASE_EXTERNO` | Nombre exacto de la clase de otros | `"Externo"` |
| `NOMBRE_DUENO` | Tu nombre para el saludo | `"Carlos"` |
| `CAMARA` | Número de cámara | `0` (o `1` si tienes webcam USB) |
| `REDES_CASA` | Primeros 3 números de la IP de tu red | `["192.168.1"]` |
| `CONOCIDOS` | MAC → nombre de tus equipos | ver abajo |
| `HORA_RESUMEN` | Hora del resumen diario (0-23) | `21` |

> Los nombres de clase deben ser **iguales** a los de `labels.txt` (mayúsculas no importan).
> Si no coinciden, el programa te avisa al arrancar.

### 8.3 Cómo saber tu `REDES_CASA`

**Windows:**

```powershell
ipconfig
```

Busca **Dirección IPv4** del adaptador WiFi, ej. `192.168.1.25` → pones `"192.168.1"`.

**Linux:**

```bash
hostname -I
```

Ej. `192.168.0.14` → pones `"192.168.0"`.

Puedes poner varias redes:

```python
REDES_CASA = ["192.168.1", "10.42.0"]   # casa + hotspot del celular
```

Si la PC está en otra red (universidad, café), el monitor de red **no escanea** (por seguridad).
Para desactivarlo del todo: `VIGILAR_RED = False`.

### 8.4 Registrar tus dispositivos conocidos (opcional)

La MAC de tu celular:

- **Android:** Ajustes → WiFi → tu red (engranaje) → *Dirección MAC*.
- **iPhone:** Ajustes → WiFi → (i) en tu red → *Dirección WiFi*.

> Los celulares usan **MAC aleatoria** por red. Copia la que sale **en tu red de casa**.

```python
CONOCIDOS = {
    "aa:bb:cc:dd:ee:ff": "Carlos",
    "11:22:33:44:55:66": "Mama",
}
```

- MAC en **minúsculas** y con **dos puntos** `:`.
- También puedes agregarlos desde Telegram con `/agregar MAC nombre`.

---

## 9. Probar cámara y Telegram

Antes del sistema completo, prueba cada parte por separado.

### Cámara

**Windows:**

```powershell
venv\Scripts\python.exe camara_test.py
```

**Linux:**

```bash
python camara_test.py
```

- Se abre una ventana con tu cámara → ✅.
- Sal con la tecla `q`.
- Si sale negra o error → cambia `CAMARA = 1` (en `camara_test.py` y en `config.py`).

### Telegram

**Windows:**

```powershell
venv\Scripts\python.exe telegram_test.py
```

**Linux:**

```bash
python telegram_test.py
```

- Te llega un mensaje y en la terminal sale `'ok': True` → ✅.
- `401` → TOKEN mal copiado.
- `400` → CHAT_ID mal, o no le diste **Start** al bot.

---

## 10. Ejecutar el sistema

**Windows:**

```powershell
venv\Scripts\python.exe sistema_seguridad.py
```

**Linux:**

```bash
source venv/bin/activate
python sistema_seguridad.py
```

Qué debería pasar:

1. En la terminal: `Iniciando sistema...`
2. Tarda unos segundos en cargar TensorFlow (normal, salen avisos amarillos).
3. Te llega a Telegram: **✅ Sistema de seguridad iniciado** + el menú de botones.
4. No se abre ninguna ventana: la cámara trabaja en segundo plano.
5. Para detenerlo: `Ctrl + C` en la terminal.

Prueba:

- Párate frente a la cámara → **👋 ¡Bienvenido TuNombre!**
- Que otra persona se pare → **⚠️ foto + botones**.
  - **✅ Conocido** → no pasa nada más.
  - **🚨 Desconocido** → graba y te manda un **video de evidencia**.
- Conecta un celular al WiFi → **📶 Se conectó...**

> La PC debe quedar **prendida** y **sin suspenderse** mientras vigila
> (Windows: Configuración → Sistema → Energía → Suspender: *Nunca*).

---

## 11. Comandos de Telegram

Puedes usar los **botones del menú** o escribir el comando.

| Botón / Comando | Qué hace |
|---|---|
| 📸 Foto · `/foto` | Foto en vivo de la cámara |
| 🎥 Video · `/video` | Video de 5 segundos |
| 📊 Estado · `/estado` | Dispositivos conectados ahora a tu red |
| 📖 Diario · `/diario` | Hora de llegada y salida de cada dispositivo hoy |
| 📅 Resumen · `/resumen` | Resumen del día |
| `/semana` | Resumen de la semana |
| 🔔 Armar · `/armar` | Activa las alertas |
| 🔇 Desarmar · `/desarmar` | Desactiva las alertas |
| 🔕 Silencio 1h · `/silencio 2h` · `/silencio 30m` | Silencia alertas por un tiempo |
| `/historial` | Últimos 10 eventos |
| `/exportar` | Te manda `historial.csv` |
| `/agregar MAC nombre` | Registra un dispositivo conocido |
| `/quitar MAC` | Lo quita |
| `/conocidos` | Lista de conocidos |
| ❓ Ayuda · `/ayuda` | Muestra el menú |

**Automático:**

- Resumen diario a la hora de `HORA_RESUMEN`.
- Resumen semanal los domingos.

---

## 12. Ajustes finos

Todo se cambia en `config.py`:

| Variable | Para qué | Si… |
|---|---|---|
| `UMBRAL_CONFIANZA` | Confianza mínima (0.90 = 90 %) | Muchas falsas alarmas → súbelo a `0.95` |
| `FRAMES_CONFIRMA` | Frames seguidos para confirmar | Tarda mucho → bájalo (`6`). Confunde clases → súbelo (`15`) |
| `COOLDOWN_CAM_S` | Segundos entre alertas de cámara | Mucho spam → súbelo |
| `SEGUNDOS_VIDEO_EVIDENCIA` | Duración del video de evidencia | — |
| `INTERVALO_S` | Pausa entre escaneos de red | PC lenta → súbelo |
| `UMBRAL_AUSENCIA` | Escaneos sin ver un equipo para darlo por desconectado | Avisos falsos de desconexión → súbelo a `5` |

> Si el modelo confunde clases, **lo que más ayuda es reentrenar** con más fotos variadas (sobre todo ropa distinta), no solo mover números.

---

## 13. Problemas comunes

| Error / síntoma | Solución |
|---|---|
| `No module named ...` | No instalaste las librerías o no estás usando el `venv` (paso 5) |
| `tensorflow` no se instala | Tu Python es 3.13/3.14. Usa **3.11 o 3.12** |
| `expects 1 named input... received 2` | Estás cargando con Keras 3. Instala `tf_keras` (`pip install tf_keras`) |
| `no existe config.py` | Copia `config.example.py` como `config.py` (paso 8) |
| `no se encontro 'keras_model.h5'` | Copia los archivos exportados de Teachable Machine a la carpeta |
| La clase no coincide con labels.txt | Pon en `config.py` los nombres exactos de `labels.txt` |
| Telegram `401` | TOKEN mal copiado |
| Telegram `400` | CHAT_ID mal, o no diste **Start** al bot |
| Cámara negra / `can't grab frame` | Cambia `CAMARA` a `1`. Cierra Zoom/Meet/otras apps que usen la cámara |
| No avisa de la red | Revisa que tu IP empiece con algo que está en `REDES_CASA` |
| Avisa conexión/desconexión de un celular cada rato | Los celulares duermen el WiFi. Sube `UMBRAL_AUSENCIA` |
| Confunde al dueño con externo | Reentrena con más fotos tuyas con **ropa distinta** y más externos |
| Linux: `Permission denied` con la cámara | `sudo usermod -a -G video $USER` y reinicia sesión |

---

## 14. Privacidad y uso responsable

- `config.py` tiene tu TOKEN: **nunca lo subas** ni lo mandes por chat.
- El bot **solo obedece a tu `CHAT_ID`**: si un extraño encuentra tu bot y le escribe, se ignora.
- Si alguna vez subiste tu token por error: en @BotFather → `/revoke` → genera uno nuevo.
- Escanea **solo tu propia red**. Escanear redes ajenas (universidad, trabajo) puede ir contra sus reglas.
- Las fotos y videos se guardan en la carpeta `evidencia/` de tu PC; bórralos cuando ya no los necesites.
- Avisa a las personas de tu casa que hay una cámara vigilando la entrada.
- Es un proyecto educativo: **no reemplaza** un sistema de seguridad profesional.

---

## 15. Estructura del proyecto

```
📁 proyecto/
├── sistema_seguridad.py   ← programa principal (cámara + red + Telegram)
├── config.example.py      ← plantilla de configuración (se sube)
├── config.py              ← TUS datos (NO se sube)          [lo creas tú]
├── keras_model.h5         ← TU modelo (NO se sube)          [lo exportas tú]
├── labels.txt             ← TUS clases (NO se sube)         [lo exportas tú]
├── camara_test.py         ← prueba de cámara
├── telegram_test.py       ← prueba de Telegram
├── requirements.txt       ← librerías necesarias
├── .gitignore             ← lo que nunca se sube
├── LICENSE                ← licencia MIT (libre de usar y modificar)
└── (se crean solos al usarlo)
    ├── evidencia/         ← fotos y videos
    ├── historial.csv      ← registro de eventos
    ├── conocidos.json     ← conocidos agregados por Telegram
    └── diario.json        ← llegadas y salidas
```

---

## ✅ Resumen rápido

1. Instala Python 3.12 (Win) / 3.11 (Linux) + VS Code.
2. Descarga el proyecto.
3. Crea el `venv` e instala `requirements.txt`.
4. Crea tu bot (@BotFather) y saca tu Id (@userinfobot). Dale **Start** al bot.
5. Entrena tu modelo de 3 clases en Teachable Machine y exporta en Keras.
6. Copia `keras_model.h5` y `labels.txt` a la carpeta.
7. Copia `config.example.py` → `config.py` y llénalo.
8. Prueba `camara_test.py` y `telegram_test.py`.
9. Ejecuta `sistema_seguridad.py`.

---

Proyecto académico — Inteligencia Artificial, Ingeniería Mecatrónica, Universidad Católica Boliviana "San Pablo", Santa Cruz.
