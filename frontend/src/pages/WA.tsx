import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const WA: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: status, isLoading, isError, error } = useQuery({
    queryKey: ['wa-status'],
    queryFn: () => fetchApi<any>('/admin/wa/status'),
  });

  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['wa-status'] }),
    ]);
  };

  const runAction = useMutation({
    mutationFn: (endpoint: string) => fetchApi<any>(endpoint, { method: 'POST' }),
    onSuccess: () => refresh(),
  });

  if (isLoading) return <div className="p-4">Loading WA connection...</div>;
  if (isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">WhatsApp Connection</h1>
        <div className="bg-white p-6 rounded-xl border border-red-200">
          <p className="text-red-600">Gagal memuat status WA: {(error as Error)?.message}</p>
          <p className="text-sm text-slate-400 mt-2">
            Backend merequester ke Evolution API. Pastikan <code>EVOLUTION_API_URL</code> &amp;
            institusi tercapai, lalu coba Scan/Refresh.
          </p>
        </div>
        <ActionButtons runAction={runAction} />
      </div>
    );
  }

  const state = status?.state ?? 'unknown';
  const instance = status?.instance ?? '-';
  const reasons = Array.isArray(status?.statusReason) ? status.statusReason : null;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">WhatsApp Connection</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <InfoCard label="Instance" value={instance} />
        <InfoCard label="State" value={state} />
        <InfoCard label="Status Reason" value={reasons ? reasons.join(', ') : (status?.statusReason ?? '-')} />
      </div>

      <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
        {JSON.stringify(status, null, 2)}
      </pre>

      <ActionButtons runAction={runAction} />
    </div>
  );
};

const InfoCard: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
    <p className="text-sm font-medium text-slate-500">{label}</p>
    <p className="text-xl font-bold text-slate-900 mt-1 break-all">{value}</p>
  </div>
);

const ActionButtons: React.FC<{ runAction: any }> = ({ runAction }) => (
  <div className="flex flex-wrap gap-3">
    <button
      onClick={() => runAction.mutate('/admin/wa/scan')}
      disabled={runAction.isPending}
      className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
    >
      {runAction.variables === '/admin/wa/scan' && runAction.isPending ? 'Scanning...' : 'Scan QR'}
    </button>
    <button
      onClick={() => runAction.mutate('/admin/wa/refresh')}
      disabled={runAction.isPending}
      className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold hover:bg-amber-700 disabled:opacity-50"
    >
      Refresh
    </button>
    <button
      onClick={() => runAction.mutate('/admin/wa/disconnect')}
      disabled={runAction.isPending}
      className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-semibold hover:bg-red-700 disabled:opacity-50"
    >
      Disconnect
    </button>
  </div>
);