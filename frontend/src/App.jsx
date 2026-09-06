import React, { useState, useEffect, useRef } from 'react';

const API_BASE = "http://127.0.0.1:5050/api";

export default function App() {
  const [selectedMode, setSelectedMode] = useState('three_wheel_vision');
  const [isCameraActive, setIsCameraActive] = useState(false);

  const videoRef = useRef(null);
  const audioCtxRef = useRef(null);
  const canvasRef = useRef(null);

  // 1. Emergency Contact State
  const [emergencyPhone, setEmergencyPhone] = useState(
    localStorage.getItem("vigildrive_emergency_contact") || "+94712345678"
  );
  const [isContactSaved, setIsContactSaved] = useState(false);
  const [gpsLocation, setGpsLocation] = useState(null);

  // 2. Two-Wheeler / ATmega32 Telemetry
  const [helmetData, setHelmetData] = useState({
    status: "SAFE",
    last_event: "System Initialized & Monitoring Active",
    emergency_contact_notified: false,
    emergency_contact: emergencyPhone,
    location: { lat: 6.7951, lng: 79.9009, address: "Moratuwa, Sri Lanka" },
    logs: []
  });
  const [isIotConnected, setIsIotConnected] = useState(false);
  const prevHelmetStatusRef = useRef("SAFE");

  // 3. Three-Wheel Real-time AI State
  const [visionData, setVisionData] = useState({
    status: "NORMAL",
    ear: 0.320,
    yaw: 0.0,
    pitch: 0.0,
    drowsyElapsed: 0.0,
    distractionElapsed: 0.0,
    lookDirection: "FORWARD",
    lastEvent: "STATUS: NORMAL - Driver Attentive",
    logs: []
  });

  const [isCvConnected, setIsCvConnected] = useState(false);
  const [visionError, setVisionError] = useState(null);
  const prevVisionStatusRef = useRef("NORMAL");

  // Synchronize Phone / Device GPS to Backend
  useEffect(() => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          const { latitude, longitude } = pos.coords;
          setGpsLocation({ lat: latitude, lng: longitude });
          try {
            await fetch(`${API_BASE}/helmet/update_gps?lat=${latitude}&lng=${longitude}`, {
              method: "POST"
            });
            console.log("📍 Live GPS Synced:", latitude, longitude);
          } catch (err) {
            console.warn("GPS backend sync failed:", err);
          }
        },
        (err) => console.warn("GPS Permission Denied, using Moratuwa fallback.", err)
      );
    }
  }, []);

  // Save Emergency Contact Function
  const saveEmergencyContact = async (num = emergencyPhone) => {
    try {
      const res = await fetch(`${API_BASE}/helmet/update_contact?phone_number=${encodeURIComponent(num)}`, {
        method: "POST"
      });
      if (res.ok) {
        localStorage.setItem("vigildrive_emergency_contact", num);
        setIsContactSaved(true);
        setTimeout(() => setIsContactSaved(false), 3000);
      }
    } catch (err) {
      console.error("Failed to update emergency contact:", err);
    }
  };

  useEffect(() => {
    saveEmergencyContact(emergencyPhone);
  }, []);

  // Audio Synthesizer
  const playAlertTone = (freq, duration, type = "square") => {
    try {
      if (!audioCtxRef.current) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) audioCtxRef.current = new AudioCtx();
      }
      const ctx = audioCtxRef.current;
      if (!ctx) return;

      if (ctx.state === 'suspended') {
        ctx.resume();
      }

      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      gain.gain.setValueAtTime(0.2, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + duration);
      osc.stop(ctx.currentTime + duration);
    } catch (e) {
      console.warn("Audio Context Warning:", e);
    }
  };

  // Motorbike Audio Alarms
  useEffect(() => {
    if (selectedMode === 'bike_simulation' && helmetData.status !== prevHelmetStatusRef.current) {
      if (helmetData.status === 'DROWSY') playAlertTone(480, 0.45, "square");
      else if (helmetData.status === 'CRASH') playAlertTone(880, 1.2, "sawtooth");
      prevHelmetStatusRef.current = helmetData.status;
    }
  }, [helmetData.status, selectedMode]);

  // Vehicle Camera Audio Alarms
  useEffect(() => {
    if (selectedMode === 'three_wheel_vision' && visionData.status !== prevVisionStatusRef.current) {
      if (visionData.status === 'DROWSY') playAlertTone(880, 0.5, "square");
      else if (visionData.status === 'DISTRACTED' || visionData.status === 'NO_FACE') playAlertTone(523, 0.6, "sawtooth");
      prevVisionStatusRef.current = visionData.status;
    }
  }, [visionData.status, selectedMode]);

  // Polling Loop for Motorbike Telemetry
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/helmet/status`);
        if (res.ok) {
          const data = await res.json();
          setHelmetData(data);
          setIsIotConnected(true);
        }
      } catch {
        setIsIotConnected(false);
      }
    }, 400);

    return () => clearInterval(interval);
  }, []);

  // Web Camera Stream Handler
  useEffect(() => {
    let stream = null;

    if (selectedMode === 'three_wheel_vision' && isCameraActive) {
      navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
        .then((s) => {
          stream = s;
          if (videoRef.current) {
            videoRef.current.srcObject = s;
            videoRef.current.play().catch(() => {});
          }
        })
        .catch((err) => {
          console.error("Camera Error:", err);
          setVisionError("Could not access camera: " + err.message);
          setIsCameraActive(false);
        });
    } else {
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach(t => t.stop());
      }
    }

    return () => {
      if (stream) stream.getTracks().forEach(t => t.stop());
    };
  }, [selectedMode, isCameraActive]);

  // Real detection loop: POST frame to backend
  useEffect(() => {
    if (selectedMode !== 'three_wheel_vision' || !isCameraActive) return;

    const interval = setInterval(async () => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;

      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      canvas.toBlob(async (blob) => {
        if (!blob) return;
        try {
          const res = await fetch(`${API_BASE}/vision/frame`, {
            method: 'POST',
            headers: { 'Content-Type': 'image/jpeg' },
            body: blob,
          });
          if (res.ok) {
            const data = await res.json();
            if (data.error) {
              setVisionError(data.error);
              setIsCvConnected(false);
            } else {
              setVisionData(data);
              setIsCvConnected(true);
              setVisionError(null);
            }
          } else {
            setIsCvConnected(false);
          }
        } catch (err) {
          setIsCvConnected(false);
          setVisionError("Could not reach backend at " + API_BASE + " — is server.py running?");
        }
      }, 'image/jpeg', 0.8);
    }, 350);

    return () => clearInterval(interval);
  }, [selectedMode, isCameraActive]);

  const resetVisionSession = async () => {
    try {
      await fetch(`${API_BASE}/vision/reset`, { method: 'POST' });
    } catch (err) {
      console.error(err);
    }
  };

  const triggerManualEvent = async (event) => {
    try {
      const res = await fetch(`${API_BASE}/helmet/trigger/${event}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setHelmetData(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center p-6 font-sans">
      
      {/* BRAND HEADER */}
      <header className="mb-6 text-center w-full max-w-4xl">
        <div className="flex items-center justify-center gap-3">
          <span className="text-4xl">🛡️</span>
          <h1 className="text-3xl font-extrabold tracking-wide bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-500 bg-clip-text text-transparent">
            VigilDrive AI
          </h1>
        </div>
        <p className="text-slate-400 text-sm mt-1">Universal Driver Fatigue, Distraction & Crash Safety System</p>

        {/* EMERGENCY CONTACT & GPS STATUS BAR */}
        <div className="mt-4 p-3 bg-slate-900/90 border border-slate-800 rounded-2xl flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2">
            <span className="text-rose-400 font-bold">🚨 Emergency SMS Target:</span>
            <input
              type="tel"
              value={emergencyPhone}
              onChange={(e) => setEmergencyPhone(e.target.value)}
              placeholder="+947XXXXXXXX"
              className="bg-slate-950 border border-slate-700 px-3 py-1 rounded-lg text-white font-mono focus:outline-none focus:border-indigo-500"
            />
            <button
              onClick={() => saveEmergencyContact(emergencyPhone)}
              className={`px-3 py-1 rounded-lg font-bold transition shadow ${
                isContactSaved ? 'bg-emerald-600 text-white' : 'bg-indigo-600 hover:bg-indigo-500 text-white'
              }`}
            >
              {isContactSaved ? 'Saved ✓' : 'Save'}
            </button>
          </div>

          <div className="flex items-center gap-2 font-mono text-slate-400">
            <span>📍 GPS:</span>
            <span className="text-emerald-400 font-bold">
              {helmetData.location?.lat ? `${Number(helmetData.location.lat).toFixed(4)}, ${Number(helmetData.location.lng).toFixed(4)}` : 'Syncing...'}
            </span>
          </div>
        </div>

        {/* MODE SELECTOR */}
        <div className="flex justify-center gap-3 mt-4">
          <button
            onClick={() => setSelectedMode('bike_simulation')}
            className={`px-5 py-2 rounded-xl text-xs font-bold uppercase tracking-wider transition ${
              selectedMode === 'bike_simulation'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-800'
            }`}
          >
            🏍️ Two-Wheeler / Smart Helmet
          </button>
          <button
            onClick={() => setSelectedMode('three_wheel_vision')}
            className={`px-5 py-2 rounded-xl text-xs font-bold uppercase tracking-wider transition ${
              selectedMode === 'three_wheel_vision'
                ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
                : 'bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-800'
            }`}
          >
            🛺 Three-Wheel & Commercial Vehicle AI
          </button>
        </div>
      </header>

      {/* 1. BIKE / HELMET SIMULATION VIEW */}
      {selectedMode === 'bike_simulation' && (
        <>
          {helmetData.status === 'CRASH' && (
            <div className="w-full max-w-4xl mb-6 bg-rose-600/90 border-2 border-rose-400 text-white p-4 rounded-2xl flex flex-col md:flex-row items-center justify-between shadow-2xl animate-bounce gap-3">
              <div className="flex items-center gap-3">
                <span className="text-3xl">🚨</span>
                <div>
                  <h3 className="font-black text-sm uppercase tracking-wide">EMERGENCY SOS DISPATCHED</h3>
                  <p className="text-xs text-rose-100 font-mono">
                    Crash coordinates and critical alert SMS dispatched to <b>{helmetData.emergency_contact || emergencyPhone}</b>.
                  </p>
                </div>
              </div>
              <a
                href={`https://www.google.com/maps?q=${helmetData.location?.lat || 6.7951},${helmetData.location?.lng || 79.9009}`}
                target="_blank"
                rel="noreferrer"
                className="px-4 py-2 bg-white text-rose-700 font-extrabold text-xs rounded-xl uppercase shadow hover:bg-rose-50 transition"
              >
                View Live Map 🗺️
              </a>
            </div>
          )}

          <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-3xl p-6 flex flex-col items-center shadow-2xl space-y-6">
            <div className="w-full flex justify-between items-center pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <span className="flex h-3 w-3 relative">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                </span>
                <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                  ACTIVE MONITOR: <span className="text-emerald-400">BIKE SIMULATION</span>
                </span>
              </div>
              <span className={`text-xs px-3 py-1 rounded-full font-mono font-bold ${isIotConnected ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'}`}>
                {isIotConnected ? 'COM2 Active' : 'COM2 Offline'}
              </span>
            </div>

            <div className="w-full grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className={`p-5 rounded-2xl border flex flex-col justify-center items-center transition-all shadow-lg ${
                helmetData.status === 'CRASH'
                  ? 'bg-rose-950/80 border-rose-500 text-rose-400 animate-pulse'
                  : helmetData.status === 'DROWSY'
                  ? 'bg-amber-950/80 border-amber-500 text-amber-400'
                  : 'bg-emerald-950/60 border-emerald-500 text-emerald-400'
              }`}>
                <span className="text-xs uppercase font-bold tracking-wider opacity-80 mb-1">Rider Status</span>
                <span className="text-xl font-black">
                  {helmetData.status === 'CRASH' && '🚨 CRASH ALERT'}
                  {helmetData.status === 'DROWSY' && '⚠️ DROWSY ALERT'}
                  {helmetData.status === 'SAFE' && '✅ RIDER SAFE'}
                </span>
              </div>

              <div className="p-5 bg-slate-950/60 border border-slate-800 rounded-2xl md:col-span-2 flex flex-col justify-center shadow-md">
                <span className="text-xs uppercase font-bold text-slate-400 mb-1">Latest Event Trigger</span>
                <p className="text-base font-semibold text-slate-200">
                  {helmetData.last_event}
                </p>
              </div>
            </div>

            <div className="w-full bg-slate-950/70 border border-slate-800 rounded-2xl p-5 shadow-inner">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  ATmega32 Serial Telemetry Feed
                </h4>
                <span className="text-[11px] text-slate-500 font-mono">Baud: 9600 bps</span>
              </div>
              
              <div className="h-44 overflow-y-auto font-mono text-xs bg-black/60 p-3 rounded-xl border border-slate-800/80 space-y-1.5">
                {helmetData.logs.length === 0 ? (
                  <p className="text-slate-600">Awaiting hardware events from Proteus simulation...</p>
                ) : (
                  helmetData.logs.map((log, idx) => (
                    <div
                      key={idx}
                      className={`p-2 rounded transition ${
                        log.includes('CRASH')
                          ? 'text-rose-400 bg-rose-950/50 border-l-4 border-rose-500'
                          : log.includes('DROWSINESS')
                          ? 'text-amber-400 bg-amber-950/50 border-l-4 border-amber-500'
                          : 'text-slate-300 bg-slate-900/40 border-l-2 border-emerald-500'
                      }`}
                    >
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="w-full p-4 bg-slate-950/80 border border-slate-800 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
              <div className="text-xs text-slate-400 font-mono">
                ⚡ Hardware Event Trigger:
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => triggerManualEvent('safe')}
                  className="px-3 py-1.5 bg-emerald-600/80 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg transition"
                >
                  ✅ Normal Safe
                </button>
                <button
                  onClick={() => triggerManualEvent('drowsy')}
                  className="px-3 py-1.5 bg-amber-600/80 hover:bg-amber-500 text-white text-xs font-bold rounded-lg transition"
                >
                  ⚠️ Tilt Head (Drowsy)
                </button>
                <button
                  onClick={() => triggerManualEvent('crash')}
                  className="px-3 py-1.5 bg-rose-600/80 hover:bg-rose-500 text-white text-xs font-bold rounded-lg transition shadow-lg shadow-rose-600/20"
                >
                  🚨 Impact Sensor (Crash)
                </button>
              </div>
            </div>

          </div>
        </>
      )}

      {/* 2. THREE-WHEEL & VEHICLE CAMERA AI VIEW */}
      {selectedMode === 'three_wheel_vision' && (
        <div className="w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-3xl p-6 flex flex-col items-center shadow-2xl space-y-6">
          
          <div className="w-full flex justify-between items-center pb-4 border-b border-slate-800">
            <div className="flex items-center gap-3">
              <span className="flex h-3 w-3 relative">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-blue-500"></span>
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
                ACTIVE MONITOR: <span className="text-blue-400">CABIN CAMERA AI (MEDIAPIPE PIPELINE)</span>
              </span>
            </div>
            
            <button
              onClick={() => setIsCameraActive(!isCameraActive)}
              className={`text-xs px-4 py-1.5 rounded-full font-bold transition shadow ${
                isCameraActive
                  ? 'bg-rose-600 text-white hover:bg-rose-500'
                  : 'bg-emerald-600 text-white hover:bg-emerald-500'
              }`}
            >
              {isCameraActive ? '🛑 Turn Off Camera' : '📷 Open Cabin Camera'}
            </button>
          </div>

          {visionError && (
            <div className="w-full bg-rose-600/90 border-2 border-rose-400 text-white p-4 rounded-2xl">
              <h3 className="font-black text-sm uppercase tracking-wide">Vision pipeline issue</h3>
              <p className="text-xs text-rose-100 font-mono mt-1">{visionError}</p>
            </div>
          )}

          <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
            <div className="relative w-full aspect-video bg-black rounded-2xl overflow-hidden border border-slate-800 flex items-center justify-center shadow-inner">
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className={`w-full h-full object-cover -scale-x-100 ${isCameraActive ? 'block' : 'hidden'}`}
              />

              {!isCameraActive && (
                <div className="flex flex-col items-center text-slate-500 space-y-2">
                  <span className="text-4xl">📹</span>
                  <span className="text-xs font-mono font-bold">Driver Cabin Camera Standby</span>
                  <span className="text-[11px] text-slate-600">Click "Open Cabin Camera" above to activate feed</span>
                </div>
              )}

              {isCameraActive && (
                <div className="absolute top-3 left-3 bg-black/70 backdrop-blur px-3 py-1 rounded-lg border border-slate-700 text-[11px] font-mono text-cyan-400 flex items-center gap-1.5">
                  <span className={`h-2 w-2 rounded-full animate-pulse ${isCvConnected ? 'bg-cyan-400' : 'bg-slate-500'}`}></span>
                  {isCvConnected ? 'OPTICAL SAFETY ACTIVE' : 'CONNECTING TO AI BACKEND...'}
                </div>
              )}
              <canvas ref={canvasRef} className="hidden" />

              {visionData.status !== 'NORMAL' && (
                <div className="absolute inset-0 border-4 border-rose-500/80 animate-pulse pointer-events-none flex items-center justify-center">
                  <span className="bg-rose-600 text-white text-xs font-black uppercase tracking-widest px-4 py-2 rounded-xl shadow-2xl">
                    {visionData.status === 'DROWSY' ? '😴 DROWSINESS ALERT' : '🔄 DISTRACTION ALERT'}
                  </span>
                </div>
              )}
            </div>

            <div className="flex flex-col space-y-3">
              <div className={`p-4 rounded-2xl border transition-all ${
                visionData.status === 'DROWSY'
                  ? 'bg-rose-950/80 border-rose-500 text-rose-400 animate-pulse'
                  : visionData.status === 'DISTRACTED'
                  ? 'bg-amber-950/80 border-amber-500 text-amber-400 animate-bounce'
                  : 'bg-slate-950/70 border-slate-800 text-slate-200'
              }`}>
                <span className="text-[11px] uppercase font-bold text-slate-400 tracking-wider">Vision Pipeline Status</span>
                <h3 className="text-base font-black mt-0.5">{visionData.lastEvent}</h3>
              </div>

              <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block">Eye Aspect (EAR)</span>
                  <span className={`font-bold ${visionData.ear < 0.21 ? 'text-rose-400' : 'text-emerald-400'}`}>
                    {Number(visionData.ear).toFixed(3)} {visionData.ear < 0.21 ? '(CLOSED)' : '(OPEN)'}
                  </span>
                </div>
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl">
                  <span className="text-slate-500 block">Head Pose (Yaw / Pitch)</span>
                  <span className={`font-bold ${Math.abs(visionData.yaw) > 20.0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                    Y:{Number(visionData.yaw).toFixed(1)}° P:{Number(visionData.pitch).toFixed(1)}°
                  </span>
                </div>
              </div>

              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl font-mono text-xs flex justify-between">
                <span className="text-slate-400">Head Direction: <span className="text-blue-400 font-bold">{visionData.lookDirection}</span></span>
                <span className="text-slate-400">Audio Alarm: <span className="text-emerald-400 font-bold">Web Audio Synth Active</span></span>
              </div>
            </div>

          </div>

          <div className="w-full bg-slate-950/70 border border-slate-800 rounded-2xl p-5 shadow-inner">
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                MediaPipe Vision Event Timeline
              </h4>
              <span className="text-[11px] text-slate-500 font-mono">Thresholds: EAR &lt; 0.21 | Yaw &gt; 20° | Pitch &gt; 18°</span>
            </div>
            
            <div className="h-40 overflow-y-auto font-mono text-xs bg-black/60 p-3 rounded-xl border border-slate-800/80 space-y-1.5">
              {visionData.logs.length === 0 ? (
                <p className="text-slate-600">Awaiting facial events from cabin camera stream...</p>
              ) : (
                visionData.logs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`p-2 rounded transition ${
                      log.includes('DROWSINESS')
                        ? 'text-rose-400 bg-rose-950/50 border-l-4 border-rose-500'
                        : log.includes('DISTRACTION')
                        ? 'text-amber-400 bg-amber-950/50 border-l-4 border-amber-500'
                        : 'text-slate-300 bg-slate-900/40 border-l-2 border-blue-500'
                    }`}
                  >
                    {log}
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="w-full p-4 bg-slate-950/80 border border-slate-800 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-xs text-slate-400 font-mono">
              🎯 Real detection: close your eyes &gt;2.0s or look away &gt;2.5s to trigger an alarm.
            </div>
            <button
              onClick={resetVisionSession}
              className="px-3 py-1.5 bg-indigo-600/80 hover:bg-indigo-500 text-white text-xs font-bold rounded-lg transition"
            >
              🔄 Reset Session Timers
            </button>
          </div>

        </div>
      )}

    </div>
  );
}