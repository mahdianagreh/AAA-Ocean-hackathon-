Screenshots here show the real, live-current state: the detector is running and
finding nothing (`forecast.anomalyQuiet` state) — a genuine positive result, not a
placeholder. Deliberately not staged/faked into a false "detected" state for a
better-looking screenshot.

The "detected" visual path (`forecast.anomalyDetected`, the risk-high bordered
banner + sparkline with marked points) is exercised by
`frontend/src/components/AnomalyBanner.tsx`'s own logic, and the underlying
data path was already verified against a real anomalous value (the Oct 2016
event's actual rain reading) in `tasks/phase6/evidence/b6/` — see
`anomaly_detector_real_and_normal.txt`. That data has not recurred in a live
GEFS pull since, so this phase's screenshot honestly reflects "quiet," not
"broken."
