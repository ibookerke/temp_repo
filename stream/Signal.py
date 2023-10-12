import re


class Signal:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    OPTIONS = 'OPTIONS'
    DESCRIBE = 'DESCRIBE'

    ALLOWED_SIGNALS = [
        SETUP,
        PLAY,
        PAUSE,
        TEARDOWN,
        OPTIONS,
        DESCRIBE,
    ]

    rtp_port = None

    def __init__(self, data):
        print("vlc request", data)
        try:
            # Get the request type
            self.request = data.split('\n')

            line1 = self.request[0].split(' ')
            self.request_type = line1[0]
            print("request type = ", self.request_type)
            if self.request_type not in self.ALLOWED_SIGNALS:
                raise Exception("signal '" + self.request_type + "' is not allowed")

            # Get the RTSP sequence number
            line2 = self.request[1].split(' ')
            self.seq_num = line2[1]
            print("secNum:", self.seq_num)

            if self.request_type == self.SETUP:
                self.rtp_port = self.parsePort()
                if not isinstance(self.rtp_port, int) or not (0 <= self.rtp_port < 65535):
                    raise Exception("provided port '" + str(self.rtp_port) + "' is invalid")

        except Exception as e:
            raise Exception("error on parsing signal:", e)

    def parsePort(self):
        line3 = self.request[2]

        client_port = -1
        # Define a regular expression pattern to match the client_port value
        pattern = r'client_port=(\d+)'

        # Use re.search to find the match in the string
        match = re.search(pattern, line3)

        # Check if a match was found
        if match:
            # Extract the client port value as an integer
            client_port = int(match.group(1))
            print("Client Port:", client_port)
        else:
            raise Exception("Client Port not found in the input string")

        return int(client_port)
