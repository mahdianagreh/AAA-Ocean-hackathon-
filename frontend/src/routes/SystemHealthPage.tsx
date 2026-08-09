import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Card, CardGrid, PageShell, Section } from '../shell/PageShell';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { ErrorState, Loading } from '../components/States';
import { api } from '../api';
import { fetchCacheStats, type CacheStats, type CacheStatsResponse } from '../api/live';
import type { Health } from '../api/types';

/** System health & diagnostics, at /system-health.
 *
 *  Built against the two things the API actually types: GET /health (the Health
 *  contract) and GET /api/v1/cache-stats (CacheStatsResponse). The cache endpoint
 *  returns { plume: {hits,misses,size}, exposure: {hits,misses,size} } — an object
 *  per cache — which is exactly why an earlier attempt printed "[object Object]":
 *  it stringified the object. Here each cache renders its three real fields (Hits,
 *  Misses, Entries) plus a hit-rate that is computed in the component and labelled
 *  derived, so nothing is stringified and nothing is invented.
 *
 *  Per-artifact availability (the ARTIFACTS list) is not part of the typed API
 *  contract, so it is flagged as not-yet-exposed rather than faked — the /health
 *  availability signals it DOES report (model artefact, data volume) are shown. */

type HealthState = { kind: 'loading' } | { kind: 'unreachable' } | { kind: 'ok'; health: Health };

const CHECK = (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 8.5 6.5 12 13 4.5" />
  </svg>
);
const WARN = (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M8 2 15 14H1z" />
    <path d="M8 6.5v3.5" />
    <circle cx="8" cy="11.8" r="0.5" fill="currentColor" />
  </svg>
);

function StatusPill({ ok, okLabel, badLabel }: { ok: boolean; okLabel: string; badLabel: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-2xs font-bold uppercase tracking-wide ${
        ok ? 'bg-ink text-ink-inverse' : 'bg-risk-high text-risk-high-on'
      }`}
    >
      {ok ? CHECK : WARN}
      {ok ? okLabel : badLabel}
    </span>
  );
}

function CacheCard({ label, stats }: { label: string; stats: CacheStats }) {
  const { t } = useTranslation('tools');
  const denom = stats.hits + stats.misses;
  // Derived in the component, labelled derived — not a value the API sends.
  const hitRate = denom > 0 ? stats.hits / denom : null;
  return (
    <Card>
      <h3 className="m-0 text-sm font-semibold">{label}</h3>
      <dl className="m-0 grid grid-cols-3 gap-3">
        <div className="flex flex-col gap-0.5">
          <dt className="text-2xs uppercase tracking-wide text-ink-2">{t('systemHealth.hits')}</dt>
          <dd className="m-0"><ValueWithUnit value={stats.hits} digits={0} provenance="measured" /></dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-2xs uppercase tracking-wide text-ink-2">{t('systemHealth.misses')}</dt>
          <dd className="m-0"><ValueWithUnit value={stats.misses} digits={0} provenance="measured" /></dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-2xs uppercase tracking-wide text-ink-2">{t('systemHealth.entries')}</dt>
          <dd className="m-0"><ValueWithUnit value={stats.size} digits={0} provenance="measured" /></dd>
        </div>
      </dl>
      <div className="flex items-baseline gap-2">
        <span className="text-2xs uppercase tracking-wide text-ink-2">{t('systemHealth.hitRate')}</span>
        {hitRate === null ? (
          <ValueWithUnit value={null} />
        ) : (
          <ValueWithUnit value={hitRate * 100} digits={1} unit="%" provenance="modelled" />
        )}
        <span className="text-2xs text-ink-3">({t('systemHealth.derived')})</span>
      </div>
    </Card>
  );
}

export function SystemHealthPage() {
  const { t } = useTranslation('tools');
  const [health, setHealth] = useState<HealthState>({ kind: 'loading' });
  const [cache, setCache] = useState<CacheStatsResponse | null>(null);
  const [cacheLoaded, setCacheLoaded] = useState(false);

  useEffect(() => {
    let live = true;
    void api()
      .health()
      .then((h) => live && setHealth({ kind: 'ok', health: h }))
      .catch(() => live && setHealth({ kind: 'unreachable' }));
    void fetchCacheStats().then((c) => {
      if (!live) return;
      setCache(c);
      setCacheLoaded(true);
    });
    return () => {
      live = false;
    };
  }, []);

  return (
    <PageShell title={t('systemHealth.title')} lede={t('systemHealth.lede')}>
      <Section label={t('systemHealth.overallSection')}>
        {health.kind === 'loading' ? (
          <Loading what={t('systemHealth.loading')} />
        ) : health.kind === 'unreachable' ? (
          <ErrorState what={t('systemHealth.title')} message={t('systemHealth.unreachable')} />
        ) : (
          <OverallHealth health={health.health} />
        )}
      </Section>

      <Section label={t('systemHealth.cacheSection')}>
        {!cacheLoaded ? (
          <Loading what={t('systemHealth.loading')} />
        ) : !cache ? (
          // Honest: cache-stats live behind the API; in fixtures/offline mode the
          // endpoint does not respond, and that is stated rather than blanked.
          <Card>
            <p className="m-0 max-w-prose text-xs text-ink-2">{t('systemHealth.cacheUnavailable')}</p>
          </Card>
        ) : (
          <CardGrid>
            <CacheCard label={t('systemHealth.cachePlume')} stats={cache.plume} />
            <CacheCard label={t('systemHealth.cacheExposure')} stats={cache.exposure} />
          </CardGrid>
        )}
      </Section>
    </PageShell>
  );
}

function OverallHealth({ health }: { health: Health }) {
  const { t } = useTranslation('tools');
  const degraded: string[] = [];
  if (!health.model_available) degraded.push(t('systemHealth.degradedModel'));
  if (!health.data_volume_mounted) degraded.push(t('systemHealth.degradedData'));
  // If the API itself reports a non-OK status with no specific artefact reason,
  // still give the "Degraded" pill something to explain it.
  if (health.status !== 'ok' && degraded.length === 0) degraded.push(t('systemHealth.degradedStatus'));
  const ok = health.status === 'ok' && degraded.length === 0;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <StatusPill ok={ok} okLabel={t('systemHealth.statusOk')} badLabel={t('systemHealth.statusDegraded')} />
        <dl className="m-0 flex flex-wrap gap-x-6 gap-y-1 text-2xs text-ink-3">
          <div>
            <dt className="inline">{t('systemHealth.version')} </dt>
            <dd className="m-0 inline"><code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">{health.version}</code></dd>
          </div>
          <div>
            <dt className="inline">{t('systemHealth.commit')} </dt>
            <dd className="m-0 inline"><code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">{health.commit}</code></dd>
          </div>
          <div>
            <dt className="inline">{t('systemHealth.time')} </dt>
            <dd className="m-0 inline"><code dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num">{health.time_utc}</code></dd>
          </div>
        </dl>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-2">{t('systemHealth.modelAvailable')}</span>
          <StatusPill ok={health.model_available} okLabel={t('systemHealth.available')} badLabel={t('systemHealth.unavailable')} />
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-ink-2">{t('systemHealth.dataVolume')}</span>
          <StatusPill ok={health.data_volume_mounted} okLabel={t('systemHealth.available')} badLabel={t('systemHealth.unavailable')} />
        </div>
      </div>

      {degraded.length ? (
        <div className="flex flex-col gap-1 rule bg-surface-2 p-3">
          <p className="m-0 text-2xs font-bold uppercase tracking-wide text-ink-2">{t('systemHealth.degradedTitle')}</p>
          <ul className="m-0 flex list-disc flex-col gap-1 ps-5 text-xs text-ink-2">
            {degraded.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="m-0 max-w-prose text-2xs text-ink-3">{t('systemHealth.artifactNote')}</p>
    </Card>
  );
}
