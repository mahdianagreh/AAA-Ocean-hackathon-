import { useTranslation } from 'react-i18next';
import type { Mode } from '../app/uiStore';
import { Segmented } from './Segmented';

const MODES: Mode[] = ['historical', 'forecast', 'scenario'];

/** The three view modes, on the shared brand segmented control.
 *
 *  `data-mode` is a test contract — five specs click `[data-mode="scenario"]`
 *  and assert `data-state="on"`, which Radix sets. Both survive the restyle.
 *
 *  Unlike the time slider, this one *should* mirror in RTL: it is navigation,
 *  not a time axis, and 06 §3 lists navigation under "mirrors".
 */
export function ModeSwitch({
  value,
  onChange,
}: {
  value: Mode;
  onChange: (m: Mode) => void;
}) {
  const { t } = useTranslation();

  return (
    <Segmented
      value={value}
      onChange={onChange}
      label={t('mode.label')}
      options={MODES.map((m) => ({
        value: m,
        label: t(`mode.${m}`),
        data: { 'data-mode': m },
      }))}
    />
  );
}
