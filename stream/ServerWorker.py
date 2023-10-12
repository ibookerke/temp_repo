from random import randint
import sys, traceback, threading, socket

from VideoStream import VideoStream
from RtpPacket import RtpPacket
from Signal import Signal


class ServerWorker:
    SETUP = 'SETUP'
    PLAY = 'PLAY'
    PAUSE = 'PAUSE'
    TEARDOWN = 'TEARDOWN'
    OPTIONS = 'OPTIONS'
    DESCRIBE = 'DESCRIBE'

    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    OK_200 = 0
    FILE_NOT_FOUND_404 = 1
    CON_ERR_500 = 2

    client_info = {}

    seqNum = 0

    def __init__(self, config):
        self.signal = None
        self.config = config

    def run(self):
        threading.Thread(target=self.recvRtspRequest).start()

    def recvRtspRequest(self):
        """Receive RTSP request from the client."""
        connSocket = self.config['rtspSocket'][0]
        while True:
            data = connSocket.recv(65535)
            if data:
                print("Data received:\n" + data.decode("utf-8"))
                self.processRtspRequest(data.decode("utf-8"))

    def processRtspRequest(self, data):
        """Process RTSP request sent from the client."""
        self.signal = Signal(data)

        print("Processing signal: ", self.signal.request_type)

        if self.signal.request_type == self.SETUP:
            self.action_setup()
        elif self.signal.request_type == self.PLAY:
            self.action_play()
        elif self.signal.request_type == self.PAUSE:
            self.action_pause()
        elif self.signal.request_type == self.TEARDOWN:
            self.action_teardown()
        elif self.signal.request_type == self.OPTIONS:
            self.action_options()

    def action_setup(self):
        if self.state == self.INIT:
            try:
                self.client_info['videoStream'] = VideoStream(self.config)
                self.state = self.READY
            except IOError:
                self.replyRtsp(self.FILE_NOT_FOUND_404, self.signal.seq_num)

            # Generate a randomized RTSP session ID
            self.client_info['session'] = randint(100000, 999999)

            # Send RTSP reply
            self.replyRtsp(self.OK_200, self.signal.seq_num, self.SETUP)

            # Get the RTP/UDP port from the last line
            self.client_info['rtpPort'] = self.signal.rtp_port

    def action_play(self):
        if self.state == self.READY:
            self.state = self.PLAYING
            # Create a new socket for RTP/UDP
            self.client_info["rtpSocket"] = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self.replyRtsp(self.OK_200, self.signal.seq_num, self.PLAY)

            # Create a new thread and start sending RTP packets
            self.client_info['event'] = threading.Event()
            self.client_info['worker'] = threading.Thread(target=self.sendRtp)
            self.client_info['worker'].start()

    def action_pause(self):
        if self.state == self.PLAYING:
            self.state = self.READY
            self.client_info['event'].set()
            self.replyRtsp(self.OK_200, self.signal.seq_num, self.PAUSE)

    def action_teardown(self):
        self.client_info['event'].set()
        self.replyRtsp(self.OK_200, self.signal.seq_num, self.TEARDOWN)
        # Close the RTP socket
        self.client_info['rtpSocket'].close()

    def action_options(self):
        self.replyRtsp(self.OK_200, self.signal.seq_num, self.OPTIONS)

    def action_describe(self):
        self.replyRtsp(self.OK_200, self.signal.seq_num, self.DESCRIBE)

    def sendRtp(self):
        """Send RTP packets over UDP."""
        while True:
            self.client_info['event'].wait(0.01)

            # Stop sending if request is PAUSE or TEARDOWN
            if self.client_info['event'].isSet():
                break

            data = self.client_info['videoStream'].getFrame()
            if data:
                seqNum = self.client_info['videoStream'].getSeqNum()
                try:
                    address = self.config['rtspSocket'][1][0]
                    port = int(self.client_info['rtpPort'])
                    self.client_info['rtpSocket'].sendto(self.makeRtp(data, seqNum), (address, port))
                except Exception as e:
                    print("Connection Error:", e)
                    print("---------")

    def makeRtp(self, payload, seqNum):
        version = 2
        padding = 0
        extension = 0
        cc = 0
        marker = 0
        pt = 26  # MJPEG type // try: 31  for H.261; 32 for MPEG1;  33 for MPEG2
        seqnum = seqNum
        ssrc = 0

        rtpPacket = RtpPacket()

        rtpPacket.encode(version, padding, extension, cc, seqnum, marker, pt, ssrc, payload)

        return rtpPacket.getPacket()

    # RTSP / 1.0 200 OK
    # Server: MajorKernelPanicRTSP Server
    # Cseq: 1
    # Content - Length: 0
    # 'Public: DESCRIBE,SETUP,TEARDOWN,PLAY,PAUSE,RECORD, ANNOUNCE'

    def replyRtsp(self, code, seq, request_type=None):
        """Send RTSP reply to the client."""
        if code == self.OK_200:
            reply = 'RTSP/1.0 200 OK\n'
            reply += 'CSeq: ' + seq + '\n'

            if request_type == self.SETUP or request_type == self.PLAY or request_type == self.PAUSE:
                reply += 'Session: ' + str(self.client_info['session']) + "\n"

            if request_type == self.OPTIONS:
                reply += "Public: DESCRIBE, SETUP, TEARDOWN, PLAY, PAUSE\n"

            if request_type == self.DESCRIBE:
                reply += "Content-Base: rtsp://localhost:5440\n"
                reply += "Content-Type: application/sdp\n"
                reply += "Content-Length: 460\n"
                reply += (
                    "m=video 0 RTP/AVP 96\n" +
                    "a=control:streamid=0\n" +
                    "a=range:npt=0-7.741000\n" +
                    "a=length:npt=7.741000\n" +
                    "a=rtpmap:96 MP4V-ES/5544\n" +
                    'a=mimetype:string;"video/MP4V-ES"\n' +
                    'a=AvgBitRate:integer;304018\n' +
                    'a=StreamName:string;"hinted video track"\n'
                )

            connSocket = self.config['rtspSocket'][0]
            connSocket.send(reply.encode())

        # Error messages
        elif code == self.FILE_NOT_FOUND_404:
            print("404 NOT FOUND")
        elif code == self.CON_ERR_500:
            print("500 CONNECTION ERROR")
