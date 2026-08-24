import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

interface BotSession {
  phone: string;
  msg_count: number;
  last_msg: string;
  last_activity: number;
  pending_ticket: boolean;
  ttl: number;
}

const fmtAgo = (ts: number) => {
  if (!ts) return '-';
  const s = Math.floor(Date.now() / 1000 - ts);
  if (s < 60) return `${s}s lalu`;
  if (s < 3600) return `${Math.floor(s / 60)}m lalu`;
  if (s < 86400) return `${Math.floor(s / 3600)}j lalu`;
  return `${Math.floor(s / 86400)}h lalu`;
};

export const Session: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: sessions, isLoading, isError, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchApi<BotSession[]>('/admin/sessions'),
    refetchInterval: 15000,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['sessions'] });

  const resetOne = useMutation({
    mutationFn: (phone: string) =>
      fetchApi(`/admin/sessions/reset?phone=${encodeURIComponent(phone)}`, { method: 'POST' }),
    onSuccess: invalidate,
  });

  const resetAll = useMutation({
    mutationFn: () => fetchApi('/admin/sessions/reset', { method: 'POST' }),
    onSuccess: invalidate,
  });

  if (isLoading) return <div className="p-4">Loading sessions...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat sessions: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Bot Sessions</h1>
          <p className="text-sm text-slate-500 mt-1">
            Memori percakapan bot per user (konteks chat AI di Redis, TTL 30 menit).
            Reset kalau bot kehilangan konteks atau jawaban terpengaruh chat lama.
          </p>
        </div>
        <button
          onClick={() => { if (confirm('Reset SEMUA session percakapan?')) resetAll.mutate(); }}
          disabled={resetAll.isPending}
          className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50"
        >
          {resetAll.isPending ? 'Resetting...' : 'Reset All'}
        </button>
      </div>

      {(resetOne.isError || resetAll.isError) && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">Gagal reset session.</div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {(sessions || []).length === 0 ? (
          <p className="p-4 text-slate-400">Belum ada sesi — bot belum menerima pesan.</p>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">User</th>
                <th className="p-4">Pesan</th>
                <th className="p-4">Chat Terakhir</th>
                <th className="p-4">Aktivitas</th>
                <th className="p-4">Status Tiket</th>
                <th className="p-4 text-right">Aksi</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(sessions || []).map((s) => (
                <tr key={s.phone} className="hover:bg-slate-50">
                  <td className="p-4 font-mono text-xs text-slate-900">{s.phone}</td>
                  <td className="p-4">{s.msg_count}</td>
                  <td className="p-4 max-w-xs truncate" title={s.last_msg}>{s.last_msg || '-'}</td>
                  <td className="p-4 whitespace-nowrap">{fmtAgo(s.last_activity)}</td>
                  <td className="p-4">
                    {s.pending_ticket
                      ? <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 text-xs font-medium">pending</span>
                      : <span className="text-slate-400">-</span>}
                  </td>
                  <td className="p-4 text-right">
                    <button
                      onClick={() => { if (confirm(`Reset session ${s.phone}?`)) resetOne.mutate(s.phone); }}
                      className="text-red-600 hover:text-red-800 text-sm font-medium"
                    >Reset</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
