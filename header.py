class Header:
    def __init__(self, ip: bytes, puerto: bytes, msg: bytes, ttl: bytes):
        ip_split = ip.split(b".")
        if len(ip_split) != 4:
            print("Formato de IP incorrecto")
            return
        ip_num = 0
        for i in range(4):
            try:
                val = int(ip_split[i].decode())
            except Exception:
                print("Formato de IP incorrecto")
                return
            ip_num |= (val << (8*i))
        self.ip = ip_num.to_bytes(4)
        # solo nos quedamos con los ultimos 2 bytes
        self.puerto = int(puerto.decode()).to_bytes(2)
        self.msg = msg
        self.ttl = int(ttl.decode()).to_bytes(1)
    def to_packet(self) -> bytes:
        msg = b""
        for i in range(4):
            msg = b"." + str(self.ip[i]).encode() + msg
        msg = msg[1:] + b";"
        msg += str(int.from_bytes(self.puerto)).encode() + b";"
        msg += str(int.from_bytes(self.ttl)).encode() + b";"
        msg += self.msg 
        return msg
