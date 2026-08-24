import React, { useEffect, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Platforms: React.FC = () => {
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

  if (isLoading) return <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs">Loading…</div>;

  // Hint token tersamar dari server; fallback last4 lokal bila server belum menyediakan.
  const hint: string =
    typeof cfg?.bot_token_hint === 'string'
      ? cfg.bot_token_hint
      : cfg?.token_last4
        ? `••••${cfg.token_last4}`
        : 'belum ada';

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Platforms</h1>

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
    </div>
  );
};
