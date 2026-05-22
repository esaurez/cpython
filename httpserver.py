import sys
import _socket

print(f"Python {sys.version}")
print(f"Platform: {sys.platform}")

srv = _socket.socket(2, 1, 0)  # AF_INET=2, SOCK_STREAM=1
print(f"socket created: fd={srv.fileno()}")

srv.bind(("0.0.0.0", 9999))
srv.listen(5)
print("HTTP server listening on 0.0.0.0:9999")

while True:
    fd, addr = srv._accept()
    print(f"Connection from {addr}")
    conn = _socket.socket(2, 1, 0, fd)
    conn.recv(4096)
    conn.send(b"HTTP/1.0 200 OK\r\nContent-Type: text/plain\r\n\r\nHello from Nanvix!\n")
    conn.close()
