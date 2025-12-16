class Api:
    def __init__(self):
        self.window = None

    def attach_window(self, window):
        self.window = window

    def ping(self):
        return "pong from python"