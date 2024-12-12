import client
import threading

def __main__():
    try:
        _client =  client.Client(server_addr = ('localhost', 54321))
    except Exception as e:
        _client =  client.Client(server_addr = ('localhost', 12345))
        
    while not _client.received_list_of_files:
        _client.receive_list_of_files()

    threads = []

    # Start a thread to read input file
    read_input_thread = threading.Thread(target = _client.get_download_file_list, args = ('input.txt', ))
    read_input_thread.start()
    threads.append(read_input_thread)

    download_thread = threading.Thread(target = _client.download_files)
    download_thread.start()
    threads.append(download_thread)
    
    for thread in threads:
        thread.join();

if __name__ == '__main__':
    __main__()