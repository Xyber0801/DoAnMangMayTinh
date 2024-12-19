import socket
import client
import threading
import struct
import hashlib
import select

class Server:
    def __init__(self, ip = 'localhost', port = 54321, max_clients_num = 100, sockets_per_client = 4):
        self.max_clients_num = max_clients_num
        self.sockets_per_client = sockets_per_client
        self.clients = []
        self.lock = threading.Lock()

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((ip, port))
        self.socket.listen(max_clients_num * sockets_per_client)
        print(f"Server is listening for connections on port {port}")

    def send_list_of_files(self, client_socket):
        with open("list.txt", "r") as f:
            data = f.read()
            client_socket.send(data.encode())

    def accept_connections(self):
        try:
            client_socket, address = self.socket.accept()
            id = int(client_socket.recv(1024).decode()) # Receive the id of the client
            print(f"Connection from {address} has been established with id: {id}!")
            
            for _client in self.clients:
                if _client.id == id:
                    _client.sockets.append(client_socket)
                    return
                    
            #If the client is not in the list, add a new client
            self.add_client(client.Client(id, [client_socket]))
        
        except KeyboardInterrupt:
            del self
            raise KeyboardInterrupt

    def add_client(self, client):
        self.clients.append(client)
        print(f"Client {client.id} has been added to the clients list")
        self.send_list_of_files(client.sockets[0])

    def create_packet(self, index, payload):
        chunk_size = len(payload)
        checksum = payload
        hash = hashlib.blake2s(digest_size=16)
        hash.update(checksum)
        checksum = hash.digest()

        header = struct.pack('<B I 16s', index, chunk_size, checksum)

        return header + payload


    def handle_client(self, client):
        client.being_handled = True # Prevent other threads from handling the same client

        while True:
            if len(client.sockets) < self.sockets_per_client:
                continue

            ready_to_read, _, _ = select.select(client.sockets, [], [], 0.1)
            for client_socket in ready_to_read:
                data = client_socket.recv(1024).decode().rstrip('\n')  # Receive filename or exit command
                if not data:
                    continue

                print(f"(out)received '{data}'") # debug

                if data == "exit":
                    print(f"Client {client.id} has disconnected!")
                    self.clients.remove(client)
                    return

                # Send the file to the client
                requested_file = None
                if data.startswith("get "):
                    requested_file = data.split()[1]
                    print(f"Client {client.id} requested file: {data}")

                with open(f'{requested_file}', 'rb') as file:
                    file_size = len(file.read())
                    chunk_size = file_size // self.sockets_per_client
                    file.seek(0)

                    packets = []
                    for i in range(self.sockets_per_client):
                        chunk = file.read(chunk_size)
                        packet = self.create_packet(i, chunk)
                        packets.append(packet)
                    
                    # client.sockets[0].send(str(chunk_size).encode()) # Send chunk size to the client

                    threads = [] # List of threads, each thread sends a chunk to a client
                    for i in range(len(client.sockets)):
                        thread = threading.Thread(target = self.send_file, args = (client.sockets[i], packets[i]))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()

                    # Listen for potential retranmissions from the client
                    while True:
                        ready_to_read, _, _ = select.select(client.sockets, [], [], 0.1)
                        file_sent_successfully = False
                        for client_socket in ready_to_read:
                            data = client_socket.recv(1024).decode().rstrip('\n')  # Receive filename or exit command
                            if not data:
                                continue
                            print(f"received '{data}'") # debug

                            if data == "exit":
                                print(f"Client {client.id} has disconnected!")
                                self.clients.remove(client)
                                return
                            
                            if data == "ACK":
                                print(f"File {requested_file} has been sent to client {client.id}")
                                file_sent_successfully = True
                                break

                            if data.startswith("getchunk"):
                                chunk_index = int(data.split()[1])
                                print(f"Client {client.id} requested retransmission of chunk {chunk_index}")
                                thread = threading.Thread(target=self.send_file, args=(client.sockets[chunk_index], packets[chunk_index]))
                                thread.start()
                                thread.join()

                        if file_sent_successfully:
                            break
                        
                    for thread in threads:
                        threads.remove(thread)
        
    def send_file(self, client_socket, file):
        client_socket.sendall(file)

    def __del__(self):
        self.socket.close()
            