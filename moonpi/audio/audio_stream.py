import threading
from collections import deque

import numpy
import pyaudio

FORMAT = pyaudio.paInt16
CHANNELS = 1
# RATE = 44100
# INPUT_BLOCK_TIME = 0.05
# INPUT_FRAMES_PER_BLOCK = int(RATE * INPUT_BLOCK_TIME)

RATE = 48100
BUFFERSIZE = 2 ** 12  # 4069 is a good buffer size
secToRecord = .1


class AudioStream:

    def __init__(self):
        self.maxVals = deque(maxlen=500)
        self.buffersToRecord = int(RATE * secToRecord / BUFFERSIZE)
        if self.buffersToRecord == 0: self.buffersToRecord = 1
        self.samplesToRecord = int(BUFFERSIZE * self.buffersToRecord)
        self.chunksToRecord = int(self.samplesToRecord / BUFFERSIZE)
        self.secPerPoint = 1.0 / RATE

        self.pa = pyaudio.PyAudio()
        self.stream = self.pa.open(format=FORMAT,
                                   channels=CHANNELS,
                                   rate=RATE,
                                   input=True,
                                   input_device_index=self.find_input_device(),
                                   frames_per_buffer=BUFFERSIZE)

        self.xsBuffer = numpy.arange(BUFFERSIZE) * self.secPerPoint
        self.xs = numpy.arange(self.chunksToRecord * BUFFERSIZE) * self.secPerPoint
        self.audio = numpy.empty((self.chunksToRecord * BUFFERSIZE), dtype=numpy.int16)

    def find_input_device(self):
        device_index = None
        for i in range(self.pa.get_device_count()):
            dev_info = self.pa.get_device_info_by_index(i)
            print("Device %d: %s" % (i, dev_info["name"]))

            for keyword in ["usb", "mic", "input"]:
                if keyword in dev_info["name"].lower():
                    print("Found an input: device %d - %s" % (i, dev_info["name"]))
                    device_index = i
                    return device_index

        if device_index is None:
            print("No preferred input found; using default input device.")

        return device_index

    def close(self):
        """cleanly back out and release sound card."""
        self.pa.close(self.stream)

    def get_audio(self):
        """get a single buffer size worth of audio."""
        audio_stream = self.stream.read(BUFFERSIZE)
        return numpy.fromstring(audio_stream, dtype=numpy.int16)

    def record(self, forever=True):
        """get a single buffer size worth of audio."""
        while True:
            for i in range(self.chunksToRecord):
                self.audio[i * BUFFERSIZE:(i + 1) * BUFFERSIZE] = self.get_audio()
            if not forever:
                break

    def continuousStart(self):
        """CALL THIS to start running forever."""
        self.t = threading.Thread(target=self.record)
        self.t.start()

    def fft(self, x_max, y_max):
        data = self.audio.flatten()
        left, right = numpy.split(numpy.abs(numpy.fft.fft(data)), 2)
        ys = numpy.add(left, right[::-1])

        # FFT max values can vary widely depending on the hardware/audio setup.
        # Take the average of the last few values which will keep everything
        # in a "normal" range (visually speaking). Also makes it volume independent.
        self.maxVals.append(numpy.amax(ys))

        ys = ys[:x_max]
        m = max(100000, numpy.average(self.maxVals))
        ys = numpy.rint(numpy.interp(ys, [0, m], [0, y_max - 1]))
        return ys