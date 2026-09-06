"""
vision_service.py
==================
Bridges drowsiness_monitor.py (webcam + MediaPipe drowsiness/distraction
detection) into a background thread that a web server can control, instead
of the original desktop cv2.imshow() loop.

- Detection math is untouched (imported directly from drowsiness_monitor.py).
- The camera is only opened when start() is called, and released on stop() —
  so it does NOT run 24/7, only while the user is on the vehicle-camera tab.
- Thread-safe: the FastAPI request thread reads the latest JPEG frame / status
  dict while a separate worker thread keeps grabbing frames from the webcam.
"""

from __future__ import annotations

import threading
import time

import cv2

from drowsiness_monitor import CFG, DrowsinessDistractionMonitor


class VisionService:
    def __init__(self, camera_index: int = 0) -> None:
        self.camera_index = camera_index
        self._cap: cv2.VideoCapture | None = None
        self._monitor: DrowsinessDistractionMonitor | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._lock = threading.Lock()
        self._latest_jpeg: bytes | None = None

    # -- lifecycle ----------------------------------------------------
    def start(self) -> dict:
        with self._lock:
            if self._running:
                return {"status": "already_running"}

            try:
                self._cap = cv2.VideoCapture(self.camera_index)
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, CFG.frame_width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CFG.frame_height)

                if not self._cap.isOpened():
                    self._cap = None
                    return {"status": "error", "detail": f"Could not open camera index {self.camera_index}"}

                self._monitor = DrowsinessDistractionMonitor(CFG)
            except Exception as exc:
                # Surface the real reason (missing camera, driver issue, etc.)
                # instead of failing silently, so the frontend can show it.
                if self._cap is not None:
                    self._cap.release()
                self._cap = None
                self._monitor = None
                return {"status": "error", "detail": str(exc)}

            self._running = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
            return {"status": "started"}

    def stop(self) -> dict:
        with self._lock:
            self._running = False

        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._cap is not None:
            self._cap.release()
            self._cap = None

        if self._monitor is not None:
            self._monitor.close()
            self._monitor = None

        self._latest_jpeg = None
        return {"status": "stopped"}

    def is_running(self) -> bool:
        return self._running

    # -- worker thread --------------------------------------------------
    def _loop(self) -> None:
        while self._running and self._cap is not None:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)
            frame = self._monitor.process_frame(frame)

            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                with self._lock:
                    self._latest_jpeg = buf.tobytes()

    # -- reads used by FastAPI routes -----------------------------------
    def get_status(self) -> dict:
        if self._monitor is None:
            return {
                "status": "NORMAL",
                "ear": 0.320,
                "yaw": 0.0,
                "pitch": 0.0,
                "roll": 0.0,
                "drowsyElapsed": 0.0,
                "distractionElapsed": 0.0,
                "lookDirection": "FORWARD",
                "lastEvent": "Backend Standby - Camera Off",
                "logs": [],
            }
        return self._monitor.get_status()

    def mjpeg_generator(self):
        """Yields multipart JPEG chunks for a StreamingResponse."""
        boundary = b"--frame"
        while self._running:
            with self._lock:
                frame = self._latest_jpeg
            if frame is not None:
                yield (
                    boundary + b"\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
                )
            time.sleep(0.04)  # ~25 fps cap on the stream


class FrameVisionSession:
    """
    For the phone/browser-camera flow: the BROWSER owns the camera (via
    getUserMedia) and periodically uploads JPEG frames to the backend. This
    process keeps ONE persistent DrowsinessDistractionMonitor alive across
    those uploads so the duration-gated timers (eyes closed >2s, looking
    away >2.5s) work correctly across frames, exactly like the desktop
    version — the only thing that changes is where the camera lives.
    """

    def __init__(self) -> None:
        self._monitor: DrowsinessDistractionMonitor | None = None
        self._lock = threading.Lock()

    def stop(self) -> dict:
        with self._lock:
            if self._monitor is not None:
                self._monitor.close()
                self._monitor = None
        return {"status": "reset"}

    def process_jpeg(self, jpeg_bytes: bytes) -> dict:
        import numpy as np

        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return {"error": "Could not decode uploaded frame (bad/empty image data)"}

        with self._lock:
            if self._monitor is None:
                self._monitor = DrowsinessDistractionMonitor(CFG)
            # We only need the computed metrics, not the drawn overlay —
            # the frontend already draws its own HUD over the live <video>.
            self._monitor.process_frame(frame)
            return self._monitor.get_status()


# Shared instances imported by server.py
frame_vision_session = FrameVisionSession()


# Single shared instance imported by server.py
vision_service = VisionService(camera_index=0)