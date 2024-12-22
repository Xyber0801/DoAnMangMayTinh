import server
import threading            

def __main__():
    # List of threads, each thread handles a client
    threads = []

    # Try to create a server on port 54321, if it fails, create it on port 12345
    # This is done for testing purposes, since when the server crashes, the port is not released immediately
    try:
        _server = server.Server(ip = 'localhost', port = 54321)
    except Exception as e:
        _server = server.Server(ip = 'localhost', port = 12345)

    while not _server.stop_event.is_set():
        try:
            # Accept connections and handle them
            _server.accept_connections()

            for client in _server.clients:
                if client.being_handled:
                    continue

                thread = threading.Thread(target = _server.handle_client, args = (client,))
                thread.start()
                threads.append(thread)

            # Check for finished threads
            for thread in threads:
                if not thread.is_alive():
                    thread.join()
                    threads.remove(thread)

        except KeyboardInterrupt:
            print("\nServer is shutting down....")
            _server.stop_event.set()
            break


if __name__ == "__main__":
    __main__()