import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Guard: React.FC = () => {
  const queryClient = useQueryClient();

  const { data: guard, isLoading, isError, error } = useQuery({
    queryKey: ['guard'],
    queryFn: () => fetchApi<any>('/admin/guard/config'),
  });

  const update = useMutation({
    mutationFn: (body: { enabled?: boolean; strict_mode?: boolean }) =>
      fetchApi<any>('/admin/guard/config', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['guard'] }),
  });

  if (isLoading) return <div className="p-4">Loading guard config...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat guard config: {(error as Error)?.message}</div>;

  const enabled = !!guard?.enabled;
  const strict = !!guard?.strict_mode;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Guard Settings</h1>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-5">
        <ToggleRow
          label="Galat / Guard aktif"
          desc="Aktifkan penyaringan pesan keluar dari scope chat bot."
          checked={enabled}
          onChange={(v) => update.mutate({ enabled: v })}
          busy={update.isPending}
        />
        <ToggleRow
          label="Strict mode"
          desc="Mode ketat untuk pola programming / out-of-scope."
          checked={strict}
          onChange={(v) => update.mutate({ strict_mode: v })}
          busy={update.isPending}
        />

        <div>
          <p className="text-sm text-slate-500 mb-1">Konfigurasi mentah (backend):</p>
          <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
            {JSON.stringify(guard, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
};

const ToggleRow: React.FC<{
  label: string;
  desc: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  busy: boolean;
}> = ({ label, desc, checked, onChange, busy }) => (
  <div className="flex items-center justify-between gap-4">
    <div>
      <p className="font-medium text-slate-900">{label}</p>
      <p className="text-sm text-slate-400">{desc}</p>
    </div>
    <button
      type="button"
      onClick={() => onChange(!checked)}
      disabled={busy}
      className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
        checked ? 'bg-indigo-600' : 'bg-slate-300'
      }`}
      aria-pressed={checked}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  </div>
);