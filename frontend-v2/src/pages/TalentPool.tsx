import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, Database, Search, ChevronLeft, ChevronRight, Pencil, Check, X, Trash2 } from 'lucide-react';
import { useTalentPool, useUpdateTalentPoolEntry, useRemoveFromTalentPool } from '../hooks/useTalentPool';
import { useConfirm } from '../hooks/useConfirm';
import { Badge, Input } from '../components/ui';
import type { TalentPoolEntry } from '../types';

const PAGE_SIZE = 20;

export const TalentPool = () => {
  const [qInput, setQInput] = useState('');
  const [q, setQ] = useState('');
  const [tag, setTag] = useState('');
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTags, setEditTags] = useState('');

  const confirm = useConfirm();

  // Debounce free-text search.
  useEffect(() => {
    const timer = setTimeout(() => { setQ(qInput.trim()); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [qInput]);

  const params = { q: q || undefined, tag: tag || undefined, page, page_size: PAGE_SIZE };
  const { data, isLoading, isError, error } = useTalentPool(params);

  const updateMutation = useUpdateTalentPoolEntry();
  const removeMutation = useRemoveFromTalentPool();

  const startEdit = (entry: TalentPoolEntry) => {
    setEditingId(entry.id);
    setEditTags(entry.tags.join(', '));
  };

  const saveTags = (entry: TalentPoolEntry) => {
    const tags = editTags.split(',').map((t) => t.trim()).filter(Boolean);
    updateMutation.mutate({ id: entry.id, patch: { tags } }, { onSuccess: () => setEditingId(null) });
  };

  const handleRemove = async (entry: TalentPoolEntry) => {
    const ok = await confirm({
      title: 'Remove from Talent Pool?',
      description: `Remove ${entry.display_name || `resume #${entry.resume_id}`} from the Talent Pool? This does not delete the candidate's resume or screening history.`,
      danger: true,
      confirmLabel: 'Remove',
    });
    if (ok) removeMutation.mutate(entry.id);
  };

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="flex items-center space-x-3 mb-8">
        <div className="w-10 h-10 bg-[var(--color-primary-subtle-bg)] text-[var(--color-primary-subtle-text)] rounded-lg flex items-center justify-center">
          <Database className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">Talent Pool</h1>
          <p className="text-sm text-[var(--text-secondary)]">Candidates saved for future roles, with tags and notes.</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-3 mb-4">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-tertiary)]" />
          <Input
            value={qInput}
            onChange={(e) => setQInput(e.target.value)}
            placeholder="Search by name or email..."
            className="pl-9"
          />
        </div>
        <div className="w-56">
          <Input
            value={tag}
            onChange={(e) => { setTag(e.target.value); setPage(1); }}
            placeholder="Filter by tag..."
          />
        </div>
      </div>

      <div className="bg-[var(--bg-surface)] border border-[var(--border-light)] rounded-xl shadow-sm overflow-hidden">
        {isLoading && !data ? (
          <div className="flex justify-center items-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary-500)]" />
          </div>
        ) : isError ? (
          <div className="p-8 text-center text-[var(--color-danger-600)]">
            Failed to load the Talent Pool{error instanceof Error ? `: ${error.message}` : '.'}
          </div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-center py-20">
            <Database className="w-12 h-12 text-[var(--text-tertiary)] mx-auto mb-4" />
            <h3 className="text-lg font-medium text-[var(--text-primary)] mb-1">
              {q || tag ? 'No matching entries' : 'No one in your Talent Pool yet'}
            </h3>
            <p className="text-[var(--text-secondary)]">
              {q || tag ? 'Try a different search or tag filter.' : 'Add candidates from any candidate list using "Add to Talent Pool".'}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-[var(--bg-app)] border-b border-[var(--border-light)] text-[var(--text-secondary)]">
                  <tr>
                    <th className="px-6 py-4 font-medium">Candidate</th>
                    <th className="px-6 py-4 font-medium">Tags</th>
                    <th className="px-6 py-4 font-medium hidden md:table-cell">Notes</th>
                    <th className="px-6 py-4 font-medium">Added From</th>
                    <th className="px-6 py-4 font-medium">Added</th>
                    <th className="px-6 py-4 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-light)]">
                  {data.items.map((entry) => (
                    <tr key={entry.id} className="hover:bg-[var(--bg-hover)] transition-colors">
                      <td className="px-6 py-4">
                        <div className="font-medium text-[var(--text-primary)]">{entry.display_name || `Resume #${entry.resume_id}`}</div>
                        <div className="text-xs text-[var(--text-tertiary)]">{entry.email || '—'}</div>
                      </td>
                      <td className="px-6 py-4 max-w-xs">
                        {editingId === entry.id ? (
                          <div className="flex items-center gap-2">
                            <Input
                              autoFocus
                              value={editTags}
                              onChange={(e) => setEditTags(e.target.value)}
                              placeholder="tag1, tag2"
                              className="h-8 text-xs"
                            />
                            <button onClick={() => saveTags(entry)} disabled={updateMutation.isPending} className="text-[var(--color-success-600)] hover:opacity-75" title="Save tags">
                              <Check className="w-4 h-4" />
                            </button>
                            <button onClick={() => setEditingId(null)} className="text-[var(--text-tertiary)] hover:opacity-75" title="Cancel">
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap items-center gap-1.5">
                            {entry.tags.length > 0 ? (
                              entry.tags.map((t) => <Badge key={t} variant="neutral">{t}</Badge>)
                            ) : (
                              <span className="text-[var(--text-tertiary)] italic text-xs">No tags</span>
                            )}
                            <button onClick={() => startEdit(entry)} className="text-[var(--text-tertiary)] hover:text-[var(--color-primary-600)]" title="Edit tags">
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 hidden md:table-cell max-w-xs">
                        <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{entry.notes || '—'}</p>
                      </td>
                      <td className="px-6 py-4 text-[var(--text-secondary)]">
                        {entry.job_title || (entry.job_id ? `Job #${entry.job_id}` : '—')}
                      </td>
                      <td className="px-6 py-4 text-xs text-[var(--text-tertiary)]">
                        {entry.added_at ? formatDistanceToNow(new Date(entry.added_at), { addSuffix: true }) : '—'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => handleRemove(entry)}
                          disabled={removeMutation.isPending}
                          title="Remove from Talent Pool"
                          className="p-1.5 rounded-full text-[var(--text-tertiary)] hover:bg-[var(--color-danger-subtle-bg)] hover:text-[var(--color-danger-600)] transition-colors disabled:opacity-50"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="px-6 py-4 border-t border-[var(--border-light)] bg-[var(--bg-app)] flex items-center justify-between text-sm text-[var(--text-secondary)]">
              <span>Showing {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, data.total)} of {data.total}</span>
              <div className="flex gap-1">
                <button disabled={page === 1} onClick={() => setPage((p) => p - 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button disabled={page * PAGE_SIZE >= data.total} onClick={() => setPage((p) => p + 1)} className="p-1 rounded hover:bg-[var(--bg-hover)] disabled:opacity-50 text-[var(--text-secondary)] focus-ring">
                  <ChevronRight className="w-5 h-5" />
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
