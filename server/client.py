class Client:
    def __init__(self, id, sockets):
        self.id = id
        self.sockets = sockets
        self.being_handled = False

    def add_socket(self, socket):
        self.sockets.append(socket)

    def __del__(self):
        for socket in self.sockets:
            socket.close()