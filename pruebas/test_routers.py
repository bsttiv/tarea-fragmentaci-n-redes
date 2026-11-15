"""Prueba de integración: levanta los 5 routers y envía paquetes entre ellos.

Uso: python3 test_routers.py <ruta_repo> <carpeta_rutas> <carpeta_salida>

Cada escenario reinicia los routers y guarda la salida de cada uno en
<carpeta_salida>/<escenario>/R<i>.txt
"""
import os
import socket
import subprocess
import sys
import time

REPO = os.path.abspath(sys.argv[1])
RUTAS = os.path.abspath(sys.argv[2])
SALIDA = os.path.abspath(sys.argv[3])
sys.path.insert(0, REPO)

import header  # noqa: E402
import router  # noqa: E402

IP = "127.0.0.1"
PUERTOS = {f"R{i}": 8880 + i for i in range(1, 6)}
PAUSA = 0.3
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def mk(msg: bytes, destino: int, ttl: int, id: int, offset=0, flag=0):
    return header.Header(IP.encode(), destino, msg, ttl, len(msg), flag, id, offset)


def enviar(p: header.Header, a: str):
    sock.sendto(router.create_packet(p), (IP, PUERTOS[a]))
    time.sleep(PAUSA)


class Red:
    def __init__(self, nombre):
        self.dir = os.path.join(SALIDA, nombre)
        os.makedirs(self.dir, exist_ok=True)
        self.procs = {}

    def __enter__(self):
        for r, puerto in PUERTOS.items():
            out = open(os.path.join(self.dir, f"{r}.txt"), "w")
            tabla = os.path.join(RUTAS, f"rutas_{r}_v3_mtu.txt")
            self.procs[r] = (subprocess.Popen(
                [sys.executable, "-u", os.path.join(REPO, "router.py"), IP, str(puerto), tabla],
                stdout=out, stderr=subprocess.STDOUT, cwd=REPO), out)
        time.sleep(0.8)
        return self

    def __exit__(self, *a):
        time.sleep(0.8)
        for p, out in self.procs.values():
            p.terminate()
            p.wait()
            out.close()
        print(f"\n######## {os.path.basename(self.dir)}")
        for r in PUERTOS:
            with open(os.path.join(self.dir, f"{r}.txt")) as f:
                contenido = f.read().rstrip()
            print(f"--- {r} ---\n{contenido if contenido else '(sin salida)'}")


MSG150 = b"".join(bytes([65 + i % 26]) for i in range(122))  # 122 B + 28 B header = 150 B
assert mk(MSG150, 8885, 10, 1).packet_size() == 150

# 1) TTL y round-robin con un paquete que no se fragmenta
with Red("1_ttl_round_robin"):
    for _ in range(4):
        enviar(mk(b"hola!", 8885, 10, 347), "R1")

# 1b) TTL insuficiente: con TTL=3 el paquete muere antes de llegar a R5
with Red("1b_ttl_bajo"):
    enviar(mk(b"hola!", 8885, 3, 348), "R1")

# 2) Paquete de 150 B enviado varias veces de R1 a R5
with Red("2_150B_R1_a_R5"):
    for i in range(4):
        enviar(mk(MSG150, 8885, 10, 500 + i), "R1")

# 3) Paquete de 150 B desde otros routers
for origen, destino in [("R2", 8885), ("R3", 8885), ("R4", 8885), ("R5", 8881)]:
    with Red(f"3_150B_{origen}_a_R{destino - 8880}"):
        for i in range(2):
            enviar(mk(MSG150, destino, 10, 600 + i), origen)

# 3b) 150 B con TTL justo (4): algunos fragmentos pueden morir en el camino
with Red("3b_150B_ttl_4"):
    for i in range(3):
        enviar(mk(MSG150, 8885, 4, 700 + i), "R1")

# 4) Envío manual de fragmentos a R5 (en orden, desorden e intercalados)
A = router.fragment_IP_packet(mk(b"Primer mensaje fragmentado, ID 11!", 8885, 10, 11), 36)
B = router.fragment_IP_packet(mk(b"Segundo mensaje, este tiene ID 22.", 8885, 10, 22), 36)
with open(os.path.join(SALIDA, "4_fragmentos.txt"), "w") as f:
    for fr in A + B:
        f.write(str(fr) + "\n")
with Red("4a_en_orden"):
    for fr in A + B:
        enviar(fr, "R5")
with Red("4b_desorden"):
    for fr in [A[3], A[0], A[4], A[2], A[1], B[4], B[2], B[0], B[3], B[1]]:
        enviar(fr, "R5")
with Red("4c_intercalado"):
    for fr in [B[2], A[1], B[0], A[4], A[0], B[3], A[3], B[4], A[2], B[1]]:
        enviar(fr, "R5")

# 5) ID reutilizado tras un datagrama incompleto: los fragmentos huérfanos
#    quedan en el diccionario de R5 y bloquean a cualquier paquete posterior con ese ID
with Red("5_id_reutilizado"):
    for fr in router.fragment_IP_packet(mk(MSG150, 8885, 10, 900), 50)[1:]:  # falta el offset 0
        enviar(fr, "R5")
    enviar(mk(b"hola con ID 900", 8885, 10, 900), "R5")
    enviar(mk(b"hola con ID 901", 8885, 10, 901), "R5")
