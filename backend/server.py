import os
import time
import socket
import threading
from contextlib import asynccontextmanager
import serial
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

# Twilio Library Import (pip install twilio)
try:
    from twilio.rest import Client
    _TWILIO_AVAILABLE = True
except ImportError:
    _TWILIO_AVAILABLE = False

from vision_service import vision_service, frame_vision_session

# ----------------- TWILIO SMS CONFIGURATION -----------------
# Twilio.com වෙතින් ලබාගන්නා Credentials මෙහි ඇතුළත් කරන්න
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN  = "YOUR_TWILIO_AUTH_TOKEN"
TWILIO_PHONE_NUMBER = "+1XXXXXXXXXX"  # Twilio Virtual Phone Number

# ----------------- EMERGENCY & GPS STATE -----------------
emergency_contact_number = "+94712345678"
current_gps = {
    "lat": 6.7951,
    "lng": 79.9009,
    "address": "Moratuwa, Sri Lanka"
}

helmet_data = {
    "status": "SAFE",
    "last_event": "System Synchronized & Monitoring Active",
    "emergency_contact_notified": False,
    "emergency_contact": emergency_contact_number,
    "location": current_gps,
    "logs": []
}

def dispatch_emergency_sos(lat, lng):
    maps_link = f"https://www.google.com/maps?q={lat},{lng}"
    t_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    sms_message = (
        f"🚨 [VIGILDRIVE CRASH SOS] 🚨\n"
        f"Severe accident detected on two-wheeler!\n"
        f"Time: {t_str}\n"
        f"Live Location: {maps_link}\n"
        f"Immediate medical/family assistance requested!"
    )
    
    print("\n" + "="*55)
    print("📡 [SMS GATEWAY DISPATCHING SOS]")
    print(f"📱 Sent To Registered Contact: {emergency_contact_number}")
    print(f"📍 GPS Coordinates: {lat}, {lng}")
    print(f"✉️ Message Payload:\n{sms_message}")
    print("="*55 + "\n")

    # සැබෑ දුරකථනයට SMS එක යැවීමේ කොටස
    if _TWILIO_AVAILABLE and TWILIO_ACCOUNT_SID != "YOUR_TWILIO_ACCOUNT_SID":
        try:
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            message = client.messages.create(
                body=sms_message,
                from_=TWILIO_PHONE_NUMBER,
                to=emergency_contact_number
            )
            print(f"✅ Real SMS Dispatched Successfully! SID: {message.sid}")
        except Exception as e:
            print(f"❌ Twilio SMS Delivery Failed: {e}")
    else:
        print("ℹ️ [MOCK MODE] Twilio credentials not configured. SMS logged to terminal only.")

def background_serial_reader():
    global helmet_data
    while True:
        try:
            with serial.Serial("COM2", 9600, timeout=1.0) as ser:
                print("🔌 [COM2] Serial Listener Active with Newline Parsing...")
                while True:
                    line = ser.readline()
                    if line:
                        raw = line.decode("utf-8", errors="ignore").strip().upper()
                        if raw:
                            current_time = time.strftime("%H:%M:%S")
                            print(f"📥 Parsed Line: {raw}")

                            new_status = helmet_data["status"]
                            new_event = helmet_data["last_event"]
                            new_emergency = helmet_data["emergency_contact_notified"]
                            log_entry = None

                            if "CRASH" in raw:
                                if new_status != "CRASH":
                                    dispatch_emergency_sos(helmet_data["location"]["lat"], helmet_data["location"]["lng"])
                                new_status = "CRASH"
                                new_event = "🚨 CRASH IMPACT DETECTED!"
                                new_emergency = True
                                log_entry = f"[{current_time}] 🚨 CRASH ALERT: Impact triggered! SOS SMS dispatched to {emergency_contact_number} with GPS link."
                            elif "DROWSY" in raw or "NODDING" in raw:
                                new_status = "DROWSY"
                                new_event = "⚠️ DRIVER DROWSINESS DETECTED (Head Nodding)!"
                                new_emergency = False
                                log_entry = f"[{current_time}] ⚠️ DROWSINESS ALERT: Head tilt angle exceeded threshold (>60%)!"
                            elif any(k in raw for k in ["READY", "SMART_HELMET", "SAFE"]):
                                new_status = "SAFE"
                                new_event = "Rider Safe & Monitoring Active"
                                new_emergency = False
                                log_entry = f"[{current_time}] ✅ SYSTEM: Telemetry restored to normal."

                            current_logs = list(helmet_data["logs"])
                            if log_entry and (len(current_logs) == 0 or current_logs[0] != log_entry):
                                current_logs.insert(0, log_entry)

                            helmet_data = {
                                "status": new_status,
                                "last_event": new_event,
                                "emergency_contact_notified": new_emergency,
                                "emergency_contact": emergency_contact_number,
                                "location": helmet_data["location"],
                                "logs": current_logs[:40]
                            }
        except Exception:
            time.sleep(1.5)

@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=background_serial_reader, daemon=True).start()
    yield

app = FastAPI(title="VigilDrive AI Telemetry", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- REST ENDPOINTS -----------------

@app.get("/api/helmet/status")
def get_status():
    return helmet_data

@app.post("/api/helmet/update_gps")
def update_gps(lat: float, lng: float):
    global helmet_data
    helmet_data["location"] = {
        "lat": lat,
        "lng": lng,
        "address": f"Lat: {lat:.4f}, Lng: {lng:.4f}"
    }
    return {"status": "GPS Updated", "location": helmet_data["location"]}

@app.post("/api/helmet/update_contact")
def update_contact(phone_number: str):
    global emergency_contact_number, helmet_data
    emergency_contact_number = phone_number
    helmet_data["emergency_contact"] = emergency_contact_number
    print(f"✅ Emergency contact updated to: {emergency_contact_number}")
    return {"status": "Success", "emergency_contact": emergency_contact_number}

@app.post("/api/helmet/trigger/{event}")
def manual_trigger(event: str):
    global helmet_data
    current_time = time.strftime("%H:%M:%S")
    current_logs = list(helmet_data["logs"])
    
    if event == "crash":
        dispatch_emergency_sos(helmet_data["location"]["lat"], helmet_data["location"]["lng"])
        helmet_data = {
            "status": "CRASH",
            "last_event": "🚨 CRASH IMPACT DETECTED!",
            "emergency_contact_notified": True,
            "emergency_contact": emergency_contact_number,
            "location": helmet_data["location"],
            "logs": [f"[{current_time}] 🚨 CRASH ALERT: SOS sent to {emergency_contact_number} with GPS link."] + current_logs
        }
    elif event == "drowsy":
        helmet_data = {
            "status": "DROWSY",
            "last_event": "⚠️ DRIVER DROWSINESS DETECTED (Head Nodding)!",
            "emergency_contact_notified": False,
            "emergency_contact": emergency_contact_number,
            "location": helmet_data["location"],
            "logs": [f"[{current_time}] ⚠️ DROWSINESS ALERT: Head tilt threshold exceeded!"] + current_logs
        }
    elif event == "safe":
        helmet_data = {
            "status": "SAFE",
            "last_event": "Rider Safe & Monitoring Active",
            "emergency_contact_notified": False,
            "emergency_contact": emergency_contact_number,
            "location": helmet_data["location"],
            "logs": [f"[{current_time}] ✅ SYSTEM: Normal telemetry synchronized."] + current_logs
        }
    return helmet_data

@app.post("/api/start/{mode}")
def start_mode(mode: str):
    if mode == "three_wheel_vision":
        result = vision_service.start()
        return {"status": result.get("status", "started"), "mode": mode, "detail": result.get("detail")}
    return {"status": "started", "mode": mode}

@app.post("/api/stop")
def stop_mode():
    result = vision_service.stop()
    return {"status": result.get("status", "stopped")}

@app.get("/api/vision/status")
def get_vision_status():
    return vision_service.get_status()

@app.get("/api/video_feed")
def video_feed():
    if not vision_service.is_running():
        vision_service.start()
    return StreamingResponse(
        vision_service.mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

@app.post("/api/vision/frame")
async def vision_frame(request: Request):
    jpeg_bytes = await request.body()
    if not jpeg_bytes:
        return {"error": "No frame data received"}
    return frame_vision_session.process_jpeg(jpeg_bytes)

@app.post("/api/vision/reset")
def vision_reset():
    return frame_vision_session.stop()

if __name__ == "__main__":
    try:
        lan_ip = socket.gethostbyname(socket.gethostname())
    except Exception:
        lan_ip = "127.0.0.1"
    print(f"VigilDrive AI backend starting.")
    print(f"  On this computer:  http://127.0.0.1:5050")
    print(f"  On your phone (same WiFi): http://{lan_ip}:5050")
    print(f"  If the phone can't connect, allow Python through your firewall on port 5050.")

    uvicorn.run(app, host="0.0.0.0", port=5050)