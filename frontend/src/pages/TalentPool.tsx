import { useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Check, Database, Pencil, Trash2, X } from 'lucide-react';
import { useTalentPool, useUpdateTalentPoolEntry, useRemoveFromTalentPool } from '../hooks/useTalentPool';
import { useConfirm } from '../hooks/useConfirm';
import {
  Badge, DataTable, EmptyState, ErrorState, FilterBar, FilterBarSpacer, IconButton, Input, PageHeader, Pagination, SearchInput,
  type Column,
} from '../components/ui';
import { CandidateIdentity } from '../components/candidate/ScreeningCells';
import { getErrorMessage } from '../utils/errors';
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
  const { data, isLoading, isFetching, isError, error, refetch } = useTalentPool(params);

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

  const filtered = !!(q || tag);

  const columns: Column<TalentPoolEntry>[] = [
    {
      id: 'candidate',
      header: 'Candidate',
      mobile: 'title',
      skeleton: 'avatar',
      className: 'w-60',
      cell: (e) => <CandidateIdentity name={e.display_name} fallback={`Resume #${e.resume_id}`} sub={e.email || undefined} />,
    },
    {
      id: 'tags',
      header: 'Tags',
      mobile: 'body',
      className: 'min-w-[17rem]',
      cell: (e) =>
        editingId === e.id ? (
          <div className="flex items-center gap-1">
            <Input
              autoFocus
              aria-label="Tags, comma separated"
              value={editTags}
              onChange={(ev) => setEditTags(ev.target.value)}
              onKeyDown={(ev) => { if (ev.key === 'Enter') saveTags(e); if (ev.key === 'Escape') setEditingId(null); }}
              placeholder="tag1, tag2"
              className="h-8 text-xs"
            />
            <IconButton label="Save tags" tone="success" icon={<Check size={15} />} disabled={updateMutation.isPending} onClick={() => saveTags(e)} />
            <IconButton label="Cancel editing" icon={<X size={15} />} onClick={() => setEditingId(null)} />
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-1.5">
            {e.tags.length > 0 ? e.tags.map((t) => <Badge key={t}>{t}</Badge>) : <span className="text-xs italic text-[var(--text-tertiary)]">No tags</span>}
            <IconButton label="Edit tags" icon={<Pencil size={13} />} className="h-6 w-6" onClick={() => startEdit(e)} />
          </div>
        ),
    },
    {
      id: 'notes',
      header: 'Notes',
      hideBelow: 'lg',
      mobile: 'body',
      className: 'w-[22%]',
      cell: (e) => <p className="line-clamp-2 text-sm text-[var(--text-secondary)]">{e.notes || '—'}</p>,
    },
    {
      id: 'from',
      header: 'Added from',
      cell: (e) => <span className="text-sm text-[var(--text-secondary)]">{e.job_title || (e.job_id ? `Job #${e.job_id}` : '—')}</span>,
    },
    {
      id: 'added',
      header: 'Added',
      className: 'w-36',
      cell: (e) => <span className="text-caption whitespace-nowrap">{e.added_at ? formatDistanceToNow(new Date(e.added_at), { addSuffix: true }) : '—'}</span>,
    },
    {
      id: 'actions',
      header: <span className="sr-only">Actions</span>,
      align: 'right',
      mobile: 'actions',
      className: 'w-14',
      skeleton: 'actions',
      cell: (e) => (
        <IconButton
          label="Remove from Talent Pool"
          tone="danger"
          icon={<Trash2 size={15} />}
          disabled={removeMutation.isPending}
          onClick={() => handleRemove(e)}
        />
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader className="mb-6" title="Talent pool" subtitle="Candidates saved for future roles, with tags and notes." />

      <FilterBar className="mb-4">
        <SearchInput aria-label="Search talent pool" placeholder="Search by name or email…" value={qInput} onValueChange={setQInput} className="sm:w-72" />
        <Input
          aria-label="Filter by tag"
          value={tag}
          onChange={(e) => { setTag(e.target.value); setPage(1); }}
          placeholder="Filter by tag…"
          className="w-full sm:w-48"
        />
        <FilterBarSpacer />
        {data && <span className="text-caption tabular" aria-live="polite">{data.total} {data.total === 1 ? 'entry' : 'entries'}</span>}
      </FilterBar>

      {isError ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--bg-surface)]">
          <ErrorState title="Failed to load the Talent Pool" message={getErrorMessage(error)} onRetry={() => refetch()} />
        </div>
      ) : (
        <>
          <DataTable
            aria-label="Talent pool"
            rows={data?.items ?? []}
            columns={columns}
            getRowId={(e) => e.id}
            isLoading={isLoading && !data}
            isRefreshing={isFetching && !!data}
            empty={
              <EmptyState
                icon={<Database size={20} />}
                title={filtered ? 'No matching entries' : 'No one in your Talent Pool yet'}
                description={filtered ? 'Try a different search or tag filter.' : 'Add candidates from any candidate list using "Add to Talent Pool".'}
              />
            }
          />
          {data && data.total > 0 && (
            <Pagination className="mt-4" page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />
          )}
        </>
      )}
    </div>
  );
};
