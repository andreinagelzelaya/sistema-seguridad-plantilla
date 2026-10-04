"""
Prueba de camara: confirma que la webcam funciona.
Se abre una ventana con la camara. Sal con la tecla 'q'.
Si sale negra o da error, cambia CAMARA a 1 (o 2) aqui y en config.py.
"""

import platform
import cv2

CAMARA = 0
BACKEND = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY

cap = cv2.VideoCapture(CAMARA, BACKEND)
if not cap.isOpened():
    raise RuntimeError("No se pudo abrir la camara. Prueba CAMARA = 1 o 2.")

print("Camara abierta. Presiona 'q' para salir.")
while True:
    ok, frame = cap.read()
    if not ok:
        print("No llega imagen.")
        break
    cv2.putText(frame, "Camara OK - 'q' para salir", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    cv2.imshow("Prueba de camara", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
