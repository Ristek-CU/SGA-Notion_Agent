import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

interface Contact {
  id?: number;
  name: string;
  phone: string;
  telegram?: string;
  telegram_chat_id?: string;
  nickname?: string;
  role?: string;
  division?: string;
  notion_member_id?: string;
}

const stripAt = (s: string) => s.trim().replace(/^@+/, '');
const waTgCell = (c: Contact) => {
  const tgPart = c.telegram?.trim() ? `@${stripAt(c.telegram)}${c.telegram_chat_id ? ` (ID: ${c.telegram_chat_id})` : ''}` : '';
  return [c.phone?.trim(), tgPart].filter(Boolean).join(' / ') || '-';
};

const EMPTY_FORM = { name: '', phone: '', telegram: '', telegram_chat_id: '', nickname: '', role: '', division: '' };

const DIVISIONS = [
  'BPH',
  'Media and Information',
  'Research and Technology',
  'Public and Community Relationship',
  'UKM Development',
  'Business And Partnership',
  'Intellectual and Career Development',
  'Student Advocacy and Welfare',
];

const ROLES = [
  'President',
  'Vice President',
  'Controller',
  'Treasurer',
  'Secretary',
  'Head',
  'Deputy Head',
  'Staff',
];

export const Members: React.FC = () => {
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [editingContact, setEditingContact] = useState<Contact | null>(null);
  const [form, setForm] = useState(EMPTY_FORM);

  const { data: contacts, isLoading, isError, error } = useQuery({
    queryKey: ['contacts'],
    queryFn: () => fetchApi<any[]>('/admin/contacts'),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['contacts'] });

  const createMut = useMutation({
    mutationFn: (body: typeof EMPTY_FORM) =>
      fetchApi('/admin/contacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    onSuccess: () => { invalidate(); setShowModal(false); },
  });

  const updateMut = useMutation({
    mutationFn: ({ phone, body }: { phone: string; body: any }) =>
      fetchApi(`/admin/contacts/${encodeURIComponent(phone)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    onSuccess: () => { invalidate(); setShowModal(false); },
  });

  const deleteMut = useMutation({
    mutationFn: (phone: string) =>
      fetchApi(`/admin/contacts/${encodeURIComponent(phone)}`, { method: 'DELETE' }),
    onSuccess: invalidate,
  });

  const openAdd = () => { setForm(EMPTY_FORM); setEditingContact(null); setShowModal(true); };
  const openEdit = (c: Contact) => {
    setForm({
      name: c.name || '',
      phone: c.phone || '',
      telegram: stripAt(c.telegram || ''),
      telegram_chat_id: c.telegram_chat_id || '',
      nickname: c.nickname || '',
      role: c.role || '',
      division: c.division || '',
    });
    setEditingContact(c);
    setShowModal(true);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name || !form.phone) return;
    const body = {
      ...form,
      id: editingContact?.id,
      notion_member_id: editingContact?.notion_member_id,
      telegram: stripAt(form.telegram),
      telegram_chat_id: form.telegram_chat_id.trim() || undefined,
    };
    if (editingContact) updateMut.mutate({ phone: editingContact.phone, body });
    else createMut.mutate(body);
  };

  if (isLoading) return <div className="p-4">Loading contacts...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat kontak: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">Members & Contacts</h1>
        <button
          onClick={openAdd}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 w-full sm:w-auto text-center cursor-pointer shadow-xs"
        >
          + Tambah Member
        </button>
      </div>

      {(createMut.isError || updateMut.isError || deleteMut.isError) && (
        <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm border border-red-200">
          Gagal menyimpan/menghapus kontak.
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        {(contacts || []).length === 0 ? (
          <p className="p-4 text-slate-400">Belum ada kontak.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600 min-w-[540px]">
              <thead className="bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700 uppercase">
                <tr>
                  <th className="p-3 sm:p-4">Name</th>
                  <th className="p-3 sm:p-4">Nickname</th>
                  <th className="p-3 sm:p-4">Whatsapp / Telegram</th>
                  <th className="p-3 sm:p-4">Division / Role</th>
                  <th className="p-3 sm:p-4 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(contacts || []).map((c: Contact, i: number) => (
                  <tr key={c.phone || i} className="hover:bg-slate-50">
                    <td className="p-3 sm:p-4 font-medium text-slate-900">{c.name}</td>
                    <td className="p-3 sm:p-4">{c.nickname || '-'}</td>
                    <td className="p-3 sm:p-4 font-mono text-xs">{waTgCell(c)}</td>
                    <td className="p-3 sm:p-4">{[c.division, c.role].filter(Boolean).join(' / ') || '-'}</td>
                    <td className="p-3 sm:p-4 text-right whitespace-nowrap">
                      <button onClick={() => openEdit(c)} className="text-indigo-600 hover:text-indigo-800 text-sm font-medium mr-3">Edit</button>
                      <button
                        onClick={() => { if (confirm(`Hapus ${c.name} (${c.phone})?`)) deleteMut.mutate(c.phone); }}
                        className="text-red-600 hover:text-red-800 text-sm font-medium"
                      >Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center p-3 z-50 overflow-y-auto" onClick={() => setShowModal(false)}>
          <form
            onSubmit={submit}
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-xl p-4 sm:p-6 w-full max-w-md space-y-4 shadow-xl max-h-[90vh] overflow-y-auto my-auto"
          >
            <h2 className="text-lg font-bold text-slate-900">{editingContact ? 'Edit Member' : 'Tambah Member'}</h2>
            {[
              ['name', 'Nama', true, ''],
              ['nickname', 'Nickname', false, ''],
              ['phone', 'Phone (62…)', true, ''],
              ['telegram', 'Telegram Username', false, 'tanpa @ (boleh ketik @, sistem hapus otomatis)'],
              ['telegram_chat_id', 'Telegram Chat ID (Numeric)', false, 'Opsional (terisi otomatis saat user chat ke bot)'],
            ].map(([key, label, req, helper]) => (
              <label key={key as string} className="block">
                <span className="text-xs font-semibold text-slate-500 uppercase">{label}{req ? ' *' : ''}</span>
                <input
                  value={(form as any)[key as string]}
                  onChange={(e) => setForm({ ...form, [key as string]: e.target.value })}
                  required={!!req}
                  className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                />
                {helper ? <span className="text-xs text-slate-400">{helper}</span> : null}
              </label>
            ))}
            <label className="block">
              <span className="text-xs font-semibold text-slate-500 uppercase">Divisi</span>
              <select
                value={form.division}
                onChange={(e) => setForm({ ...form, division: e.target.value })}
                className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Pilih divisi</option>
                {DIVISIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-500 uppercase">Role</span>
              <select
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
                className="mt-1 w-full px-3 py-2 border border-slate-300 rounded-lg text-sm bg-white focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">Pilih role</option>
                {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
              </select>
            </label>
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={() => setShowModal(false)} className="px-4 py-2 rounded-lg border border-slate-300 text-sm">Batal</button>
              <button type="submit" disabled={createMut.isPending || updateMut.isPending} className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50">
                {createMut.isPending || updateMut.isPending ? 'Menyimpan...' : 'Simpan'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
};
