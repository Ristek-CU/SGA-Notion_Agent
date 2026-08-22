import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Session: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: sessions, isLoading, isError, error } = useQuery({
    queryKey: ['sessions'],
    queryFn: () => fetchApi<any[]>('/admin/sessions'),
  });

  const reset = useMutation({
    mutationFn: () => fetchApi<any>('/admin/sessions/reset', { method: 'POST' }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  });

  if (isLoading) return <div className="p-4">Loading sessions...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat sessions: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">Redis Sessions</h1>
        <button
          onClick={() => reset.mutate()}
          disabled={reset.isPending}
          className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50"
        >
          {reset.isPending ? 'Resetting...' : 'Reset All Sessions'}
        </button>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {(sessions || []).length === 0 ? (
          <p className="p-4 text-slate-400">Tidak ada sesi tersimpan.</p>
        ) : (
          <table className="w-full text-left text-sm text-slate-600">
            <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
              <tr>
                <th className="p-4">Key</th>
                <th className="p-4">Data</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {(sessions || []).map((s: any, i: number) => (
                <tr key={i} className="hover:bg-slate-50 align-top">
                  <td className="p-4 font-mono text-xs text-slate-500">{s?.key}</td>
                  <td className="p-4">
                    <pre className="text-xs whitespace-pre-wrap overflow-x-auto">{s?.data}</pre>
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