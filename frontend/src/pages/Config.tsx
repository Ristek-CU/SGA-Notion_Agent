import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { fetchApi } from '../api/client';

export const Config: React.FC = () => {
  const queryClient = useQueryClient();
  const [baseUrl, setBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [aiModel, setAiModel] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const { data: envConfig, isLoading: envLoading } = useQuery({
    queryKey: ['system-env'],
    queryFn: () => fetchApi<any>('/admin/system/env'),
  });

  const { data: aiConfig, isLoading: aiLoading, isError, error } = useQuery({
    queryKey: ['ai-config'],
    queryFn: () => fetchApi<any>('/admin/ai/config'),
  });

  useEffect(() => {
    if (aiConfig) {
      setBaseUrl(aiConfig.anthropic_base_url || '');
      setApiKey(aiConfig.anthropic_api_key || '');
      setAiModel(aiConfig.ai_model || '');
    }
  }, [aiConfig]);

  const updateMut = useMutation({
    mutationFn: (body: any) =>
      fetchApi('/admin/ai/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-config'] });
      setSuccessMsg('Pengaturan AI Provider berhasil diperbarui!');
      setTimeout(() => setSuccessMsg(''), 4000);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMut.mutate({
      anthropic_base_url: baseUrl,
      anthropic_api_key: apiKey.includes('...') ? undefined : apiKey,
      ai_model: aiModel,
    });
  };

  if (envLoading || aiLoading) return <div className="p-4">Loading config...</div>;
  if (isError) return <div className="p-4 text-red-600">Gagal memuat config: {(error as Error)?.message}</div>;

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">App Configuration</h1>

      {successMsg && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-lg text-sm">
          {successMsg}
        </div>
      )}

      {/* AI Provider Settings */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-4">
        <h2 className="text-lg font-semibold text-slate-800">AI Model & Provider Config</h2>
        <form onSubmit={handleSubmit} className="space-y-4 max-w-xl">
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Anthropic / Router Base URL</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="https://api.z.ai/api/anthropic"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">API Key</label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="sk-..."
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">AI Model Name</label>
            <input
              type="text"
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
              className="w-full border border-slate-300 rounded-lg p-2 text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
              placeholder="ag/gemini-3.6-flash-medium"
            />
          </div>

          <button
            type="submit"
            disabled={updateMut.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg text-sm transition-colors"
          >
            {updateMut.isPending ? 'Saving...' : 'Simpan AI Config'}
          </button>
        </form>
      </div>

      {/* Raw Env View */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 space-y-2">
        <h2 className="text-sm font-semibold text-slate-700">System Info</h2>
        <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg text-xs overflow-x-auto">
          {JSON.stringify(envConfig || {}, null, 2)}
        </pre>
      </div>
    </div>
  );
};
