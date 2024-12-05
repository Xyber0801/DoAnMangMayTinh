import socket
import threading
import os
import sys
import random
import struct

class Client:
    def  __init__(self,  server_addr = ('localhost', 12345), socket_count = 4):
        self.sockets = []
        self.socket_count = socket_count
        self.id = random.randrange(0, 1000000)
        self.progresses = [0] * 4 # Progresses of each download thread
        self.chunk_size = 0
        self.received_list_of_files = False

        self.lock = threading.Lock()

        for i in range(self.socket_count):
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_addr)
            self.sockets.append(client_socket)
            print(f"Connected to server with id: {self.id}")

        #send the id to the server
        for _socket in self.sockets:
            _socket.send(str(self.id).encode())

    def receive_list_of_files(self):
        # Loop through the sockets and receive the list of files (only one socket will receive the list)
        for _socket in self.sockets:
            data = _socket.recv(1024).decode()
            if not data:
                continue
            print(f"List of files:\n{data}")
            self.received_list_of_files = True
            break

    def send_file_request(self, filename):
        print(f"{len(self.sockets)} sockets are connected")

        print(f"Requesting file: {filename}")
        self.sockets[0].send(filename.encode())

    def print_progress(self):
        with self.lock:
            sys.stdout.write("\r")  # Move the cursor to the beginning of the line
            for i in range(self.socket_count):
                sys.stdout.write(f"Thread {i}: {self.progresses[i]:.2f}%  ")
            sys.stdout.flush()

    def receive_chunk(self, index):
        header = self.sockets[index].recv(21);
        chunk_index, chunk_size, checksum = struct.unpack('<B I 16s', header)

        with open(f"received_{index}.zip", "wb") as f:
            remaining = chunk_size
            while remaining > 0:
                chunk = self.sockets[index].recv(min(1024, remaining)) # Use this for testing(basically limiting the bandwidth)
                # chunk = client_sockets[index].recv(chunk_sizes[index]) # Use this for production
                if not chunk:
                    break
                f.write(chunk)
                remaining -= len(chunk)
                
                with threading.Lock():
                    self.progresses[index] = (chunk_size - remaining) / chunk_size * 100
                self.print_progress()

    def receive_file(self):
        try:
            threads = [] # List of threads, each thread receives a chunk
            for i in range(4):
                thread = threading.Thread(target=self.receive_chunk, args=(i,))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            # Join the received temporary files
            with open("received.zip", "wb") as file:
                for i in range(4):
                    with open(f"received_{i}.zip", "rb") as part_file:
                        file.write(part_file.read())

            # Remove the temporary files
            for i in range(4):
                os.remove(f"received_{i}.zip")

            print("\nFile has been received and joined successfully!")

        except KeyboardInterrupt:
            print("\nClient is shutting down...")
            self.__del__()

    def __del__(self):
        self.sockets[0].send("exit".encode()) # Send exit command to the server
        for client_socket in self.sockets:
            client_socket.close()
        print("Client has been deleted")