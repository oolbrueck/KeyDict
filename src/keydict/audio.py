from __future__ import annotations

import io
import threading
import wave

import sounddevice as sd

from .config import AudioConfig


class Recorder:
    def __init__(self, config: AudioConfig):
        self.config = config
        self._lock = threading.Lock()
        self._chunks: list[bytes] = []
        self._stream: sd.RawInputStream | None = None
        self._sample_rate = 0

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            device = self.config.device
            if self.config.sample_rate > 0:
                sample_rate = self.config.sample_rate
            else:
                info = sd.query_devices(device, "input")
                sample_rate = int(info["default_samplerate"])
            self._chunks = []
            self._sample_rate = sample_rate
            stream = sd.RawInputStream(
                samplerate=sample_rate,
                channels=self.config.channels,
                dtype="int16",
                device=device,
                callback=self._callback,
            )
            stream.start()
            self._stream = stream

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ANN001
        del frames, time_info, status
        with self._lock:
            if self._stream is not None:
                self._chunks.append(bytes(indata))

    def stop(self) -> bytes:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is None:
            return b""
        stream.stop()
        stream.close()
        with self._lock:
            raw_audio = b"".join(self._chunks)
            self._chunks = []
        if not raw_audio:
            return b""
        output = io.BytesIO()
        with wave.open(output, "wb") as wav:
            wav.setnchannels(self.config.channels)
            wav.setsampwidth(2)
            wav.setframerate(self._sample_rate)
            wav.writeframes(raw_audio)
        return output.getvalue()

    def abort(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
            self._chunks = []
        if stream is not None:
            stream.abort()
            stream.close()

