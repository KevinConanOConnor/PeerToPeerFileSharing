import socket
import sys
import selectors
import types
import errno
import struct


#User input handled on a separate thread from sockets
import threading
import queue

HOST = "127.0.0.1"  # The server's hostname or IP address, 127.0.0.1 is localhost 
PORT = 65432  # The port used by the server

connections = 0;

sel = selectors.DefaultSelector()
input_queue = queue.Queue() #Queue to handle user requests


#Open up a listening socket so that the client can listen for other P2P connections
lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, 0))
    
print("Client Listening on " +  str(lsock))
lsock.listen()

lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)

#Function to receive input from the user (e.g. ask server what files are available, ask to download files)
def receive_user_input():
    while True:
        user_input = input("Enter command:")
        if user_input:
            input_queue.put(user_input) #Send input to this queue, when this queue is full it should be handled

#Function to handle/process user input requests
def handle_user_command(command):
        print(f"User requested completion of {command}")


def register_socket_selector(sock, selector = sel, connection_type = "client"):
    """
    Register socket connection to be handled by a selector

    Arguments:
          sock: socket to be registered
          selector: selector object to register socket to (default is sel, a global selector)
          connection_type: Data to be stored for each connection so we can differentiate types of connection (probably just client vs server)
    
    Returns: N/A
    """
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    
    #Buffers will be registered to each socket for incoming and outgoing data to ensure no data is lost from incomplete sends and receives.
    data = types.SimpleNamespace(
            type = connection_type,

            incoming_buffer = b'',
            messageLength = None, #to record how many bytes we should expect an incoming message to be (to make sure we receive messages in their entirety)

            outgoing_buffer =  b'',
        )
    
    sel.register(sock, events, data = data)


def open_server_connection(ip = HOST, port_number = PORT, timeout = 5):
    """
    Connect to a server using the host and port specified as file constants. This connection will be handled in a blocking manner at first,
    as there is no reason to worry about blocking other messages before we have even established a connection with the central server

    Arguments:
        ip:
        port_number:
        timeout: The number of seconds you would like to wait before timing out the server    
    
    Returns:
        socket: The connected socket if successful, or None if the connection fails.

    Raises:
        socket.timeout: If the connection attempt exceeds the specified timeout.
        ConnectionRefusedError: If the server is not accepting connections (Server.py probably not running on it)
    """
    server_addr = (ip, port_number)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(server_addr)
        print(f"Connected to Main Server at {server_addr}")

        # Change connection to non blocking after connection is opened
        sock.setblocking(False)

        register_socket_selector(sock = sock, connection_type = "server")
        
        return sock

    except Exception as e:
        print(f"Error Occured trying to establish connection to main server")


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

    register_socket_selector(sock = sock)

    return sock

def accept_incoming_connection(sock):
    conn, addr = sock.accept() #Socket should already be read to read if this fn is called

    connections += 1
    newCid = "inc" + connections

    print(f"Accepted connection {connections} from {addr} and assigned {newCid}")
    conn.setblocking(False)

    #Buffers will be registered to each socket for incoming and outgoing data to ensure no data is lost from incomplete sends and receives.
    data = types.SimpleNamespace(
            type = 'client', #Client only receives new connections with client connections

            cid = newCid,
            incoming_buffer = b'',
            messageLength = None, #to record how many bytes we should expect an incoming message to be (to make sure we receive messages in their entirety)

            outgoing_buffer =  b'',
        )
    
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    sel.register(conn, events, data = data)

def close_connection(sock):
    sel.unregister(sock)
    sock.close()

def package_message(message_type, message_content):
    """
    package_message will handle the packaging of messages into a format receivable by clients and peers in our system. Returns a message encoded into bytes.
    """
    content_bytes = message_content.encode('utf-8')

    #The length of the message is 4 for type header (int) + content bytes
    message_length = 4 + len(content_bytes)
    #Pack message length as (4 bytes int) and message type as 4 bytes int, all in network byte order (!)
    header = struct.pack('!I I', message_length, message_type)

    finalMessage = header + content_bytes
    return finalMessage

def unpackage_message(message):
    """
    Unpackage message will handle the interpretation of messages received. 
        Arguments:
            message: message data in bytes form, should still contain header data without the length (, 4 bytes type)
        
    """

    #Unpack the type, will handle types of messages and different formats of contents later
    message_type = struct.unpack('!I', message[:4])[0]

    message_content = message[4:].decode('utf-8')

    return message_content
    

    print("placeholder")

#This function will send a message of a fixed length to a packet. This function should receive the information of an open socket connection. It should also receive a message in bit format to be sent 
def send_message(sock, message):
    """
    send_message will handle the adding of messages to an outgoing socket buffer. This function will take in a message that should have already been packaged
    into a bit readable format for the receiver. (call package_message first)
    """
    key = sel.get_key(sock)
    data = key.data

    key.data.outgoing_buffer += message;    

def handle_connection(key, mask):
    sock = key.fileobj
    data = key.data

    #print(data)
    if mask & selectors.EVENT_READ: #Ready to read data
        #Handle case where socket is the listening socket handling a new P2P connection
        if data is None:
            accept_incoming_connection(sock)

        received = sock.recv(1024)

        if received:
            print(f"Received: {data}")
            data.incoming_buffer += received

            #If we don't know the incoming message length yet. We should try to read it
            if data.messageLength is None and len(data.incoming_buffer) >= 4:
                #We can extract first 4 bytes as this is the message length prefix
                data.messageLength = struct.unpack('!I', data.incoming_buffer[:4])[0] #
                data.incoming_buffer = data.incoming_buffer[4:]
                print(f"Expected Message Length {data.messageLength} bytes")

            #If we do know the message length, we should process/clear incoming buffer once it has been fully received
            if data.messageLength is not None and len(data.incoming_buffer) >= data.messageLength:
                message = data.incoming_buffer[:data.messageLength]

                #NEED TO PROCESS MESSAGE HERE (For now just print the processed message)
                print(unpackage_message(message))

                data.incoming_buffer = data.incoming_buffer[data.messageLength: ] #Clear the message from buffer
                data.messageLength = None #Reset message length so that we know there's no message currently


            # For demonstration, we immediately echo back the received data
            #data.outgoing_buffer += received  # Add it to outgoing buffer to echo it back
        else: #If 0 bytes received, client closed connection
            print(f"Closing connection to {sock}")
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
                    handle_connection(key, mask)
                
    except KeyboardInterrupt:
        print("caught Keyboard Interrupt, Exiting")
    finally:
        sel.close()


if __name__ == "__main__":
    #Start connection to Server(Tracker)
    serverSock = open_server_connection()

    msg = package_message(1, "I speak the truth in Christ—I am not lying, my conscience confirms it through the Holy Spirit— 2 I have great sorrow and unceasing anguish in my heart. 3 For I could wish that I myself were cursed and cut off from Christ for the sake of my people, those of my own race, 4 the people of Israel. Theirs is the adoption to sonship; theirs the divine glory, the covenants, the receiving of the law, the temple worship and the promises. 5 Theirs are the patriarchs, and from them is traced the human ancestry of the Messiah, who is God over all, forever praised![a] Amen.")
    send_message(serverSock, msg)
    event_loop()



#print(f"Received {data!r}")
