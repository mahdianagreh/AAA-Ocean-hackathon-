import { useEffect, useRef, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { Geometry, FeatureCollection } from 'geojson';
import {
  Map as MapLibreMap,
  NavigationControl,
  AttributionControl,
  type GeoJSONSource,
} from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useUi } from '../app/uiStore';
import { palette } from '../design/palette.generated';
import { buildJourneyStyle, PLUME_HEIGHT_PER_LEVEL_M } from './journeyStyle';

/** The 3D Journey (feature 14). Rainfall -> wadi -> outlet -> plume -> reef, the
 *  concept doc's own chain, flown through in one real, data-driven 3D scene.
 *
 *  Every number on screen traces to a committed artefact or a live-derived fixture
 *  (`scripts/frontend_journey.py`, `scripts/frontend_basemap.py`'s
 *  `relief_bands()`) — nothing here is generated geometry or an invented mesh.
 *  What the scene cannot honestly show, it says so: the plume's own
 *  current-grid-masking caveat is surfaced verbatim, not smoothed over, exactly
 *  as `docs/model_card.md` and `docs/HANDOFF_abd_2026-08-06.md` §2.5 already state
 *  it for this same outlet.
 */

interface Contour {
  probability: number;
  geometry: Geometry;
}

interface JourneyFixture {
  event_id: string;
  outlet_id: string;
  horizon_hours: number;
  release: { lon: number; lat: number; catchment_id: string };
  is_stub: boolean;
  model_version: string;
  plume_source: string;
  frames: Array<{ t_hours: number; contours: Contour[] }>;
  reef_exposure: Array<{ reef_zone_id: string; risk_score: number; risk_level: string }>;
  current_masking_caveat: string | null;
  source: string;
}

interface CatchmentFeature {
  properties: { catchment_id: string };
  geometry: Geometry;
}

const FIXTURE_URL = `${import.meta.env.BASE_URL}fixtures/journey3d.json`;
const CATCHMENTS_URL = `${import.meta.env.BASE_URL}basemap/catchments.geojson`;

/** Plain-average centroid of a polygon/multipolygon's exterior ring(s) — good
 *  enough to point a camera at, not a claim of geometric precision. */
function roughCentroid(geom: Geometry): [number, number] {
  const rings: number[][][] =
    geom.type === 'Polygon'
      ? [geom.coordinates[0]]
      : geom.type === 'MultiPolygon'
        ? geom.coordinates.map((p) => p[0])
        : [];
  const pts = rings.flat();
  if (pts.length === 0) return [0, 0];
  const [sx, sy] = pts.reduce(
    ([ax, ay]: number[], [x, y]: number[]) => [ax + x, ay + y],
    [0, 0],
  );
  return [sx / pts.length, sy / pts.length];
}

const AUTOPLAY_MS = 2200;

export function Journey3D() {
  const { t } = useTranslation();
  const theme = useUi((s) => s.theme);
  const resolved =
    theme === 'system'
      ? window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
      : theme;
  const c = palette[resolved];

  const container = useRef<HTMLDivElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const [fixture, setFixture] = useState<JourneyFixture | null>(null);
  const [wadiCenter, setWadiCenter] = useState<[number, number] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [stage, setStage] = useState<'wadi' | 'outlet' | 'reef'>('wadi');

  useEffect(() => {
    let live = true;
    void Promise.all([
      fetch(FIXTURE_URL).then((r) => {
        if (!r.ok) throw new Error(`journey3d.json: HTTP ${r.status}`);
        return r.json() as Promise<JourneyFixture>;
      }),
      fetch(CATCHMENTS_URL).then((r) => r.json()),
    ])
      .then(([j, catchmentsFc]) => {
        if (!live) return;
        setFixture(j);
        const feat = (catchmentsFc.features as CatchmentFeature[]).find(
          (f) => f.properties.catchment_id === j.release.catchment_id,
        );
        if (feat) setWadiCenter(roughCentroid(feat.geometry));
      })
      .catch((e: Error) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, []);

  const riskMatch = useCallback(
    (exposure: JourneyFixture['reef_exposure']) => {
      const bands = c.risk as Record<string, string>;
      if (exposure.length === 0) {
        return c.ink_3;
      }
      return [
        'match',
        ['get', 'reef_zone_id'],
        ...exposure.flatMap((r) => [r.reef_zone_id, bands[r.risk_level] ?? c.ink_3]),
        c.ink_3,
      ] as unknown as string;
    },
    [c],
  );

  // Build the map once the fixture (and its release point) are known.
  useEffect(() => {
    if (!container.current || map.current || !fixture) return;
    const m = new MapLibreMap({
      container: container.current,
      style: buildJourneyStyle(resolved, riskMatch(fixture.reef_exposure)),
      center: [fixture.release.lon, fixture.release.lat],
      zoom: 11,
      pitch: 58,
      bearing: -18,
      attributionControl: false,
      dragRotate: true,
      touchZoomRotate: true,
    });
    m.addControl(new NavigationControl({ visualizePitch: true }), 'top-right');
    m.addControl(
      new AttributionControl({
        compact: true,
        customAttribution: [
          'Bathymetry/terrain: GEBCO / GMRT (substituted)',
          'Reef habitat © Allen Coral Atlas (CC BY 4.0)',
        ],
      }),
      'bottom-right',
    );
    m.on('load', () => setMapReady(true));
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      setMapReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixture]);

  // Push the current frame's real contours into the plume source.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;
    const frame = fixture.frames[frameIndex];
    const fc: FeatureCollection = {
      type: 'FeatureCollection',
      features: frame.contours.map((ct) => ({
        type: 'Feature',
        properties: { probability: ct.probability, height: ct.probability * PLUME_HEIGHT_PER_LEVEL_M },
        geometry: ct.geometry,
      })),
    };
    (m.getSource('plume-frame') as GeoJSONSource | undefined)?.setData(fc);
  }, [frameIndex, mapReady, fixture]);

  // Autoplay through the real timesteps.
  useEffect(() => {
    if (!playing || !fixture) return;
    const id = window.setInterval(() => {
      setFrameIndex((i) => {
        if (i >= fixture.frames.length - 1) {
          setPlaying(false);
          return i;
        }
        return i + 1;
      });
    }, AUTOPLAY_MS);
    return () => window.clearInterval(id);
  }, [playing, fixture]);

  const flyTo = useCallback((stageName: 'wadi' | 'outlet' | 'reef') => {
    const m = map.current;
    if (!m || !fixture) return;
    setStage(stageName);
    if (stageName === 'wadi' && wadiCenter) {
      m.flyTo({ center: wadiCenter, zoom: 10.5, pitch: 62, bearing: 10, duration: 1800 });
    } else if (stageName === 'outlet') {
      m.flyTo({
        center: [fixture.release.lon, fixture.release.lat],
        zoom: 12.5,
        pitch: 65,
        bearing: -18,
        duration: 1800,
      });
    } else {
      m.flyTo({
        center: [fixture.release.lon, fixture.release.lat],
        zoom: 12,
        pitch: 45,
        bearing: 40,
        duration: 1800,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixture, wadiCenter]);

  if (error) {
    return (
      <p role="alert" className="text-xs text-risk-critical">
        {error}
      </p>
    );
  }
  if (!fixture) {
    return <p className="text-xs text-ink-3">{t('rail.loading')}</p>;
  }

  const frame = fixture.frames[frameIndex];

  return (
    <div className="flex h-full flex-col gap-2" data-journey="true">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-1">
          {(['wadi', 'outlet', 'reef'] as const).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => flyTo(s)}
              data-journey-stage={s}
              aria-pressed={stage === s}
              className={`rule px-2 py-1 ${stage === s ? 'border-accent text-accent' : 'text-ink-2'}`}
            >
              {t(`journey.stage.${s}`)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPlaying((p) => !p)}
            data-journey-play="true"
            className="rule px-2 py-1 text-ink-2 hover:border-accent"
          >
            {playing ? t('journey.pause') : t('journey.play')}
          </button>
          <input
            type="range"
            min={0}
            max={fixture.frames.length - 1}
            value={frameIndex}
            onChange={(e) => setFrameIndex(Number(e.target.value))}
            data-journey-scrub="true"
            aria-label={t('journey.scrubLabel')}
          />
          <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-ink-2">
            {t('journey.hourLabel', { h: frame.t_hours })}
          </span>
        </div>
      </div>

      <div
        ref={container}
        data-journey-map="true"
        className="relative min-h-0 flex-1 rule"
        dir="ltr"
        aria-label={t('journey.mapLabel')}
      />

      <div className="flex flex-col gap-1 text-2xs text-ink-3">
        <p>
          {t('journey.realismCaveat', { exaggeration: 6 })}
        </p>
        {fixture.current_masking_caveat ? (
          <p className="text-risk-high-on">{fixture.current_masking_caveat}</p>
        ) : null}
        <p>
          {t('journey.source')} <code className="font-mono num">{fixture.source}</code>
        </p>
      </div>
    </div>
  );
}
