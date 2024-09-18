import socket
import threading
import selectors
import types

sel = selectors.DefaultSelector()


HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)


lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, PORT))
    
print("Listening on " +  str(PORT))
lsock.listen()

lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)



def accept_wrapper(sock):
    conn, addr = sock.accept() #Socket should already be read to read if this fn is called
    print(f"Accepted connection from {addr}")
    conn.setblocking(False)
    data = types.SimpleNamespace(addr = addr, inb = b"", outb = b"")
    events = selectors.EVENT_READ | selectors.EVENT_WRITE
    sel.register(conn, events, data = data)


def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    print(data)

    if mask & selectors.EVENT_READ:
        #try:
        recv_data = sock.recv(1024) #Should be ready to read
        #except Exception as e:
         #   print("Unhandled Read Error")
            
        if recv_data:
            data.outb += recv_data
        else:
            print(f"Closing connection {data.addr}")
            sel.unregister(sock)
            sock.close()

    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print(f"Echoing {data.outb!r} to {data.addr}")
            sent = sock.send(data.outb) #Should be ready to write
            data.outb = data.outb[sent:]



try:
    while True:
        events = sel.select(timeout = None)
        for key, mask in events:
            if key.data is None:
                accept_wrapper(key.fileobj)
            else:
                service_connection(key, mask)
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()




"""
    conn, addr = s.accept()
    with conn:
        print(f"connected by {addr}")
        while True:
            data = conn.recv(1024)
            if not data:
                break
            conn.sendall(data)
"""

#def start_server(server_port):
    


""""
if __name__ == "__main__":
    SERVER_PORT = 8000
    start_server(SERVER_PORT)

"""