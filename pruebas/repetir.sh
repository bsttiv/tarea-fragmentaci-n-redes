#!/bin/sh
# Uso: sh pruebas/repetir.sh <ruta_repo> <N>
# Corre test_routers.py N veces y muestra, por corrida, los escenarios de 150 B:
# <corrida> <escenario> <fragmentos con TTL 0> <paquetes re-ensamblados>
DIR=$(dirname "$0")
for k in $(seq 1 "$2"); do
  rm -rf "/tmp/rep$k"
  python3 -I "$DIR/test_routers.py" "$1" "$DIR/rutas" "/tmp/rep$k" > /dev/null 2>&1
  python3 -I "$DIR/resumen.py" "/tmp/rep$k" | awk -v k="$k" 'NR>1 && /^(2|3)/ {print k, $1, $3, $4}'
done
