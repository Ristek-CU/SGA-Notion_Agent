import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

const NEED_SCAN = ['SCAN_QR_CODE', 'STARTING'];

export const WA: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: status, isLoading, isError, error } = useQuery({
    queryKey: ['wa-status'],
    queryFn: () => fetchApi<any>('/admin/wa/status'),
  });

  const statusName: string = status?.status ?? '';
  const showQr = NEED_SCAN.includes(statusName);

  const { data: qr, refetch: refetchQr } = useQuery({
    queryKey: ['wa-qr', statusName],
    enabled: showQr,
    retry: false,
    refetchInterval: showQr ? 8000 : false, // QR kedaluwarsa; perbarui berkala
    queryFn: () => fetchApi<{ qr_png_base64?: string }>('/admin/wa/qr'),
  });

  const refreshAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['wa-status'] }),
      refetchQr(),
    ]);
  };

  const runAction = useMutation({
    mutationFn: (endpoint: string) => fetchApi<any>(endpoint, { method: 'POST' }),
    onSuccess: () => refreshAll(),
  });

  if (isLoading) return <div className="p-4">Loading WA connection...</div>;
  if (isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-slate-900">WhatsApp Connection</h1>
        <div className="bg-white p-6 rounded-xl border border-red-200">
          <p className="text-red-600">Gagal memuat status WA: {(error as Error)?.message}</p>
          <p className="text-sm text-slate-400 mt-2">
            Pastikan service WaHa (<code>{status?.name || 'orc-waha'}</code>) aktif.
          </p>
        </div>
        <ActionButtons runAction={runAction} />
      </div>
    );
  }

  const instance = status?.name ?? '-';
  const me = status?.me;
  const reasons = JSON.stringify(status?.engine ?? {});

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">WhatsApp Connection</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <InfoCard label="Instance" value={instance} />
        <InfoCard label="Status" value={statusName} highlight={statusName === 'WORKING'} />
        <InfoCard
          label="Bot (me)"
          value={me?.id ? `${me.id}` : 'Belum terhubung'}
        />
      </div>

      {showQr && (
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
          <h2 className="text-lg font-semibold text-slate-900 mb-1">Scan QR untuk menghubungkan WhatsApp</h2>
          <p className="text-sm text-slate-400 mb-4">
            Buka WhatsApp di HP → <strong>Menu → Perangkat tertaut → Tautkan perangkat</strong>, lalu scan QR ini.
            QR otomatis diperbarui tiap beberapa detik.
          </p>
          <div className="flex items-start gap-6 flex-wrap">
            {qr?.qr_png_base64 ? (
              <img
                src={`data:image/png;base64,${qr.qr_png_base64}`}
                alt="WhatsApp QR"
                className="w-56 h-56 border border-slate-200 rounded-lg bg-white"
              />
            ) : (
              <div className="w-56 h-56 border border-dashed border-slate-300 rounded-lg flex items-center justify-center text-sm text-slate-400">
                {statusName === 'STARTING' ? 'Menyiapkan QR…' : 'QR belum tersedia'}
              </div>
            )}
            <div className="text-sm text-slate-500">
              <p className="font-medium text-slate-700 mb-1">Engine ({status?.engine?.engine ?? 'WEBJS'})</p>
              <pre className="text-xs">{reasons}</pre>
            </div>
          </div>
        </div>
      )}

      {statusName === 'WORKING' && (
        <div className="bg-white p-6 rounded-xl border border-emerald-200">
          <p className="text-emerald-600 font-medium">WhatsApp terhubung ✅</p>
          <p className="text-sm text-slate-500 mt-1">
            Sesi <code>{instance}</code> aktif dan siap menerima pesan via webhook.
          </p>
        </div>
      )}

      <ActionButtons runAction={runAction} showQr={showQr} />
    </div>
  );
};

const InfoCard: React.FC<{ label: string; value: string; highlight?: boolean }> = ({
  label,
  value,
  highlight,
}) => (
  <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">
    <p className="text-sm font-medium text-slate-500">{label}</p>
    <p
      className={`text-xl font-bold mt-1 break-all ${
        highlight ? 'text-emerald-600' : 'text-slate-900'
      }`}
    >
      {value}
    </p>
  </div>
);

const ActionButtons: React.FC<{ runAction: any; showQr?: boolean }> = ({ runAction, showQr }) => (
  <div className="flex flex-wrap gap-3">
    <button
      onClick={() => runAction.mutate('/admin/wa/scan')}
      disabled={runAction.isPending}
      className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
    >
      {showQr && runAction.variables === '/admin/wa/scan' && runAction.isPending
        ? 'Membuat QR…'
        : 'Scan / Buat QR'}
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