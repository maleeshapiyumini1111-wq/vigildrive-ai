import React, { useEffect, useState } from 'react';

export default function MotorbikeMonitor({ onBack }) {
  const [helmetData, setHelmetData] = useState({
    status: "SAFE",
    last_event: "Initializing IoT Connection...",
    logs: []
  });
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const response = await fetch("http://127.0.0.1:5050/api/helmet/status");
        if (response.ok) {
          const data = await response.json();
          setHelmetData(data);
          setIsConnected(true);
        }
      } catch (error) {
        setIsConnected(false);
      }
    }, 400); // Poll every 400ms

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-[#0b1120] text-slate-100 p-6 flex flex-col items-center">
      {/* Top Header */}
      <div className="w-full max-w-5xl flex items-center justify-between pb-6 border-b border-slate-800">
        <button
          onClick={onBack}
          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-sm font-medium rounded-lg transition"
        >
          ⬅ Back to Selection
        </button>
        <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          🏍️ Motorbike Smart Helmet Monitor
        </h1>
        <div className="flex items-center gap-2">
          <span className={`h-3 w-3 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
          <span className="text-xs text-slate-400 font-mono">
            {isConnected ? 'IoT COM2 Active' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Main Status Cards */}
      <div className="w-full max-w-5xl grid grid-cols-1 md:grid-cols-3 gap-6 my-6">
        {/* Status Indicator */}
        <div className={`p-6 rounded-2xl border transition-all flex flex-col justify-center items-center shadow-lg ${
          helmetData.status === 'CRASH'
            ? 'bg-rose-950/40 border-rose-500 text-rose-400'
            : helmetData.status === 'DROWSY'
            ? 'bg-amber-950/40 border-amber-500 text-amber-400'
            : 'bg-emerald-950/40 border-emerald-500 text-emerald-400'
        }`}>
          <span className="text-xs uppercase tracking-wider font-semibold opacity-70 mb-1">Rider Status</span>
          <span className="text-2xl font-black tracking-wide">
            {helmetData.status === 'CRASH' && '🚨 CRASH ALERT'}
            {helmetData.status === 'DROWSY' && '⚠️ DROWSY'}
            {helmetData.status === 'SAFE' && '✅ SAFE'}
          </span>
        </div>

        {/* Real-Time Telemetry */}
        <div className="p-6 bg-slate-900/60 border border-slate-800 rounded-2xl md:col-span-2 flex flex-col justify-center shadow-lg">
          <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1">Latest Sensor Event</span>
          <p className="text-lg font-medium text-slate-200">
            {helmetData.last_event}
          </p>
        </div>
      </div>

      {/* Incident Log Feed */}
      <div className="w-full max-w-5xl bg-slate-900/40 border border-slate-800 rounded-2xl p-6 shadow-xl">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Hardware Event Logs (ATmega32 Link)
        </h3>
        <div className="h-56 overflow-y-auto font-mono text-xs bg-slate-950/80 p-4 rounded-xl border border-slate-800/80 space-y-2">
          {helmetData.logs.length === 0 ? (
            <p className="text-slate-600">Awaiting hardware events from Proteus simulation...</p>
          ) : (
            helmetData.logs.map((log, idx) => (
              <div
                key={idx}
                className={`p-1.5 rounded ${
                  log.includes('CRASH')
                    ? 'text-rose-400 bg-rose-950/30'
                    : log.includes('DROWSINESS')
                    ? 'text-amber-400 bg-amber-950/30'
                    : 'text-slate-400'
                }`}
              >
                {log}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}