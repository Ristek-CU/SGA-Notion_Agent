import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Broadcast: React.FC = () => {
  const [message, setMessage] = useState('');
  const [recipients, setRecipients] = useState('');

  const send = useMutation({
    mutationFn: () =>
      fetchApi<any>('/admin/broadcast', {
        method: 'POST',
        body: JSON.stringify({
          message,
          recipients: recipients
            .split(',')
            .map((r) => r.trim())
            .filter(Boolean),
        }),
      }),
  });

  const result = send.data as
    | { total?: number; success?: number; failed?: string[] }
    | undefined;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Broadcast Task</h1>

      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">Pesan</label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
            className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
            placeholder="Pesan yang akan dikirim ke seluruh penerima..."
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1">
            Penerima (pisahkan dengan koma — nomor atau nama kontak)
          </label>
          <input
            value={recipients}
            onChange={(e) => setRecipients(e.target.value)}
            className="w-full p-2.5 border border-slate-300 rounded-lg text-sm"
            placeholder="0812xxxx, Alif, 62xxx..."
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => send.mutate()}
            disabled={send.isPending || !message.trim() || !recipients.trim()}
            className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50"
          >
            {send.isPending ? 'Mengirim...' : 'Kirim Broadcast'}
          </button>

          {send.isError && (
            <span className="text-sm text-red-600">Gagal: {(send.error as Error)?.message}</span>
          )}
          {send.isSuccess && result && (
            <span className="text-sm text-emerald-600">
              Terkirim {result.success}/{result.total}
              {result.failed && result.failed.length > 0 ? ` — gagal: ${result.failed.join(', ')}` : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};