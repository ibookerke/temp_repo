import sys, socket
import argparse
from ServerWorker import ServerWorker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RTSP server launcher")
    parser.add_argument(
        "--webcam-resolution",
        default=[480, 360],
        nargs=2,
        type=int
    )
    parser.add_argument(
        "--port",
        default=5440,
        nargs=1,
        type=int
    )
    args = parser.parse_args()
    return args


class Server:
    def __init__(self):
        args = parse_args()
        self.server_port = args.port
        self.frame_width, self.frame_height = args.webcam_resolution

    def main(self):
        rtsp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        rtsp_socket.bind(('', self.server_port))
        rtsp_socket.listen(5)

        # Receive client info (address,port) through RTSP/TCP session
        print("server successfully Running on port " + str(self.server_port))
        while True:
            config = {
                'rtspSocket': rtsp_socket.accept(),
                'frame_width':  self.frame_width,
                'frame_height': self.frame_height,
            }
            ServerWorker(config).run()


if __name__ == "__main__":
    (Server()).main()
