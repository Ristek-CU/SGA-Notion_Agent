import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, MessageSquare, Send, ArrowLeft, RefreshCw, KeyRound, Lock, User } from 'lucide-react';
import { setToken } from '../api/client';

export const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  // OTP Step State
  const [step, setStep] = useState<'credentials' | 'otp'>('credentials');
  const [sessionId, setSessionId] = useState('');
  const [otp, setOtp] = useState(['', '', '', '', '', '']);
  const [timer, setTimer] = useState(300);
  const [resending, setResending] = useState(false);
  const [infoMessage, setInfoMessage] = useState('');

  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);
  const navigate = useNavigate();

  // Countdown timer for OTP
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (step === 'otp' && timer > 0) {
      interval = setInterval(() => {
        setTimer((prev) => prev - 1);
      }, 1000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [step, timer]);

  // Focus first OTP input when transitioning to OTP step
  useEffect(() => {
    if (step === 'otp') {
      inputRefs.current[0]?.focus();
    }
  }, [step]);

  const handleCredentialsSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfoMessage('');
    setLoading(true);

    try {
      const res = await fetch('/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Login gagal');
      }

      // Check if OTP is required
      if (data.status === 'otp_required' || (data.data && data.data.status === 'otp_required')) {
        const sid = data.session_id || (data.data && data.data.session_id);
        const exp = data.expires_in || (data.data && data.data.expires_in) || 300;
        setSessionId(sid);
        setTimer(exp);
        setStep('otp');
        setOtp(['', '', '', '', '', '']);
        setInfoMessage('Kode OTP 6 digit telah dikirimkan ke WhatsApp & Telegram Salman.');
      } else if (data.data && data.data.token) {
        // Fallback jika OTP dinonaktifkan di backend
        setToken(data.data.token);
        navigate('/');
      } else {
        throw new Error('Format respon tidak valid');
      }
    } catch (err: any) {
      setError(err.message || 'Terjadi kesalahan saat menghubungi server');
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (index: number, val: string) => {
    // Only allow digits
    const cleaned = val.replace(/\D/g, '');
    
    // Support pasting multiple digits (e.g. paste 6-digit OTP directly)
    if (cleaned.length > 1) {
      const pastedDigits = cleaned.slice(0, 6).split('');
      const newOtp = [...otp];
      pastedDigits.forEach((d, i) => {
        if (i < 6) newOtp[i] = d;
      });
      setOtp(newOtp);
      const nextIndex = Math.min(pastedDigits.length, 5);
      inputRefs.current[nextIndex]?.focus();
      return;
    }

    const newOtp = [...otp];
    newOtp[index] = cleaned;
    setOtp(newOtp);

    // Auto-focus next input
    if (cleaned && index < 5) {
      inputRefs.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (index: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Backspace' && !otp[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpSubmit = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const fullOtp = otp.join('');
    if (fullOtp.length !== 6) {
      setError('Harap masukkan 6 digit kode OTP secara lengkap');
      return;
    }

    setError('');
    setLoading(true);

    try {
      const res = await fetch('/admin/login/verify-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          otp: fullOtp,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Verifikasi OTP gagal');
      }

      const token = data.token || (data.data && data.data.token);
      if (token) {
        setToken(token);
        navigate('/');
      } else {
        throw new Error('Token login tidak ditemukan dalam respon');
      }
    } catch (err: any) {
      setError(err.message || 'Gagal memverifikasi OTP');
    } finally {
      setLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (resending || timer > 240) return; // Cooldown 60 detik sebelum boleh kirim ulang
    setResending(true);
    setError('');
    setInfoMessage('');

    try {
      const res = await fetch('/admin/login/resend-otp', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Gagal mengirim ulang OTP');
      }

      setTimer(data.expires_in || (data.data && data.data.expires_in) || 300);
      setOtp(['', '', '', '', '', '']);
      inputRefs.current[0]?.focus();
      setInfoMessage('Kode OTP baru telah dikirimkan ke WhatsApp & Telegram Salman.');
    } catch (err: any) {
      setError(err.message || 'Gagal mengirim ulang OTP');
    } finally {
      setResending(false);
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-900 p-3 sm:p-4 font-sans text-slate-100 relative overflow-hidden">
      {/* Subtle glowing ambient lights */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-blue-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="bg-slate-800/90 backdrop-blur-md p-4 sm:p-8 rounded-2xl border border-slate-700/80 shadow-2xl w-full max-w-md relative z-10 transition-all">
        
        {/* Header Branding */}
        <div className="flex flex-col items-center mb-5 sm:mb-6">
          <div className="w-12 h-12 sm:w-14 sm:h-14 rounded-2xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-500/30 mb-3">
            {step === 'credentials' ? (
              <ShieldCheck className="w-6 h-6 sm:w-7 sm:h-7 text-white" />
            ) : (
              <KeyRound className="w-6 h-6 sm:w-7 sm:h-7 text-white animate-pulse" />
            )}
          </div>
          <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-white text-center">
            {step === 'credentials' ? 'Dashboard Roro' : 'Verifikasi OTP 2-Langkah'}
          </h2>
          <p className="text-xs text-slate-400 mt-1 text-center">
            {step === 'credentials' 
              ? 'Masuk ke dashboard manajemen Notion Agent & Broadcast' 
              : 'Keamanan ekstra: masukkan 6-digit kode verifikasi'}
          </p>
        </div>

        {/* Feedback Messages */}
        {error && (
          <div className="p-3.5 mb-4 bg-red-500/15 border border-red-500/30 text-red-300 rounded-xl text-xs flex items-start space-x-2">
            <span className="font-semibold shrink-0">⚠️ Error:</span>
            <span>{error}</span>
          </div>
        )}

        {infoMessage && (
          <div className="p-3.5 mb-4 bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 rounded-xl text-xs flex items-start space-x-2">
            <span className="font-semibold shrink-0">✅</span>
            <span>{infoMessage}</span>
          </div>
        )}

        {step === 'credentials' ? (
          /* Step 1: Username & Password Form */
          <form onSubmit={handleCredentialsSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Username
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input 
                  type="text" 
                  value={username} 
                  onChange={e => setUsername(e.target.value)} 
                  placeholder="admin"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-900/70 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                  required 
                  autoFocus
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                <input 
                  type="password" 
                  value={password} 
                  onChange={e => setPassword(e.target.value)} 
                  placeholder="••••••••"
                  className="w-full pl-10 pr-3.5 py-2.5 bg-slate-900/70 border border-slate-700 rounded-xl text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                  required 
                />
              </div>
            </div>

            <button 
              type="submit" 
              disabled={loading}
              className="w-full mt-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white py-2.5 px-4 rounded-xl font-medium text-sm transition-all duration-200 shadow-md shadow-indigo-600/20 flex items-center justify-center space-x-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Memvalidasi...</span>
                </>
              ) : (
                <span>Lanjutkan</span>
              )}
            </button>
          </form>
        ) : (
          /* Step 2: OTP Verification Form */
          <form onSubmit={handleOtpSubmit} className="space-y-5">
            {/* Target Information Card */}
            <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-700/60 text-xs space-y-2">
              <div className="flex items-center space-x-2 text-slate-300 font-medium">
                <MessageSquare className="w-4 h-4 text-emerald-400 shrink-0" />
                <span className="truncate">WhatsApp: +62 851-7501-9086</span>
              </div>
              <div className="flex items-center space-x-2 text-slate-300 font-medium">
                <Send className="w-4 h-4 text-sky-400 shrink-0" />
                <span className="truncate">Telegram: @pangestuu19 (Salman)</span>
              </div>
            </div>

            {/* OTP Input Boxes */}
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2.5 text-center">
                Masukkan 6 Digit OTP
              </label>
              <div className="flex justify-center gap-1.5 sm:gap-2">
                {otp.map((digit, idx) => (
                  <input
                    key={idx}
                    ref={(el) => (inputRefs.current[idx] = el)}
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    value={digit}
                    onChange={(e) => handleOtpChange(idx, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(idx, e)}
                    className="w-9 h-11 sm:w-12 sm:h-13 text-center text-lg sm:text-xl font-bold bg-slate-900 border border-slate-700 rounded-lg sm:rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition"
                  />
                ))}
              </div>
            </div>

            {/* Expiry & Resend Controls */}
            <div className="flex items-center justify-between text-xs text-slate-400 pt-1">
              <span>
                Masa berlaku: <span className={`font-mono font-semibold ${timer <= 60 ? 'text-red-400' : 'text-indigo-300'}`}>{formatTimer(timer)}</span>
              </span>
              <button
                type="button"
                onClick={handleResendOtp}
                disabled={resending || timer > 240}
                className="text-indigo-400 hover:text-indigo-300 font-medium disabled:opacity-40 disabled:cursor-not-allowed transition flex items-center space-x-1"
              >
                <RefreshCw className={`w-3 h-3 ${resending ? 'animate-spin' : ''}`} />
                <span>{timer > 240 ? `Tunggu ${timer - 240}s` : 'Kirim Ulang'}</span>
              </button>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2 pt-2">
              <button
                type="submit"
                disabled={loading || otp.join('').length !== 6 || timer === 0}
                className="w-full bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white py-2.5 px-4 rounded-xl font-medium text-sm transition-all duration-200 shadow-md shadow-indigo-600/20 flex items-center justify-center space-x-2 disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Memverifikasi...</span>
                  </>
                ) : (
                  <span>Verifikasi & Masuk</span>
                )}
              </button>

              <button
                type="button"
                onClick={() => {
                  setStep('credentials');
                  setError('');
                  setInfoMessage('');
                }}
                className="w-full py-2 text-xs text-slate-400 hover:text-slate-200 transition flex items-center justify-center space-x-1.5"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>Kembali ke login username</span>
              </button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
};
