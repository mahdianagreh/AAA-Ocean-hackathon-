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
import { catchmentOpacity } from './layers/catchments';
import { makeRainSeeds, rainFrameFeatures, RAIN_POOL_SIZE, type RainSeed } from './layers/rain';
import {
  createRainStreaks,
  stepRainStreaks,
  clearRainCanvas,
  paintRainInClip,
  geometryToScreenPath,
  drawClouds,
  type RainStreak,
  type CloudAnchor,
} from './layers/rainOverlay';
import { runoffFeatures, runoffPolygonFeatures } from './layers/runoff';
import {
  buildFlowPaths,
  createFlowParticles,
  stepFlowParticles,
  drawWaterFlow,
  type FlowParticle,
} from './layers/waterFlowOverlay';
import { JourneyAlert, type JourneyAlertCatchment } from './JourneyAlert';
import { TERRAIN_EXAGGERATION } from './layers/terrain';
import { loadImageryCorners, imageUrlFor, TERRAIN_STEM, CORRIDOR_STEM } from './layers/imagery';
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
  //: All five real catchments' own measured peak for the event day (2016-10-27
  //: was a regional storm, not a single-catchment cell) -- `null` for any
  //: catchment with no real value that day, never a borrowed/zero stand-in.
  rainfall_by_catchment: Record<string, { peak_mm: number } | null>;
  //: This catchment's own real 99th-percentile day, from its whole real
  //: record -- see JourneyAlert.tsx's docstring for why this is the honest
  //: comparison point, not a bare mm figure.
  rainfall_p99_by_catchment: Record<string, number | null>;
  runoff_lines: number[][][];
  //: The same real centrelines above, buffered by a real-drainage-density-
  //: scaled width -- see runoff.ts's docstring and frontend_journey.py's
  //: `_real_runoff_polygon`. One exterior ring per disjoint polygon.
  runoff_polygon: number[][][];
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
//: The overlay's own pool, independent of RAIN_POOL_SIZE (the ripple pool) --
//: a full-canvas storm sheet reads right at a higher count than the small
//: real-lon/lat ripple field does.
const RAIN_STREAK_POOL_SIZE = 260;

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
  const rainCanvasRef = useRef<HTMLCanvasElement>(null);
  const map = useRef<MapLibreMap | null>(null);
  const [fixture, setFixture] = useState<JourneyFixture | null>(null);
  const [wadiCenter, setWadiCenter] = useState<[number, number] | null>(null);
  const [catchmentFeatures, setCatchmentFeatures] = useState<CatchmentFeature[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [alertDismissed, setAlertDismissed] = useState(false);

  const timeline = usePhaseTimeline(fixture?.frames.length ?? 0);
  const { phase, playing, frameIndex } = timeline;

  // Re-arm the warning every time the story restarts, so replaying the
  // journey (Reset, or clicking back to Normal) shows it again rather than
  // remembering a dismissal from a previous run.
  useEffect(() => {
    if (phase === 'normal') setAlertDismissed(false);
  }, [phase]);

  const rainSeedsRef = useRef<RainSeed[] | null>(null);
  const rainStreaksRef = useRef<RainStreak[] | null>(null);
  const lastOverlayTsRef = useRef<number | null>(null);
  const effectRafRef = useRef<number | null>(null);
  const lastRainTickRef = useRef(0);
  const floodStartTsRef = useRef<number | null>(null);
  const flowParticlesRef = useRef<FlowParticle[] | null>(null);

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
        const features = catchmentsFc.features as CatchmentFeature[];
        setCatchmentFeatures(features);
        const feat = features.find((f) => f.properties.catchment_id === j.release.catchment_id);
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
      // Async: the sidecar JSON carries each real image's corner bounds, so
      // the `image` sources can't be declared in the static style
      // (journeyStyle.ts) the way every other source is — see
      // layers/imagery.ts's own docstring. Resolves to null (degrade
      // honestly, no drape) if a baked file was never copied into
      // frontend/public/basemap-raster/ in this environment. Both inserted
      // "before terrain-hillshade" in sequence -- the corridor bake (added
      // second) lands directly beneath hillshade and above the full-AOI
      // bake, so it simply draws over the coarser image wherever its real
      // extent covers, with no per-phase switching logic.
      void loadImageryCorners(TERRAIN_STEM).then((corners) => {
        if (!corners || !map.current) return;
        map.current.addSource('imagery', { type: 'image', url: imageUrlFor(TERRAIN_STEM), coordinates: corners.coordinates });
        map.current.addLayer(
          { id: 'imagery-raster', type: 'raster', source: 'imagery', paint: { 'raster-opacity': 1 } },
          'terrain-hillshade',
        );
      });
      void loadImageryCorners(CORRIDOR_STEM).then((corners) => {
        if (!corners || !map.current) return;
        map.current.addSource('imagery-corridor', { type: 'image', url: imageUrlFor(CORRIDOR_STEM), coordinates: corners.coordinates });
        map.current.addLayer(
          { id: 'imagery-corridor-raster', type: 'raster', source: 'imagery-corridor', paint: { 'raster-opacity': 1 } },
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

  // Keep the rain overlay canvas pixel-matched to the map container,
  // including devicePixelRatio, so streaks stay crisp rather than
  // blurred/upscaled the way a stale canvas.width would leave them.
  useEffect(() => {
    const el = container.current;
    const canvas = rainCanvasRef.current;
    if (!el || !canvas) return;
    const resize = () => {
      const rect = el.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      const ctx = canvas.getContext('2d');
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(el);
    return () => observer.disconnect();
    // `fixture` gates the JSX below (the container/canvas refs are null
    // until it loads, per the early `if (!fixture) return <p>...` above) --
    // an empty dep array here would run once against those nulls and never
    // fire again once the real elements mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fixture]);

  // Camera follows the phase automatically during Play; also reachable by
  // clicking a phase directly (goToPhase) for manual exploration.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;
    if (phase === 'normal') {
      m.flyTo({ center: [fixture.release.lon, fixture.release.lat - 0.01], zoom: 9.6, pitch: 35, bearing: -10, duration: 1600 });
    } else if (phase === 'rain' && wadiCenter) {
      const midLon = (wadiCenter[0] + fixture.release.lon) / 2;
      const midLat = (wadiCenter[1] + fixture.release.lat) / 2;
      m.flyTo({ center: [midLon, midLat], zoom: 10.2, pitch: 55, bearing: 5, duration: 1800 });
    } else if (phase === 'flood' && wadiCenter) {
      // Its own framing, not a reuse of 'rain''s: bearing is the real
      // compass direction from the catchment's own centroid to the real
      // release point (small-distance planar approximation, cos(lat)
      // correction for the east/west component), so the camera looks down
      // the real flow direction toward the outlet rather than a fixed,
      // arbitrary angle. Slightly closer and steeper than 'rain' so the
      // widening water channel (layers/runoff.ts) reads clearly.
      const midLon = (wadiCenter[0] + fixture.release.lon) / 2;
      const midLat = (wadiCenter[1] + fixture.release.lat) / 2;
      const latRad = (midLat * Math.PI) / 180;
      const dLon = (fixture.release.lon - wadiCenter[0]) * Math.cos(latRad);
      const dLat = fixture.release.lat - wadiCenter[1];
      const bearing = ((Math.atan2(dLon, dLat) * 180) / Math.PI + 360) % 360;
      m.flyTo({ center: [midLon, midLat], zoom: 10.6, pitch: 60, bearing, duration: 1800 });
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

  // Catchment boundaries: full strength while the story is upstream (normal/
  // rain/flood), faded once it moves to the plume/reef so they read as
  // context rather than competing with the sediment cloud.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady) return;
    const op = catchmentOpacity(phase);
    m.setPaintProperty('catchment-fill', 'fill-opacity', op.fill);
    m.setPaintProperty('catchment-outline', 'line-opacity', op.line);
    m.setPaintProperty('catchment-label', 'text-opacity', op.text);
  }, [phase, mapReady]);

  // Rain + runoff: one shared rAF loop, active only while its phase is live.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapReady || !fixture) return;

    if (phase !== 'rain' && phase !== 'flood') {
      (m.getSource('rain') as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: [] });
      (m.getSource('runoff') as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: [] });
      (m.getSource('runoff-fill') as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: [] });
      if (m.getLayer('runoff-wet-ground')) m.setPaintProperty('runoff-wet-ground', 'line-opacity', 0);
      const canvas = rainCanvasRef.current;
      const ctx = canvas?.getContext('2d');
      const dpr0 = window.devicePixelRatio || 1;
      if (canvas && ctx) clearRainCanvas(ctx, canvas.width / dpr0, canvas.height / dpr0);
      rainStreaksRef.current = null;
      lastOverlayTsRef.current = null;
      floodStartTsRef.current = null;
      flowParticlesRef.current = null;
      return;
    }

    const pad = 0.02;
    if (phase === 'rain' && !rainSeedsRef.current) {
      rainSeedsRef.current = makeRainSeeds([
        fixture.release.lon - pad, fixture.release.lat - pad,
        fixture.release.lon + pad, fixture.release.lat + pad,
      ]);
    }
    if (phase === 'flood') {
      (m.getSource('runoff') as GeoJSONSource | undefined)?.setData(runoffFeatures(fixture.runoff_lines));
      (m.getSource('runoff-fill') as GeoJSONSource | undefined)?.setData(runoffPolygonFeatures(fixture.runoff_polygon));
      if (!flowParticlesRef.current) {
        const initialPaths = buildFlowPaths(
          fixture.runoff_lines,
          (lon, lat) => m.project([lon, lat]),
          [fixture.release.lon, fixture.release.lat],
        );
        flowParticlesRef.current = createFlowParticles(initialPaths, 9);
      }
    }

    let cancelled = false;
    const loop = (now: number) => {
      if (cancelled) return;
      const mm = fixture.rainfall?.peak_mm ?? RAIN_INTENSITY_REFERENCE_MM;
      const intensity = Math.min(1, mm / RAIN_INTENSITY_REFERENCE_MM);
      if (phase === 'rain' && rainSeedsRef.current) {
        if (now - lastRainTickRef.current >= RAIN_TICK_MS) {
          lastRainTickRef.current = now;
          const active = Math.round(RAIN_POOL_SIZE * intensity);
          const fc = rainFrameFeatures(rainSeedsRef.current, now, active);
          (m.getSource('rain') as GeoJSONSource | undefined)?.setData(fc);
        }
        // Every rAF frame, not throttled like the ripple tick above -- the
        // falling motion needs to read as continuous, not stepped. One
        // shared streak pool falls across the whole canvas (cheap, and a
        // streak doesn't know which catchment it's over); what actually
        // confines the *visible* rain to real ground is the per-catchment
        // clip below, not the streaks' own spawn range.
        const canvas = rainCanvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (canvas && ctx && catchmentFeatures) {
          const dpr = window.devicePixelRatio || 1;
          const w = canvas.width / dpr;
          const h = canvas.height / dpr;
          if (!rainStreaksRef.current) rainStreaksRef.current = createRainStreaks(w, h, RAIN_STREAK_POOL_SIZE);
          const dt = lastOverlayTsRef.current === null ? 0 : (now - lastOverlayTsRef.current) / 1000;
          lastOverlayTsRef.current = now;
          stepRainStreaks(rainStreaksRef.current, w, h, Math.min(dt, 0.05));

          clearRainCanvas(ctx, w, h);
          const project = (lon: number, lat: number) => m.project([lon, lat]);
          const cloudAnchors: CloudAnchor[] = [];
          for (const feat of catchmentFeatures) {
            const real = fixture.rainfall_by_catchment[feat.properties.catchment_id];
            // Missing is never zero (Standing Law rule 1) -- a catchment with
            // no real measured value for this event day gets no rendered
            // rain at all, not a borrowed/zero intensity.
            if (!real) continue;
            const catchIntensity = Math.min(1, real.peak_mm / RAIN_INTENSITY_REFERENCE_MM);
            const { path, bounds } = geometryToScreenPath(feat.geometry, project);
            paintRainInClip(ctx, w, h, rainStreaksRef.current, path, catchIntensity);
            // AQ-C01 alone is 4,453 km2 -- most of the terrain AOI -- so its
            // real topmost point often projects well above the visible
            // canvas at this camera distance. Clamping keeps every
            // catchment's cloud somewhere on screen rather than silently
            // rendering off the top edge for the one catchment big enough
            // to need it.
            cloudAnchors.push({
              centerX: Math.min(w, Math.max(0, (bounds.x0 + bounds.x1) / 2)),
              topY: Math.max(40, bounds.y0),
              widthPx: Math.min(w, bounds.x1 - bounds.x0),
              intensity: catchIntensity,
            });
          }
          drawClouds(ctx, cloudAnchors, now / 1000);
        }
      }
      if (phase === 'flood') {
        if (floodStartTsRef.current === null) floodStartTsRef.current = now;

        // The actual "this is moving water" signal: screen-space particles
        // riding the real wadi path, every rAF frame (not throttled) so the
        // motion reads as continuous, same reasoning as the rain streak
        // step above. Paths are rebuilt fresh each frame from the current
        // camera projection (cheap -- a handful of already-simplified
        // lines) since the flood camera is still easing into place; only
        // the particles' own along-path progress persists across frames.
        const canvas = rainCanvasRef.current;
        const ctx = canvas?.getContext('2d');
        if (canvas && ctx && flowParticlesRef.current) {
          const dpr = window.devicePixelRatio || 1;
          const w = canvas.width / dpr;
          const h = canvas.height / dpr;
          const dt = lastOverlayTsRef.current === null ? 0 : (now - lastOverlayTsRef.current) / 1000;
          lastOverlayTsRef.current = now;
          const project = (lon: number, lat: number) => m.project([lon, lat]);
          const paths = buildFlowPaths(fixture.runoff_lines, project, [fixture.release.lon, fixture.release.lat]);
          // Speed scales with the same real intensity as everything else
          // this phase drives -- heavier real rain, visibly faster current.
          stepFlowParticles(flowParticlesRef.current, paths, Math.min(dt, 0.05), 0.5 + 1.5 * intensity);
          clearRainCanvas(ctx, w, h);
          drawWaterFlow(ctx, paths, flowParticlesRef.current, intensity);
        }

        // The wet-ground halo ramps in over real time, scaled by the same
        // real intensity -- no floor, so a catchment with almost no real
        // rain shows an almost-imperceptible halo, not a fixed one at
        // reduced opacity. `rampMs` shrinks (faster fill-in) as intensity
        // rises, clamped so near-zero intensity can't freeze it entirely.
        if (m.getLayer('runoff-wet-ground')) {
          const rampMs = Math.max(2000, Math.min(9000, 6000 / (0.4 + 1.2 * intensity)));
          const fillProgress = Math.min(1, (now - floodStartTsRef.current) / rampMs);
          m.setPaintProperty('runoff-wet-ground', 'line-opacity', 0.55 * intensity * fillProgress);
        }
      }
      effectRafRef.current = requestAnimationFrame(loop);
    };
    effectRafRef.current = requestAnimationFrame(loop);
    return () => {
      cancelled = true;
      if (effectRafRef.current !== null) cancelAnimationFrame(effectRafRef.current);
    };
  }, [phase, mapReady, fixture, catchmentFeatures]);

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

  // Every real catchment that actually recorded rainfall this event day —
  // `rainfall_by_catchment` entries are `null` (never a borrowed zero) for
  // any catchment with no real measured value, so this list is already the
  // honest "only these actually had rain" set.
  const alertCatchments: JourneyAlertCatchment[] = Object.entries(fixture.rainfall_by_catchment)
    .filter((entry): entry is [string, { peak_mm: number }] => entry[1] !== null)
    .map(([catchmentId, r]) => ({
      catchmentId,
      peakMm: r.peak_mm,
      p99Mm: fixture.rainfall_p99_by_catchment[catchmentId] ?? null,
    }));

  const hasSediment = (fixture.frames[frameIndex]?.contours.length ?? 0) > 0;
  const hasExposure = fixture.reef_exposure.length > 0;
  // If a real day/event has no plume contours or no reef exposure at all,
  // the phase text says so honestly instead of describing a simulation that
  // isn't there for this particular run -- this event has real data for
  // both, so this branch exists for correctness, not because today's replay
  // exercises it.
  const phaseBodyKey =
    (phase === 'transport' || phase === 'accumulation') && !hasSediment ? `${phase}Empty`
      : phase === 'impact' && !hasExposure ? 'impactEmpty'
      : phase;

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
        data-journey-map="true"
        className="relative grid min-h-0 flex-1 rule"
        dir="ltr"
        aria-label={t('journey.mapLabel')}
      >
        {/* A shared grid cell, not absolute+inset-0: MapLibre reads its
            container's laid-out size to set its own canvas dimensions, and
            an absolutely positioned container measured before the browser
            settled its inset-derived height was handing MapLibre a stale
            (default-canvas-sized) height. Both children stacking in one
            grid cell size against the grid track instead, which is settled
            before either child's own layout runs. */}
        <div ref={container} className="col-start-1 row-start-1 h-full w-full" />
        {/* Screen-space rain overlay (layers/rainOverlay.ts) -- sits above the
            map's own WebGL canvas, never intercepts pointer events so map
            drag/zoom/click still reach the map underneath it.
            `relative` is load-bearing, not decoration: MapLibre's own
            internal canvas is `position:absolute` (its own stylesheet), and
            a positioned element always paints above a plain `static`
            sibling regardless of DOM order -- without this the overlay drew
            correctly (confirmed via direct canvas pixel sampling) but was
            invisible, composited entirely behind the map. */}
        <canvas
          ref={rainCanvasRef}
          className="pointer-events-none relative col-start-1 row-start-1 h-full w-full"
        />
        {/* Pops in once the story reaches real rainfall, built from the same
            real per-catchment numbers the phase text below already quotes —
            see JourneyAlert.tsx for why the wording says "recorded", not
            "predicted". `relative`, same stacking reason as the rain canvas
            above: a non-positioned sibling would still lose to MapLibre's
            own `position:absolute` canvas. */}
        {(phase === 'rain' || phase === 'flood') && !alertDismissed && alertCatchments.length > 0 ? (
          <JourneyAlert
            catchments={alertCatchments}
            dateUtc={fixture.rainfall?.peak_date_utc ?? null}
            onDismiss={() => setAlertDismissed(true)}
          />
        ) : null}
      </div>

      <div className="flex flex-col gap-1 text-2xs text-ink-3">
        <p className="font-semibold text-ink-2">{t(`journey.phaseBody.${phaseBodyKey}`, {
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
