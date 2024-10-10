import socket
import threading
import selectors
import types
import struct
import json

sel = selectors.DefaultSelector()


HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)


#Use Dictionaries to store which files we have, which users have that file, and which chunks each file has.
file_list = {
    "file1": #Format for example
    {
        "hash": "931231923etc.", #Hashcode to differentiate that files with different names are actually same file
        "chunkCount": "", #Count of Chunks in file to make sure peers can't register the presence of non existing chunks
        #List of users with parts of the file, "Key here will be a cid string assigned when a connection is established"
        "users":
        {
            "user1": {"chunks" : {0, 1, 2}},
        },
    },
}

connections = 0

lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, PORT))
    
print("Listening on " +  str(PORT))
lsock.listen()

lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)


def send_message_json(sock, message_json):
    """
    Adds a length header to the inputted JSON message and packages that message into bytes to be sent. Proceeds to add the message to the socket which it will be sent through's buffer
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

#With the decoded message and type passed in, this function should handle the Server's reaction to the message based on the type and content
def handle_message_reaction(sock, message_type, message_content):
    """

        Arguments:
            sock: Which connection sent the message (needed to send a return message)
            message_type: Decoded int representing what type of message we are reacting to
            message_content: Decoded content of message we are reacting to
    """

    outgoing_message = {
        "type": "",
        "content": ""
    }

    #File Registration from Client. Outgoing Message Neccessary.
    if message_type == "FILEREG":
        return

    #Chunk Registration from Client. Outgoing Message Neccessary.
    if message_type == "CHUNKREG":
        return
    
    #File List Request from Client. Outgoing Message Neccessary.
    elif message_type == "FILELISTREQ":
        return
    
    #File Location Request from Server Outgoing Message Neccessary.
    elif message_type == "FILELOCREQ":
        return
    
    else:
        print(f"Unknown message Type received: {message_type}: {message_content} ", )

def accept_incoming_connection(sock):
    conn, addr = sock.accept() #Socket should already be read to read if this fn is called
    global connections

    conn.setblocking(False)
    connections += 1
    
    newCid = 'conn' + str(connections)
    print(f"Accepted connection from {addr}, gave cid: {newCid}")

    #Buffers will be registered to each socket for incoming and outgoing data to ensure no data is lost from incomplete sends and receives.
    data = types.SimpleNamespace(
            cid = newCid,
            type = 'client', #Assuming 1 server, server only deals with client connections

            incoming_buffer = b'',
            messageLength = None, #to record how many bytes we should expect an incoming message to be (to make sure we receive messages in their entirety)

            outgoing_buffer =  b'',
        )
    
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    sel.register(conn, events, data = data)


def handle_connection(key, mask):
    sock = key.fileobj
    data = key.data

    #print(data)
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
                print(message)
                
                #Server's reaction to message
                handle_message_reaction(sock, message["type"], message["content"])

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


try:
    while True:
        events = sel.select(timeout = None)
        for key, mask in events:
            if key.data is None:
                accept_incoming_connection(key.fileobj)
            else:
                handle_connection(key, mask)
except KeyboardInterrupt:
    print("Caught keyboard interrupt, exiting")
finally:
    sel.close()

