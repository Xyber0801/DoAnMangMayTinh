import socket
import threading
import os
import sys
import random
import struct
import queue
import time

class Client:
    def  __init__(self,  server_addr = ('localhost', 12345), socket_count = 4):
        self.sockets = []
        self.socket_count = socket_count
        self.id = random.randrange(0, 1000000)
        self.progresses = [0] * 4 # Progresses of each download thread
        self.chunk_size = 0
        self.received_list_of_files = False
        self.file_queue = []

        self.lock = threading.Lock()

        for i in range(self.socket_count):
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_addr)
            self.sockets.append(client_socket)
            # print(f"Connected to server with id: {self.id}")

        #send the id to the server
        for _socket in self.sockets:
            _socket.send(str(self.id).encode())

    def get_download_file_list(self, file_path):
        interval = 5;
        run = True;
        readFilesCount = 0;
        while True:
            try:
                with open(file_path, "r") as file:
                    for i in range(readFilesCount):
                        file.readline();
                    while file_name := file.readline():
                        readFilesCount += 1;
                        file_name = file_name.rstrip("\n")
                        self.file_queue.append(file_name);
                        print(f"Added {file_name} to the queue")
                        if (file_name == "\close\n"):
                            run = False;
                            break;
                    file.close();
                    
                if (run == False):
                    break;
                start = time.time();
                while True:
                    if ((time.time() - start) >= interval):
                        break;
                    time.sleep(0.1);
            except KeyboardInterrupt:
                print("\nClient is shutting down...")
                self.exit()
                

    def receive_list_of_files(self):
        # Loop through the sockets and receive the list of files (only one socket will receive the list)
        for _socket in self.sockets:
            data = _socket.recv(1024).decode()
            if not data:
                continue
            print(f"List of files available for download:\n{data}")
            self.received_list_of_files = True
            break

    def print_progress(self):
        with self.lock:
            sys.stdout.write("\r")  # Move the cursor to the beginning of the line
            for i in range(self.socket_count):
                sys.stdout.write(f"Thread {i}: {self.progresses[i]:.2f}%  ")
            sys.stdout.flush()

    def download_files(self):
        while True:
            try:    
                if len(self.file_queue) == 0:
                    continue

                file_name = self.file_queue.pop(0)
                self.send_file_request(file_name)
                self.receive_file(file_name)

            except KeyboardInterrupt:
                self.exit();


    def send_file_request(self, filename):
        print(f"Requesting file: {filename}")
        self.sockets[0].sendall((filename + '\n').encode())

    def receive_chunk(self, index, filename):
        header = self.sockets[index].recv(21);
        chunk_index, chunk_size, checksum = struct.unpack('<B I 16s', header)

        with open(f"{filename}.chk{index}", "wb") as f:
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

    def receive_file(self, filename):
        try:
            threads = [] # List of threads, each thread receives a chunk
            for i in range(4):
                thread = threading.Thread(target=self.receive_chunk, args=(i, filename))
                thread.start()
                threads.append(thread)

            for thread in threads:
                thread.join()

            # Join the received temporary files
            with open(f"{filename}", "wb") as file:
                for i in range(4):
                    with open(f"{filename}.chk{i}", "rb") as part_file:
                        file.write(part_file.read())

            # Remove the temporary files
            for i in range(4):
                os.remove(f"{filename}.chk{i}")

            print(f"\n{filename} is downloaded.")

        except KeyboardInterrupt:
            print("\nClient is shutting down...")
            self.exit()

    def exit(self):
        self.sockets[0].send("exit".encode()) # Send exit command to the server
        for client_socket in self.sockets:
            client_socket.close()
        print("Client has been deleted")