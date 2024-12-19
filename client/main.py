import client
import threading
import time

def __main__():
    global _client
    try:
        _client =  client.Client(server_addr = ('localhost', 54321))
    except Exception as e:
        _client =  client.Client(server_addr = ('localhost', 12345))
        
    while not _client.received_list_of_files:
        _client.receive_list_of_files()

    # Start a thread to read input file
    read_input_thread = threading.Thread(target = _client.get_download_file_list, args = ('input.txt', ))
    read_input_thread.start()

    download_thread = threading.Thread(target = _client.download_files)
    download_thread.start()
    
    try:
        read_input_thread.join()
        download_thread.join()
    except KeyboardInterrupt:
        _client.stop_event.set()

    _client.exit()

    try:
        time.sleep(1) #Sleep for a second to let the client shut down (all threads to finish)
    except KeyboardInterrupt:
        pass
    print("\nClient has shut down.")
    

if __name__ == '__main__':
    __main__()