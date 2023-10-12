import cv2


class VideoStream:
    def __init__(self, config):
        self.seq_num = 0
        self.config = config

        try:
            # Initialize a video capture object cap to capture video from the default camera (0).
            self.cap = cv2.VideoCapture(0)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config['frame_width'])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config['frame_height'])

        except IOError:
            raise Exception("error on try to create video stream")

    def getFrame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None

        self.seq_num += 1
        # TODO: solve seq num problem properly
        if self.seq_num > 255:
            self.seq_num = 0

        print(frame.size)
        resized_image = cv2.resize(frame, (480, 360), interpolation = cv2.INTER_AREA)
        print(resized_image.size)
        converted_resized_image = cv2.imencode('.jpg', resized_image)[1].tobytes()
        print("converted_resized_image:", len(converted_resized_image))

        # converted_frame = cv2.imencode('.jpg', frame)[1].tobytes()
        # print("converted frame", len(converted_frame))

        return converted_resized_image

    def getSeqNum(self):
        return self.seq_num
