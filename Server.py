import socket
import threading
import selectors
import types
import struct

sel = selectors.DefaultSelector()


HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 65432  # Port to listen on (non-privileged ports are > 1023)


lsock =  socket.socket(socket.AF_INET, socket.SOCK_STREAM)
lsock.bind((HOST, PORT))
    
print("Listening on " +  str(PORT))
lsock.listen()

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
    Unpackage message will handle the interpretation of messages received. 
        Arguments:
            message: message data in bytes form, should still contain header data without the length (, 4 bytes type)
        
    """

    #Unpack the type, will handle types of messages and different formats of contents later
    message_type = struct.unpack('!I', message[:4])[0]

    message_content = message[4:].decode('utf-8')

    return message_content
    

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

"""
def service_connection(key, mask):
    sock = key.fileobj
    data = key.data
    #print(data)

    if mask & selectors.EVENT_READ:
        #try:
        recv_data = sock.recv(1024) #Should be ready to read
        #except Exception as e:
         #   print("Unhandled Read Error")
            
        if recv_data:
            print(recv_data)
            data.inb += recv_data
        else:
            print(f"Closing connection {data.addr}")
            sel.unregister(sock)
            sock.close()

    if mask & selectors.EVENT_WRITE:
        if data.outb:
            print(f"Echoing {data.outb!r} to {data.addr}")
            sent = sock.send(data.outb) #Should be ready to write
            data.outb = data.outb[sent:]
"""

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