import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const TicketDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  // Detail diambil dari list backlog (cache dipakai bareng halaman Tickets);
  // ponytail: ganti ke GET /admin/notion/tickets/{id} kalau backend expose endpoint single.
  const { data: tickets, isLoading, isError, error } = useQuery({
    queryKey: ['tickets'],
    queryFn: () => fetchApi<any[]>('/admin/notion/backlog'),
    select: (list) => (list || []).find((t: any) => t?.id === id),
  });

  const [status, setStatus] = useState('');
  const [priority, setPriority] = useState('');
  const [pic, setPic] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  useEffect(() => {
    if (!ticket) return;
    const p = ticket.properties ?? {};
    setStatus(p?.Status?.status?.name ?? '');
    setPriority(p?.Priority?.select?.name ?? '');
    setPic(p?.PIC?.relation?.[0]?.id ?? '');
  }, [ticket]);

  const handleSave = async () => {
    setSaving(true);
    setSaveError('');
    try {
      const body: Record<string, string> = {};
      if (status) body.status = status;
      if (priority) body.priority = priority;
      if (pic) body.pic_id = pic;
      await fetchApi(`/admin/notion/tickets/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      navigate('/tickets');
    } catch (e) {
      setSaveError((e as Error).message || 'Gagal menyimpan');
    } finally {
      setSaving(false);
    }
  };

  if (isLoading) return <div className="p-4">Loading ticket...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat ticket: {(error as Error)?.message}</div>;
  if (!ticket) return <div className="p-4 text-slate-400">Ticket tidak ditemukan.</div>;

  const props = ticket.properties ?? {};
  const name =
    props?.Name?.title?.[0]?.plain_text ??
    props?.Name?.title?.[0]?.text?.content ??
    id;
  const rows: Array<[string, React.ReactNode]> = [
    ['Page ID', ticket.id],
    ['Ticket ID', props?.ID?.rich_text?.[0]?.plain_text ?? '-'],
    ['Name', name],
    ['Status', props?.Status?.status?.name ?? '-'],
    ['Priority', props?.Priority?.select?.name ?? '-'],
    ['Division', props?.Division?.select?.name ?? '-'],
    ['Description', props?.Description?.rich_text?.[0]?.plain_text ?? '-'],
    ['Created', ticket.created_time ?? '-'],
    ['Updated', ticket.last_edited_time ?? '-'],
  ];

  return (
    <div className="space-y-6">
      <button onClick={() => navigate('/tickets')} className="text-sm text-sky-600 hover:text-sky-800">
        &larr; Back to Tickets
      </button>
      <h1 className="text-2xl font-bold text-slate-900">{name}</h1>

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6">
        <table className="w-full text-left text-sm text-slate-600">
          <tbody className="divide-y divide-slate-100">
            {rows.map(([label, value]) => (
              <tr key={label}>
                <td className="py-2 pr-4 font-medium text-slate-700 w-40 align-top">{label}</td>
                <td className="py-2 break-all">{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="text-lg font-semibold text-slate-900">Edit Ticket</h2>
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-6 space-y-4 max-w-md">
        <div>
          <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Status</label>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {['', 'Backlog', 'To Do', 'In Progress', 'Done'].map((s) => (
              <option key={s || 'keep'} value={s}>{s || '(tidak diubah)'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">Priority</label>
          <select
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            {['', 'Low', 'Medium', 'High', 'Urgent'].map((p) => (
              <option key={p || 'keep'} value={p}>{p || '(tidak diubah)'}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold uppercase text-slate-700 mb-1">PIC (Notion user/page ID)</label>
          <input
            type="text"
            value={pic}
            onChange={(e) => setPic(e.target.value)}
            placeholder="ID relasi Notion"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
          />
        </div>
        {saveError && <p className="text-sm text-red-600">{saveError}</p>}
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:opacity-50"
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </div>
  );
};
