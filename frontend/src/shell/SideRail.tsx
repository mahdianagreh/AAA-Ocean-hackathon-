import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { api } from '../api';
import type { Catchment, Outlet, ReefZone } from '../api/types';
import { HARBOUR_BASIN_OUTLETS } from '../api/types';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { CatchmentGlyph, OutletGlyph, ReefZoneGlyph } from '../icons';

/** Side rail: risk cards, layer toggles, legend — 03 §3.
 *
 *  In Phase 1 it carries the textual equivalent of what the map draws, which is
 *  09 rule 7: the map is never the only path to a fact. Risk cards and the
 *  exposure legend arrive in Phase 2 with the data that fills them.
 */
export function SideRail() {
  const { t } = useTranslation();
  const [data, setData] = useState<{
    catchments: Catchment[];
    outlets: Outlet[];
    reef: ReefZone[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const c = api();
    let live = true;
    void Promise.all([c.catchments(), c.outlets(), c.reefZones()])
      .then(([catchments, outlets, reef]) => {
        if (live) setData({ catchments, outlets, reef });
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);

  return (
    <aside
      className="flex min-h-0 flex-col gap-4 overflow-y-auto bg-surface p-4"
      aria-label={t('rail.label')}
    >
      {error ? (
        <p role="alert" className="text-xs text-risk-critical">
          {error}
        </p>
      ) : null}

      {/* Loading is a designed state, not a spinner-shaped absence — 04. */}
      {!data && !error ? <p className="text-xs text-ink-3">{t('rail.loading')}</p> : null}

      {data ? (
        <>
          <Group icon={<CatchmentGlyph size={16} />} title={t('rail.catchments')}>
            {data.catchments.map((c) => (
              <Row
                key={c.catchment_id}
                id={c.catchment_id}
                label={c.name ?? t('rail.unnamed')}
                caveat={c.caveat}
              >
                <ValueWithUnit value={c.area_km2} unit="km²" digits={2} provenance="modelled" />
              </Row>
            ))}
          </Group>

          <Group icon={<OutletGlyph size={16} />} title={t('rail.outlets')}>
            {data.outlets.map((o) => (
              <Row
                key={o.outlet_id}
                id={o.outlet_id}
                label={o.catchment_id}
                // 01 §6.7: AQ-O04's enclosed-harbour caveat travels with it
                // wherever it appears, not only where someone remembered.
                caveat={o.caveat}
                warn={HARBOUR_BASIN_OUTLETS.has(o.outlet_id)}
              >
                <ValueWithUnit
                  value={o.upstream_km2 ?? null}
                  unit="km²"
                  digits={0}
                  provenance="modelled"
                />
              </Row>
            ))}
          </Group>

          <Group icon={<ReefZoneGlyph size={16} />} title={t('rail.reefZones')}>
            {data.reef.map((r) => (
              <Row key={r.reef_zone_id} id={r.reef_zone_id} label={r.zone_name}>
                <ValueWithUnit value={r.area_km2} unit="km²" digits={2} provenance="modelled" />
              </Row>
            ))}
            {/* 01 §6.6: provisional data is labelled in the UI, not only in the
                repo. sensitivity_weight is 1.0 on all eight zones, so the legend
                must not imply they differ. */}
            <p className="mt-1 text-2xs text-ink-3">{t('rail.reefProvisional')}</p>
          </Group>

          {/* The honesty device, in words as well as on the map. */}
          <Group title={t('rail.coverage')}>
            <p className="text-2xs text-ink-3">{t('rail.coverageNote')}</p>
          </Group>
        </>
      ) : null}
    </aside>
  );
}

function Group({
  icon,
  title,
  children,
}: {
  icon?: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="flex items-center gap-2 border-b border-hairline pb-1 text-xs font-semibold text-ink-2">
        {icon}
        {title}
      </h2>
      <div className="flex flex-col gap-1">{children}</div>
    </section>
  );
}

function Row({
  id,
  label,
  caveat,
  warn,
  children,
}: {
  id: string;
  label: string;
  caveat?: string;
  warn?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-baseline justify-between gap-2 text-xs" title={caveat}>
      <span className="flex min-w-0 items-baseline gap-2">
        {/* shrink-0 and nowrap, because flex was happy to break `R-02` across two
            lines to make room for a long zone name. An identifier that wraps is
            no longer an identifier. */}
        <span
          dir="ltr"
          style={{ unicodeBidi: 'isolate' }}
          className="shrink-0 whitespace-nowrap font-mono num text-2xs"
        >
          {id}
        </span>
        {/* dir="auto", not a fixed direction. These names come from the data and
            can be either script — "Marine Science Station / Cedar Pride" or an
            Arabic zone name. In an RTL container a Latin name truncated with a
            fixed direction puts the ellipsis at the START, so the rail showed
            "…rine Science Station / Cedar Pride" and lost the identifying half.
            Letting the browser resolve direction from the first strong character
            keeps the ellipsis at the end in both scripts. */}
        <span dir="auto" style={{ unicodeBidi: 'isolate' }} className="truncate text-ink-2">
          {label}
        </span>
        {warn ? (
          <span
            className="shrink-0 border border-risk-high-stroke bg-risk-high px-1 text-2xs text-risk-high-on"
            title={caveat}
          >
            !
          </span>
        ) : null}
      </span>
      {children}
    </div>
  );
}
