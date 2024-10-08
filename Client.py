import socket
import sys
import selectors
import types
import errno
import struct
import os
import hashlib
import json
import math

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


def calc_number_of_chunks(file_path, chunk_size = CHUNKSIZE):
    if not os.path.exists(file_path):
        print(f"There does not exist a file at {file_path}.")
        return
    try:
        file_size = os.path.getsize(file_path)
        number_of_chunks = math.ceil(file_size / chunk_size)
        return number_of_chunks


    except Exception as e:
        print(f"Problem calculating chunk count for {file_path}: {e}")
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

def send_message_json(sock, message_dict):
    """
    Turn inputted dictionary into a JSON object, give it a length header, and package that message into bytes to be sent. Proceeds to add the message to the socket which it will be sent through's buffer
    """
    json_message = json.dumps(message_dict)
    json_message_byte_encoded = json_message.encode('utf-8')
    message_length = len(json_message_byte_encoded)
    header = struct.pack('!I', message_length)

    finalMessage = header + json_message_byte_encoded;

    key = sel.get_key(sock)
    data = key.data
    key.data.outgoing_buffer += finalMessage;


def unpack_json_message(received_message):
    json_message = received_message.decode('utf-8')

    return json.loads(json_message)


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

def debug_selector_map():
    # Iterate over the registered sockets in the selector
    for key, value in sel.get_map().items():
        print(f"File Object (key): {key}, SelectorKey (value): {value}, Data: {value.data}")

def get_server_socket():
    # Iterate over registered sockets in the selector
    for key, value in sel.get_map().items():
        #print(f"File Object (key): {key}, SelectorKey (value): {value}, Data: {value.data}")
        # Check if the registered data marks this as the server socket
        if isinstance(value.data, types.SimpleNamespace) and value.data.type == "server":
            return key  # Return the LITERALY server socket (key.fileobj) NOT THE SELECTORKEY
    print("Server socket not found.")
    return None


#Function to handle/process user input requests
def handle_user_command(command):

    server_sock = get_server_socket()

    outgoing_message = {
    "type": "",
    "content":"",
    }

    print(f"User requested completion of {command}")
    words = command.strip().split()


    if len(words) == 0:
        print(f"No command entered.")
        return

    action = words[0].lower()

    if action == "1":
        print(f"Requesting File List from Server:")
        outgoing_message["type"] = "FILELISTREQ"
        send_message_json(server_sock, outgoing_message)

    elif len(words) != 2:
        print(f"Command Not In Correct Format")
    
    elif action ==  "register":
        print(f"Attempting to register file {words[1]} with server")
        outgoing_message["type"] = "FILEREG"
        outgoing_message["content"] = words[1]

        #Add local filepath to words to filename
        file_path = adjust_for_storage_directory(words[1])

        outgoing_message["chunk_count"] = calc_number_of_chunks(file_path)
        send_message_json(server_sock, outgoing_message)
        

    elif action == "download":
        (f"Attempting to download file {words[1]} from system")


        

#With the decoded message and type passed in, this function should handle the Server's reaction to the message based on the type and content
def handle_message_reaction(sock, message):
    """

        Arguments:
            sock: Which connection sent the message (needed to send a return message)
            message_type: Decoded int representing what type of message we are reacting to
            message_content: Decoded content of message we are reacting to
    """
    message_type = message["type"]
    message_content = message["content"]


    outgoing_message = {
        "type": "",
        "content": ""
    }

    #File Registration Reply from Server. No outgoing message neccessary.
    if message_type == "FILEREGREPLY":
        if message_content["success"] == True:
            print(f"{message_content["filename"]} was registered successfully with the server")
        else:
            print(f"{message_content["filename"]} was not able to be registered with the server. Mayhaps it was already registered?")
        return

    #Chunk Registration Reply. No outgoing message neccessary.
    if message_type == "CHUNKREGREPLY":
        return
    
    #File List Reply from Server. No outgoing message neccessary.
    elif message_type == "FILELISTREPLY":
        print(f"File List Received From Server:")
        for each in message_content:
            print(each)
        return
    
    #File Location Reply from Server No outgoing message neccessary.
    elif message_type == "SENDCHUNK":
        return
    
    #Received chunk from other client. No outgoing message neccessary.
    elif message_type == "CHUNKACK":
        return
    
    #RECEIVED CHUNK REQUEST FROM OTHER CLIENT. REPLY NECCESSARY
    elif message_type == 105:
        outgoing_message["type"] = "SENDCHUNK"
        
        send_message_json(outgoing_message)
    
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

                    message = unpack_json_message(message)
                    #NEED TO PROCESS MESSAGE HERE (For now just print the processed message)
                    print(message)

                    handle_message_reaction(sock, message)

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

    msg = {
        "type": "Yaahhhhh",
        "content": "yaaahhhh"
    }
    send_message_json(serverSock, msg)
    event_loop()



#print(f"Received {data!r}")