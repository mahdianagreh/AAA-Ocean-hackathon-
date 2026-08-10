import { useState } from 'react';
import { registerSpecimen } from './registry';
import { ModeSwitch } from '../components/ModeSwitch';
import { TimeSlider } from '../components/TimeSlider';
import { LayerToggle } from '../components/LayerToggle';
import { Legend } from '../components/Legend';
import { RiskCard, type RiskCardData } from '../components/RiskCard';
import { Hyetograph } from '../components/Hyetograph';
import type { LayerKey, Mode } from '../app/uiStore';
import type { RainPoint } from '../api/event';
import { Empty, ErrorState, Loading, Stale } from '../components/States';
import { ValueWithUnit } from '../components/ValueWithUnit';
import { AlertCard } from '../components/AlertCard';
import { CaveatCard } from '../components/CaveatCard';
import { DataTable, type Column } from '../components/DataTable';
import { Timeline } from '../components/Timeline';
import type { AlertRow } from '../api/live';

/** Every Phase 2 component, on all four specimen panes.
 *
 *  04-component-inventory.md: "Every component lands on /specimen the day it is
 *  written… A primitive that is not on the specimen route has not been checked."
 *  These render live and interactive rather than as static screenshots, because
 *  the RTL questions that matter are behavioural — which way a slider steps, which
 *  side a popover opens on, which end a name truncates from.
 *
 *  The required states from 04 are exercised here too: the risk card appears at
 *  every band, and the hyetograph gets a row with a real gap in it so the
 *  missing-is-not-zero rendering is visible rather than asserted.
 */

const STEPS = [
  '2016-10-26T00:00:00Z',
  '2016-10-27T00:00:00Z',
  '2016-10-28T00:00:00Z',
  '2016-10-29T00:00:00Z',
  '2016-10-30T00:00:00Z',
];

const BANDS = ['minimal', 'low', 'moderate', 'high', 'critical'] as const;

function card(band: (typeof BANDS)[number], score: number): RiskCardData {
  return {
    catchment_id: 'AQ-C01',
    name: 'Wadi Yutum',
    band,
    // The real AQ-C01 area, because a specimen that invents a number teaches the
    // wrong column width — 7 digits is what the widest card actually has to hold.
    area_km2: 4453.08,
    score,
    // null on purpose in half of them, so the gap rendering is on the page. This is
    // now the ONLY place the main view guarantees a visible gap in default mode: the
    // registered model fills runoff_probability everywhere else.
    runoff_probability: band === 'critical' ? 0.8121 : null,
    // Always null on every real path — a classifier has no volume to report.
    // No band-conditional case here, unlike runoff_probability above: this gap
    // is not a fixture-of-convenience, it is what the model always returns.
    predicted_runoff_m3: null,
    provisional: band !== 'critical',
    modelVersion: band === 'critical' ? 'runoff_weighted_gbm_2194b48_20260803T214757Z' : undefined,
    caveat:
      band === 'high'
        ? 'Engineered Wadi Yutum flood channel; mouth verified against imagery at the shoreline.'
        : undefined,
    drivers: [
      {
        key: 'rain_today',
        contribution: 0.42,
        value: { value: 8.29, unit: 'mm', provenance: 'modelled' },
      },
      {
        key: 'antecedent_rain_48h',
        contribution: 0.19,
        value: { value: 9.67, unit: 'mm', provenance: 'modelled' },
      },
      {
        key: 'catchment_area',
        contribution: 0.31,
        value: { value: 4453.08, unit: 'km²', provenance: 'modelled' },
      },
      {
        // Negative, so both directions of the diverging axis are on the page.
        key: 'transmission_loss',
        contribution: -0.22,
        value: { value: 50, unit: '%', provenance: 'modelled' },
      },
    ],
    confidence: {
      members_exceeding: 22,
      members_total: 30,
      threshold_key: 'risk.thresholdWetDay',
      threshold_value: { value: 15, unit: 'mm', provenance: 'modelled' },
    },
  };
}

/** A series with a deliberate gap, so "missing is never zero" is visible. */
const SERIES: Record<string, RainPoint[]> = {
  'AQ-C01': STEPS.map((t, i) => ({ t, mm: [0.01, 4.6, 8.29, 1.2, 0][i], coverage: 1 })),
  'AQ-C02': STEPS.map((t, i) => ({
    t,
    // index 3 is null: a gap, not a dry day.
    mm: [0, 3.1, 9.2, null, 0][i],
    coverage: i === 3 ? null : 1,
  })),
  'AQ-C05': STEPS.map((t, i) => ({ t, mm: [0, 2.4, 9.73, 0.4, 0][i], coverage: 1 })),
};

function ControlsDemo() {
  const [mode, setMode] = useState<Mode>('historical');
  const [cursor, setCursor] = useState(2);
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({
    isobaths: true,
    catchments: true,
    rainfall: true,
    plume: true,
    reef: true,
    outlets: true,
    mooring: true,
    divesites: false,
    modelGrid: false,
    coverage: true,
    labels: true,
  });

  return (
    <div className="flex flex-col gap-4">
      <ModeSwitch value={mode} onChange={setMode} />

      {/* The subtle one: the track keeps left = earlier even in the RTL panes,
          because the chart below it does. Drag it in the ar/rtl pane. */}
      <div className="rule p-2">
        <TimeSlider
          steps={STEPS}
          value={cursor}
          onChange={setCursor}
          marks={[
            { t: '2016-10-28T06:50:00Z', key: 'onset', label: 'Turbidity onset' },
            { t: '2016-10-29T14:15:00Z', key: 'cleared', label: 'Turbidity cleared' },
          ]}
        />
      </div>

      <Hyetograph
        byCatchment={SERIES}
        unit="mm/day"
        cursor={cursor}
        onCursor={setCursor}
        marks={[{ t: '2016-10-28T06:50:00Z', label: 'Turbidity onset' }]}
      />

      <LayerToggle
        layers={layers}
        onToggle={(k) => setLayers((s) => ({ ...s, [k]: !s[k] }))}
      />
    </div>
  );
}

export function registerPhase2Specimens() {
  registerSpecimen({
    id: 'controls',
    titleKey: 'specimen.sectionControls',
    noteKey: 'specimen.controlsNote',
    render: () => <ControlsDemo />,
  });

  registerSpecimen({
    id: 'risk-cards',
    titleKey: 'specimen.sectionRiskCards',
    noteKey: 'specimen.riskCardsNote',
    render: () => (
      <div className="flex flex-col gap-2">
        {BANDS.map((b, i) => (
          <RiskCard key={b} data={card(b, [12, 33, 51, 74, 92][i])} />
        ))}
      </div>
    ),
  });

  registerSpecimen({
    id: 'states',
    titleKey: 'specimen.sectionStates',
    noteKey: 'specimen.statesNote',
    render: () => (
      <div className="flex flex-col gap-3">
        <Loading what="Reading the snapshot…" />
        <Empty
          title="No plume at this step"
          body="No cell reached the lowest density band. This is a quiet step, not a failed layer — and the two must never look the same."
        />
        {/* A real failure the demo can still hit, rather than the obsolete one.
            The API does not start at all (OPEN-ISSUES #21), so a wrong
            VITE_DATA_SOURCE fails at connect — where "no trained model" is a
            state the registered artefact has now made unreachable. */}
        <ErrorState message="event.json: TypeError: Failed to fetch (http://localhost:8000)" />
        <Stale ageLabel="18 min">
          <div className="flex items-baseline justify-between gap-2 rule bg-surface p-2 text-xs">
            <span className="text-ink-2">Runoff probability</span>
            <ValueWithUnit value={0.7213} digits={4} provenance="modelled" />
          </div>
        </Stale>
        <div className="flex items-baseline justify-between gap-2 rule bg-surface p-2 text-xs">
          <span className="text-ink-2">Sediment class (no data)</span>
          <ValueWithUnit value={null} />
        </div>
      </div>
    ),
  });

  registerSpecimen({
    id: 'legend',
    titleKey: 'specimen.sectionLegend',
    render: () => <Legend plumeLevels={[0.1, 0.25, 0.5, 0.75]} />,
  });

  // The alert card is built ahead of the data: the exposure engine reaches no
  // named zone today, so /alerts is empty, but the card must be reviewable now.
  // Two samples — one with an arrival window, one with a null window rendered as
  // a gap — exercise both paths with fabricated specimen data.
  registerSpecimen({
    id: 'alert-card',
    titleKey: 'specimen.sectionAlertCard',
    render: () => (
      <div className="flex flex-col gap-3">
        <AlertCard alert={SAMPLE_ALERT} zoneName="Power Station Reef" />
        <AlertCard alert={SAMPLE_ALERT_NO_WINDOW} />
      </div>
    ),
  });

  // The three shared components introduced this phase land on the specimen too,
  // per the design-system rule: a primitive not on /specimen has not been checked.
  registerSpecimen({
    id: 'caveat-card',
    titleKey: 'specimen.sectionCaveatCard',
    render: () => (
      <div className="flex flex-col gap-3">
        <CaveatCard severity="critical" headline="Critical example" message="A critical caveat, with a source pill." source="backend/src/api/caveats.py" field="depth_median_m" />
        <CaveatCard severity="warning" message="A warning-level caveat with no headline." source="docs/data_dictionary.md" />
        <CaveatCard severity="info" message="An informational note. Info and unknown severities read as a note." />
      </div>
    ),
  });

  registerSpecimen({
    id: 'data-table',
    titleKey: 'specimen.sectionDataTable',
    render: () => {
      const rows = [
        { id: 'R-01', name: 'Tala Bay', n: 0.42 },
        { id: 'R-02', name: 'Power Station Reef', n: null },
      ];
      const cols: Column<(typeof rows)[number]>[] = [
        { key: 'id', header: 'Zone', cell: (r) => <span dir="ltr" className="num font-mono">{r.id}</span> },
        { key: 'name', header: 'Name', cell: (r) => r.name },
        { key: 'n', align: 'end', header: 'Value', cell: (r) => <ValueWithUnit value={r.n} digits={2} provenance="modelled" /> },
      ];
      return <DataTable columns={cols} rows={rows} getRowKey={(r) => r.id} ariaLabel="Specimen data table" />;
    },
  });

  registerSpecimen({
    id: 'timeline',
    titleKey: 'specimen.sectionTimeline',
    render: () => (
      <Timeline
        ariaLabel="Specimen timeline"
        entries={[
          { key: 'onset', label: 'Turbidity onset', time: '2016-10-28T06:50:00Z', meta: 'measured', provenance: 'measured' },
          { key: 'cleared', label: 'Turbidity cleared', time: '2016-10-29T14:15:00Z', meta: 'measured', provenance: 'measured' },
          { key: 'modelled', label: 'Modelled arrival', time: '2016-10-28T07:30:00Z', meta: 'modelled', provenance: 'modelled' },
        ]}
      />
    ),
  });
}

const SAMPLE_ALERT: AlertRow = {
  alert_id: 'alert_sample_01',
  source_run_id: 'sim_01KZSPECIMEN0000000000000',
  reef_zone_id: 'R-03',
  risk_level: 'high',
  risk_score: 72.4,
  issued_at: '2016-10-28T09:15:00Z',
  arrival_window_hours: [6, 14],
  headline_en: 'Elevated sediment exposure expected at Power Station Reef within the day.',
  headline_ar: 'يُتوقّع تعرّض مرتفع للرواسب عند شعاب محطة الكهرباء خلال اليوم.',
};

const SAMPLE_ALERT_NO_WINDOW: AlertRow = {
  ...SAMPLE_ALERT,
  alert_id: 'alert_sample_02',
  reef_zone_id: 'R-01',
  risk_level: 'moderate',
  risk_score: 48.1,
  arrival_window_hours: null,
  headline_en: 'Moderate exposure at Tala Bay; arrival window not resolved for this run.',
  headline_ar: 'تعرّض متوسّط عند خليج تالا؛ لم تُحدَّد نافذة الوصول لهذا التشغيل.',
};
