import socket
import sys
import selectors
import types
import errno
import struct

import threading
import queue

HOST = "127.0.0.1"  # The server's hostname or IP address, 127.0.0.1 is localhost 
PORT = 65432  # The port used by the server


"""
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    s.sendall(b"Hello, world")
    data = s.recv(1024)
"""
    
sel = selectors.DefaultSelector()
input_queue = queue.Queue() #Queue to handle user requests


#Function to receive input from the user (e.g. ask server what files are available, ask to download files)
def receive_user_input():
    while True:
        user_input = input("Enter command:")
        if user_input:
            input_queue.put(user_input) #Send input to this queue, when this queue is full it should be handled

#Function to handle/process user input requests
def handle_user_command(command):
        print(f"User requested completion of {command}")

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

        #Buffers will be registered to each socket for incoming and outgoing data to ensure no data is lost from incomplete sends and receives.
        data = types.SimpleNamespace(
            type = "sock",
            endpoint = server_addr, #Which peer/server the connection is to
            incoming_buffer = b'',
            messageLength = None, #to record how many bytes we should expect an incoming message to be (so we know if we have received it all)

            outgoing_buffer =  b'',
        )

        sel.register(sock, events, data = data)

        return sock

def close_connection(sock):
    sel.unregister(sock)
    sock.close()

#This function will send a message of a fixed length to a packet. This function should receive the information of an open socket connection. It should also receive 
def send_message(sock, version, msg_type, payload):
    print("placeholder")
    

def handle_connection(key, mask):
    sock = key.fileobj
    data = key.data

    if mask & selectors.EVENT_READ: #Ready to read data
        received = sock.recv(1024)

        if received:
            print(f"Received: {data}")
            data.incoming_buffer += received

            #If we don't know the incoming message length yet. We should try to read it
            if data.messageLength is None and len(data.incoming_buffer >= 4):
                #We can extract first 4 bytes as this be the message length prefix
                data.messageLength = struct.unpack('!I', data.incoming_buffer[:4])[0] #Network byte order?????
                data.incoming_buffer = data.incoming_buffer[4:]
                print(f"Expected Message Length {data.messageLength} bytes")

            #If we do know the message length, we should process/clear incoming buffer once it has been fully received
            if data.messageLength is not None and len(data.incoming_buffer) >= data.messageLength:
                message = data.incoming_buffer[:data.messageLength]
                #NEED TO PROCESS MESSAGE HERE
                data.incoming_buffer = data.incoming_buffer[data.messageLength: ] #Remove the message from buffer
                data.messageLength = None #Reset message length so that we know there's no message currently


            # For demonstration, we immediately echo back the received data
            #data.outgoing_buffer += received  # Add it to outgoing buffer to echo it back
        else: #If 0 bytes received, client closed connection
            print(f"Closing connection to {data.endpoint}")
            sel.unregister(sock)
            sock.close()
            
    if mask & selectors.EVENT_WRITE and data.outgoing_buffer:
        sent = sock.send(data.outgoing_buffer) #Non-blocking send (Hopefully the message should have already been encoded prior to being put into the buffer)
        data.outgoing_buffer = data.outgoing_buffer[sent: ] #Remove sent part from the buffer


#Main event loop to handle checking sockets and user input
def event_loop():
    threading.Thread(target = receive_user_input, daemon=True).start()


    try:
        while True:
            # Exit event loop there are no currently registered sockets to avoid errors
            """
            if not sel.get_map().keys():
                print("No sockets Registered")
                break
            """
            #Check for user input
            while not input_queue.empty():
                userCommand = input_queue.get()
                handle_user_command(userCommand)


            events = sel.select(timeout=None)
            for key, mask in events:
                if key.data.type == "sock":
                    handle_connection(key, mask)
                
    except KeyboardInterrupt:
        print("caught Keyboard Interrupt, Exiting")
    finally:
        sel.close()


if __name__ == "__main__":
    #Start connection to Server(Tracker)
    serverSock = open_connection(HOST, PORT)

    event_loop()



#print(f"Received {data!r}")
