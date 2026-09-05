import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';
import { Layers, MessageSquare, Radio, PauseCircle, PlayCircle, Clock } from 'lucide-react';

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

export const Queues: React.FC = () => {
  const { data: queueData, isLoading: isQueueLoading } = useQuery<QueueStatusResponse>({
    queryKey: ['queues-status'],
    queryFn: () => fetchApi<QueueStatusResponse>('/admin/queues/status'),
    refetchInterval: 1500,
  });

  const chatItems = queueData?.chat_queue?.items || [];
  const broadcastJobs = queueData?.broadcast_jobs || [];

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Layers className="w-6 h-6 text-indigo-600" />
            Queue Monitor
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Pemantauan real-time Dual Priority Queue: Active Chat (High Priority) & Broadcast Pipeline (Low Priority)
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            Live Polling (1.5s)
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Chat Priority Queue Column */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-indigo-600" />
                <h2 className="text-base font-semibold text-slate-900">
                  Active Chat Queue (High Priority)
                </h2>
              </div>
              <span className="px-2.5 py-0.5 bg-indigo-50 text-indigo-700 font-bold text-xs rounded-full">
                {chatItems.length} Aktif
              </span>
            </div>

            <p className="text-xs text-slate-500">
              Pesan chat masuk diproses FIFO dengan jeda antrean 3 detik. Chat otomatis menyela (yield) pengiriman broadcast jika antrean aktif.
            </p>

            {isQueueLoading && chatItems.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400">Memuat status antrean chat...</div>
            ) : chatItems.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg">
                Tidak ada pesan chat yang sedang menunggu / diproses
              </div>
            ) : (
              <div className="space-y-3">
                {chatItems.map((item) => (
                  <div
                    key={item.id}
                    className="p-3.5 rounded-lg border border-slate-200 bg-slate-50/50 flex items-start justify-between gap-3"
                  >
                    <div className="space-y-1 min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold text-slate-900 text-xs">{item.sender}</span>
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-200 text-slate-700">
                          {item.platform}
                        </span>
                        <span className="font-mono text-[10px] text-slate-400">#{item.id}</span>
                      </div>
                      {item.preview && (
                        <p className="text-xs text-slate-600 truncate">"{item.preview}"</p>
                      )}
                      <div className="flex items-center gap-1 text-[11px] text-slate-400">
                        <Clock className="w-3 h-3" />
                        <span>
                          {Math.max(0, Math.round(Date.now() / 1000 - item.enqueued_at))}s yang lalu
                        </span>
                      </div>
                    </div>

                    <div>
                      {item.status === 'processing' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-100 text-emerald-800 rounded-md font-semibold text-[11px] animate-pulse">
                          <PlayCircle className="w-3.5 h-3.5" />
                          Processing
                        </span>
                      ) : item.status === 'cooldown' ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-100 text-amber-800 rounded-md font-semibold text-[11px]">
                          <PauseCircle className="w-3.5 h-3.5" />
                          Cooldown (3s)
                        </span>
                      ) : (
                        <span className="px-2.5 py-1 bg-slate-200 text-slate-700 rounded-md font-semibold text-[11px]">
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

        {/* Broadcast Queue Overview Column */}
        <div className="lg:col-span-6 space-y-4">
          <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Radio className="w-5 h-5 text-indigo-600" />
                <h2 className="text-base font-semibold text-slate-900">
                  Broadcast Queue (Low Priority)
                </h2>
              </div>
              <span className="px-2.5 py-0.5 bg-slate-100 text-slate-700 font-bold text-xs rounded-full">
                {broadcastJobs.length} Job Terdata
              </span>
            </div>

            <p className="text-xs text-slate-500">
              Antrean pengiriman broadcast massal. Otomatis memberi ruang (yield) kepada antrean chat prioritas tinggi.
            </p>

            {isQueueLoading && broadcastJobs.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400">Memuat status antrean broadcast...</div>
            ) : broadcastJobs.length === 0 ? (
              <div className="py-12 text-center text-sm text-slate-400 border border-dashed border-slate-200 rounded-lg">
                Belum ada antrean broadcast
              </div>
            ) : (
              <div className="space-y-3 max-h-[550px] overflow-y-auto pr-1">
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
                          ? 'border-indigo-300 bg-indigo-50/40'
                          : isYielding
                          ? 'border-amber-300 bg-amber-50/40'
                          : 'border-slate-200 bg-white'
                      } space-y-2.5 transition-all`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className="font-mono text-xs font-semibold text-slate-800">
                              {job.id}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              Div: {job.division}
                            </span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              {job.platform.toUpperCase()}
                            </span>
                          </div>
                          <p className="text-xs text-slate-600 mt-1 line-clamp-1">
                            "{job.message}"
                          </p>
                        </div>

                        <div>
                          {isRunning && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-indigo-100 text-indigo-800 rounded font-semibold text-xs animate-pulse">
                              <PlayCircle className="w-3 h-3" />
                              Running
                            </span>
                          )}
                          {isYielding && (
                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-amber-100 text-amber-800 rounded font-semibold text-xs animate-pulse">
                              <PauseCircle className="w-3 h-3" />
                              Yielding
                            </span>
                          )}
                          {isCompleted && (
                            <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-800 rounded font-semibold text-xs">
                              Completed
                            </span>
                          )}
                          {isCancelled && (
                            <span className="px-2.5 py-0.5 bg-red-100 text-red-800 rounded font-semibold text-xs">
                              Cancelled
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px] text-slate-500">
                          <span>
                            Progress: {job.sent + job.failed}/{job.total} (Sukses: {job.sent}, Gagal: {job.failed})
                          </span>
                          <span className="font-semibold text-slate-700">{progressPct}%</span>
                        </div>
                        <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
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

                      {job.current_recipient && (
                        <div className="text-[11px] text-indigo-600 font-medium">
                          Mengirim ke: {job.current_recipient}
                        </div>
                      )}
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
