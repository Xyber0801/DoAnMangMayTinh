import socket
import client
import threading

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

    def handle_client(self, client):
        client.being_handled = True # Prevent other threads from handling the same client

        while True:
            if len(client.sockets) < self.sockets_per_client:
                continue

            for client_socket in client.sockets:
                data = client_socket.recv(1024).decode(); # Receive filename or exit command
                if not data:
                    continue

                if data == "exit":
                    print(f"Client {client.id} has disconnected!")
                    self.clients.remove(client)
                    del client
                    return

                # Send the file to the client
                print(f"Client {client.id} requested file: {data}")

                with open(f'{data}', 'rb') as file:
                    file_size = len(file.read())
                    chunk_size = file_size // self.sockets_per_client
                    file.seek(0)
                    
                    client.sockets[0].send(str(chunk_size).encode()) # Send chunk size to the client

                    threads = [] # List of threads, each thread sends a chunk to a client
                    for _socket in client.sockets:
                        thread = threading.Thread(target = self.send_file, args = (_socket, file, chunk_size))
                        threads.append(thread)
                        thread.start()

                    for thread in threads:
                        thread.join()

                    print(f"File {data} has been sent to client {client.id}")

    def send_file(self, client_socket, file, chunk_size):
        while True:
            with self.lock: # Lock the file to prevent other threads from reading it
                data = file.read(chunk_size);
            if not data:
                break
            client_socket.sendall(data)

    def __del__(self):
        self.socket.close()
            