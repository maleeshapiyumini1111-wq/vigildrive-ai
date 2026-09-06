import serial
import time

SERIAL_PORT = "COM2"
BAUD_RATE = 9600

def main():
    print(f"Connecting to Smart Helmet on {SERIAL_PORT}...")
    
    try:
        # Open port with low timeout
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
        time.sleep(1.0)
        ser.reset_input_buffer()  # Clear old garbage data
        print("[SUCCESS] Connected to COM2! Waiting for Sensor Events from Proteus...\n")

        while True:
            # Check if bytes are available in the serial buffer
            if ser.in_waiting > 0:
                # Read all available bytes immediately without waiting for \n
                raw_bytes = ser.read(ser.in_waiting)
                raw_data = raw_bytes.decode("utf-8", errors="ignore").strip()
                
                if raw_data:
                    current_time = time.strftime("%H:%M:%S")

                    if "CRASH" in raw_data:
                        print(f"[{current_time}] 🚨 [ALERT] CRASH DETECTED! Impact Switch triggered.")
                    elif "DROWSY" in raw_data:
                        print(f"[{current_time}] ⚠️  [WARNING] DRIVER DROWSINESS DETECTED (Head Nodding)!")
                    elif any(k in raw_data for k in ["READY", "SMART_HELMET", "SAFE"]):
                        print(f"[{current_time}] ✅ [STATUS] Smart Helmet System Online & Normal.")
                    else:
                        print(f"[{current_time}] [RAW DATA]: {raw_data}")

            time.sleep(0.05)

    except serial.SerialException as error:
        print(f"[ERROR] Could not open {SERIAL_PORT}: {error}")
        print("💡 Proteus COMPIM settings (COM1) සහ Virtual Serial Port Pair (COM1-COM2) පරීක්ෂා කරන්න.")
    except KeyboardInterrupt:
        print("\n[STOPPED] Backend monitoring stopped by user.")
        if 'ser' in locals() and ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()