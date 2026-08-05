-- Corrects a Phase 2 transcription error. data-model.md §4.7 originally specified
-- risk_level CHECK (risk_level IN ('low','moderate','high','severe')), but the
-- exposure engine (backend/src/exposure/engine.py::RISK_BANDS, matching concept
-- doc §14.5) actually produces minimal/low/moderate/high/critical. Any real
-- 'minimal' or 'critical' result would have violated the old constraint.

ALTER TABLE reef_exposures DROP CONSTRAINT IF EXISTS reef_exposures_risk_level_check;
ALTER TABLE reef_exposures ADD CONSTRAINT reef_exposures_risk_level_check
    CHECK (risk_level IN ('minimal','low','moderate','high','critical'));
