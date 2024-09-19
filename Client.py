import socket
import sys
import selectors
import types
import errno

HOST = "127.0.0.1"  # The server's hostname or IP address, 127.0.0.1 is localhost 
PORT = 65432  # The port used by the server

"""
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(b"Hello, world")
    data = s.recv(1024)
"""
    
sel = selectors.DefaultSelector()
messages = [b"Message 1 from client.", b"Message 2 from client."]



def start_connections(host, port, num_conns):
    server_addr = (host, port)
    for i in range (0, num_conns):
        connid = i + 1
        print(f"Starting Connection {connid} to {server_addr}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        sock.connect_ex(server_addr)


        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        data = types.SimpleNamespace(
            connid = connid,
            msg_total = sum(len(m) for m in messages),
            recv_total = 0,
            messages = messages.copy(),
            outb = b"",
        )

        sel.register(sock, events, data = data)



def service_connection(key, mask):
    sock = key.fileobj
    data = key.data

    if mask & selectors.EVENT_READ:
        recv_data = sock.recv(1024)

        if recv_data:
            print(f"Received {recv_data!r} from connection {data.connid}")
            data.recv_total += len(recv_data)

        try:
            sel.unregister(sock)
            sock.close()
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    if mask & selectors.EVENT_WRITE:
        if not data.outb and data.messages: #No outgoing data but messages to send, Pop next message and add it to out list
            data.outb = data.messages.pop(0)
        if data.outb: #Send any outgoing data if there is any
            print(f"Sending {data.outb!r} to connection {data.connid}")
            sent = sock.send(data.outb) #should be ready to write
            data.outb = data.outb[sent: ]



def event_loop():
    try:
        while True:
            # Exit event loop there are no currently registered sockets to avoid errors
            if not sel.get_map().keys():
                print("No sockets Registered")
                break
            events = sel.select(timeout=None)
            for key, mask in events:
                service_connection(key, mask)
            
                
    except KeyboardInterrupt:
        print("caught Keyboard Interrupt, Exiting")
    finally:
        sel.close()


#This function should take in an ip and port number and return a TCP socket connection to that IP/Port
def open_connection(ip, port_number):
        server_addr = (ip, port_number)
        print(f"Starting Connection to {server_addr}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)

        #Attempt to connect
        result = sock.connect_ex(server_addr)

        if result == 0:
            print(f"Connection to {server_addr} successful immediately")

        elif result == errno.EINPROGRESS or result == errno.EWOULDBLOCK:
            print(f"Connection to {server_addr} in progress")

        else:
            print(f"Error connecting to {server_addr}")
            sock.close()
            return None

        events = selectors.EVENT_READ | selectors.EVENT_WRITE
        sel.register(sock, events, data = None)

        return sock

def close_connection(sock):
    sel.unregister(sock)
    sock.close()


#This function should receive the information of an open socket connection. It should also receive 
def send_message(sock, version, msg_type, payload):



if __name__ == "__main__":
    #Start connections (e.g. 2 clients)
    start_connections(HOST, PORT, num_conns=2)

    event_loop()



#print(f"Received {data!r}")
