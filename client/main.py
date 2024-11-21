import client

def __main__():
    try:
        _client =  client.Client(server_addr = ('localhost', 54321))
    except Exception as e:
        _client =  client.Client(server_addr = ('localhost', 12345))
        
    while not _client.received_list_of_files:
        _client.receive_list_of_files()

    _client.send_file_request('200MB.zip')
    _client.receive_file()

if __name__ == '__main__':
    __main__()