"""Tests unitarios de router.py (pasos 1, 2, 3 y 5 de la actividad).

Uso: python3 test_unitarios.py <ruta_repo> <carpeta_rutas>
"""
import os
import random
import sys

REPO = os.path.abspath(sys.argv[1])
RUTAS = os.path.abspath(sys.argv[2])
sys.path.insert(0, REPO)

import header  # noqa: E402
import router  # noqa: E402


def titulo(t):
    print("\n" + "=" * 60 + f"\n{t}\n" + "=" * 60)


def mk(msg: bytes, ttl=10, id=347, offset=0, flag=0, puerto=8885):
    return header.Header(b"127.0.0.1", puerto, msg, ttl, len(msg), flag, id, offset)


# ---------------------------------------------------------------- Paso 1
titulo("Paso 1: parse_packet / create_packet")
IP_packet_v1 = mk(b"hola!").to_packet()
campos = [("IP", 4), ("Puerto", 2), ("TTL", 1), ("ID", 8), ("Offset", 8), ("Tamaño", 4), ("FLAG", 1)]
print(f"IP_packet_v1 ({len(IP_packet_v1)} B):")
i = 0
for nombre, n in campos:
    print(f"  {nombre:<7}({n} B) = {IP_packet_v1[i:i + n].hex(' ')}")
    i += n
print(f"  mensaje      = {IP_packet_v1[i:]}")
parsed = router.parse_packet(IP_packet_v1)
print(f"parse_packet(IP_packet_v1) = {parsed}")
IP_packet_v2 = router.create_packet(parsed)
print(f"IP_packet_v1 = IP_packet_v2 ? {IP_packet_v1 == IP_packet_v2}")
print(f"Paquete truncado (<28 B) -> {router.parse_packet(IP_packet_v1[:20])}")
malo = bytearray(IP_packet_v1)
malo[26] = 9  # Tamaño declarado no coincide con el mensaje
print(f"Tamaño inconsistente -> {router.parse_packet(bytes(malo))}")

# ---------------------------------------------------------------- Paso 2
titulo("Paso 2: check_routes retorna (next_hop, MTU)")
routers = {}
for nombre, puerto_router, destino in [
    ("R1", 8881, 8885), ("R2", 8882, 8885), ("R2", 8882, 8885), ("R2", 8882, 8885),
    ("R3", 8883, 8885), ("R3", 8883, 8885), ("R4", 8884, 8885), ("R4", 8884, 8885),
    ("R5", 8885, 8881), ("R5", 8885, 8881),
]:
    archivo = os.path.join(RUTAS, f"rutas_{nombre}_v3_mtu.txt")
    # se reutiliza el mismo objeto por router para ver el round-robin
    r = routers.setdefault(nombre, router.Router("127.0.0.1", puerto_router, archivo))
    print(f"{nombre}: check_routes(dest=127.0.0.1:{destino}) -> {r.check_routes(archivo, ('127.0.0.1', destino))}")

r5 = router.Router("127.0.0.1", 8885, "")
try:
    r5.check_routes(os.path.join(RUTAS, "rutas_R5_enunciado.txt"), ("127.0.0.1", 8881))
    print("Tabla R5 literal del enunciado: OK")
except Exception as e:
    print(f"Tabla R5 literal del enunciado (sin /24): falla con {type(e).__name__}: {e}")

# ---------------------------------------------------------------- Paso 3
titulo("Paso 3: fragment_IP_packet")
for largo, mtu in [(5, 100), (72, 100), (122, 100), (122, 50), (122, 150), (1, 29)]:
    p = mk(b"x" * largo)
    frs = router.fragment_IP_packet(p, mtu)
    tam = [f.packet_size() for f in frs]
    print(f"msg={largo:>3} B (total {p.packet_size():>3} B), MTU={mtu:>3} -> "
          f"{len(frs)} fragmento(s), tamaños={tam}, max<=MTU: {max(tam) <= mtu}")

print("\nDetalle: paquete de 150 B con MTU 100 y luego cada fragmento con MTU 50")
MSG150 = b"".join(bytes([65 + i % 26]) for i in range(122))  # ABC...XYZABC...
p = mk(MSG150)
for f in router.fragment_IP_packet(p, 100):
    print(f"  [MTU 100] {f}")
    for g in router.fragment_IP_packet(f, 50):
        print(f"     [MTU 50] {g}")

# ---------------------------------------------------------------- Paso 5
titulo("Paso 5: fragment_IP_packet + reassemble_IP_packet")
ok_total = True
rng = random.Random(42)
for largo in [5, 22, 23, 72, 122, 300]:
    for mtu in [29, 50, 55, 80, 100, 140]:
        IP_packet_v1 = mk(bytes(rng.randrange(256) for _ in range(largo)), id=rng.randrange(1000))
        fragment_list = router.fragment_IP_packet(IP_packet_v1, mtu)
        rng.shuffle(fragment_list)
        IP_packet_v2 = router.reassemble_IP_packet(fragment_list)
        ok = IP_packet_v2 is not None and IP_packet_v1.to_packet() == IP_packet_v2.to_packet()
        ok_total &= ok
print(f"36 combinaciones (largo x MTU, fragmentos desordenados): todas iguales = {ok_total}")

# Re-fragmentación en cadena: 100 -> 80 -> 55 -> 50
IP_packet_v1 = mk(b"M" * 122)
frs = [IP_packet_v1]
for mtu in [100, 80, 55, 50]:
    frs = [g for f in frs for g in router.fragment_IP_packet(f, mtu)]
rng.shuffle(frs)
v2 = router.reassemble_IP_packet(frs)
print(f"Cadena de MTU 100->80->55->50: {len(frs)} fragmentos, "
      f"IP_packet_v1 = IP_packet_v2 ? {v2 is not None and IP_packet_v1.to_packet() == v2.to_packet()}")

print("\nCasos de lista incompleta:")
frs = router.fragment_IP_packet(mk(b"z" * 122), 50)
print(f"  Solo el primer fragmento (FLAG=1)      -> {router.reassemble_IP_packet(frs[:1])}")
print(f"  Falta un fragmento del medio           -> {router.reassemble_IP_packet(frs[:2] + frs[3:])}")
print(f"  Falta el último fragmento              -> {router.reassemble_IP_packet(frs[:-1])}")
print(f"  Solo el último fragmento (offset != 0) -> {router.reassemble_IP_packet(frs[-1:])}")
print(f"  Paquete completo sin fragmentar        -> {router.reassemble_IP_packet([mk(b'hola!')])}")
