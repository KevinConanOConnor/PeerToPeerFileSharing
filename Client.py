import socket
import sys
import selectors
import types
import errno
import struct
import os
import hashlib

#User input handled on a separate thread from sockets
import threading
import queue

HOST = "127.0.0.1"  # The server's hostname or IP address, 127.0.0.1 is localhost 
PORT = 65432  # The port used by the server
FILEPATH = ""
CHUNKSIZE = 4096 #Bytes

dir = os.path.dirname(os.path.abspath(__file__))

#print(f'Current Directory:')
#print(dir)
FILEPATH = os.path.join(dir, 'files') #For where to share files from and download shared files to
#print(FILEPATH)
    
sel = selectors.DefaultSelector()
input_queue = queue.Queue() #Queue to handle user requests
###########################################################################################################################################
#HASHING CODE

def calc_file_hash(file_path):
    hash_sha256 = hashlib.sha256()

    try:
        with open(file_path, "rb") as file:
            while chunk := file.read(4096):
                hash_sha256.update(chunk)
    except Exception as e:
        print(f"Error hashing file at {file_path}")
        return
    return hash_sha256.hexdigest()


def calc_chunk_hash(chunk):
    hash_sha256 = hashlib.sha256()
    try:
        hash_sha256.update(chunk)
    except Exception as e:
        print(f"Error hashing chunk: {chunk}")
        return
    return hash_sha256.hexdigest()
        

###########################################################################################################################################
# CLIENT SIDE LISTENING SOCKET CODE
lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, 0))
    
print("Listening on ", lsock)
lsock.listen()

lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=types.SimpleNamespace(type = 'lsock'))


###########################################################################################################################################
# CLIENT SIDE LOCAL FILE MODIFICATION CODE
def adjust_for_storage_directory(fileName, path = FILEPATH):
    """
    Code for adjusting fileName's to include the filepath of our storage directory since I will need to reuse this a lot.
    """
    return os.path.join(FILEPATH, fileName)


def get_files_in_directory(directory = FILEPATH):
    try:
        with os.scandir(directory) as files:
            for file in files: # Print the name of all files in the directory
                if file.is_file():
                    print(file.name)

    except Exception as e:
        print(f"Error accessing directory: {directory}")
        print(f"{e}")


def initialize_file(file_path, file_size):
    #Check that file path is not already in use.
    if os.path.exists(file_path):
        print(f"There already exists a file at {file_path}. User should check before downloading over.")
        return

    #otherwise open a new file there in write mode
    with open(file_path, 'wb') as file:
        file.seek(file_size - 1)
        file.write(b'\0') #Setting a null byte at the end will give us a file of the correct size
    
    print(f"File of {file_size} bytes has been created at {file_path}")


def peek_chunk(file_path, chunk_index, chunk_size = CHUNKSIZE):
    try:
        with open(file_path, 'rb') as file:
            spot = chunk_index * chunk_size
            file.seek(spot)
            
            chunk_content = file.read(chunk_size)

            #Debugging
            print(f"Peeked chunk {chunk_index} at {file_path}")

            return chunk_content

    except OSError as e:
        print(f"Error reading chunk {chunk_index} in {file_path}: {e}")
        return None

def set_chunk(file_path, chunk_index, chunk_content, chunk_size = CHUNKSIZE):
    try:
        with open(file_path, 'r+b') as file:
            spot = chunk_index * chunk_size
            file.seek(spot)
            
            chunk_content = file.write(chunk_content)

            #Debugging
            print(f"Set chunk {chunk_index} at {file_path}")

            return chunk_content

    except OSError as e:
        print(f"Error setting chunk {chunk_index} in {file_path}: {e}")
        return None

#Testing that raeding and writing an entire file works on single system (the current client duh)
def chunksFunctionsTest():
    initialize_file("testfile", 4096)
    set_chunk("testfile", 0 , b"hey dude the empire is pretty cool, maybe you should like, join it or something")
    print(peek_chunk("testfile", 0))


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
    """
    open_connection is for connecting to other client on a specified ip and port_number. This function returns the generated socket connection.
    """
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

def close_connection(sock):
    """
    close_connection takes in an open socket connection, removes from the global Selector sel and closes the socket.
    """
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
    
#Function to receive input from the user (e.g. ask server what files are available, ask to download files)
def receive_user_input():
    while True:
        print(f"")
        print(f"Files that you can share:")
        get_files_in_directory()

        print(f"")
        print(f"Possible commands:")
        print(f"1 - Request File List from Server FORMAT: 1")
        print(f"2 - Register File with Server. FORMAT: Register filename.txt")
        print(f"3 - Initiate Download of File from Server FORMAT: Download filename.txt (from list given by server)")
        print(f"")

        user_input = input("Enter command:")
        if user_input:
            input_queue.put(user_input) #Send input to this queue, when this queue is full it should be handled

def register_file(file_name):
    actualPath = adjust_for_storage_directory(file_name)


    if not os.path.exists(file_name):
        print(f"The file {file_name} is not present in your files directory")
        return
    
    #DEFINE File Registration Message Sizes so that sender knows how many bytes each string will be
    FILENAME_SIZE = 50
    HASH_SIZE = 64


    filesize = os.path.getsize(FILEPATH)


    #Calculate Chunk Size
    
    print('blah')


#Function to handle/process user input requests
def handle_user_command(command):
        print(f"User requested completion of {command}")
        words = command.strip().split()

        if len(words) == 0:
            print(f"No command entered.")
            return
    
        action = words[0].lower()

        if action == "1":
            print(f"Requesting File List from Server:")

        elif len(words) != 2:
            print(f"Command Not In Correct Format")
        
        elif action ==  "register":
            print(f"Attempting to register file {words[1]} with server")

        elif action == "download":
            (f"Attempting to download file {words[1]} from system")


        

#With the decoded message and type passed in, this function should handle the Server's reaction to the message based on the type and content
def handle_message_reaction(sock, message_type, message_content):
    """

        Arguments:
            sock: Which connection sent the message (needed to send a return message)
            message_type: Decoded int representing which code this corresponds to
            message_content: Decoded content of message
    """

    #File Registration Reply from Server
    if message_type == 2:
        print(message_content)
        send_message(sock, package_message(2, f"I actually don't know what to do for the file list yet lol"))

    #Chunk Registration Reply
    if message_type == 4:
        print("placeholder")

    #File List Reply from Server
    elif message_type == 102:
        send_message(sock, package_message(0, f"Message Type Not Recognized"))

    #File Location Reply from Server
    elif message_type == 104:
        print(f"placeholder")

    #Received chunk from other client
    elif message_type == 106:
        print(f"placeholder")
    
    else:
        print(f"Unknown message Type received: {message_type}: {message_content} ", )


def handle_connection(key, mask):
    sock = key.fileobj
    data = key.data

    #print(data)
    if data.type == 'lsock':
        try:
            #handle accepting connections on the listening socket
            conn, addr = sock.accept();
            print(f"Accepted connection from {addr}")
            conn.setblocking(False)
            register_socket_selector(conn)
        except Exception as e:
            print(f"Problem with accepting connection to peer")
    else:
        if mask & selectors.EVENT_READ: #Ready to read data
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

    #chunksFunctionsTest();

    msg = package_message(1, "I speak the truth in Christ—I am not lying, my conscience confirms it through the Holy Spirit— 2 I have great sorrow and unceasing anguish in my heart. 3 For I could wish that I myself were cursed and cut off from Christ for the sake of my people, those of my own race, 4 the people of Israel. Theirs is the adoption to sonship; theirs the divine glory, the covenants, the receiving of the law, the temple worship and the promises. 5 Theirs are the patriarchs, and from them is traced the human ancestry of the Messiah, who is God over all, forever praised![a] Amen.")
    send_message(serverSock, msg)
    event_loop()



#print(f"Received {data!r}")