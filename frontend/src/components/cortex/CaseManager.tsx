import { useEffect, useMemo, useState } from 'react';
import { Search, Trash2, ExternalLink, ChevronDown, Filter, X, Download } from 'lucide-react';
import { useCortexStore } from '@/store/cortex';
import type { RecentRunSummary } from '@/types/simulation';

const DOMAINS = ['', 'Political Campaign', 'Public Health', 'Urban Planning', 'Corporate Comms', 'Public Policy'];
const CITIES: Record<string, string> = {
  '': 'All cities',
  'los-angeles-ca': 'Los Angeles',
  'new-york-ny': 'New York',
  'chicago-il': 'Chicago',
  'miami-fl': 'Miami',
  'phoenix-az': 'Phoenix',
  'houston-tx': 'Houston',
};

function formatDate(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

export const CaseManager = ({ onClose }: { onClose?: () => void }) => {
  const { recentRuns, recentRunsStatus, loadRecentRuns, openRun, deleteRun } = useCortexStore();
  const [search, setSearch] = useState('');
  const [domain, setDomain] = useState('');
  const [cityId, setCityId] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  useEffect(() => {
    loadRecentRuns(50);
  }, [loadRecentRuns]);

  const filtered = useMemo(() => {
    let runs = recentRuns;
    if (search.trim()) {
      const q = search.toLowerCase();
      runs = runs.filter(
        (r) =>
          r.case_goal.toLowerCase().includes(q) ||
          r.domain.toLowerCase().includes(q) ||
          r.city_id.toLowerCase().includes(q),
      );
    }
    if (domain) runs = runs.filter((r) => r.domain === domain);
    if (cityId) runs = runs.filter((r) => r.city_id === cityId);
    return runs;
  }, [recentRuns, search, domain, cityId]);

  async function handleOpen(runId: number) {
    await openRun(runId);
    onClose?.();
  }

  async function handleDelete(runId: number) {
    setDeletingId(runId);
    await deleteRun(runId);
    setDeletingId(null);
  }

  return (
    <div className="space-y-4">
      {/* Search bar */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-muted" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search cases..."
            className="w-full rounded-[10px] border border-white/[0.10] bg-bg-input py-2.5 pl-9 pr-3 text-[13px] text-text-primary placeholder:text-text-muted focus:border-pastel-2/40 focus:outline-none"
          />
          {search && (
            <button onClick={() => setSearch('')} className="absolute right-3 top-1/2 -translate-y-1/2">
              <X className="h-3.5 w-3.5 text-text-muted" />
            </button>
          )}
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={`flex items-center gap-1.5 rounded-[10px] border px-3 py-2 text-[11px] transition-colors ${
            showFilters || domain || cityId
              ? 'border-pastel-2/30 bg-pastel-2/10 text-pastel-2'
              : 'border-white/[0.10] bg-bg-input text-text-muted hover:text-text-secondary'
          }`}
        >
          <Filter className="h-3.5 w-3.5" />
          Filter
          {(domain || cityId) && (
            <span className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-pastel-2/20 text-[9px] text-pastel-2">
              {(domain ? 1 : 0) + (cityId ? 1 : 0)}
            </span>
          )}
        </button>
      </div>

      {/* Filter row */}
      {showFilters && (
        <div className="flex flex-wrap gap-2">
          <select
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            className="rounded-[8px] border border-white/[0.10] bg-bg-input px-3 py-1.5 text-[11px] text-text-secondary"
          >
            {DOMAINS.map((d) => (
              <option key={d} value={d}>
                {d || 'All domains'}
              </option>
            ))}
          </select>
          <select
            value={cityId}
            onChange={(e) => setCityId(e.target.value)}
            className="rounded-[8px] border border-white/[0.10] bg-bg-input px-3 py-1.5 text-[11px] text-text-secondary"
          >
            {Object.entries(CITIES).map(([id, label]) => (
              <option key={id} value={id}>
                {label}
              </option>
            ))}
          </select>
          {(domain || cityId) && (
            <button
              onClick={() => { setDomain(''); setCityId(''); }}
              className="rounded-[8px] border border-white/[0.08] px-3 py-1.5 text-[11px] text-text-muted hover:text-text-secondary"
            >
              Clear filters
            </button>
          )}
        </div>
      )}

      {/* Run list */}
      <div className="space-y-2">
        {recentRunsStatus === 'loading' && (
          <div className="py-8 text-center text-[13px] text-text-muted">Loading cases...</div>
        )}

        {recentRunsStatus === 'error' && (
          <div className="py-8 text-center text-[13px] text-text-muted">Failed to load cases.</div>
        )}

        {recentRunsStatus === 'ready' && filtered.length === 0 && (
          <div className="py-8 text-center text-[13px] text-text-muted">
            {search || domain || cityId ? 'No cases match your filters.' : 'No saved cases yet. Run a simulation to create one.'}
          </div>
        )}

        {filtered.map((run) => (
          <div
            key={run.id}
            className="group flex items-center gap-3 rounded-[12px] border border-white/[0.08] bg-bg-surface/60 px-4 py-3 transition-colors hover:border-white/[0.14]"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-text-muted">#{run.id}</span>
                <span className="rounded-[4px] bg-white/[0.06] px-2 py-0.5 text-[10px] text-text-secondary">
                  {run.domain}
                </span>
                <span className="text-[10px] text-text-muted">{CITIES[run.city_id] || run.city_id}</span>
              </div>
              <p className="mt-1 text-[13px] text-text-primary truncate">{run.case_goal}</p>
              <p className="mt-0.5 text-[11px] text-text-muted">{formatDate(run.created_at)}</p>
            </div>

            <div className="flex items-center gap-1">
              <button
                onClick={() => handleOpen(run.id)}
                className="rounded-[6px] border border-white/[0.10] p-1.5 text-text-muted hover:border-pastel-2/30 hover:text-pastel-2"
                title="Open case"
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
              <a
                href={`/api/runs/${run.id}/report`}
                className="rounded-[6px] border border-white/[0.10] p-1.5 text-text-muted hover:border-pastel-2/30 hover:text-pastel-2"
                title="Download PDF report"
              >
                <Download className="h-3.5 w-3.5" />
              </a>
              <button
                onClick={() => handleDelete(run.id)}
                disabled={deletingId === run.id}
                className="rounded-[6px] border border-white/[0.10] p-1.5 text-text-muted hover:border-red-400/40 hover:text-red-400 disabled:opacity-50"
                title="Delete case"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
