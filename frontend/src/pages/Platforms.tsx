import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

const NEED_SCAN = ['SCAN_QR_CODE', 'STARTING'];

export const Platforms: React.FC = () => {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Platforms</h1>
      <WASection />
      <TelegramCard />
    </div>
  );
};

/* ---------- WhatsApp (WaHa) ---------- */

const WASection: React.FC = () => {
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

  if (isLoading) return <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">Loading WA connection...</div>;
  if (isError) {
    return (
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-slate-900">WhatsApp Connection</h2>
        <div className="bg-white p-6 rounded-xl border border-red-200">
          <p className="text-red-600">Gagal memuat status WA: {(error as Error)?.message}</p>
          <p className="text-sm text-slate-400 mt-2">
            Pastikan service WaHa (<code>{status?.name || 'orc-waha'}</code>) aktif.
          </p>
        </div>
        <WAButtons runAction={runAction} />
      </div>
    );
  }

  const instance = status?.name ?? '-';
  const me = status?.me;
  const reasons = JSON.stringify(status?.engine ?? {});

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">WhatsApp</h2>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium ${
            statusName === 'WORKING' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'
          }`}
        >
          {statusName || 'unknown'}
        </span>
      </div>

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
          <h3 className="font-semibold text-slate-900 mb-1">Scan QR untuk menghubungkan WhatsApp</h3>
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

      <WAButtons runAction={runAction} showQr={showQr} />
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

const WAButtons: React.FC<{ runAction: any; showQr?: boolean }> = ({ runAction, showQr }) => (
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
      onClick={() => runAction.mutate('/admin/wa/webhook-setup')}
      disabled={runAction.isPending}
      className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-semibold hover:bg-blue-700 disabled:opacity-50"
    >
      Connect / Setup Webhook
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

/* ---------- Telegram ---------- */

const TelegramCard: React.FC = () => {
  const queryClient = useQueryClient();
  const [token, setToken] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [notice, setNotice] = useState<{ kind: 'ok' | 'err'; text: string } | null>(null);

  const { data: cfg, isLoading } = useQuery({
    queryKey: ['telegram-config'],
    queryFn: () => fetchApi<any>('/admin/platforms/telegram'),
  });

  // Server adalah sumber kebenaran untuk enabled; token tak pernah di-prefill.
  useEffect(() => {
    if (cfg) setEnabled(!!cfg.enabled);
  }, [cfg]);

  const saveMut = useMutation({
    mutationFn: () =>
      fetchApi('/admin/platforms/telegram', {
        method: 'PUT',
        body: JSON.stringify({ enabled, bot_token: token || undefined }),
      }),
    onSuccess: (d: any) => {
      setToken('');
      setNotice({ kind: 'ok', text: d?.message || 'Konfigurasi tersimpan.' });
      queryClient.invalidateQueries({ queryKey: ['telegram-config'] });
    },
    onError: (e: Error) => setNotice({ kind: 'err', text: e.message }),
  });

  const testMut = useMutation({
    // Telegram getMe mengembalikan username bot bila token valid.
    mutationFn: () => fetchApi<any>('/admin/platforms/telegram/test'),
    onSuccess: (d: any) =>
      setNotice({
        kind: d ? 'ok' : 'err',
        text: d
          ? `Token valid — bot @${d.username ?? d.bot_username ?? JSON.stringify(d)}`
          : 'Respons kosong dari server.',
      }),
    onError: (e: Error) => setNotice({ kind: 'err', text: e.message }),
  });

  const hookMut = useMutation({
    mutationFn: () => fetchApi<any>('/admin/platforms/telegram/webhook-setup', { method: 'POST' }),
    onSuccess: (d: any) =>
      setNotice({ kind: 'ok', text: `Webhook: ${JSON.stringify(d).slice(0, 200)}` }),
    onError: (e: Error) => setNotice({ kind: 'err', text: e.message }),
  });

  if (isLoading)
    return <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">Loading…</div>;

  // Hint token tersamar dari server; fallback last4 lokal bila server belum menyediakan.
  const hint: string =
    typeof cfg?.bot_token_hint === 'string'
      ? cfg.bot_token_hint
      : cfg?.token_last4
        ? `••••${cfg.token_last4}`
        : 'belum ada';

  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Telegram</h2>
        <span
          className={`text-xs px-2 py-1 rounded-full font-medium ${
            enabled ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
          }`}
        >
          {enabled ? 'enabled' : 'disabled'}
          {testMut.data?.username ? ' · terverifikasi' : ''}
        </span>
      </div>

      <label className="block">
        <span className="text-xs font-semibold text-slate-500 uppercase">Bot Token</span>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder={hint}
          autoComplete="new-password"
          className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
        />
        {/* ponytail: hint via placeholder; ganti ke teks terpisah kalau perlu copy-paste hint */}
      </label>

      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => setEnabled(e.target.checked)}
          className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
        />
        <span className="text-sm text-slate-700">Enabled</span>
      </label>

      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => saveMut.mutate()}
          disabled={saveMut.isPending}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
        >
          {saveMut.isPending ? 'Menyimpan…' : 'Save'}
        </button>
        <button
          onClick={() => testMut.mutate()}
          disabled={testMut.isPending}
          className="px-4 py-2 rounded-lg border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50"
        >
          {testMut.isPending ? 'Menguji…' : 'Test Token'}
        </button>
        <button
          onClick={() => hookMut.mutate()}
          disabled={hookMut.isPending}
          className="px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-semibold hover:bg-amber-700 disabled:opacity-50"
        >
          {hookMut.isPending ? 'Menyiapkan webhook…' : 'Setup Webhook'}
        </button>
      </div>

      {notice && (
        <p
          className={`text-sm break-all ${
            notice.kind === 'ok'
              ? 'text-emerald-600 bg-emerald-50 border border-emerald-200 rounded-lg p-3'
              : 'text-red-600 bg-red-50 border border-red-200 rounded-lg p-3'
          }`}
        >
          {notice.text}
        </p>
      )}
    </div>
  );
};
