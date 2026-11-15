"""Resume las salidas de test_routers.py.

Uso: python3 resumen.py <carpeta_salida>
"""
import os
import re
import sys

SALIDA = sys.argv[1]
MSG150 = "".join(chr(65 + i % 26) for i in range(122))
patron = re.compile(r"Redirigiendo paquete [^;]+;\d+;(\d+);(\d+);(\d+);(\d+);(\d);")

print(f"{'Escenario':<22}{'Reenvíos':>9}{'TTL 0':>7}{'Rearmados':>10}  Por router (reenvíos)")
for esc in sorted(os.listdir(SALIDA)):
    d = os.path.join(SALIDA, esc)
    if not os.path.isdir(d):
        continue
    reenv, ttl0, rearm, por_router, nuevos = 0, 0, [], {}, 0
    for r in [f"R{i}" for i in range(1, 6)]:
        lineas = open(os.path.join(d, f"{r}.txt")).read().splitlines()
        n = sum(1 for l in lineas if l.startswith("Redirigiendo"))
        por_router[r] = n
        reenv += n
        ttl0 += sum(1 for l in lineas if "con TTL 0" in l)
        rearm += [(r, l) for l in lineas if not l.startswith(("Redirigiendo", "Se recibió", "No hay", "Mensaje"))]
    ok = all(m == MSG150 or len(m) < 60 for _, m in rearm)
    pr = " ".join(f"{k}={v}" for k, v in por_router.items())
    print(f"{esc:<22}{reenv:>9}{ttl0:>7}{len(rearm):>10}  {pr}  {'(contenido OK)' if ok else '(CONTENIDO DISTINTO)'}")
