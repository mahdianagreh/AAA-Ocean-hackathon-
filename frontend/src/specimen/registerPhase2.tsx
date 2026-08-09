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
}
