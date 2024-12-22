import socket
import threading
import os
import sys
import random
import struct
import hashlib
import time

class Client:
    def  __init__(self,  server_addr = ('localhost', 12345), socket_count = 4):
        self.sockets = []
        self.socket_count = socket_count
        self.id = random.randrange(0, 1000000)
        self.progresses = [0] * 4 # Progresses of each download thread
        self.chunk_size = 0
        self.files_available_for_download = []
        self.file_queue = []

        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        for i in range(self.socket_count):
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(server_addr)
            self.sockets.append(client_socket)

        #send the id to the server
        for _socket in self.sockets:
            _socket.send(str(self.id).encode())

    def parse_input_file(self, path):
        interval = 5;
        run = True;
        readFilesCount = 0;
        while not self.stop_event.is_set():
            try:
                with open(path, "r") as file:
                    for i in range(readFilesCount):
                        file.readline();
                    while file_name := file.readline():
                        readFilesCount += 1;
                        file_name = file_name.rstrip("\n")
                        self.file_queue.append(file_name);
                        print(f"Added {file_name} to the queue")
                    file.close();
                    
                if (run == False):
                    break;
                start = time.time();
                while True:
                    if ((time.time() - start) >= interval):
                        break;
                    time.sleep(0.1);
            except KeyboardInterrupt:
                self.stop_event.set()
                

    def parse_file_list(self, data):
        files = []
        lines = data.split("\n")
        for line in lines:
            if line.strip():
                parts = line.split()
                filename = " ".join(parts[:-1])
                files.append(filename)
        return files

    def receive_list_of_files(self):
        # Loop through the sockets and receive the list of files (only one socket will receive the list)
        for _socket in self.sockets:
            data = _socket.recv(1024).decode()
            if not data:
                continue
            print(f"List of files available for download:\n{data}")
            print("------------------------------------------")
            self.files_available_for_download = self.parse_file_list(data)
            break

    def print_progress(self, filename):
        with self.lock:
            sys.stdout.write("\r")  # Move the cursor to the beginning of the line
            sys.stdout.write(f"Downloading {filename}: ")
            for i in range(self.socket_count):
                sys.stdout.write(f"Thread {i}: {self.progresses[i]:.2f}%  ")
            sys.stdout.flush()

    def download_files(self):
        while not self.stop_event.is_set():
            try:    
                if len(self.file_queue) == 0:
                    continue

                file_name = self.file_queue.pop(0)
                if (not file_name in self.files_available_for_download):
                    print(f"{file_name} is not available for download.")
                    continue
                self.send_file_request(file_name)
                self.receive_file(file_name)

            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    self.stop_event.set()
                else:
                    continue


    def send_file_request(self, filename):
        # print(f"Requesting file: {filename}")
        self.sockets[0].sendall(f"get {filename}\n".encode())

    # Kiểm tra lỗi gói tin
    def is_corrupt(self, server_checksum, received_chunk):
        hash = hashlib.blake2s(digest_size=16)
        client_checksum = received_chunk
        hash.update(client_checksum)
        client_checksum = hash.digest()
        return (server_checksum != client_checksum)

    # Cập nhật lại hàm nhận gói tin từ server
    def receive_chunk(self, index, filename):
        while not self.stop_event.is_set():
            try:
                accumulated_chunk = b''

                header = self.sockets[index].recv(21)
                chunk_index, chunk_size, checksum = struct.unpack('<B I 16s', header)

                remaining = chunk_size

                while remaining > 0:
                    # chunk = self.sockets[index].recv(min(50000, remaining)) # Use this for testing(basically limiting the bandwidth)
                    chunk = self.sockets[index].recv(remaining) # Use this for production
                    if not chunk:
                        break
                    accumulated_chunk += chunk
                    remaining -= len(chunk)
                    with threading.Lock():
                        self.progresses[index] = (chunk_size - remaining) / chunk_size * 100
                    self.print_progress(filename)

                if self.is_corrupt(checksum, accumulated_chunk):
                    self.sockets[index].send(f"getchunk {chunk_index}\n".encode())
                    continue
                else:
                    os.makedirs("./received", exist_ok=True)
                    with open(f"./received/{filename}.chk{chunk_index}", "wb") as f:
                        f.write(accumulated_chunk)
                    break
            except Exception as e:
                if isinstance(e, KeyboardInterrupt):
                    self.stop_event.set()
                else:
                    continue

    def receive_file(self, filename):
        try:
            threads = [] # List of threads, each thread receives a chunk
            for i in range(4):
                thread = threading.Thread(target=self.receive_chunk, args=(i, filename))
                thread.start()
                threads.append(thread)

            try:
                for thread in threads:
                    thread.join()
            except KeyboardInterrupt:
                self.stop_event.set()
            
            # Join the received temporary files
            with open(f"./received/{filename}", "wb") as file:
                for i in range(4):
                    with open(f"./received/{filename}.chk{i}", "rb") as part_file:
                        file.write(part_file.read())

            # Remove the temporary files
            for i in range(4):
                os.remove(f"./received/{filename}.chk{i}")

            print(f"\n{filename} is downloaded.")

            # Send ACK to the server
            self.sockets[0].send("ACK\n".encode())

        except KeyboardInterrupt:
            self.stop_event.set()

    def exit(self):
        self.sockets[0].send("exit".encode()) # Send exit command to the server
        for client_socket in self.sockets:
            client_socket.close()
        print("Client is shutting down...")