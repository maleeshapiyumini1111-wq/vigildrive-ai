#!/usr/bin/env python3
"""
Smart Driver Drowsiness & Cognitive Distraction Monitoring System
====================================================================

Real-time monitoring pipeline built on OpenCV + MediaPipe Face Mesh that
detects two independent risk states from a webcam feed:

    1. DROWSINESS   -> sustained low Eye Aspect Ratio (EAR)  (eyes closing)
    2. DISTRACTION  -> sustained head pose deviation (Yaw/Pitch) (looking away)

Both states use *duration-gated* logic: a momentary blink or glance does NOT
trigger an alarm. Only when the abnormal condition persists continuously
beyond a configurable time window does the system escalate to an audible +
visual alert. The timer resets immediately the moment the condition clears.

Author : Senior CV/Python Engineer (reference implementation)
Python : 3.9+
--------------------------------------------------------------------------

Quick start
-----------
    pip install -r requirements.txt
    python drowsiness_monitor.py --camera 0

Press 'q' to quit, 'r' to reset counters/calibration.
"""

from __future__ import annotations

import argparse
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "mediapipe is required. Install with: pip install mediapipe"
    ) from exc

try:
    import pygame
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pygame is required for audio alerts. Install with: pip install pygame"
    ) from exc

# pyttsx3 is optional (adds spoken alerts on top of the tone alarms).
try:
    import pyttsx3

    _PYTTSX3_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYTTSX3_AVAILABLE = False


# ============================================================================
# 1. CONFIGURATION  (tune everything here — see README section at bottom)
# ============================================================================
@dataclass
class Config:
    # --- Eye Aspect Ratio (drowsiness) ---
    ear_threshold: float = 0.21          # below this => eyes considered "closed"
    drowsy_time_limit: float = 2.0       # seconds of continuous closure before ALERT
    ear_smoothing_window: int = 5        # frames, moving-average smoothing

    # --- Head pose (distraction) ---
    yaw_threshold_deg: float = 20.0      # left/right look-away angle
    pitch_threshold_deg: float = 18.0    # up/down look-away angle
    distraction_time_limit: float = 2.5  # seconds of continuous look-away before ALERT

    # --- No-face-detected edge case ---
    no_face_time_limit: float = 2.5      # seconds with no face before a distraction alert

    # --- Camera / performance ---
    camera_index: int = 0
    frame_width: int = 960
    frame_height: int = 540
    fps_smoothing: float = 0.9           # exponential moving average factor

    # --- Voice alerts (optional, throttled) ---
    enable_voice: bool = True
    voice_repeat_interval: float = 4.0   # min seconds between repeated spoken warnings


CFG = Config()


# ============================================================================
# 2. MEDIAPIPE FACE MESH LANDMARK INDICES
# ============================================================================
# 6-point eye contours used for the classic Soukupova & Cech EAR formula.
LEFT_EYE_IDX = [362, 385, 387, 263, 373, 380]
RIGHT_EYE_IDX = [33, 160, 158, 133, 153, 144]

# 6-point subset used for solvePnP head-pose estimation (approximate
# generic 3D face model in millimeters -> standard head-pose tutorial set).
POSE_LANDMARK_IDX = {
    "nose_tip": 1,
    "chin": 152,
    "left_eye_corner": 263,
    "right_eye_corner": 33,
    "left_mouth_corner": 291,
    "right_mouth_corner": 61,
}

MODEL_POINTS_3D = np.array(
    [
        (0.0, 0.0, 0.0),          # nose tip
        (0.0, -330.0, -65.0),     # chin
        (-225.0, 170.0, -135.0),  # left eye corner
        (225.0, 170.0, -135.0),   # right eye corner
        (-150.0, -150.0, -125.0),  # left mouth corner
        (150.0, -150.0, -125.0),   # right mouth corner
    ],
    dtype=np.float64,
)


# ============================================================================
# 3. AUDIO ALERT SYSTEM  (non-blocking tones via pygame + optional TTS)
# ============================================================================
class AlertSystem:
    """
    Generates two acoustically distinct, looping alarm tones (drowsiness vs.
    distraction) entirely in-memory (no external .wav assets needed) and
    plays them on independent mixer channels so they never block the main
    video loop. Optionally layers throttled spoken warnings via pyttsx3
    running on its own worker thread.
    """

    def __init__(self, enable_voice: bool = True) -> None:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=1)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(8)

        self._drowsy_sound = self._make_tone(freq=880, duration=0.35, pattern="pulse")
        self._distraction_sound = self._make_tone(freq=523, duration=0.5, pattern="sweep")

        self._drowsy_channel = pygame.mixer.Channel(0)
        self._distraction_channel = pygame.mixer.Channel(1)

        self._voice_enabled = enable_voice and _PYTTSX3_AVAILABLE
        self._voice_queue: "queue.Queue[str]" = queue.Queue()
        self._last_voice_time = {"drowsy": 0.0, "distraction": 0.0}
        if self._voice_enabled:
            self._voice_thread = threading.Thread(target=self._voice_worker, daemon=True)
            self._voice_thread.start()

    # -- tone synthesis -----------------------------------------------------
    @staticmethod
    def _make_tone(freq: int, duration: float, pattern: str = "pulse") -> pygame.mixer.Sound:
        """Synthesize a short alarm tone as a numpy sine wave -> pygame Sound."""
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        wave = np.sin(2 * np.pi * freq * t)

        if pattern == "pulse":
            # amplitude-modulated "beep-beep" envelope -> reads as urgent
            envelope = (np.sin(2 * np.pi * 6 * t) > 0).astype(np.float64)
            wave *= envelope
        elif pattern == "sweep":
            # gentle rising sweep -> perceptually distinct from the pulse tone
            sweep = np.sin(2 * np.pi * (freq + 200 * t) * t)
            wave = 0.6 * wave + 0.4 * sweep

        wave = (wave * 32767 * 0.5).astype(np.int16)
        
        # --- FIX: Convert 1D Mono wave into 2D Stereo wave for Pygame ---
        stereo_wave = np.column_stack((wave, wave))
        
        return pygame.sndarray.make_sound(stereo_wave)

    # -- public control -------------------------------------------------
    def start_drowsy_alert(self) -> None:
        if not self._drowsy_channel.get_busy():
            self._drowsy_channel.play(self._drowsy_sound, loops=-1)
        self._maybe_speak("drowsy", "Warning. Drowsiness detected. Please stay alert.")

    def stop_drowsy_alert(self) -> None:
        if self._drowsy_channel.get_busy():
            self._drowsy_channel.stop()

    def start_distraction_alert(self) -> None:
        if not self._distraction_channel.get_busy():
            self._distraction_channel.play(self._distraction_sound, loops=-1)
        self._maybe_speak("distraction", "Warning. Eyes on the road.")

    def stop_distraction_alert(self) -> None:
        if self._distraction_channel.get_busy():
            self._distraction_channel.stop()

    def shutdown(self) -> None:
        self.stop_drowsy_alert()
        self.stop_distraction_alert()
        pygame.mixer.quit()

    # -- voice (optional, throttled, background thread) -----------------
    def _maybe_speak(self, key: str, message: str) -> None:
        if not self._voice_enabled:
            return
        now = time.time()
        if now - self._last_voice_time[key] >= CFG.voice_repeat_interval:
            self._last_voice_time[key] = now
            self._voice_queue.put(message)

    def _voice_worker(self) -> None:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        while True:
            message = self._voice_queue.get()
            try:
                engine.say(message)
                engine.runAndWait()
            except Exception:
                # Never let TTS errors crash the monitoring loop.
                pass


# ============================================================================
# 4. GEOMETRY HELPERS
# ============================================================================
def euclidean(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return float(np.linalg.norm(np.array(p1) - np.array(p2)))


def eye_aspect_ratio(landmarks_px, eye_idx) -> float:
    """
    Classic 6-point EAR:  (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
    Lower values indicate a more closed eye.
    """
    p1, p2, p3, p4, p5, p6 = [landmarks_px[i] for i in eye_idx]
    vertical_1 = euclidean(p2, p6)
    vertical_2 = euclidean(p3, p5)
    horizontal = euclidean(p1, p4)
    if horizontal == 0:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def estimate_head_pose(
    landmarks_px, frame_shape
) -> Optional[Tuple[float, float, float]]:
    """
    Runs solvePnP against a generic 3D face model to recover approximate
    Euler angles (pitch, yaw, roll) in degrees.  Returns None if the pose
    cannot be solved (e.g. degenerate landmark configuration).
    """
    h, w = frame_shape[:2]
    image_points = np.array(
        [landmarks_px[idx] for idx in POSE_LANDMARK_IDX.values()], dtype=np.float64
    )

    focal_length = w
    center = (w / 2.0, h / 2.0)
    camera_matrix = np.array(
        [[focal_length, 0, center[0]], [0, focal_length, center[1]], [0, 0, 1]],
        dtype=np.float64,
    )
    dist_coeffs = np.zeros((4, 1))  # assume no lens distortion

    success, rotation_vec, _translation_vec = cv2.solvePnP(
        MODEL_POINTS_3D,
        image_points,
        camera_matrix,
        dist_coeffs,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not success:
        return None

    rotation_mat, _ = cv2.Rodrigues(rotation_vec)
    angles, *_ = cv2.RQDecomp3x3(rotation_mat)
    pitch, yaw, roll = angles[0], angles[1], angles[2]
    return pitch, yaw, roll


# ============================================================================
# 5. DURATION-GATED STATE TRACKER
# ============================================================================
class DurationTrigger:
    """
    Generic helper that turns an instantaneous boolean condition into a
    debounced, time-gated alert state:

        - starts a timer the instant `condition=True` begins
        - resets the timer the instant `condition=False`
        - `active` becomes True only once the condition has held
          continuously for longer than `time_limit` seconds
    """

    def __init__(self, time_limit: float) -> None:
        self.time_limit = time_limit
        self._start_time: Optional[float] = None
        self.active: bool = False
        self.elapsed: float = 0.0

    def update(self, condition: bool) -> None:
        now = time.time()
        if condition:
            if self._start_time is None:
                self._start_time = now
            self.elapsed = now - self._start_time
            self.active = self.elapsed >= self.time_limit
        else:
            self._start_time = None
            self.elapsed = 0.0
            self.active = False


# ============================================================================
# 6. FPS COUNTER
# ============================================================================
class FPSMeter:
    def __init__(self, smoothing: float = 0.9) -> None:
        self.smoothing = smoothing
        self._last_time = time.time()
        self.fps = 0.0

    def tick(self) -> float:
        now = time.time()
        dt = now - self._last_time
        self._last_time = now
        if dt > 0:
            instant_fps = 1.0 / dt
            self.fps = self.smoothing * self.fps + (1 - self.smoothing) * instant_fps
        return self.fps


# ============================================================================
# 7. UI DRAWING HELPERS
# ============================================================================
COLOR_OK = (60, 200, 60)       # green
COLOR_WARN = (0, 165, 255)     # orange
COLOR_ALERT = (0, 0, 255)      # red
COLOR_TEXT = (255, 255, 255)


def draw_status_box(frame, top_left, label, value_text, color) -> None:
    x, y = top_left
    w, h = 260, 60
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)
    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    cv2.putText(frame, label, (x + 10, y + 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, COLOR_TEXT, 1, cv2.LINE_AA)
    cv2.putText(frame, value_text, (x + 10, y + 48), cv2.FONT_HERSHEY_SIMPLEX, 0.65, COLOR_TEXT, 2, cv2.LINE_AA)


def draw_banner(frame, text, color) -> None:
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 45), color, -1)
    cv2.putText(frame, text, (15, 31), cv2.FONT_HERSHEY_SIMPLEX, 0.9, COLOR_TEXT, 2, cv2.LINE_AA)


# ============================================================================
# 8. MAIN MONITOR
# ============================================================================
class DrowsinessDistractionMonitor:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.alerts = AlertSystem(enable_voice=cfg.enable_voice)

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.drowsy_trigger = DurationTrigger(cfg.drowsy_time_limit)
        self.distraction_trigger = DurationTrigger(cfg.distraction_time_limit)
        self.no_face_trigger = DurationTrigger(cfg.no_face_time_limit)

        self.ear_history: list[float] = []
        self.fps_meter = FPSMeter(cfg.fps_smoothing)

    # -- landmark extraction -------------------------------------------
    @staticmethod
    def _landmarks_to_px(face_landmarks, frame_shape) -> list[Tuple[float, float]]:
        h, w = frame_shape[:2]
        return [(lm.x * w, lm.y * h) for lm in face_landmarks.landmark]

    def _smoothed_ear(self, raw_ear: float) -> float:
        self.ear_history.append(raw_ear)
        if len(self.ear_history) > self.cfg.ear_smoothing_window:
            self.ear_history.pop(0)
        return float(np.mean(self.ear_history))

    # -- per-frame processing -------------------------------------------
    def process_frame(self, frame: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self.face_mesh.process(rgb)
        rgb.flags.writeable = True

        fps = self.fps_meter.tick()

        if not results.multi_face_landmarks:
            # --- Edge case: no face detected ---
            self.no_face_trigger.update(True)
            self.drowsy_trigger.update(False)
            self.distraction_trigger.update(False)
            self.ear_history.clear()

            draw_banner(frame, "NO FACE DETECTED", COLOR_WARN)
            if self.no_face_trigger.active:
                self.alerts.start_distraction_alert()
                draw_banner(
                    frame,
                    f"DISTRACTION ALERT: FACE NOT VISIBLE {self.no_face_trigger.elapsed:0.1f}s",
                    COLOR_ALERT,
                )
            else:
                self.alerts.stop_distraction_alert()
            self.alerts.stop_drowsy_alert()
            self._draw_fps(frame, fps)
            return frame

        self.no_face_trigger.update(False)
        landmarks_px = self._landmarks_to_px(results.multi_face_landmarks[0], frame.shape)

        # ---------------- Drowsiness (EAR) ----------------
        left_ear = eye_aspect_ratio(landmarks_px, LEFT_EYE_IDX)
        right_ear = eye_aspect_ratio(landmarks_px, RIGHT_EYE_IDX)
        raw_avg_ear = (left_ear + right_ear) / 2.0
        avg_ear = self._smoothed_ear(raw_avg_ear)

        eyes_closed = avg_ear < self.cfg.ear_threshold
        self.drowsy_trigger.update(eyes_closed)

        if self.drowsy_trigger.active:
            self.alerts.start_drowsy_alert()
        else:
            self.alerts.stop_drowsy_alert()

        # ---------------- Distraction (Head pose) ----------------
        pose = estimate_head_pose(landmarks_px, frame.shape)
        if pose is not None:
            pitch, yaw, roll = pose
            looking_away = (
                abs(yaw) > self.cfg.yaw_threshold_deg
                or abs(pitch) > self.cfg.pitch_threshold_deg
            )
        else:
            pitch = yaw = roll = 0.0
            looking_away = False

        self.distraction_trigger.update(looking_away)
        if self.distraction_trigger.active:
            self.alerts.start_distraction_alert()
        else:
            self.alerts.stop_distraction_alert()

        # ---------------- UI ----------------
        self._draw_ui(frame, avg_ear, pitch, yaw, roll, fps, landmarks_px)
        return frame

    # -- UI rendering -----------------------------------------------------
    def _draw_fps(self, frame, fps) -> None:
        cv2.putText(
            frame, f"FPS: {fps:0.1f}", (frame.shape[1] - 150, 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_TEXT, 2, cv2.LINE_AA,
        )

    def _draw_ui(self, frame, avg_ear, pitch, yaw, roll, fps, landmarks_px) -> None:
        # Eye landmarks (visual debug aid)
        for idx in LEFT_EYE_IDX + RIGHT_EYE_IDX:
            x, y = landmarks_px[idx]
            cv2.circle(frame, (int(x), int(y)), 2, (0, 255, 255), -1)

        drowsy_color = COLOR_ALERT if self.drowsy_trigger.active else (
            COLOR_WARN if avg_ear < self.cfg.ear_threshold else COLOR_OK
        )
        distraction_color = COLOR_ALERT if self.distraction_trigger.active else (
            COLOR_WARN
            if (abs(yaw) > self.cfg.yaw_threshold_deg or abs(pitch) > self.cfg.pitch_threshold_deg)
            else COLOR_OK
        )

        draw_status_box(frame, (10, 60), "EAR (Eye Aspect Ratio)", f"{avg_ear:0.3f}", drowsy_color)
        draw_status_box(frame, (10, 130), "Head Yaw / Pitch (deg)", f"Y:{yaw:0.1f}  P:{pitch:0.1f}", distraction_color)

        self._draw_fps(frame, fps)

        # Top banner: highest-priority active alert wins visually.
        if self.drowsy_trigger.active:
            draw_banner(frame, f"DROWSINESS ALERT!  Eyes closed {self.drowsy_trigger.elapsed:0.1f}s", COLOR_ALERT)
        elif self.distraction_trigger.active:
            direction = self._look_direction(yaw, pitch)
            draw_banner(frame, f"DISTRACTION ALERT!  Looking {direction} {self.distraction_trigger.elapsed:0.1f}s", COLOR_ALERT)
        else:
            draw_banner(frame, "STATUS: NORMAL - Driver Attentive", COLOR_OK)

    def _look_direction(self, yaw: float, pitch: float) -> str:
        if abs(yaw) >= abs(pitch):
            return "RIGHT" if yaw > 0 else "LEFT"
        return "DOWN" if pitch > 0 else "UP"

    def close(self) -> None:
        self.face_mesh.close()
        self.alerts.shutdown()


# ============================================================================
# 9. ENTRY POINT
# ============================================================================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Driver Drowsiness & Distraction Monitor")
    parser.add_argument("--camera", type=int, default=CFG.camera_index, help="Webcam device index")
    parser.add_argument("--ear-threshold", type=float, default=CFG.ear_threshold)
    parser.add_argument("--drowsy-time", type=float, default=CFG.drowsy_time_limit)
    parser.add_argument("--distraction-time", type=float, default=CFG.distraction_time_limit)
    parser.add_argument("--no-voice", action="store_true", help="Disable spoken TTS alerts")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    CFG.camera_index = args.camera
    CFG.ear_threshold = args.ear_threshold
    CFG.drowsy_time_limit = args.drowsy_time
    CFG.distraction_time_limit = args.distraction_time
    CFG.enable_voice = not args.no_voice

    cap = cv2.VideoCapture(CFG.camera_index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, CFG.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CFG.frame_height)

    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {CFG.camera_index}")

    monitor = DrowsinessDistractionMonitor(CFG)
    window_name = "Driver Drowsiness & Distraction Monitor"

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Frame grab failed — retrying...")
                continue

            frame = cv2.flip(frame, 1)  # mirror for natural selfie-view
            frame = monitor.process_frame(frame)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                monitor.ear_history.clear()
    finally:
        cap.release()
        cv2.destroyAllWindows()
        monitor.close()


if __name__ == "__main__":
    main()
