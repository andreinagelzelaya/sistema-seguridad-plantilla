"""
Prueba de Telegram: confirma que tu bot te puede mandar mensajes.
Usa el TOKEN y CHAT_ID de config.py.
Si funciona, te llega un mensaje y aqui sale  'ok': True
"""

import sys
import requests

try:
    import config as cfg
except ImportError:
    print("ERROR: no existe config.py. Copia config.example.py como config.py y llenalo.")
    sys.exit(1)

r = requests.post(f"https://api.telegram.org/bot{cfg.TOKEN}/sendMessage",
                  data={"chat_id": cfg.CHAT_ID,
                        "text": "✅ Prueba: tu sistema de seguridad ya puede mandarte mensajes."},
                  timeout=10)

print("Codigo HTTP:", r.status_code)
print(r.json())
if r.status_code == 401:
    print("-> TOKEN incorrecto. Copialo de nuevo desde @BotFather.")
elif r.status_code == 400:
    print("-> CHAT_ID incorrecto, o no le diste 'Start' a tu bot.")
