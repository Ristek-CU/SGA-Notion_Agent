import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';
import { Send, MessageSquare, Radio, PauseCircle, PlayCircle, XCircle, Clock } from 'lucide-react';

interface ChatQueueItem {
  id: string;
  sender: string;
  platform: string;
  preview: string;
  status: 'waiting' | 'processing' | 'cooldown';
  enqueued_at: number;
}

interface BroadcastJob {
  id: string;
  message: string;
  division: string;
  platform: string;
  delay_seconds: number;
  total: number;
  sent: number;
  failed: number;
  current_recipient: string | null;
  status: 'running' | 'yielding' | 'completed' | 'cancelled';
  created_at: number;
}

interface QueueStatusResponse {
  chat_queue: {
    active_count: number;
    items: ChatQueueItem[];
  };
  broadcast_jobs: BroadcastJob[];
}

export const Broadcast: React.FC = () => {
  const queryClient = useQueryClient();
  const [message, setMessage] = useState('');
  const [division, setDivision] = useState('all');
  const [platform, setPlatform] = useState('all');
  const [delaySeconds, setDelaySeconds] = useState(5);
  const [recipientsOverride, setRecipientsOverride] = useState('');

  // Fetch unique divisions
  const { data: divisions = [] } = useQuery<string[]>({
    queryKey: ['contacts-divisions'],
    queryFn: () => fetchApi<string[]>('/admin/contacts/divisions'),
  });

  // Polling queue status every 1.5s
  const { data: queueData, isLoading: isQueueLoading } = useQuery<QueueStatusResponse>({
    queryKey: ['queues-status'],
    queryFn: () => fetchApi<QueueStatusResponse>('/admin/queues/status'),
    refetchInterval: 1500,
  });

  const send = useMutation({
    mutationFn: () =>
      fetchApi<any>('/admin/broadcast', {
        method: 'POST',
        body: JSON.stringify({
          message,
          division,
          platform,
          delay_seconds: Number(delaySeconds) || 5,
          recipients: recipientsOverride
            ? recipientsOverride
                .split(',')
                .map((r) => r.trim())
                .filter(Boolean)
            : undefined,
        }),
      }),
    onSuccess: () => {
      setMessage('');
      queryClient.invalidateQueries({ queryKey: ['queues-status'] });
    },
  });

  const cancelJob = useMutation({
    mutationFn: (jobId: string) =>
      fetchApi<any>('/admin/broadcast/cancel', {
        method: 'POST',
        body: JSON.stringify({ job_id: jobId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['queues-status'] });
    },
  });

  const chatItems = queueData?.chat_queue?.items || [];
  const broadcastJobs = queueData?.broadcast_jobs || [];

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Broadcast & Queue Monitor</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Kirim pengumuman massal dengan filter divisi & platform serta pantau dual priority queue
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Form Column */}
        <div className="lg:col-span-6 space-y-6">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
              <Send className="w-4 h-4 text-indigo-600" />
              Buat Broadcast Baru
            </h2>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Pesan Pengumuman</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={4}
                className="w-full p-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                placeholder="Tulis pesan pengumuman di sini..."
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Target Divisi</label>
                <select
                  value={division}
                  onChange={(e) => setDivision(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                >
                  <option value="all">Semua Divisi (All)</option>
                  {divisions.map((div) => (
                    <option key={div} value={div}>
                      {div}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Platform</label>
                <select
                  value={platform}
                  onChange={(e) => setPlatform(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm bg-white focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                >
                  <option value="all">Semua Platform (WA & TG)</option>
                  <option value="wa">WhatsApp Saja</option>
                  <option value="telegram">Telegram Saja</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Delay per Pesan (detik)
                </label>
                <input
                  type="number"
                  min="1"
                  max="60"
                  value={delaySeconds}
                  onChange={(e) => setDelaySeconds(Number(e.target.value))}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">
                  Override Penerima <span className="text-slate-400 font-normal">(Opsional)</span>
                </label>
                <input
                  value={recipientsOverride}
                  onChange={(e) => setRecipientsOverride(e.target.value)}
                  className="w-full p-2.5 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:outline-hidden"
                  placeholder="0812xxx, Mika, @username"
                />
              </div>
            </div>

            <div className="pt-2 flex items-center justify-between">
              <button
                onClick={() => send.mutate()}
                disabled={send.isPending || !message.trim()}
                className="px-5 py-2.5 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-2 cursor-pointer transition-colors"
              >
                <Send className="w-4 h-4" />
                {send.isPending ? 'Memasukkan Antrean...' : 'Mulai Broadcast'}
              </button>

              {send.isError && (
                <span className="text-xs text-red-600 font-medium">
                  Gagal: {(send.error as Error)?.message}
                </span>
              )}
            </div>
          </div>

          {/* Chat Queue Card */}
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-emerald-600" />
                <h2 className="text-base font-semibold text-slate-900">Active Chat Queue (High Priority)</h2>
              </div>
              <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
                {chatItems.length} antrean
              </span>
            </div>
            <p className="text-xs text-slate-500">
              Incoming pesan chat diproses FIFO dengan jeda antrean 3s. Chat otomatis menyela (yield) pengiriman broadcast.
            </p>

            {chatItems.length === 0 ? (
              <div className="py-6 text-center text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg">
                Tidak ada chat yang sedang mengantre (Queue Idle)
              </div>
            ) : (
              <div className="space-y-2 max-h-56 overflow-y-auto">
                {chatItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs"
                  >
                    <div className="space-y-1 max-w-[70%]">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{item.sender}</span>
                        <span className="px-1.5 py-0.5 rounded-xs bg-slate-200 text-slate-700 text-[10px]">
                          {item.platform}
                        </span>
                      </div>
                      <p className="text-slate-600 truncate">{item.preview || '(Pesan)'}</p>
                    </div>
                    <div>
                      {item.status === 'processing' && (
                        <span className="px-2 py-1 bg-amber-100 text-amber-800 rounded-md font-medium text-[11px] animate-pulse">
                          Processing
                        </span>
                      )}
                      {item.status === 'cooldown' && (
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-md font-medium text-[11px]">
                          Cooldown 3s
                        </span>
                      )}
                      {item.status === 'waiting' && (
                        <span className="px-2 py-1 bg-slate-200 text-slate-700 rounded-md font-medium text-[11px]">
                          Waiting
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Live Broadcast Visualizer Column */}
        <div className="lg:col-span-6 space-y-6">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="w-4 h-4 text-indigo-600" />
                <h2 className="text-base font-semibold text-slate-900">Broadcast Queue (Low Priority)</h2>
              </div>
              <span className="text-xs text-slate-400">Live Status (1.5s)</span>
            </div>

            {isQueueLoading && broadcastJobs.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400">Memuat status antrean...</div>
            ) : broadcastJobs.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg">
                Belum ada antrean atau riwayat broadcast
              </div>
            ) : (
              <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
                {broadcastJobs.map((job) => {
                  const progressPct =
                    job.total > 0 ? Math.round(((job.sent + job.failed) / job.total) * 100) : 100;
                  const isRunning = job.status === 'running';
                  const isYielding = job.status === 'yielding';
                  const isCompleted = job.status === 'completed';
                  const isCancelled = job.status === 'cancelled';

                  return (
                    <div
                      key={job.id}
                      className={`p-4 rounded-xl border ${
                        isRunning
                          ? 'border-indigo-300 bg-indigo-50/30'
                          : isYielding
                          ? 'border-amber-300 bg-amber-50/30'
                          : 'border-slate-200 bg-white'
                      } space-y-3 transition-all`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs font-semibold text-slate-700">
                              {job.id}
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700">
                              Divisi: {job.division}
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700">
                              Platform: {job.platform.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 mt-1 line-clamp-2">
                            "{job.message}"
                          </p>
                        </div>

                        <div>
                          {isRunning && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-indigo-100 text-indigo-800 rounded-md font-semibold text-xs animate-pulse">
                              <PlayCircle className="w-3.5 h-3.5" />
                              Running
                            </span>
                          )}
                          {isYielding && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-100 text-amber-800 rounded-md font-semibold text-xs animate-pulse">
                              <PauseCircle className="w-3.5 h-3.5" />
                              Yielding (Chat Active)
                            </span>
                          )}
                          {isCompleted && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-md font-semibold text-xs">
                              Completed
                            </span>
                          )}
                          {isCancelled && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-100 text-red-800 rounded-md font-semibold text-xs">
                              Cancelled
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-slate-500">
                          <span>
                            Progress: {job.sent + job.failed} / {job.total} (Terkirim: {job.sent}
                            {job.failed > 0 ? `, Gagal: ${job.failed}` : ''})
                          </span>
                          <span className="font-semibold text-slate-700">{progressPct}%</span>
                        </div>
                        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-300 ${
                              isCancelled
                                ? 'bg-red-500'
                                : isYielding
                                ? 'bg-amber-500'
                                : 'bg-indigo-600'
                            }`}
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>
                      </div>

                      {/* Footer Info & Actions */}
                      <div className="flex items-center justify-between text-xs pt-1 border-t border-slate-100">
                        <div className="text-slate-500">
                          {job.current_recipient ? (
                            <span className="text-indigo-600 font-medium">
                              Mengirim ke: {job.current_recipient}
                            </span>
                          ) : (
                            <span>Jeda: {job.delay_seconds}s</span>
                          )}
                        </div>

                        {(isRunning || isYielding) && (
                          <button
                            onClick={() => cancelJob.mutate(job.id)}
                            disabled={cancelJob.isPending}
                            className="inline-flex items-center gap-1 px-2.5 py-1 bg-red-50 text-red-600 hover:bg-red-100 rounded-md text-xs font-semibold cursor-pointer transition-colors"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Batalkan
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
