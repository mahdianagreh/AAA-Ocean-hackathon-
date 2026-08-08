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
import { buildJourneyStyle } from './journeyStyle';
import { usePhaseTimeline } from './usePhaseTimeline';
import { transportPaint, accumulationPaint } from './layers/plume';
import { reefRiskColorExpression, reefStrokeExpression } from './layers/reef';
import { makeRainSeeds, rainFrameFeatures, RAIN_POOL_SIZE, type RainSeed } from './layers/rain';
import { runoffFeatures, runoffDashArray } from './layers/runoff';
import { TERRAIN_EXAGGERATION } from './layers/terrain';
import { loadImageryCorners, IMAGE_URL } from './layers/imagery';
import type { JourneyPhase } from './constants';

//: The same Esri World Imagery this project's 2D plume map already ships in
//: production output (backend/src/rendering/plume_map.py), same attribution
//: convention (a documented fallback string, not a live network fetch of the
//: attribution text) — see docs/data_dictionary.md's Esri entry and
//: docs/plume_imagery_decision.md for why real imagery is the deliberate
//: choice here, not a generated basemap.
const IMAGERY_ATTRIBUTION = 'Esri, Maxar, Earthstar Geographics, and the GIS User Community';

/** The 3D Journey (feature 14). Rainfall -> wadi -> outlet -> plume -> reef,
 *  the concept doc's own chain, flown through as one real, data-driven,
 *  phased 3D scene.
 *
 *  Every layer's data is real (see journeyStyle.ts and layers/*.ts for what
 *  and where from); the PHASE SEQUENCE that reveals them (normal, heavy rain,
 *  flood, sediment transport, accumulation, coastal impact) is a stylised
 *  narrative device — real durations for six sequential environmental phases
 *  are not data this project has, and this docstring says so rather than
 *  implying otherwise.
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
  rainfall: { peak_date_utc: string; peak_mm: number; unit: string; source: string; note: string } | null;
  runoff_lines: number[][][];
  source: string;
}

interface CatchmentFeature {
  properties: { catchment_id: string };
  geometry: Geometry;
}

const FIXTURE_URL = `${import.meta.env.BASE_URL}fixtures/journey3d.json`;
const CATCHMENTS_URL = `${import.meta.env.BASE_URL}basemap/catchments.geojson`;

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

//: Real rainfall mm has no universal "how intense does this look" scale;
//: 15 mm/day is used only as the animation's own reference ceiling (not a
//: meteorological threshold) so the real measured value maps onto a visible
//: 0-1 range. The real mm value itself is shown in the caption, never hidden
//: behind this normalisation.
const RAIN_INTENSITY_REFERENCE_MM = 15;
const RAIN_TICK_MS = 90;
const RUNOFF_TICK_MS = 220;

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

  const timeline = usePhaseTimeline(fixture?.frames.length ?? 0);
  const { phase, playing, frameIndex } = timeline;

  const rainSeedsRef = useRef<RainSeed[] | null>(null);
  const effectRafRef = useRef<number | null>(null);
  const lastRainTickRef = useRef(0);
  const lastRunoffTickRef = useRef(0);
  const runoffTickCountRef = useRef(0);

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

  // Build the map once the fixture (and its release point) are known.
  useEffect(() => {
    if (!container.current || map.current || !fixture) return;
    const m = new MapLibreMap({
      container: container.current,
      style: buildJourneyStyle(resolved),
      // A strong overview first — coastline, sea, terrain and the urban strip
      // all visible at once, not a close-in shot of one building. Phases fly
      // in closer as the story progresses.
      center: [fixture.release.lon, fixture.release.lat - 0.01],
      zoom: 9.6,
      pitch: 35,
      bearing: -10,
      attributionControl: false,
      dragRotate: true,
      touchZoomRotate: true,
    });
    m.addControl(new NavigationControl({ visualizePitch: true }), 'top-right');
    m.addControl(
      new AttributionControl({
        compact: true,
        customAttribution: [
          'Terrain: Copernicus DEM GLO-30 (land) + GMRT bathymetry (sea, GEBCO stand-in)',
          `Imagery: ${IMAGERY_ATTRIBUTION}`,
          'Buildings, wadis © OpenStreetMap contributors (ODbL)',
          'Reef habitat © Allen Coral Atlas (CC BY 4.0)',
        ],
      }),
      'bottom-right',
    );
    m.on('load', () => {
      m.setTerrain({ source: 'terrain', exaggeration: TERRAIN_EXAGGERATION });
      setMapReady(true);
      // Async: the sidecar JSON carries the real image's corner bounds, so
      // the `image` source can't be declared in the static style (journeyStyle.ts)
      // the way every other source is — see layers/imagery.ts's own docstring.
      // Resolves to null (degrade honestly, no drape) if the baked file was
      // never copied into frontend/public/basemap-raster/ in this environment.
      void loadImageryCorners().then((corners) => {
        if (!corners || !map.current) return;
        map.current.addSource('imagery', { type: 'image', url: IMAGE_URL, coordinates: corners.coordinates });
        map.current.addLayer(
          { id: 'imagery-raster', type: 'raster', source: 'imagery', paint: { 'raster-opacity': 1 } },
          'terrain-hillshade',
        );
      });
    });
    map.current = m;
    // Dev/specimen only — same pattern as map/MapView.tsx's own __map handle,
    // used there to prove RTL labels were actually placed, not just requested.
    if (import.meta.env.DEV || import.meta.env.VITE_SPECIMEN === '1') {
      (window as unknown as { __journeyMap?: MapLibreMap }).__journeyMap = m;
    }
    return () => {
      m.remove();
      map.current = null;
      setMapReady(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixture]);

  // Camera follows the phase automatically during Play; also reachable by
  // clicking a phase directly (goToPhase) for manual exploration.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;
    if (phase === 'normal') {
      m.flyTo({ center: [fixture.release.lon, fixture.release.lat - 0.01], zoom: 9.6, pitch: 35, bearing: -10, duration: 1600 });
    } else if ((phase === 'rain' || phase === 'flood') && wadiCenter) {
      const midLon = (wadiCenter[0] + fixture.release.lon) / 2;
      const midLat = (wadiCenter[1] + fixture.release.lat) / 2;
      m.flyTo({ center: [midLon, midLat], zoom: 10.2, pitch: 55, bearing: 5, duration: 1800 });
    } else if (phase === 'transport' || phase === 'accumulation') {
      m.flyTo({ center: [fixture.release.lon, fixture.release.lat], zoom: 12.5, pitch: 65, bearing: -18, duration: 1800 });
    } else if (phase === 'impact') {
      m.flyTo({ center: [fixture.release.lon, fixture.release.lat], zoom: 12, pitch: 45, bearing: 40, duration: 1800 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, mapReady, fixture, wadiCenter]);

  // Plume frame data + transport/accumulation paint switch.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;
    if (phase === 'transport' || phase === 'accumulation') {
      const frame = fixture.frames[frameIndex];
      const fc: FeatureCollection = {
        type: 'FeatureCollection',
        features: frame.contours.map((ct) => ({
          type: 'Feature',
          properties: { probability: ct.probability },
          geometry: ct.geometry,
        })),
      };
      (m.getSource('plume-frame') as GeoJSONSource | undefined)?.setData(fc);
      const paint = phase === 'accumulation' ? accumulationPaint(c) : transportPaint(c);
      // setPaintProperty's key type is a closed union of every paint property
      // MapLibre knows about; `paint` is built from that same union in
      // layers/plume.ts, so the runtime keys are always valid even though
      // Object.entries widens them to `string` for TypeScript.
      for (const [k, v] of Object.entries(paint)) {
        m.setPaintProperty('plume-extrusion', k as Parameters<typeof m.setPaintProperty>[1], v as never);
      }
    } else if (phase === 'normal' || phase === 'rain' || phase === 'flood') {
      (m.getSource('plume-frame') as GeoJSONSource | undefined)?.setData({
        type: 'FeatureCollection',
        features: [],
      });
    }
    // 'impact' deliberately leaves the plume as accumulation left it — the
    // sediment doesn't vanish once the story moves on to reef impact.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, frameIndex, mapReady, fixture, c]);

  // Reef reveal: neutral until 'impact', then the real exposure colour.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;
    const fillColor = phase === 'impact' ? reefRiskColorExpression(c, fixture.reef_exposure) : c.ink_3;
    const strokeColor = phase === 'impact' ? reefStrokeExpression(c, fixture.reef_exposure) : c.ink;
    m.setPaintProperty('reef-extrusion', 'fill-extrusion-color', fillColor as never);
    m.setPaintProperty('reef-outline', 'line-color', strokeColor as never);
  }, [phase, mapReady, fixture, c]);

  // Rain + runoff: one shared rAF loop, active only while its phase is live.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;

    if (phase !== 'rain' && phase !== 'flood') {
      (m.getSource('rain') as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: [] });
      (m.getSource('runoff') as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: [] });
      return;
    }

    if (phase === 'rain' && !rainSeedsRef.current) {
      const pad = 0.02;
      rainSeedsRef.current = makeRainSeeds([
        fixture.release.lon - pad, fixture.release.lat - pad,
        fixture.release.lon + pad, fixture.release.lat + pad,
      ]);
    }
    if (phase === 'flood') {
      (m.getSource('runoff') as GeoJSONSource | undefined)?.setData(runoffFeatures(fixture.runoff_lines));
    }

    let cancelled = false;
    const loop = (now: number) => {
      if (cancelled) return;
      if (phase === 'rain' && rainSeedsRef.current) {
        if (now - lastRainTickRef.current >= RAIN_TICK_MS) {
          lastRainTickRef.current = now;
          const mm = fixture.rainfall?.peak_mm ?? RAIN_INTENSITY_REFERENCE_MM;
          const intensity = Math.min(1, mm / RAIN_INTENSITY_REFERENCE_MM);
          const active = Math.round(RAIN_POOL_SIZE * intensity);
          const fc = rainFrameFeatures(rainSeedsRef.current, now, active);
          (m.getSource('rain') as GeoJSONSource | undefined)?.setData(fc);
        }
      }
      if (phase === 'flood') {
        if (now - lastRunoffTickRef.current >= RUNOFF_TICK_MS) {
          lastRunoffTickRef.current = now;
          runoffTickCountRef.current += 1;
          if (m.getLayer('runoff-flow')) {
            m.setPaintProperty('runoff-flow', 'line-dasharray', runoffDashArray(runoffTickCountRef.current) as never);
          }
        }
      }
      effectRafRef.current = requestAnimationFrame(loop);
    };
    effectRafRef.current = requestAnimationFrame(loop);
    return () => {
      cancelled = true;
      if (effectRafRef.current !== null) cancelAnimationFrame(effectRafRef.current);
    };
  }, [phase, mapReady, fixture]);

  const handlePhaseClick = useCallback((p: JourneyPhase) => {
    timeline.goToPhase(p);
  }, [timeline]);

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

  const phases: JourneyPhase[] = ['normal', 'rain', 'flood', 'transport', 'accumulation', 'impact'];

  return (
    <div className="flex h-full flex-col gap-2" data-journey="true">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-1" role="tablist" aria-label={t('journey.phaseNav')}>
          {phases.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => handlePhaseClick(p)}
              data-journey-phase={p}
              aria-pressed={phase === p}
              className={`rule px-2 py-1 ${phase === p ? 'border-accent text-accent' : 'text-ink-2'}`}
            >
              {t(`journey.phase.${p}`)}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => (playing ? timeline.pause() : timeline.play())}
            data-journey-play="true"
            className="rule px-2 py-1 text-ink-2 hover:border-accent"
          >
            {playing ? t('journey.pause') : t('journey.play')}
          </button>
          <button
            type="button"
            onClick={timeline.reset}
            data-journey-reset="true"
            className="rule px-2 py-1 text-ink-2 hover:border-accent"
          >
            {t('journey.reset')}
          </button>
          {(phase === 'transport' || phase === 'accumulation') ? (
            <span dir="ltr" style={{ unicodeBidi: 'isolate' }} className="font-mono num text-ink-2">
              {t('journey.hourLabel', { h: fixture.frames[frameIndex]?.t_hours ?? 0 })}
            </span>
          ) : null}
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
        <p className="font-semibold text-ink-2">{t(`journey.phaseBody.${phase}`, {
          mm: fixture.rainfall?.peak_mm,
          date: fixture.rainfall?.peak_date_utc?.slice(0, 10),
        })}</p>
        <p>{t('journey.realismCaveat', { exaggeration: TERRAIN_EXAGGERATION })}</p>
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
