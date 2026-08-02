# 10 · Performance and Offline

**Status:** scaffold — filled during Phase 5 · **Owner:** Ali

DoD item 9: **runs in Docker Compose, and works with wifi off** against the offline snapshot.

---

## Budgets

- [ ] Time-scrub holds **60fps** with every layer live — the hard one
- [ ] Initial JS budget — to be set in Phase 1, measured every phase after
- [ ] Map interaction stays responsive with all layers on
- [ ] Time to first meaningful map render — to be set

## Known payload problems

| Asset | Size | Plan |
|---|---|---|
| QA figures | **27 MB**, 11 files over 1 MB, `overview_01` alone 5.4 MB | WebP thumbnails at build time, lazy-load, full-res only in the lightbox |
| Plume raster | **4.2 MB** for one timestep | Ask #1 — contoured GeoJSON instead |
| Arabic font | shaping limits `unicode-range` splitting | Subset over glyphs actually used; measure, do not assume it behaves like the Latin face |
| Basemap tiles | to be measured | Sized and packed in Phase 5 |

## Offline

- [ ] Every asset self-hosted. **No CDN anywhere** — fonts, the MapLibre RTL plugin, tiles, figures
- [ ] Offline snapshot covers all eight storyboard scenes
- [ ] Service worker or bundled cache — decide in Phase 5
- [ ] Connection state is visible, and degradation is explicit rather than silent

## Deterministic demo mode

- [ ] Fixed snapshot, seeded scenario parameters, byte-identical every run
- [ ] Reachable without network, and without the API
- [ ] Rehearsed on the actual demo machine, not just locally

## Verification

- [ ] `docker compose up`, disconnect wifi, Playwright walks all eight scenes green
- [ ] Network panel shows zero external requests
- [ ] DevTools performance trace across a full scrub
