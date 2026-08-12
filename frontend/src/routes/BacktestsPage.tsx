import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { PageShell } from '../shell/PageShell';
import { Section } from '../shell/PageShell';
import { runBacktest, fetchEvents, type EventRow, type BacktestResult } from '../api/live';

export function BacktestsPage() {
  const { t } = useTranslation('pages');
  const [eventId, setEventId] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [events, setEvents] = useState<EventRow[] | null>(null);

  useEffect(() => {
    let mounted = true;
    void fetchEvents().then((rows) => { if (mounted) setEvents(rows ?? null); });
    return () => { mounted = false; };
  }, []);

  const handleRun = async () => {
    if (!eventId) return;
    setRunning(true);
    setError(null);
    setResult(null);

    try {
      const res = await runBacktest({ event_id: eventId });
      if (res) {
        setResult(res);
      } else {
        setError(t('backtest.error', { defaultValue: 'Failed to run backtest.' }));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <PageShell title={t('backtests.title', { defaultValue: 'Exposure Backtesting' })}>
      <Section label={t('backtests.new', { defaultValue: 'Run New Backtest' })}>
        <div className="flex flex-col gap-4 max-w-xl">
          <p className="text-sm text-ink-2 leading-relaxed">
            {t('backtests.description', { defaultValue: 'Run historical event data through the current exposure model to evaluate predictability and baseline drift.' })}
          </p>

          <div className="flex items-center gap-3">
            <select
              value={eventId}
              onChange={(e) => setEventId(e.target.value)}
              className="flex-1 rounded-md border border-hairline-2 bg-surface p-2 text-sm text-ink focus:border-accent focus:outline-none"
            >
              <option value="">{t('backtests.selectEvent', { defaultValue: 'Select historical event...' })}</option>
              {events?.map((e: any) => (
                <option key={e.id} value={e.id}>
                  {e.id} — {e.storm_name ?? 'Unnamed'}
                </option>
              ))}
            </select>

            <button
              onClick={handleRun}
              disabled={!eventId || running}
              className="premium-button px-6 py-2 text-sm disabled:opacity-50 disabled:hover:scale-100"
            >
              {running ? t('backtests.running', { defaultValue: 'Running...' }) : t('backtests.run', { defaultValue: 'Run' })}
            </button>
          </div>

          {error && (
            <div className="glass-panel border-red-500/30 bg-red-500/10 p-4">
              <p className="m-0 text-sm text-red-400">{error}</p>
            </div>
          )}

          {result && (
            <div className="glass-panel flex flex-col gap-4 p-5 mt-4 animate-content-show">
              <div className="flex justify-between items-start">
                <h3 className="m-0 text-lg font-bold premium-gradient-text">
                  {t('backtests.resultTitle', { defaultValue: 'Backtest Result' })}
                </h3>
                <span className="rounded-full bg-accent/20 px-3 py-1 text-xs font-bold text-accent">
                  {result.status}
                </span>
              </div>
              
              <div className="flex flex-col gap-2">
                <p className="m-0 text-sm">
                  <strong>Run ID:</strong> <span className="font-mono text-xs">{result.run_id}</span>
                </p>
                {result.note && (
                  <p className="m-0 text-sm text-ink-2 italic">{result.note}</p>
                )}
              </div>

              {result.metrics && (
                <div className="mt-2 grid grid-cols-2 gap-4">
                  {Object.entries(result.metrics).map(([key, val]: [string, any]) => (
                    <div key={key} className="flex flex-col gap-1 rule p-3 rounded-md bg-surface">
                      <span className="text-2xs text-ink-3 uppercase tracking-wider">{key}</span>
                      <span className="text-xl font-bold num">{val.toFixed(2)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Section>
    </PageShell>
  );
}
