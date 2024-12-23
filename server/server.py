import socket
import client
import threading
import struct
import hashlib
import select

class Server:
    def __init__(self, ip = '0.0.0.0', port = 54321, max_clients_num = 100, sockets_per_client = 4):
        self.max_clients_num = max_clients_num
        self.sockets_per_client = sockets_per_client
        self.clients = []
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.command_queue = []

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((ip, port))
        self.socket.listen(max_clients_num * sockets_per_client)
        print(f"Server is listening for connections on port {port}")

    def send_list_of_files(self, client_socket):
        try:
            with open("list.txt", "r", encoding="utf-8") as f:
                data = f.read()
            client_socket.send(data.encode("utf-8"))
        except UnicodeEncodeError:
            with open("list.txt", "r", encoding="latin-1") as f:
                data = f.read()
            client_socket.send(data.encode("latin-1"))

    def accept_connections(self):
        try:
            client_socket, address = self.socket.accept()
            id = int(client_socket.recv(1024).decode()) # Receive the id of the client
            # print(f"Connection from {address} has been established with id: {id}!")
            
            for _client in self.clients:
                if _client.id == id:
                    _client.sockets.append(client_socket)
                    return
                    
            #If the client is not in the list, add a new client
            self.add_client(client.Client(id, [client_socket]))
        
        except KeyboardInterrupt:
            self.stop_event.set()

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
        # Packets to be sent to the client
        packets = []

        try:
            while not self.stop_event.is_set():
                if len(client.sockets) < self.sockets_per_client:
                    continue

                ready_to_read, _, _ = select.select(client.sockets, [], [], 0.1)
                for client_socket in ready_to_read:
                    data = client_socket.recv(1024).decode().rstrip('\n')  # Receive filename or exit command
                    if not data:
                        continue
                    
                    commands = data.split('\n')
                    for command in commands:
                        command = command.strip()
                        if command:
                            self.command_queue.append(command)

                    while (len(self.command_queue) > 0):
                        command = self.command_queue.pop(0)

                        if command == "exit":
                            print(f"Client {client.id} has disconnected!")
                            self.clients.remove(client)
                            return

                        # Send the file to the client
                        if command.startswith("get "):
                            requested_file = " ".join(command.split()[1:])
                            print(f"Client {client.id} requested file: {requested_file}")
                    
                            with open(f'files/{requested_file}', 'rb') as file:
                                file_size = len(file.read())
                                chunk_size = file_size // self.sockets_per_client
                                file.seek(0)
                                
                                for i in range(self.sockets_per_client):
                                    chunk = file.read(chunk_size)
                                    packet = self.create_packet(i, chunk)
                                    packets.append(packet)

                                threads = [] # List of threads, each thread sends a chunk to a client
                                for i in range(len(client.sockets)):
                                    thread = threading.Thread(target = self.send_file, args = (client.sockets[i], packets[i]))
                                    threads.append(thread)
                                    thread.start()

                                for thread in threads:
                                    thread.join()
                            
                        if command == "ACK":
                            print(f"File {requested_file} has been successfully sent to client {client.id}")
                            packets = []

                        if command.startswith("getchunk"):
                            chunk_index = int(command.split()[1])
                            print(f"Client {client.id} requested retransmission of chunk {chunk_index}")
                            thread = threading.Thread(target=self.send_file, args=(client.sockets[chunk_index], packets[chunk_index]))
                            thread.start()
                            thread.join()
        
        except Exception as e:
            if isinstance(e, KeyboardInterrupt):
                self.stop_event.set()
            else:
                print(e)
        
    def send_file(self, client_socket, file):
        client_socket.sendall(file)

    def __del__(self):
        self.socket.close()
            