import socket
import threading
import struct

# see https://developer.valvesoftware.com/wiki/Source_RCON_Protocol
# and https://wiki.vg/RCON

__all__ = ['Connection']

def bidi_dict(d):
    d.update(dict([reversed(item) for item in d.items()]))
    return d

class Counter:
    # let's not deal with packet id overflow for now
    def __init__(self):
        self.lock = threading.Lock()
        self.value = -1

    def next(self):
        with self.lock:
            self.value += 1
            return self.value

class Connection:
    class PACKET_TYPE:
        SEND = bidi_dict({
            3: 'AUTH',
            2: 'EXEC'
        })
        RECV = bidi_dict({
            2: 'AUTH_RESP',
            0: 'RESP'
        })

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.counter = Counter()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))

    def authenticate(self, password):
        return self._send_packet(self.PACKET_TYPE.SEND['AUTH'], password) == ''

    def execute(self, command):
        return self._send_packet(self.PACKET_TYPE.SEND['EXEC'], command)

    def _send_packet(self, type1, body):
        pid1 = self.counter.next()
        payload  = struct.pack('<ii', pid1, type1)
        payload += body.encode()
        payload += b'\x00\x00'
        size = len(payload)
        payload = struct.pack('<i', size) + payload
        self.socket.sendall(payload)

        # send an invalid packet afterwards
        # (type 0 is not a valid type for the client to send)
        # this way we can detect whether a multi packet response
        # was received completely
        pid2 = self.counter.next()
        payload  = struct.pack('<ii', pid2, 0)
        payload += b'\x00\x00'
        size = len(payload)
        payload = struct.pack('<i', size) + payload
        self.socket.sendall(payload)

        #print('pid1', pid1, 'pid2', pid2)

        # buffer should always have this layout:
        # 4  bytes packet size (not included in size)
        # 4  bytes packet id
        # 4  bytes packet type
        # 1+ bytes body (0x00 terminated)
        # 1  byte 0x00
        buffer = b''
        body = ''
        # until we have a response
        while True:
            data = self.socket.recv(4096)
            if not data:
                # connection failure
                return None
            #print('data', data)
            buffer += data
            # as long as we can read a packet size
            while len(buffer) >= 4:
                (size,) = struct.unpack('<i', buffer[:4])
                #print('size', size)
                # do we have enough data to read the whole packet?
                # (4 additional bytes for the size field in front)
                if len(buffer) >= size + 4:
                    pid, type = struct.unpack('<ii', buffer[4:12])
                    #print('pid', pid, 'type', type, self.PACKET_TYPE.RECV.get(type, None))
                    if pid == pid1:
                        # response to our original packet
                        # body starts from 3x 4 bytes and we skip the last 2 0x00
                        body_chunk = buffer[12:size+4-2].decode()
                        # accumulate body until we received the whole response
                        body += body_chunk
                        # remove packet from buffer
                        buffer = buffer[size+4:]
                    elif pid == pid2:
                        # response to our invalid packet
                        # remove packet from buffer
                        buffer = buffer[size+4:]
                        # as we received a response to our invalid packet
                        # we are now sure to have received the whole response
                        return body
                    elif pid == -1:
                        # minecraft responds with pid -1 to unauthenticated clients
                        return False
                else:
                    # we cannot read the whole packet from the current buffer
                    # we have to receive more data over the network
                    break
