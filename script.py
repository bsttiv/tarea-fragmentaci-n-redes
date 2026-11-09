import socket
import header

if __name__ == "__main__":
    # Se asume que se introduciran datos correctos
    ip_router_final = input("Introduzca la IP del router final: ")
    puerto_router_final = input("Introduzca el puerto del router final: ")
    mensaje = input("Introduzca el mensaje a enviar: ")
    ip_envio = input("Introduzca la IP de envio: ")
    puerto_envio = input("Introduzca el puerto de envio: ")
    ttl = input("Introduzca el TTL: ")
    
    msg = header.Header(ip_router_final.encode(), puerto_router_final.encode(), mensaje.encode(), ttl.encode())
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(msg.to_packet(), (ip_envio, int(puerto_envio)))