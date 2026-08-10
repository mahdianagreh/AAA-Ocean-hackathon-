import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { PageShell } from '../shell/PageShell';
import { Section } from '../shell/PageShell';
import { fetchCatchments, fetchOutlets, fetchDiveSites } from '../api/live';

export function DataExplorerPage() {
  const { t } = useTranslation('pages');
  const [catchments, setCatchments] = useState<any[] | null>(null);
  const [outlets, setOutlets] = useState<any[] | null>(null);
  const [diveSites, setDiveSites] = useState<any[] | null>(null);
  const [loading, setLoading] = useState(true);

  const [activeTab, setActiveTab] = useState<'catchments' | 'outlets' | 'divesites'>('catchments');

  useEffect(() => {
    let mounted = true;
    Promise.all([fetchCatchments(), fetchOutlets(), fetchDiveSites()]).then(([c, o, d]) => {
      if (!mounted) return;
      setCatchments(c ?? null);
      setOutlets(o ?? null);
      setDiveSites(d ?? null);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  const renderTable = (data: any[] | null, columns: { key: string; label: string }[]) => {
    if (loading) return <p className="text-sm text-ink-2 animate-pulse">{t('explorer.loading', { defaultValue: 'Loading data...' })}</p>;
    if (!data || data.length === 0) return <p className="text-sm text-ink-3 italic">{t('explorer.empty', { defaultValue: 'No data available.' })}</p>;

    return (
      <div className="overflow-x-auto w-full glass-panel">
        <table className="w-full text-left border-collapse text-sm">
          <thead className="bg-surface-2/50 border-b border-hairline-2">
            <tr>
              {columns.map((col) => (
                <th key={col.key} className="p-3 font-semibold text-ink-2 uppercase tracking-wider text-xs">
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((item, i) => (
              <tr key={i} className="border-b border-hairline hover:bg-surface/50 transition-colors">
                {columns.map((col) => (
                  <td key={col.key} className="p-3 text-ink-2 max-w-[200px] truncate">
                    {typeof item[col.key] === 'object' ? JSON.stringify(item[col.key]) : String(item[col.key] ?? '-')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <PageShell title={t('explorer.title', { defaultValue: 'Geographic Data Explorer' })}>
      <div className="flex flex-col gap-6">
        
        {/* Tabs */}
        <div className="flex items-center gap-2 border-b border-hairline pb-2">
          {[
            { id: 'catchments', label: t('explorer.catchments', { defaultValue: 'Catchments' }), count: catchments?.length },
            { id: 'outlets', label: t('explorer.outlets', { defaultValue: 'Outlets' }), count: outlets?.length },
            { id: 'divesites', label: t('explorer.divesites', { defaultValue: 'Dive Sites' }), count: diveSites?.length },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 rounded-t-md text-sm font-semibold transition-colors ${
                activeTab === tab.id 
                  ? 'border-b-2 border-accent text-accent bg-surface-2/30' 
                  : 'text-ink-3 hover:text-ink hover:bg-surface-2/10'
              }`}
            >
              {tab.label} {tab.count !== undefined ? <span className="ml-2 text-xs opacity-60 bg-surface-2 px-1.5 py-0.5 rounded-full">{tab.count}</span> : null}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="animate-overlay-show">
          {activeTab === 'catchments' && (
            <Section label={t('explorer.catchmentsTitle', { defaultValue: 'Registered Catchments' })}>
              {renderTable(catchments, [
                { key: 'id', label: 'ID' },
                { key: 'area_sqkm', label: 'Area (km²)' },
                { key: 'outlet_id', label: 'Outlet ID' },
              ])}
            </Section>
          )}

          {activeTab === 'outlets' && (
            <Section label={t('explorer.outletsTitle', { defaultValue: 'Coastal Outlets' })}>
              {renderTable(outlets, [
                { key: 'id', label: 'ID' },
                { key: 'type', label: 'Type' },
                { key: 'description', label: 'Description' },
              ])}
            </Section>
          )}

          {activeTab === 'divesites' && (
            <Section label={t('explorer.divesitesTitle', { defaultValue: 'Dive Sites' })}>
              {renderTable(diveSites, [
                { key: 'id', label: 'ID' },
                { key: 'name', label: 'Name' },
                { key: 'rating', label: 'Rating' },
                { key: 'depth_m', label: 'Depth (m)' },
                { key: 'difficulty', label: 'Difficulty' },
              ])}
            </Section>
          )}
        </div>

      </div>
    </PageShell>
  );
}
