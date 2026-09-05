import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';
import {
  Send,
  Radio,
  PlayCircle,
  PauseCircle,
  XCircle,
  CheckCircle2,
  AlertCircle,
  Clock,
  History,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Users,
  Search,
  ExternalLink,
  MessageSquare
} from 'lucide-react';

interface RecipientItem {
  contact_id?: string;
  name: string;
  platform: string;
  target: string;
  division?: string;
  status: 'pending' | 'sent' | 'failed';
  error?: string | null;
  sent_at?: number | null;
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
  status: 'running' | 'yielding' | 'pending' | 'completed' | 'cancelled';
  created_at: number;
  completed_at?: number | null;
  recipients?: RecipientItem[];
}

export const Broadcast: React.FC = () => {
  const queryClient = useQueryClient();

  // Form State
  const [message, setMessage] = useState('');
  const [division, setDivision] = useState('all');
  const [platform, setPlatform] = useState('all');
  const [delaySeconds, setDelaySeconds] = useState(5);
  const [recipientsOverride, setRecipientsOverride] = useState('');

  // UI State
  const [activeTab, setActiveTab] = useState<'create' | 'status' | 'history'>('create');
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [selectedJobForModal, setSelectedJobForModal] = useState<BroadcastJob | null>(null);
  const [recipientFilter, setRecipientFilter] = useState<'all' | 'sent' | 'failed' | 'pending'>('all');
  const [recipientSearch, setRecipientSearch] = useState('');

  // Queries
  const { data: divisions = [] } = useQuery<string[]>({
    queryKey: ['contacts-divisions'],
    queryFn: () => fetchApi<string[]>('/admin/contacts/divisions'),
  });

  const { data: activeJobs = [], isLoading: isLoadingActive, refetch: refetchActive } = useQuery<BroadcastJob[]>({
    queryKey: ['broadcast-active'],
    queryFn: () => fetchApi<BroadcastJob[]>('/admin/broadcast/active'),
    refetchInterval: 1500,
  });

  const { data: historyJobs = [], isLoading: isLoadingHistory, refetch: refetchHistory } = useQuery<BroadcastJob[]>({
    queryKey: ['broadcast-history'],
    queryFn: () => fetchApi<BroadcastJob[]>('/admin/broadcast/history?limit=50'),
  });

  // Mutations
  const sendMutation = useMutation({
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
      queryClient.invalidateQueries({ queryKey: ['broadcast-active'] });
      queryClient.invalidateQueries({ queryKey: ['broadcast-history'] });
      queryClient.invalidateQueries({ queryKey: ['queues-status'] });
      setActiveTab('status');
    },
  });

  const cancelJobMutation = useMutation({
    mutationFn: (jobId: string) =>
      fetchApi<any>('/admin/broadcast/cancel', {
        method: 'POST',
        body: JSON.stringify({ job_id: jobId }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['broadcast-active'] });
      queryClient.invalidateQueries({ queryKey: ['broadcast-history'] });
    },
  });

  const runningOrWaitingCount = activeJobs.length;

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2.5">
            <Send className="w-6 h-6 text-indigo-600" />
            Broadcast Hub
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Manajemen pengiriman pengumuman massal, pemantauan status penerima detail, dan riwayat siaran
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center p-1 bg-slate-100 rounded-xl border border-slate-200/80">
          <button
            onClick={() => setActiveTab('create')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === 'create'
                ? 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            Buat Broadcast
          </button>
          <button
            onClick={() => setActiveTab('status')}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer relative ${
              activeTab === 'status'
                ? 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            Status Berjalan
            {runningOrWaitingCount > 0 && (
              <span className="w-2 h-2 rounded-full bg-indigo-600 animate-ping" />
            )}
          </button>
          <button
            onClick={() => {
              setActiveTab('history');
              refetchHistory();
            }}
            className={`flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
              activeTab === 'history'
                ? 'bg-white text-indigo-600 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            Riwayat Broadcast
          </button>
        </div>
      </div>

      {/* TAB 1: FORM BUAT BROADCAST */}
      {activeTab === 'create' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8 space-y-6">
            <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-5">
              <h2 className="text-base font-semibold text-slate-900 flex items-center gap-2">
                <Send className="w-4 h-4 text-indigo-600" />
                Form Pengiriman Broadcast
              </h2>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Isi Pesan Pengumuman
                </label>
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={5}
                  placeholder="Tulis pesan pengumuman untuk dikirimkan secara serentak ke tim..."
                  className="w-full px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white transition-all font-sans"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Format otomatis menyertakan header divisi dan penutup bot secara otomatis.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Target Divisi
                  </label>
                  <select
                    value={division}
                    onChange={(e) => setDivision(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white"
                  >
                    <option value="all">Semua Divisi (Seluruh Anggota)</option>
                    {divisions.map((d) => (
                      <option key={d} value={d}>
                        Divisi {d}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Platform Pengiriman
                  </label>
                  <select
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white"
                  >
                    <option value="all">Semua Platform (WhatsApp & Telegram)</option>
                    <option value="wa">WhatsApp Saja</option>
                    <option value="telegram">Telegram Saja</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Jeda Antar Pesan (Detik)
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={delaySeconds}
                    onChange={(e) => setDelaySeconds(Number(e.target.value))}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Direkomendasikan minimal 5s untuk mencegah anti-spam ban.
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Target Khusus / Override (Opsional)
                  </label>
                  <input
                    type="text"
                    value={recipientsOverride}
                    onChange={(e) => setRecipientsOverride(e.target.value)}
                    placeholder="Contoh: 628123456789, @username, Salman"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-900 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 focus:bg-white"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Pisahkan dengan koma jika ingin mengirim ke kontak tertentu saja.
                  </p>
                </div>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  disabled={!message.trim() || sendMutation.isPending}
                  onClick={() => sendMutation.mutate()}
                  className="w-full sm:w-auto px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer transition-colors shadow-xs"
                >
                  <Send className="w-4 h-4" />
                  {sendMutation.isPending ? 'Mendaftarkan Broadcast...' : 'Jalankan Broadcast Sekarang'}
                </button>
              </div>
            </div>
          </div>

          <div className="lg:col-span-4 space-y-4">
            <div className="bg-slate-50 p-5 rounded-xl border border-slate-200 space-y-3">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-indigo-600" />
                Ketentuan Dual Priority
              </h3>
              <ul className="text-xs text-slate-600 space-y-2 list-disc pl-4 leading-relaxed">
                <li>
                  <span className="font-semibold text-slate-800">Chat Menyela Otomatis:</span> Setiap kali ada pesan chat pengguna masuk, broadcast worker akan otomatis berhenti sejenak (Yielding) sampai pesan chat selesai dikirim.
                </li>
                <li>
                  <span className="font-semibold text-slate-800">Detail Status Penerima:</span> Setiap kontak penerima akan dicatat statusnya: Berhasil terkirim, Gagal (beserta pesan kegagalan), atau Menunggu antrean.
                </li>
                <li>
                  <span className="font-semibold text-slate-800">Pembatalan Aman:</span> Anda dapat membatalkan siaran yang sedang berjalan kapan saja melalui tab Status Berjalan.
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: STATUS BROADCAST (RUNNING & WAITING) */}
      {activeTab === 'status' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Radio className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base font-semibold text-slate-900">
                Status Siaran Berjalan & Menunggu Antrean
              </h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => refetchActive()}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors"
                title="Refresh Status"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
              <span className="text-xs text-slate-400">Live Polling (1.5s)</span>
            </div>
          </div>

          {isLoadingActive && activeJobs.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-400 bg-white rounded-xl border border-slate-200">
              Memuat status siaran berjalan...
            </div>
          ) : activeJobs.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-500 bg-white rounded-xl border border-dashed border-slate-200 space-y-2">
              <Radio className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="font-medium text-slate-700">Tidak ada broadcast yang sedang berjalan</p>
              <p className="text-xs text-slate-400">
                Semua tugas broadcast telah selesai atau belum ada pengiriman aktif.
              </p>
              <button
                onClick={() => setActiveTab('create')}
                className="mt-2 inline-flex items-center gap-1 px-3.5 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
              >
                <Send className="w-3.5 h-3.5" />
                Buat Broadcast Baru
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {activeJobs.map((job) => {
                const progressPct =
                  job.total > 0 ? Math.round(((job.sent + job.failed) / job.total) * 100) : 0;
                const isRunning = job.status === 'running';
                const isYielding = job.status === 'yielding';
                const recipients = job.recipients || [];
                const isExpanded = expandedJobId === job.id;

                const sentCount = recipients.filter((r) => r.status === 'sent').length;
                const failedCount = recipients.filter((r) => r.status === 'failed').length;
                const pendingCount = recipients.filter((r) => r.status === 'pending').length;

                return (
                  <div
                    key={job.id}
                    className={`bg-white rounded-xl border ${
                      isRunning
                        ? 'border-indigo-300 ring-2 ring-indigo-500/10'
                        : isYielding
                        ? 'border-amber-300 ring-2 ring-amber-500/10'
                        : 'border-slate-200'
                    } overflow-hidden shadow-xs transition-all`}
                  >
                    {/* Header */}
                    <div className="p-5 space-y-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono text-xs font-bold text-slate-900 bg-slate-100 px-2 py-0.5 rounded">
                              {job.id}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-700">
                              Divisi: {job.division}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-slate-100 text-slate-700">
                              Platform: {job.platform.toUpperCase()}
                            </span>
                            <span className="text-xs text-slate-400">
                              Jeda: {job.delay_seconds}s
                            </span>
                          </div>
                          <p className="text-sm font-medium text-slate-800 mt-1">"{job.message}"</p>
                        </div>

                        <div className="flex items-center gap-2">
                          {isRunning && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-100 text-indigo-800 rounded-full font-semibold text-xs animate-pulse">
                              <PlayCircle className="w-3.5 h-3.5" />
                              Sedang Mengirim
                            </span>
                          )}
                          {isYielding && (
                            <span className="inline-flex items-center gap-1.5 px-3 py-1 bg-amber-100 text-amber-800 rounded-full font-semibold text-xs animate-pulse">
                              <PauseCircle className="w-3.5 h-3.5" />
                              Menyela (Chat Aktif)
                            </span>
                          )}

                          <button
                            onClick={() => cancelJobMutation.mutate(job.id)}
                            disabled={cancelJobMutation.isPending}
                            className="inline-flex items-center gap-1 px-3 py-1 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                          >
                            <XCircle className="w-3.5 h-3.5" />
                            Batalkan
                          </button>
                        </div>
                      </div>

                      {/* Progress Bar & Badges */}
                      <div className="space-y-2 pt-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-slate-600">
                            Kemajuan: <span className="font-semibold text-slate-900">{job.sent + job.failed}</span> dari{' '}
                            <span className="font-semibold text-slate-900">{job.total}</span> penerima
                          </span>
                          <span className="font-bold text-slate-900">{progressPct}%</span>
                        </div>
                        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full transition-all duration-300 ${
                              isYielding ? 'bg-amber-500' : 'bg-indigo-600'
                            }`}
                            style={{ width: `${progressPct}%` }}
                          />
                        </div>

                        {/* Counts summary pills */}
                        <div className="flex items-center gap-3 pt-1 text-xs">
                          <span className="inline-flex items-center gap-1 text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200/60 font-medium">
                            <CheckCircle2 className="w-3 h-3" /> Berhasil: {job.sent}
                          </span>
                          <span className="inline-flex items-center gap-1 text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-200/60 font-medium">
                            <AlertCircle className="w-3 h-3" /> Gagal: {job.failed}
                          </span>
                          <span className="inline-flex items-center gap-1 text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-200/60 font-medium">
                            <Clock className="w-3 h-3" /> Menunggu: {Math.max(0, job.total - (job.sent + job.failed))}
                          </span>
                          {job.current_recipient && (
                            <span className="text-indigo-600 font-semibold ml-auto animate-pulse text-[11px]">
                              Mengirim ke: {job.current_recipient}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Toggle Recipient Breakdown */}
                    <div className="border-t border-slate-100 bg-slate-50/70 px-5 py-2.5 flex items-center justify-between">
                      <button
                        onClick={() => setExpandedJobId(isExpanded ? null : job.id)}
                        className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 inline-flex items-center gap-1 cursor-pointer"
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp className="w-3.5 h-3.5" /> Sembunyikan Detail Kontak Target
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3.5 h-3.5" /> Lihat Detail Kontak Target ({recipients.length})
                          </>
                        )}
                      </button>

                      <span className="text-[11px] text-slate-400">
                        Dibuat: {new Date(job.created_at * 1000).toLocaleTimeString()}
                      </span>
                    </div>

                    {/* Collapsible Recipient Table */}
                    {isExpanded && (
                      <div className="p-4 border-t border-slate-200 bg-white">
                        <div className="max-h-72 overflow-y-auto rounded-lg border border-slate-200">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 sticky top-0">
                              <tr>
                                <th className="px-3 py-2 font-medium">Nama</th>
                                <th className="px-3 py-2 font-medium">Target</th>
                                <th className="px-3 py-2 font-medium">Platform</th>
                                <th className="px-3 py-2 font-medium">Divisi</th>
                                <th className="px-3 py-2 font-medium">Status</th>
                                <th className="px-3 py-2 font-medium">Keterangan / Error</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 text-slate-700">
                              {recipients.length === 0 ? (
                                <tr>
                                  <td colSpan={6} className="px-3 py-4 text-center text-slate-400">
                                    Tidak ada daftar penerima ditemukan
                                  </td>
                                </tr>
                              ) : (
                                recipients.map((r, idx) => (
                                  <tr key={idx} className="hover:bg-slate-50/60">
                                    <td className="px-3 py-2 font-medium text-slate-900">{r.name}</td>
                                    <td className="px-3 py-2 font-mono text-[11px]">{r.target}</td>
                                    <td className="px-3 py-2 uppercase text-[10px] font-semibold">
                                      {r.platform}
                                    </td>
                                    <td className="px-3 py-2">{r.division || '-'}</td>
                                    <td className="px-3 py-2">
                                      {r.status === 'sent' && (
                                        <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-[11px]">
                                          <CheckCircle2 className="w-3 h-3" /> Sukses
                                        </span>
                                      )}
                                      {r.status === 'failed' && (
                                        <span className="inline-flex items-center gap-1 text-red-700 font-semibold text-[11px]">
                                          <AlertCircle className="w-3 h-3" /> Gagal
                                        </span>
                                      )}
                                      {r.status === 'pending' && (
                                        <span className="inline-flex items-center gap-1 text-slate-500 font-semibold text-[11px]">
                                          <Clock className="w-3 h-3" /> Pending
                                        </span>
                                      )}
                                    </td>
                                    <td className="px-3 py-2 text-red-600 font-mono text-[10px]">
                                      {r.error || '-'}
                                    </td>
                                  </tr>
                                ))
                              )}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: HISTORY BROADCAST (COMPLETED & CANCELLED) */}
      {activeTab === 'history' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <History className="w-5 h-5 text-indigo-600" />
              <h2 className="text-base font-semibold text-slate-900">
                Riwayat Siaran Selesai & Dibatalkan
              </h2>
            </div>
            <button
              onClick={() => refetchHistory()}
              className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors inline-flex items-center gap-1 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </button>
          </div>

          {isLoadingHistory && historyJobs.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-400 bg-white rounded-xl border border-slate-200">
              Memuat riwayat siaran...
            </div>
          ) : historyJobs.length === 0 ? (
            <div className="py-16 text-center text-sm text-slate-500 bg-white rounded-xl border border-dashed border-slate-200 space-y-2">
              <History className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="font-medium text-slate-700">Belum ada riwayat broadcast</p>
              <p className="text-xs text-slate-400">
                Siaran yang selesai atau dibatalkan akan tercatat rapi di sini lengkap dengan detail penerima.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-600 border-b border-slate-200">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Job ID & Waktu</th>
                      <th className="px-4 py-3 font-semibold">Divisi & Platform</th>
                      <th className="px-4 py-3 font-semibold">Pesan</th>
                      <th className="px-4 py-3 font-semibold text-center">Status</th>
                      <th className="px-4 py-3 font-semibold text-center">Hasil (Sukses / Gagal)</th>
                      <th className="px-4 py-3 font-semibold text-right">Aksi</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {historyJobs.map((job) => {
                      const isCompleted = job.status === 'completed';
                      const isCancelled = job.status === 'cancelled';
                      const createdDate = new Date(job.created_at * 1000).toLocaleString();

                      return (
                        <tr key={job.id} className="hover:bg-slate-50/70 transition-colors">
                          <td className="px-4 py-3 font-mono text-[11px] text-slate-900 whitespace-nowrap">
                            <span className="font-bold">{job.id}</span>
                            <div className="text-[10px] text-slate-400 mt-0.5">{createdDate}</div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="font-medium text-slate-800">Div: {job.division}</div>
                            <div className="text-[10px] uppercase font-semibold text-slate-500">
                              {job.platform}
                            </div>
                          </td>
                          <td className="px-4 py-3 max-w-xs">
                            <p className="truncate text-slate-700" title={job.message}>
                              "{job.message}"
                            </p>
                          </td>
                          <td className="px-4 py-3 text-center whitespace-nowrap">
                            {isCompleted && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded-full font-semibold text-[11px]">
                                Completed
                              </span>
                            )}
                            {isCancelled && (
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-800 rounded-full font-semibold text-[11px]">
                                Cancelled
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-center whitespace-nowrap">
                            <div className="inline-flex items-center gap-2">
                              <span className="text-emerald-700 font-semibold text-xs">
                                ✓ {job.sent}
                              </span>
                              <span className="text-slate-300">/</span>
                              <span className="text-red-600 font-semibold text-xs">
                                ✗ {job.failed}
                              </span>
                              <span className="text-[10px] text-slate-400">
                                ({job.total} total)
                              </span>
                            </div>
                          </td>
                          <td className="px-4 py-3 text-right whitespace-nowrap">
                            <button
                              onClick={() => {
                                setSelectedJobForModal(job);
                                setRecipientFilter('all');
                                setRecipientSearch('');
                              }}
                              className="inline-flex items-center gap-1.5 px-3 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
                            >
                              <Users className="w-3.5 h-3.5" />
                              Lihat Penerima
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* DETAIL MODAL UNTUK RECIPIENT INSPECTION */}
      {selectedJobForModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in duration-150">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200 flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="text-base font-bold text-slate-900">
                    Detail Riwayat Broadcast: {selectedJobForModal.id}
                  </h3>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-semibold ${
                      selectedJobForModal.status === 'completed'
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-red-100 text-red-800'
                    }`}
                  >
                    {selectedJobForModal.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Divisi: {selectedJobForModal.division} • Platform: {selectedJobForModal.platform.toUpperCase()} •
                  Waktu: {new Date(selectedJobForModal.created_at * 1000).toLocaleString()}
                </p>
              </div>

              <button
                onClick={() => setSelectedJobForModal(null)}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors cursor-pointer"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body Info */}
            <div className="p-5 space-y-4 overflow-y-auto flex-1">
              <div className="p-3.5 bg-slate-50 rounded-lg border border-slate-200">
                <div className="text-xs font-semibold text-slate-700 mb-1">Pesan Pengumuman:</div>
                <div className="text-xs text-slate-800 whitespace-pre-wrap font-sans">
                  {selectedJobForModal.message}
                </div>
              </div>

              {/* Stats Bar */}
              <div className="grid grid-cols-4 gap-3">
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/60 text-center">
                  <div className="text-xs text-slate-500 font-medium">Total Penerima</div>
                  <div className="text-lg font-bold text-slate-900 mt-0.5">
                    {selectedJobForModal.total}
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/50 text-center">
                  <div className="text-xs text-emerald-700 font-medium">Berhasil Terkirim</div>
                  <div className="text-lg font-bold text-emerald-800 mt-0.5">
                    {selectedJobForModal.sent}
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-red-200 bg-red-50/50 text-center">
                  <div className="text-xs text-red-700 font-medium">Gagal Terkirim</div>
                  <div className="text-lg font-bold text-red-800 mt-0.5">
                    {selectedJobForModal.failed}
                  </div>
                </div>
                <div className="p-3 rounded-lg border border-slate-200 bg-slate-50/60 text-center">
                  <div className="text-xs text-slate-500 font-medium">Tingkat Sukses</div>
                  <div className="text-lg font-bold text-indigo-700 mt-0.5">
                    {selectedJobForModal.total > 0
                      ? Math.round((selectedJobForModal.sent / selectedJobForModal.total) * 100)
                      : 0}
                    %
                  </div>
                </div>
              </div>

              {/* Filters & Search */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                <div className="flex items-center gap-1.5 p-1 bg-slate-100 rounded-lg border border-slate-200">
                  <button
                    onClick={() => setRecipientFilter('all')}
                    className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer transition-colors ${
                      recipientFilter === 'all'
                        ? 'bg-white text-slate-900 shadow-xs'
                        : 'text-slate-600 hover:text-slate-900'
                    }`}
                  >
                    Semua ({selectedJobForModal.recipients?.length || 0})
                  </button>
                  <button
                    onClick={() => setRecipientFilter('sent')}
                    className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer transition-colors ${
                      recipientFilter === 'sent'
                        ? 'bg-emerald-600 text-white shadow-xs'
                        : 'text-emerald-700 hover:text-emerald-900'
                    }`}
                  >
                    Sukses ({selectedJobForModal.sent})
                  </button>
                  <button
                    onClick={() => setRecipientFilter('failed')}
                    className={`px-2.5 py-1 rounded text-xs font-semibold cursor-pointer transition-colors ${
                      recipientFilter === 'failed'
                        ? 'bg-red-600 text-white shadow-xs'
                        : 'text-red-700 hover:text-red-900'
                    }`}
                  >
                    Gagal ({selectedJobForModal.failed})
                  </button>
                </div>

                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Cari nama atau target..."
                    value={recipientSearch}
                    onChange={(e) => setRecipientSearch(e.target.value)}
                    className="pl-8 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg text-slate-900 focus:outline-hidden focus:ring-1 focus:ring-indigo-500 w-full sm:w-60"
                  />
                </div>
              </div>

              {/* Recipient Details Table */}
              <div className="border border-slate-200 rounded-xl overflow-hidden">
                <div className="max-h-80 overflow-y-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 sticky top-0">
                      <tr>
                        <th className="px-4 py-2.5 font-semibold">Nama Kontak</th>
                        <th className="px-4 py-2.5 font-semibold">Target (Nomor / Akun)</th>
                        <th className="px-4 py-2.5 font-semibold">Platform</th>
                        <th className="px-4 py-2.5 font-semibold">Divisi</th>
                        <th className="px-4 py-2.5 font-semibold">Status</th>
                        <th className="px-4 py-2.5 font-semibold">Keterangan / Pesan Error</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 text-slate-700">
                      {(() => {
                        const filtered = (selectedJobForModal.recipients || []).filter((r) => {
                          if (recipientFilter !== 'all' && r.status !== recipientFilter) {
                            return false;
                          }
                          if (recipientSearch) {
                            const q = recipientSearch.toLowerCase();
                            const matchName = (r.name || '').toLowerCase().includes(q);
                            const matchTarget = (r.target || '').toLowerCase().includes(q);
                            const matchDiv = (r.division || '').toLowerCase().includes(q);
                            return matchName || matchTarget || matchDiv;
                          }
                          return true;
                        });

                        if (filtered.length === 0) {
                          return (
                            <tr>
                              <td colSpan={6} className="px-4 py-6 text-center text-slate-400">
                                Tidak ada kontak yang sesuai filter
                              </td>
                            </tr>
                          );
                        }

                        return filtered.map((r, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/70">
                            <td className="px-4 py-2.5 font-semibold text-slate-900">{r.name}</td>
                            <td className="px-4 py-2.5 font-mono text-[11px] text-slate-600">
                              {r.target}
                            </td>
                            <td className="px-4 py-2.5 uppercase font-bold text-[10px] text-slate-500">
                              {r.platform}
                            </td>
                            <td className="px-4 py-2.5">{r.division || '-'}</td>
                            <td className="px-4 py-2.5">
                              {r.status === 'sent' && (
                                <span className="inline-flex items-center gap-1 text-emerald-700 font-semibold text-[11px]">
                                  <CheckCircle2 className="w-3.5 h-3.5" /> Terkirim
                                </span>
                              )}
                              {r.status === 'failed' && (
                                <span className="inline-flex items-center gap-1 text-red-700 font-semibold text-[11px]">
                                  <AlertCircle className="w-3.5 h-3.5" /> Gagal
                                </span>
                              )}
                              {r.status === 'pending' && (
                                <span className="inline-flex items-center gap-1 text-slate-500 font-semibold text-[11px]">
                                  <Clock className="w-3.5 h-3.5" /> Pending
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-2.5 font-mono text-[10px] text-red-600 max-w-xs">
                              {r.error || '-'}
                            </td>
                          </tr>
                        ));
                      })()}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-4 bg-slate-50 border-t border-slate-200 flex justify-end">
              <button
                onClick={() => setSelectedJobForModal(null)}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-700 rounded-lg text-xs font-semibold cursor-pointer transition-colors"
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
