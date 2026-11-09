import sys
import socket
import header

def parse_packet(IP_Packet: bytes) -> header.Header:
    # un paquete debe tener por lo menos el tamaño de un header
    if len(IP_Packet) < 28:
        return None
    # los primeros 4 bytes son la ip
    ip     = ".".join(str(b) for b in IP_Packet[0:4]).encode()
    # los siguientes 2 bytes son el puerto
    puerto = int.from_bytes(IP_Packet[4:6])
    # el siguiente byte es el ttl
    ttl    = int.from_bytes(IP_Packet[6:7])
    # la id son los 8 siguientes bytes
    id     = int.from_bytes(IP_Packet[7:15])
    # el offset son los 8 siguientes bytes
    offset = int.from_bytes(IP_Packet[15:23])
    # 4 bytes con el tamaño
    tamaño = int.from_bytes(IP_Packet[23:27])
    # la flag solo tiene 1 byte (podría ser un bit, pero se decidió por simplicidad)
    flag   = int.from_bytes(IP_Packet[27:28])
    # el resto es el mensaje
    msg    = IP_Packet[28:]
    if tamaño != len(msg) or flag not in (0, 1):
        return None
    return header.Header(ip, puerto, msg, ttl, tamaño, flag, id, offset)

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

def num_to_ip(ip_num: int) -> str:
    s = ""
    for i in range(4):
        s = s + str((ip_num >> (8*(3-i))) & 0xFF) + "."
    return s[:-1]

def ip_in_cidr(ip_dest_num: int, cidr_ip: str, cidr_mascara: int) -> bool:
    cidr_ip_num = ip_to_num(cidr_ip)
    desp = 32-cidr_mascara
    return ((ip_dest_num >> desp) ^ (cidr_ip_num >> desp)) == 0

def fragment_IP_packet(packet: header.Header, MTU: int):
    if packet.packet_size() <= MTU:
        return [packet]
    ip_txt = num_to_ip(int.from_bytes(packet.ip)).encode()
    puerto = int.from_bytes(packet.puerto)
    ttl = int.from_bytes(packet.ttl)
    id = int.from_bytes(packet.id)

    offset_base = int.from_bytes(packet.offset)
    flag_original = int.from_bytes(packet.flag)
    trozo = MTU - 28

    fragmentos = []
    partes = (len(packet.msg) / trozo).__ceil__()
    for i in range(partes):
        sl = packet.msg[i*trozo:(i+1)*trozo]
        tamaño = len(sl)
        flag = 1 if i < partes-1 else flag_original
        offset = offset_base + i*trozo
        p = header.Header(ip_txt, puerto, sl, ttl, tamaño, flag, id, offset)
        fragmentos.append(p)
    return fragmentos

def reassemble_IP_packet(fragment_list: list[header.Header]) -> header.Header:
    ordenados = sorted(fragment_list, key=lambda f: int.from_bytes(f.offset))
    esperado = 0
    for f in ordenados:
        if int.from_bytes(f.offset) != esperado:
            return None
        esperado += len(f.msg)
    if int.from_bytes(ordenados[-1].flag) != 0:
        return None
    cualquiera = ordenados[0]
    puerto = int.from_bytes(cualquiera.puerto)
    ttl = int.from_bytes(cualquiera.ttl)
    id = int.from_bytes(cualquiera.id)
    p = header.Header(num_to_ip(int.from_bytes(cualquiera.ip)).encode(), puerto, b"", ttl, 0, 0, id, 0)
    for paquete in ordenados:
        p.msg += paquete.msg
    p.tamaño = len(p.msg).to_bytes(4)
    return p

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
        # Diccionario para los fragmentos
        self.fragmentos = {}
    def start(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.ip, self.puerto))
        while True:
            msg, _ = sock.recvfrom(1024)
            msg_dec = parse_packet(msg)
            if msg_dec is None:
                print("Mensaje con formato incorrecto ignorado")
                continue
            if int.from_bytes(msg_dec.ttl) <= 0:
                print(f"Se recibió paquete {str(msg_dec)} con TTL 0")
                continue
            ip = num_to_ip(int.from_bytes(msg_dec.ip))
            puerto = int.from_bytes(msg_dec.puerto)
            if self.ip != ip or puerto != self.puerto:
                res = self.check_routes(router_rutas, (ip, puerto))
                if res is None:
                    print(f"No hay rutas hacia {ip}:{puerto} para paquete {str(msg_dec)}")
                    continue
                forward, mtu = res
                paquetes = fragment_IP_packet(msg_dec, mtu)
                for paquete in paquetes:
                    print(f"Redirigiendo paquete {str(paquete)} con destino final {ip} desde {self.ip}:{self.puerto} hacia {forward}")
                    paquete.ttl = (int.from_bytes(paquete.ttl) - 1).to_bytes(1)
                    to_bytes = create_packet(paquete)
                    sock.sendto(to_bytes, forward)
                continue
            id = int.from_bytes(msg_dec.id)
            if id in self.fragmentos:
                self.fragmentos[id].append(msg_dec)
            else:
                self.fragmentos[id] = [msg_dec]
            ensamblado = reassemble_IP_packet(self.fragmentos[id])
            if ensamblado is not None:
                print(ensamblado.msg.decode(errors="replace"))
                del self.fragmentos[id]
    def check_routes(self, routes_file_name: str, destination_address: tuple[str, int]) -> tuple[tuple[str, int], int]:
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
            
            # MTU
            mtu = int(linea_split[5])
            
            if ip_in_cidr(ip_dest_num, cidr_ip, cidr_mascara) and inicio_rango_puerto <= puerto_destino <= fin_rango_puerto:
                if cidr_mascara == 0:
                    rutas_default.append(((ip_siguiente, puerto_siguiente), mtu))
                else:
                    posibles_destinos.append(((ip_siguiente, puerto_siguiente), mtu))
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