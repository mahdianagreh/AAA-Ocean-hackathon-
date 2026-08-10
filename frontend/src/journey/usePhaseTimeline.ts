import { useCallback, useEffect, useRef, useState } from 'react';
import { PHASE_DURATION_MS, PHASE_ORDER, PLUME_FRAME_MS, type JourneyPhase } from './constants';

/** The Play sequence's state machine: normal -> rain -> flood -> transport ->
 *  accumulation -> impact.
 *
 *  `transport` is not timer-advanced like the others — it steps one real
 *  plume timestep at a time (`frameIndex` 0..frameCount-1, `PLUME_FRAME_MS`
 *  apart) and only proceeds to `accumulation` once the real, final timestep
 *  has actually been shown. Every other phase runs for a fixed
 *  `PHASE_DURATION_MS`, chosen for legibility, not derived from any real
 *  duration (there is no real data on how long "heavy rain" or "flood"
 *  should be shown for) — stated here rather than left to look like a
 *  measurement.
 *
 *  One `requestAnimationFrame` loop drives the whole thing; `elapsedInPhase`
 *  is exposed (0-1 normalised) so layers can ease in/out rather than snap.
 */

export interface PhaseTimelineState {
  phase: JourneyPhase;
  phaseIndex: number;
  playing: boolean;
  /** 0-1 progress within the current phase (time-based, or frame-based during transport). */
  phaseProgress: number;
  frameIndex: number;
  play: () => void;
  pause: () => void;
  reset: () => void;
  /** Jump straight to a phase (manual exploration, not autoplay). Also seeks
   *  frameIndex sensibly for 'transport'/'accumulation'. */
  goToPhase: (phase: JourneyPhase) => void;
  /** Jump straight to one real plume timestep, always under 'transport'
   *  (the phase with a real reason to browse individual frames —
   *  'accumulation' is deliberately always the final one). Pauses autoplay,
   *  same as goToPhase. */
  goToFrame: (index: number) => void;
}

export function usePhaseTimeline(frameCount: number): PhaseTimelineState {
  const [phase, setPhase] = useState<JourneyPhase>('normal');
  const [playing, setPlaying] = useState(false);
  const [phaseProgress, setPhaseProgress] = useState(0);
  const [frameIndex, setFrameIndex] = useState(0);

  const rafRef = useRef<number | null>(null);
  const phaseStartRef = useRef<number>(0);
  const phaseRef = useRef<JourneyPhase>('normal');
  const frameIndexRef = useRef(0);

  const clearRaf = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const enterPhase = useCallback((next: JourneyPhase, now: number) => {
    phaseRef.current = next;
    phaseStartRef.current = now;
    setPhase(next);
    setPhaseProgress(0);
    if (next === 'normal' || next === 'transport') {
      frameIndexRef.current = 0;
      setFrameIndex(0);
    } else if (next === 'accumulation' || next === 'impact') {
      frameIndexRef.current = Math.max(0, frameCount - 1);
      setFrameIndex(frameIndexRef.current);
    }
  }, [frameCount]);

  const tick = useCallback((now: number) => {
    const current = phaseRef.current;
    const elapsed = now - phaseStartRef.current;

    if (current === 'transport') {
      const step = Math.min(Math.floor(elapsed / PLUME_FRAME_MS), Math.max(frameCount - 1, 0));
      if (step !== frameIndexRef.current) {
        frameIndexRef.current = step;
        setFrameIndex(step);
      }
      const totalMs = Math.max(frameCount, 1) * PLUME_FRAME_MS;
      setPhaseProgress(Math.min(elapsed / totalMs, 1));
      if (elapsed >= totalMs) {
        const idx = PHASE_ORDER.indexOf('transport');
        enterPhase(PHASE_ORDER[idx + 1], now);
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
    } else {
      const duration = PHASE_DURATION_MS[current];
      setPhaseProgress(duration > 0 ? Math.min(elapsed / duration, 1) : 1);
      // No `duration > 0` guard: `normal` has duration 0 by design (it is the
      // resting state before Play, not an animated one) and must advance on
      // the very first tick once playing, not stall forever waiting for a
      // strictly-positive elapsed time to exceed a zero target.
      if (elapsed >= duration) {
        const idx = PHASE_ORDER.indexOf(current);
        if (idx < PHASE_ORDER.length - 1) {
          enterPhase(PHASE_ORDER[idx + 1], now);
          rafRef.current = requestAnimationFrame(tick);
          return;
        }
        setPlaying(false);
        clearRaf();
        return;
      }
    }
    rafRef.current = requestAnimationFrame(tick);
  }, [clearRaf, enterPhase, frameCount]);

  useEffect(() => clearRaf, [clearRaf]);

  const play = useCallback(() => {
    setPlaying(true);
    const now = performance.now();
    // Uniform resume, no special-casing "fresh start" vs. "mid-sequence": the
    // tick loop's own zero-duration handling for 'normal' already advances
    // immediately once playing, so resuming from phaseProgress (0 on a fresh
    // 'normal', wherever it was left off otherwise) is correct for every
    // phase including the first one.
    const duration = phaseRef.current === 'transport'
      ? Math.max(frameCount, 1) * PLUME_FRAME_MS
      : PHASE_DURATION_MS[phaseRef.current];
    phaseStartRef.current = now - phaseProgress * duration;
    clearRaf();
    rafRef.current = requestAnimationFrame(tick);
  }, [clearRaf, frameCount, phaseProgress, tick]);

  const pause = useCallback(() => {
    setPlaying(false);
    clearRaf();
  }, [clearRaf]);

  const reset = useCallback(() => {
    setPlaying(false);
    clearRaf();
    enterPhase('normal', performance.now());
  }, [clearRaf, enterPhase]);

  const goToPhase = useCallback((target: JourneyPhase) => {
    setPlaying(false);
    clearRaf();
    enterPhase(target, performance.now());
    setPhaseProgress(1);
  }, [clearRaf, enterPhase]);

  const goToFrame = useCallback((index: number) => {
    setPlaying(false);
    clearRaf();
    const clamped = Math.max(0, Math.min(Math.max(frameCount - 1, 0), index));
    const now = performance.now();
    phaseRef.current = 'transport';
    setPhase('transport');
    frameIndexRef.current = clamped;
    setFrameIndex(clamped);
    // Keeps a subsequent Play resuming from here rather than snapping back
    // to frame 0 -- phaseProgress and phaseStartRef both reflect the frame
    // actually selected, same bookkeeping enterPhase does for a fresh entry.
    const totalMs = Math.max(frameCount, 1) * PLUME_FRAME_MS;
    const progress = totalMs > 0 ? (clamped * PLUME_FRAME_MS) / totalMs : 0;
    phaseStartRef.current = now - progress * totalMs;
    setPhaseProgress(progress);
  }, [clearRaf, frameCount]);

  return {
    phase,
    phaseIndex: PHASE_ORDER.indexOf(phase),
    playing,
    phaseProgress,
    frameIndex,
    play,
    pause,
    reset,
    goToPhase,
    goToFrame,
  };
}
