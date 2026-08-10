import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { PageShell } from '../shell/PageShell';
import { Section } from '../shell/PageShell';
import { fetchSystemHealth, fetchCacheStats, type HealthOut } from '../api/live';

export function SystemHealthPage() {
  const { t } = useTranslation('pages');
  const [health, setHealth] = useState<HealthOut | null>(null);
  const [cacheStats, setCacheStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    Promise.all([fetchSystemHealth(), fetchCacheStats()]).then(([h, c]) => {
      if (!mounted) return;
      setHealth(h ?? null);
      setCacheStats(c ?? null);
      setLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  return (
    <PageShell title={t('system.title', { defaultValue: 'System Health & Diagnostics' })}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        <Section label={t('system.statusTitle', { defaultValue: 'Platform Status' })}>
          {loading ? (
            <p className="text-sm text-ink-2 animate-pulse">{t('system.loading', { defaultValue: 'Loading diagnostics...' })}</p>
          ) : !health ? (
            <div className="glass-panel border-red-500/30 bg-red-500/10 p-4">
              <p className="m-0 text-sm text-red-400 font-bold">{t('system.offline', { defaultValue: 'Backend is offline or unreachable.' })}</p>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className={`glass-panel p-5 flex items-center justify-between ${health.status === 'ok' ? 'border-accent/50' : 'border-red-500/50'}`}>
                <div className="flex flex-col gap-1">
                  <span className="text-sm font-bold premium-gradient-text uppercase tracking-widest">{t('system.overall', { defaultValue: 'Overall Health' })}</span>
                  <span className="text-2xs text-ink-2">{t('system.version', { defaultValue: 'Version' })}: <span className="font-mono text-ink">{health.version}</span></span>
                </div>
                <div className={`px-4 py-2 rounded-full text-sm font-bold shadow-lg ${health.status === 'ok' ? 'bg-accent/20 text-accent shadow-accent/20' : 'bg-red-500/20 text-red-400 shadow-red-500/20'}`}>
                  {health.status.toUpperCase()}
                </div>
              </div>

              {health.degraded_reason.length > 0 && (
                <div className="glass-panel border-red-500/30 p-4 flex flex-col gap-2">
                  <span className="text-xs font-bold text-red-400 uppercase">{t('system.issues', { defaultValue: 'Active Issues' })}</span>
                  <ul className="m-0 pl-4 text-sm text-ink-2 list-disc">
                    {health.degraded_reason.map((reason: string, i: number) => (
                      <li key={i}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex flex-col gap-2">
                <span className="text-xs font-bold text-ink-3 uppercase tracking-wider">{t('system.artifacts', { defaultValue: 'Artifact Availability' })}</span>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(health.artifacts_present).map(([artifact, present]) => (
                    <div key={artifact} className="flex items-center justify-between p-2 rule rounded-md bg-surface-2/50">
                      <span className="text-xs text-ink-2 truncate">{artifact}</span>
                      <span className={`w-2 h-2 rounded-full ${present ? 'bg-accent shadow-[0_0_8px_var(--accent)]' : 'bg-red-500 shadow-[0_0_8px_rgb(239,68,68)]'}`} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Section>

        <Section label={t('system.cacheTitle', { defaultValue: 'Memory & Cache Stats' })}>
          {!loading && cacheStats ? (
            <div className="flex flex-col gap-3">
              {Object.entries(cacheStats).map(([key, value]) => (
                <div key={key} className="glass-panel p-4 flex items-center justify-between group hover:glass-panel-hover">
                  <span className="text-sm font-medium text-ink-2 group-hover:text-ink transition-colors capitalize">{key.replace(/_/g, ' ')}</span>
                  <span className="text-base font-bold num text-accent">
                    {typeof value === 'number' ? value.toLocaleString() : String(value)}
                  </span>
                </div>
              ))}
            </div>
          ) : !loading ? (
            <p className="text-sm text-ink-3 italic">{t('system.noCache', { defaultValue: 'Cache statistics unavailable.' })}</p>
          ) : null}
        </Section>
      </div>
    </PageShell>
  );
}
