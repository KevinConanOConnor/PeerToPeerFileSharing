import socket
import threading
import selectors
import types
import struct

sel = selectors.DefaultSelector()


HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)

connections = 0;

lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, PORT))
    
print("Listening on " +  str(PORT))
lsock.listen()

sharedFileList = []

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

lsock.setblocking(False)
sel.register(lsock, selectors.EVENT_READ, data=None)


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
    Unpackage message will handle the unpacking of messages received.  WI
        Arguments:
            message: message data in bytes form, should still contain header data without the length (, 4 bytes type)
        
    """

    #Unpack the type, will handle types of messages and different formats of contents later
    message_type = struct.unpack('!I', message[:4])[0]

    message_content = message[4:].decode('utf-8')

    return (message_type, message_content)
    

    print("placeholder")

def accept_incoming_connection(sock):
    conn, addr = sock.accept() #Socket should already be read to read if this fn is called

    print(f"Accepted connection from {addr}")
    conn.setblocking(False)

    #Buffers will be registered to each socket for incoming and outgoing data to ensure no data is lost from incomplete sends and receives.
    data = types.SimpleNamespace(
            type = 'client', #Assuming 1 server, server only deals with client connections

            incoming_buffer = b'',
            messageLength = None, #to record how many bytes we should expect an incoming message to be (to make sure we receive messages in their entirety)

            outgoing_buffer =  b'',
        )
    
    events = selectors.EVENT_READ | selectors.EVENT_WRITE

    sel.register(conn, events, data = data)


#This function will send a message of a fixed length to a packet. This function should receive the information of an open socket connection. It should also receive a message in bit format to be sent 
def send_message(sock, message):
    """
    send_message will handle the adding of messages to an outgoing socket buffer. This function will take in a message that should have already been packaged
    into a bit readable format for the receiver. (call package_message first)
    """
    key = sel.get_key(sock)
    data = key.data

    key.data.outgoing_buffer += message;  


#With the decoded message and type passed in, this function should handle the Server's reaction to the message based on the type and content
def handle_message_reaction(sock, message_type, message_content):
    if message_type == 1:
        print(message_content)
        send_message(sock, package_message(2, "I actually don't know what to do for the file list yet lol"))
    else:
        send_message(sock, package_message(0, "Message Type Not Recognized"))


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

                #NEED TO PROCESS MESSAGE HERE (For now just print the processed message)
                (message_type, message_content) = unpackage_message(message)
                
                #Server's reaction to message
                handle_message_reaction(sock, message_type, message_content)


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


while True:
    try:
        events = sel.select(timeout = None)
        for key, mask in events:
            if key.data is None:
                accept_incoming_connection(key.fileobj)
            else:
                handle_connection(key, mask)
    except KeyboardInterrupt:
        print("Caught keyboard interrupt, exiting")
    except Exception as e:
        print(f"An error occured")

sel.close()

