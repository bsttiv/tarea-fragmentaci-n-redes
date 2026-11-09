import sys
import socket
import header

def parse_packet(IP_Packet: bytes) -> header.Header:
    split = IP_Packet.split(b";", 3)
    if len(split) != 4:
        print("El paquete recibido tiene un formato incorrecto")
        return
    ip_bytes = split[0]
    puerto_bytes = split[1]
    msg = split[3]
    ttl = split[2]
    return header.Header(ip_bytes, puerto_bytes, msg, ttl)

def create_packet(ip_packet: header.Header) -> bytes:
    return ip_packet.to_packet()

def ip_to_num(ip:str) -> int:
    num = 0
    ip_split = ip.split(".")
    for i in range(4):
        try:
            val = int(ip_split[i])
        except Exception:
            print("Formato de IP incorrecto")
            return
        num |= (val << (8 * (3 - i)))
    return num

def ip_in_cidr(ip_dest_num: int, cidr_ip: str, cidr_mascara: int) -> bool:
    cidr_ip_num = ip_to_num(cidr_ip)
    desp = 32-cidr_mascara
    return ((ip_dest_num >> desp) ^ (cidr_ip_num >> desp)) == 0

class Router:
    def __init__(self, ip, puerto, archivo):
        self.ip = ip
        self.puerto = puerto
        self.archivo = archivo
        # Guarda el estado del round robin para cada area de la red.
        # Llave: (archivo_de_rutas, tupla con las lineas de la tabla que calzaron),
        # es decir, el conjunto de rutas que identifica el area.
        # Valor: indice de la siguiente ruta a usar en esa area.
        # Las rutas default (/0) usan el area (routes_file_name, ("default",) y solo se usan si
        # ninguna otra ruta calza.
        self.visitadas = {}
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.ip, self.puerto))
        while True:
            msg, _ = sock.recvfrom(1024)
            try:
                msg_dec = msg.decode().split(";", 3)
                ip = msg_dec[0]
                puerto = int(msg_dec[1])
                ttl = int(msg_dec[2])
            except Exception:
                print("Mensaje con formato incorrecto ignorado")
                continue
            if ttl <= 0:
                print(f"Se recibió paquete {msg.decode()} con TTL 0")
                continue
            if router_ip != ip or puerto != router_puerto:
                forward = self.check_routes(router_rutas, (ip, puerto))
                if forward is None:
                    print(f"No hay rutas hacia {ip}:{puerto} para paquete {msg.decode()}")
                    continue
                print(f"Redirigiendo paquete {msg.decode()} con destino final {ip} desde {router_ip}:{router_puerto} hacia {forward}")
                parsed = parse_packet(msg)
                parsed.ttl = (int.from_bytes(parsed.ttl) - 1).to_bytes(1)
                to_bytes = create_packet(parsed)
                sock.sendto(to_bytes, forward)
                continue
            print(msg_dec[3])
    def check_routes(self, routes_file_name: str, destination_address: tuple[str, int]) -> tuple[str, int]:
        lector = open(routes_file_name)
        ip_destino = destination_address[0]
        ip_dest_num = ip_to_num(ip_destino)
        puerto_destino = int(destination_address[1])
        posibles_destinos = []
        lineas_area = []
        # Rutas con mascara /0, solo se usan si ninguna otra ruta calza
        rutas_default = []
        for linea in lector:
            linea_strip = linea.strip()
            linea_split = linea_strip.split(" ")
            # Grupo de IPs
            cidr_dest = linea_split[0].split("/")
            cidr_ip = cidr_dest[0]
            cidr_mascara = int(cidr_dest[1])
            
            # Conjunto de puertos de destino
            inicio_rango_puerto = int(linea_split[1])
            fin_rango_puerto = int(linea_split[2])
            
            # Router al que enviar la peticion
            ip_siguiente = linea_split[3]
            puerto_siguiente = int(linea_split[4])
            
            if ip_in_cidr(ip_dest_num, cidr_ip, cidr_mascara) and inicio_rango_puerto <= puerto_destino <= fin_rango_puerto:
                if cidr_mascara == 0:
                    rutas_default.append((ip_siguiente, puerto_siguiente))
                else:
                    posibles_destinos.append((ip_siguiente, puerto_siguiente))
                    lineas_area.append(linea_strip)
        lector.close()
        if len(posibles_destinos) == 0:
            posibles_destinos = rutas_default
            lineas_area = ["default"]
        if len(posibles_destinos) == 0: return None
        area = (routes_file_name, tuple(lineas_area))
        indice = self.visitadas.get(area, 0)
        self.visitadas[area] = (indice + 1) % len(posibles_destinos)
        return posibles_destinos[indice]
            
if __name__ == "__main__":
    args = sys.argv
    if len(args) != 4:
        print("router.py recibe 3 argumentos: router_ip, router_puerto router_rutas")
        sys.exit(1)
    
    # Se asume que se entregan los tipos correctos, por simplicidad
    # Se asume tambien que la tabla de rutas tiene el formato correcto
    router_ip = sys.argv[1]
    router_puerto = int(sys.argv[2])
    router_rutas = sys.argv[3]
    
    router = Router(router_ip, router_puerto, router_rutas)
    router.start()