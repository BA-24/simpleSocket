from traceback import format_exc
import threading
import socket
import time

class Server:

    def __init__(
        self, 
        ip="127.0.0.1", 
        port=1337, 
        interpreter=print, 
        splitCmdStr=None, 
        splitArgStr=None, 
        readLen=1024, 
        retryAddress=True, 
        autoDisconnect=False,
        welcomeString=b"Valkommen",
        clientAgnostic=True
        ):

        self.ip         = ip
        self.port       = port
        self.socket     = None
        self.clients    = []

        self.autoDisconnect = autoDisconnect # whether to disconnect the client after receiving the first messages (REST-esque)
        self.welcomeString  = welcomeString # the string to send to the client on connection
        self.retryAddress   = retryAddress # whether to retry binding to the address if binding fails
        self.interpreter    = interpreter # where to send the (parsed) data
        self.splitCmdStr    = splitCmdStr # delimeter used to separate commands (ex. "\n")
        self.splitArgStr    = splitArgStr # delimiter used to separate arguments (ex. " ")
        self.readLen        = readLen # how many bytes to read from the stream at once

        if clientAgnostic: # if the client should be included to the interpreter
            self.recver = self.recver_clientAgnostic
        

    def accepter(self):
        # loop to continuously accept new incoming connections
        
        connected = False
        
        while not connected:
            
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.bind((self.ip, self.port))
                self.socket.listen(5) # https://docs.python.org/3/library/socket.html#socket.socket.listen

                print("receiver started\n") # redundant new line for thread safer printing
                connected = True

            except OSError as error:
                if self.retryAddress:
                    print("Address already in use. Waiting 4 seconds.")
                    time.sleep(4)
                    
                else:
                    raise error # propagate 

        while True:
            try:
                client, address = self.socket.accept()
                self.clients.append(client)
                
                if self.welcomeString: client.send(self.welcomeString)
                    
                print(f"Connection from {address} has been accepted.")
                self.threcver(client)
                
            except OSError: # from previous testing, "self.socket.accept()" throws an OSError when the socket is shutdown, so we want to exit quietely.
                pass
            


    def recver(self, client):
        while True:
            try:
                received = client.recv(self.readLen)
                if received:
                    self.process(received, client)
                    if self.autoDisconnect:
                        try: self.clients.remove(client)
                        except Exception: pass
                        client.close()
                        return
                    
            except Exception as e:
                try: peername = client.getpeername()
                except Exception: peername = client

                if client:
                    print(f"Error trying to receive from {peername}. Stopping receiver.")
                    try: self.clients.remove(client)
                    except Exception: pass
                    client.close()
                    
                else: print(f"Encountered error in receiver: {str(e)}")

                return


    def recver_clientAgnostic(self, client):
        while True:
            try:
                received = client.recv(self.readLen)
                if received:
                    self.process(received)
                    if self.autoDisconnect:
                        try: self.clients.remove(client)
                        except Exception: pass
                        client.close()
                        return
                    
            except Exception as e:
                try: peername = client.getpeername()
                except Exception: peername = client
                print(format_exc())

                if client:
                    print(f"Error trying to receive from {peername}. Stopping receiver.")
                    try: self.clients.remove(client)
                    except Exception: pass
                    client.close()
                    
                else: print(f"Encountered error in receiver: {str(e)}")

                return


    def threcver(self, socket):
        threading.Thread(target=self.recver, args=[socket], daemon=True).start()


    def sendAll(self, payload: bytes): # send "payload" to all connected clients
        for client in self.clients:
            try:
                client.sendall(payload)

            except Exception:
                try: peername = client.getpeername()
                except Exception: peername = None
                
                print(f"Error trying to send to {peername or client}. Shutting Down.")
                
                self.clients.remove(client) # this order of removing and closing client is used to 
                client.close()              # ensure that a broken client doesn't stay in self.clients


    def start(self):
        threading.Thread(target=self.accepter, daemon=True).start()


    def process(self, msg, *client): # processes received data
        if self.interpreter: # if no interpreter is given, discard the data
            
            if self.splitCmdStr:
                for cmd in msg.split(self.splitCmdStr):
                    
                    if self.splitArgStr:
                        args = cmd.split(self.splitArgStr)
                        self.interpreter(*args)

                    else: self.interpreter(cmd)
                        
            elif self.splitArgStr: self.interpreter(*msg.split(self.splitArgStr))

            else: self.interpreter(*(msg, *client))


    def close(self): # A function to properly close down self.socket
        try:
            self.socket.shutdown(socket.SHUT_RDWR) # close the socket for receiving and sending
        except OSError:
            pass # this happens sometimes

        self.socket.close()


class Client:

    def __init__(self, ip="127.0.0.1", port=1337, interpreter=print, readLen=10124, retryAddress=True):
        self.ip           = ip
        self.port         = port
        self.interpreter  = interpreter
        self.server       = None
        self.retryAddress = retryAddress
        self.readLen      = readLen


    def connect(self):
        connected = False
        while not connected:
            try:
                self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server.connect((self.ip, self.port))

                print("connected\n")
                connected = True

            except ConnectionRefusedError as error:
                if self.retryAddress:
                    print("Could not connect to server. Waiting 4 seconds.")
                    time.sleep(4)
                else:
                    raise error

        self.threcver(self.server)
                

    def recver(self, client):
        while True:
            try:
                received = client.recv(self.readLen)
                if received and self.interpreter:
                    self.interpreter(received.decode())
                    
            except Exception as e:
                try: peername = client.getpeername()
                except Exception: peername = None

                if client: print(f"Error trying to receive from {peername}. Stopping receiver.")
                else: print(f"Encountered error in receiver: {str(e)}")
                
                client.close()
                return
                
                print(f"Encountered error: {str(e)}")
                print(f"Error trying to receive from {client.getpeername()}. Shutting Down.")
                client.close()
                return


    def threcver(self, socket):
        threading.Thread(target=self.recver, args=[socket], daemon=True).start()


    def send(self, payload):
        self.server.send(payload)
