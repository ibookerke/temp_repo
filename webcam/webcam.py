import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
import time

import aiortc
from ultralytics import YOLO

import cv2
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaRecorder
from aiortc.rtcrtpsender import RTCRtpSender
from Client import Client
from av.video.frame import VideoFrame
import numpy as np
from asyncio import Queue

ROOT = os.path.dirname(__file__)

relay = None
webcam = None

global fpsLimit
fpsLimit = 1
global startTime
startTime = time.time()

# Global variable to store the RTSP client
rtsp_client = None


class YOLOVideoStreamTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        print("yolo created")
        self.frame_queue = Queue()
        self.last_frame_time = time.time()

    def calculate_pts(self):
        # Calculate PTS (Presentation Time Stamp) based on frame rate
        current_time = time.time()
        elapsed_time = current_time - self.last_frame_time
        frame_rate = 30  # Adjust this value as needed
        pts = int(elapsed_time * frame_rate)
        self.last_frame_time = current_time
        return pts

    def create_empty_frame(self):
        # Create and return an empty frame or an error frame
        # You can use a black frame, a frame with a specific error message, or any suitable placeholder
        # Here's an example of creating a black frame:
        width, height = 480, 360  # Specify frame dimensions
        black_frame = np.zeros((height, width, 3), dtype=np.uint8)
        return VideoFrame.from_ndarray(black_frame, format="bgr24")

    async def recv(self):
        global fpsLimit
        global startTime
        global rtsp_client

        try:
            print("yolo video called")
            print("wait started")
            frame_bytes = await rtsp_client.getFrame()

            if not frame_bytes:
                print("empty frame received")
                return None
            print("Received frame bytes:", len(frame_bytes))

            if len(frame_bytes) > 0:
                frame = np.frombuffer(frame_bytes, dtype=np.uint8)  # Convert bytes to ndarray
                frame = cv2.imdecode(frame, cv2.IMREAD_COLOR)
                # img = frame.to_ndarray(format="bgr24")
                # # convert aiortc frame to numpy array

                new_frame = VideoFrame.from_ndarray(frame, format="bgr24")
                new_frame.pts = self.calculate_pts()
                new_frame.time_base = 1

                await self.frame_queue.put(new_frame)

                return new_frame

            else:
                if not self.frame_queue.empty():
                    frame = await self.frame_queue.get()
                    # Clear the queue after retrieving the frame
                    while not self.frame_queue.empty():
                        self.frame_queue.get_nowait()
                    return frame

        except Exception as e:
            print("erorr: ", e)
            return self.create_empty_frame


def create_local_tracks():
    global relay, webcam

    options = {"framerate": "30", "video_size": "640x480"}
    if relay is None:
        if platform.system() == "Darwin":
            webcam = MediaPlayer(
                "default:none", format="avfoundation", options=options
            )
        elif platform.system() == "Windows":
            webcam = MediaPlayer(
                "video=Integrated Camera", format="dshow", options=options
            )
        else:
            webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
        relay = MediaRelay()

        print(type(webcam.video))
    return relay.subscribe(webcam.video)


def force_codec(pc, sender, forced_codec):
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


async def index(request):
    content = open(os.path.join(ROOT, "index.html"), "r").read()
    return web.Response(content_type="text/html", text=content)


async def javascript(request):
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def setup(request):
    global rtsp_client

    rtsp_client.setupMovie()

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"message": "setup ended successfully"}
        ),
    )


async def play(request):
    global rtsp_client
    rtsp_client.playMovie()

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    custom_video_track = YOLOVideoStreamTrack()
    video_sender = pc.addTrack(custom_video_track)
    # video_sender = pc.addTrack(video)
    if args.video_codec:
        force_codec(pc, video_sender, args.video_codec)
    elif args.play_without_decoding:
        raise Exception("You must specify the video codec using --video-codec")

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


def pause():
    print("pause called")
    # call the client.pause


def teardown():
    print("teardown called")
    # call the client.teardown


pcs = set()


async def on_shutdown(app):
    global rtsp_client
    # close peer connections
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--play-from", help="Read the media from a file and sent it."),
    parser.add_argument(
        "--play-without-decoding",
        help=(
            "Read the media without decoding it (experimental). "
            "For now it only works with an MPEGTS container with only H.264 video."
        ),
        action="store_true",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument(
        "--audio-codec", help="Force a specific audio codec (e.g. audio/opus)"
    )
    parser.add_argument(
        "--video-codec", help="Force a specific video codec (e.g. video/H264)"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    if args.cert_file:
        ssl_context = ssl.SSLContext()
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
    else:
        ssl_context = None

    rtsp_client = Client("localhost", "5440", "4432")  # You will need to implement RTSPClient

    # rtsp_client.setupMovie()
    # print("setup ended")
    # time.sleep(4)
    # rtsp_client.playMovie()
    # print("playing")

    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/setup", setup)
    app.router.add_post("/play", play)
    app.router.add_post("/pause", pause)
    app.router.add_post("/teardown", teardown)
    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
