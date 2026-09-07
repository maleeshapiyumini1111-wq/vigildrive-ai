```python
readme_content = """# VigilDrive AI 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-ATmega32%20%7C%20FastAPI%20%7C%20React%20%7C%20MediaPipe-61dafb.svg)](#)
[![Simulation](https://img.shields.io/badge/Simulation-Proteus%20Design%20Suite-orange.svg)](#)
[![Status](https://img.shields.io/badge/Status-Complete%20Architecture%20v2.0-brightgreen.svg)](#)

> **A Dual-Pipeline Intelligent Driver & Rider Safety Ecosystem:** Bare-Metal Embedded Kinematics for Two-Wheelers & Edge-Vision Cabin Monitoring for Three-Wheelers / Fleets, Unified with Smartphone Satellite Telemetry.

---

## 📌 Architectural Philosophy

Different vehicular realities demand fundamentally tailored sensing strategies:
* **Two-Wheelers:** Cameras fail behind tinted helmet visors and dynamic sunlight. Safety relies on **direct embedded analog sensing** sampled at bare-metal level, while offloading expensive GPS hardware to the rider's smartphone.
* **Three-Wheelers & Commercial Fleets:** Cabin enclosures allow unobstructed optical tracking, replacing physical sensors with **real-time edge computer vision**.

**VigilDrive AI** eliminates costly onboard hardware modules ($150–$400 commercial smart helmets) through an **Edge-Offloaded Architecture**: the embedded node samples bare-metal kinematics, while the user's connected smartphone supplies high-precision satellite GPS telemetry, coordinates indexing, and cellular emergency dispatch.

---

## 🏗️ System Topology


```

+──────────────────────────────────────────────────────────────────────────+
| PIPELINE 1: EMBEDDED TWO-WHEELER KINEMATICS (ATmega32 / Proteus)         |
| • ADC0 (PA0): Head-Tilt / Nodding Analog Sensor                          |
| • ADC1 (PA1): Piezo Structural Impact Force Sensor                       |
| • PD2 (INT0): Hardware Emergency Override Pushbutton                     |
| • PB0 & PB2: Caution Yellow LED & Multi-Tone Active Buzzer Alarm         |
| • USART: 9600 baud, 8-N-1 Serial Stream over Virtual COM Port (VSPD)     |
+────────────────────────────────────┬─────────────────────────────────────+
│ Serial Telemetry Ingest (pyserial)
▼
+──────────────────────────────────────────────────────────────────────────+
| UNIFIED BACKEND & CENTRAL DISPATCH (FastAPI Core: server.py)             |
| • Serial Stream Ingestion & Telemetry Normalization                      |
| • Emergency State Machine & Multi-Level Alert Trigger Pipeline           |
| • Simulated Coordinate Dispatcher (Instant Emergency SMS with Map Pin)   |
+──────────────────▲─────────────────────────────────┬─────────────────────+
│ Inter-Process / REST            │ WebSockets / HTTP
│                                 ▼
+──────────────────┴──────────────────────+  +─────────────────────────────+
| PIPELINE 2: CABIN VISION MONITORING     |  | FRONTEND REACT DASHBOARD    |
| (vision_service.py / drowsiness_monitor)|  | • MotorbikeMonitor.jsx      |
| • MediaPipe Face Mesh (468 Landmarks)   |  | • Real-time ADC & Speed Bar |
| • Eye Aspect Ratio (EAR) Blink Engine   |  | • Smartphone GPS Map Pin    |
| • solvePnP Spatial Head-Pose Estimation |  | • Centralized SOS Alert Hub |
+─────────────────────────────────────────+  +─────────────────────────────+

```

---

## 🏍️ Pipeline 1: Embedded Two-Wheelers (ATmega32)

Developed in Embedded C and fully verified via **Proteus Design Suite**, this node leverages the ATmega32 10-bit successive approximation ADC (0–1023 discretization across 0–5V $V_{REF}$) to continuously evaluate rider status.

### 1. Head Tilt / Nodding Channel (`ADC0` / `PA0`)
Identifies dangerous head drooping indicative of micro-sleep or extreme fatigue:
* **0 - 613 ADC (< 60%):** Normal upright riding posture (nominal state).
* **614 - 1023 ADC (>= 60%):** Sustained downward head displacement detected -> Activates **Yellow Caution LED** and pulsed buzzer warning cadence.

### 2. Piezo Structural Impact Channel (`ADC1` / `PA1`)
Classifies vehicle collision intensity and isolates baseline road noise:
* **0 - 399 ADC (< 40%):** Ambient road vibration, speed bumps, and surface noise -> Automatically suppressed.
* **400 - 749 ADC (40% - 74%):** Moderate impact, sharp jolt, or low-speed tip-over -> Activates **Yellow Caution LED**, intermediate buzzer cadence, and telemetry event log.
* **750 - 1023 ADC (>= 75%):** Severe high-energy structural collision -> Locks on a **continuous high-frequency emergency siren**, signals the connected smartphone gateway to grab instant satellite coordinates, and triggers emergency SOS dispatch.

### 3. Smartphone Satellite GPS Integration (Zero Hardware Cost)
* Rather than adding an expensive, power-hungry GPS hardware module (e.g., NEO-6M) to the embedded board, the system interfaces with the rider's **connected smartphone GPS**.
* When a severe crash (>= 75% ADC1) or manual interrupt (INT0) is validated, the system retrieves the smartphone's live satellite coordinates and builds a dynamic Google Maps URL (`https://maps.google.com/?q=LAT,LON`) for automated SMS broadcast.

### 4. Hardware Interrupt & Serial Pipeline
* **Hardware Interrupt 0 (`PD2` / `INT0`):** Direct manual emergency button override that bypasses ADC sampling to trigger immediate maximum emergency dispatch with live phone GPS coordinates and continuous acoustic siren.
* **Serial Telemetry:** Pushes structured frame strings over **USART at 9600 baud** via Virtual Serial Port Driver (VSPD) straight into `server.py`.

---

## 🚗 Pipeline 2: Vision-Based Cabin Monitoring (Three-Wheelers & Fleets)

Designed for unobstructed cabin setups using an RGB feed and **MediaPipe Face Mesh (468 3D Landmarks)**, processing with low inference latency via `drowsiness_monitor.py` and `vision_service.py`.

### 1. Drowsiness Analysis — Eye Aspect Ratio (EAR)
Tracks Euclidean distances between vertical and horizontal eye fiducials:
* **Condition:** EAR < 0.21 sustained for **> 2.0 seconds**.
* **Action:** Triggers an immediate 880 Hz audio alert and synthesized voice prompt.
* **False-Alarm Mitigation:** Natural blinks (~100 - 300 ms) fall well below the duration gate.

### 2. Distraction Tracking — Perspective-n-Point (solvePnP)
Calculates rotational vectors (Yaw, Pitch, Roll) mapping 2D camera points to a canonical 3D human head model.
* **Condition:** |Yaw| > 20 deg or |Pitch| > 18 deg sustained for **> 2.5 seconds**.
* **Action:** Emits a 523 Hz acoustic sweep and on-screen driver alert.
* **False-Alarm Mitigation:** Quick side-mirror or speedometer checks (< 1.5 seconds) are treated as routine driver scanning and ignored.

---

## 🔌 Hardware Simulation Pinout (ATmega32)

| ATmega32 Pin | Interface | Connected Peripheral | Function |
| :--- | :--- | :--- | :--- |
| **Pin 40 (`PA0`)** | `ADC0` | Potentiometer / Tilt Sensor | Head-drop analog voltage measurement |
| **Pin 39 (`PA1`)** | `ADC1` | Piezo Sensor / Signal Generator | Crash shockwave analog measurement |
| **Pin 16 (`PD2`)** | `INT0` | Push Button (Active Low Pull-Up) | Manual Emergency SOS hardware interrupt |
| **Pin 14 (`PD0`)** | `RXD` | Virtual COMPIM (TX) | Serial control receive line |
| **Pin 15 (`PD1`)** | `TXD` | Virtual COMPIM (RX) | 9600bps Telemetry data transmission line |
| **Pin 1 (`PB0`)** | Digital Out | Yellow LED | Caution & Tilt warning visual indicator |
| **Pin 3 (`PB2`)** | Digital Out | Active Piezo Buzzer | Local acoustic warning sounder & siren |

---

## 📂 Repository File Structure

```text
VigilDrive AI/
├── backend/
│   ├── drowsiness_monitor.py      # Core MediaPipe EAR & Head-Pose vision algorithms
│   ├── server.py                  # FastAPI server, Serial/VSPD reader & WebSocket broker
│   └── vision_service.py          # Vision pipeline service wrapper & camera streamer
├── document/                      # Technical specifications, architecture PDFs & diagrams
├── frontend/
│   ├── public/                    # Static assets, icons, and SVG favicons
│   ├── src/
│   │   ├── assets/                # Visual UI assets
│   │   ├── components/            # Reusable UI modules
│   │   ├── App.css
│   │   ├── App.jsx                # Main application view container
│   │   ├── index.css              # Tailwind base styling
│   │   ├── main.jsx               # React virtual DOM entry point
│   │   └── MotorbikeMonitor.jsx   # Dedicated real-time telemetry dashboard & gauges
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.cjs
│   └── tailwind.config.cjs
├── .gitignore                     # Git build & cache ignore rules
├── .oxlintrc.json
└── README.md                      # Project documentation

```

---

## 🚀 Running the Project Locally

### 1. Embedded Simulation Setup (Proteus)

1. Open your ATmega32 circuit simulation file in **Proteus Design Suite**.
2. Configure a virtual serial port pair (e.g., `COM1` <-> `COM2`) using **com0com** or **VSPD**.
3. In Proteus, set the **COMPIM** module to use `COM1` at `9600` baud.
4. Load the compiled `.hex` file into the ATmega32 properties and start the simulation.

### 2. Backend Gateway (FastAPI & Vision)

```bash
cd backend
pip install fastapi uvicorn pyserial opencv-python mediapipe numpy
uvicorn server:app --reload --host 0.0.0.0 --port 8000

```

### 3. Frontend Dashboard (React + Vite)

```bash
npm install
npm run dev

```

Open `http://localhost:5173` to access the live **MotorbikeMonitor** dashboard.

---

## 📄 License

Distributed under the MIT License. See [LICENSE](https://www.google.com/search?q=LICENSE) for more details.
"""

with open("README.md", "w", encoding="utf-8") as f:
f.write(readme_content)

print("Generated README.md successfully")

```

```text?code_stdout&code_event_index=1
Generated README.md successfully


```

Your Markdown file is ready
[file-tag: code-generated-file-f67383aa-30ae-43c5-8419-1ce3fcbad57a]

කෙලින්ම download කර ගැනීමට අවශ්‍ය නම් ඉහත file එක ලබාගත හැක.

නැතහොත් පහත code block එකේ දකුණු කෙළවරේ ඇති **Copy** icon එක click කර ඔබගේ project එකේ `README.md` file එකට Paste කරගන්න:

```markdown
# VigilDrive AI 🛡️

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-ATmega32%20%7C%20FastAPI%20%7C%20React%20%7C%20MediaPipe-61dafb.svg)](#)
[![Simulation](https://img.shields.io/badge/Simulation-Proteus%20Design%20Suite-orange.svg)](#)
[![Status](https://img.shields.io/badge/Status-Complete%20Architecture%20v2.0-brightgreen.svg)](#)

> **A Dual-Pipeline Intelligent Driver & Rider Safety Ecosystem:** Bare-Metal Embedded Kinematics for Two-Wheelers & Edge-Vision Cabin Monitoring for Three-Wheelers / Fleets, Unified with Smartphone Satellite Telemetry.

---

## 📌 Architectural Philosophy

Different vehicular realities demand fundamentally tailored sensing strategies:
* **Two-Wheelers:** Cameras fail behind tinted helmet visors and dynamic sunlight. Safety relies on **direct embedded analog sensing** sampled at bare-metal level, while offloading expensive GPS hardware to the rider's smartphone.
* **Three-Wheelers & Commercial Fleets:** Cabin enclosures allow unobstructed optical tracking, replacing physical sensors with **real-time edge computer vision**.

**VigilDrive AI** eliminates costly onboard hardware modules ($150–$400 commercial smart helmets) through an **Edge-Offloaded Architecture**: the embedded node samples bare-metal kinematics, while the user's connected smartphone supplies high-precision satellite GPS telemetry, coordinates indexing, and cellular emergency dispatch.

---

## 🏗️ System Topology


```

+──────────────────────────────────────────────────────────────────────────+
| PIPELINE 1: EMBEDDED TWO-WHEELER KINEMATICS (ATmega32 / Proteus)         |
| • ADC0 (PA0): Head-Tilt / Nodding Analog Sensor                          |
| • ADC1 (PA1): Piezo Structural Impact Force Sensor                       |
| • PD2 (INT0): Hardware Emergency Override Pushbutton                     |
| • PB0 & PB2: Caution Yellow LED & Multi-Tone Active Buzzer Alarm         |
| • USART: 9600 baud, 8-N-1 Serial Stream over Virtual COM Port (VSPD)     |
+────────────────────────────────────┬─────────────────────────────────────+
│ Serial Telemetry Ingest (pyserial)
▼
+──────────────────────────────────────────────────────────────────────────+
| UNIFIED BACKEND & CENTRAL DISPATCH (FastAPI Core: server.py)             |
| • Serial Stream Ingestion & Telemetry Normalization                      |
| • Emergency State Machine & Multi-Level Alert Trigger Pipeline           |
| • Simulated Coordinate Dispatcher (Instant Emergency SMS with Map Pin)   |
+──────────────────▲─────────────────────────────────┬─────────────────────+
│ Inter-Process / REST            │ WebSockets / HTTP
│                                 ▼
+──────────────────┴──────────────────────+  +─────────────────────────────+
| PIPELINE 2: CABIN VISION MONITORING     |  | FRONTEND REACT DASHBOARD    |
| (vision_service.py / drowsiness_monitor)|  | • MotorbikeMonitor.jsx      |
| • MediaPipe Face Mesh (468 Landmarks)   |  | • Real-time ADC & Speed Bar |
| • Eye Aspect Ratio (EAR) Blink Engine   |  | • Smartphone GPS Map Pin    |
| • solvePnP Spatial Head-Pose Estimation |  | • Centralized SOS Alert Hub |
+─────────────────────────────────────────+  +─────────────────────────────+

```

---

## 🏍️ Pipeline 1: Embedded Two-Wheelers (ATmega32)

Developed in Embedded C and fully verified via **Proteus Design Suite**, this node leverages the ATmega32 10-bit successive approximation ADC (0–1023 discretization across 0–5V $V_{REF}$) to continuously evaluate rider status.

### 1. Head Tilt / Nodding Channel (`ADC0` / `PA0`)
Identifies dangerous head drooping indicative of micro-sleep or extreme fatigue:
* **0 - 613 ADC (< 60%):** Normal upright riding posture (nominal state).
* **614 - 1023 ADC (>= 60%):** Sustained downward head displacement detected -> Activates **Yellow Caution LED** and pulsed buzzer warning cadence.

### 2. Piezo Structural Impact Channel (`ADC1` / `PA1`)
Classifies vehicle collision intensity and isolates baseline road noise:
* **0 - 399 ADC (< 40%):** Ambient road vibration, speed bumps, and surface noise -> Automatically suppressed.
* **400 - 749 ADC (40% - 74%):** Moderate impact, sharp jolt, or low-speed tip-over -> Activates **Yellow Caution LED**, intermediate buzzer cadence, and telemetry event log.
* **750 - 1023 ADC (>= 75%):** Severe high-energy structural collision -> Locks on a **continuous high-frequency emergency siren**, signals the connected smartphone gateway to grab instant satellite coordinates, and triggers emergency SOS dispatch.

### 3. Smartphone Satellite GPS Integration (Zero Hardware Cost)
* Rather than adding an expensive, power-hungry GPS hardware module (e.g., NEO-6M) to the embedded board, the system interfaces with the rider's **connected smartphone GPS**.
* When a severe crash (>= 75% ADC1) or manual interrupt (INT0) is validated, the system retrieves the smartphone's live satellite coordinates and builds a dynamic Google Maps URL (`https://maps.google.com/?q=LAT,LON`) for automated SMS broadcast.

### 4. Hardware Interrupt & Serial Pipeline
* **Hardware Interrupt 0 (`PD2` / `INT0`):** Direct manual emergency button override that bypasses ADC sampling to trigger immediate maximum emergency dispatch with live phone GPS coordinates and continuous acoustic siren.
* **Serial Telemetry:** Pushes structured frame strings over **USART at 9600 baud** via Virtual Serial Port Driver (VSPD) straight into `server.py`.

---

## 🚗 Pipeline 2: Vision-Based Cabin Monitoring (Three-Wheelers & Fleets)

Designed for unobstructed cabin setups using an RGB feed and **MediaPipe Face Mesh (468 3D Landmarks)**, processing with low inference latency via `drowsiness_monitor.py` and `vision_service.py`.

### 1. Drowsiness Analysis — Eye Aspect Ratio (EAR)
Tracks Euclidean distances between vertical and horizontal eye fiducials:
* **Condition:** EAR < 0.21 sustained for **> 2.0 seconds**.
* **Action:** Triggers an immediate 880 Hz audio alert and synthesized voice prompt.
* **False-Alarm Mitigation:** Natural blinks (~100 - 300 ms) fall well below the duration gate.

### 2. Distraction Tracking — Perspective-n-Point (solvePnP)
Calculates rotational vectors (Yaw, Pitch, Roll) mapping 2D camera points to a canonical 3D human head model.
* **Condition:** |Yaw| > 20 deg or |Pitch| > 18 deg sustained for **> 2.5 seconds**.
* **Action:** Emits a 523 Hz acoustic sweep and on-screen driver alert.
* **False-Alarm Mitigation:** Quick side-mirror or speedometer checks (< 1.5 seconds) are treated as routine driver scanning and ignored.

---

## 🔌 Hardware Simulation Pinout (ATmega32)

| ATmega32 Pin | Interface | Connected Peripheral | Function |
| :--- | :--- | :--- | :--- |
| **Pin 40 (`PA0`)** | `ADC0` | Potentiometer / Tilt Sensor | Head-drop analog voltage measurement |
| **Pin 39 (`PA1`)** | `ADC1` | Piezo Sensor / Signal Generator | Crash shockwave analog measurement |
| **Pin 16 (`PD2`)** | `INT0` | Push Button (Active Low Pull-Up) | Manual Emergency SOS hardware interrupt |
| **Pin 14 (`PD0`)** | `RXD` | Virtual COMPIM (TX) | Serial control receive line |
| **Pin 15 (`PD1`)** | `TXD` | Virtual COMPIM (RX) | 9600bps Telemetry data transmission line |
| **Pin 1 (`PB0`)** | Digital Out | Yellow LED | Caution & Tilt warning visual indicator |
| **Pin 3 (`PB2`)** | Digital Out | Active Piezo Buzzer | Local acoustic warning sounder & siren |

---

## 📂 Repository File Structure

```text
VigilDrive AI/
├── backend/
│   ├── drowsiness_monitor.py      # Core MediaPipe EAR & Head-Pose vision algorithms
│   ├── server.py                  # FastAPI server, Serial/VSPD reader & WebSocket broker
│   └── vision_service.py          # Vision pipeline service wrapper & camera streamer
├── document/                      # Technical specifications, architecture PDFs & diagrams
├── frontend/
│   ├── public/                    # Static assets, icons, and SVG favicons
│   ├── src/
│   │   ├── assets/                # Visual UI assets
│   │   ├── components/            # Reusable UI modules
│   │   ├── App.css
│   │   ├── App.jsx                # Main application view container
│   │   ├── index.css              # Tailwind base styling
│   │   ├── main.jsx               # React virtual DOM entry point
│   │   └── MotorbikeMonitor.jsx   # Dedicated real-time telemetry dashboard & gauges
│   ├── index.html
│   ├── package.json
│   ├── postcss.config.cjs
│   └── tailwind.config.cjs
├── .gitignore                     # Git build & cache ignore rules
├── .oxlintrc.json
└── README.md                      # Project documentation

```

---

## 🚀 Running the Project Locally

### 1. Embedded Simulation Setup (Proteus)

1. Open your ATmega32 circuit simulation file in **Proteus Design Suite**.
2. Configure a virtual serial port pair (e.g., `COM1` <-> `COM2`) using **com0com** or **VSPD**.
3. In Proteus, set the **COMPIM** module to use `COM1` at `9600` baud.
4. Load the compiled `.hex` file into the ATmega32 properties and start the simulation.

### 2. Backend Gateway (FastAPI & Vision)

```bash
cd backend
pip install fastapi uvicorn pyserial opencv-python mediapipe numpy
uvicorn server:app --reload --host 0.0.0.0 --port 8000

```

### 3. Frontend Dashboard (React + Vite)

```bash
npm install
npm run dev

```

Open `http://localhost:5173` to access the live **MotorbikeMonitor** dashboard.

---

## 📄 License

Distributed under the MIT License. See [LICENSE](https://www.google.com/search?q=LICENSE) for more details.

```

```