import { Checkbox } from 'radix-ui';
import { useTranslation } from 'react-i18next';
import type { LayerKey } from '../app/uiStore';

/** Layer toggles, grouped by family — 04-component-inventory.md.
 *
 *  Radix Checkbox rather than a styled div: it supplies the hidden native input,
 *  the label association, Space-to-toggle, and correct `aria-checked` including the
 *  indeterminate case. Those are exactly the things a hand-rolled toggle silently
 *  omits while looking finished.
 */
const FAMILIES: Array<{ key: string; layers: LayerKey[] }> = [
  { key: 'base', layers: ['isobaths', 'labels', 'coverage'] },
  { key: 'land', layers: ['catchments', 'rainfall', 'outlets'] },
  { key: 'marine', layers: ['plume', 'reef', 'mooring'] },
  { key: 'honesty', layers: ['modelGrid'] },
];

export function LayerToggle({
  layers,
  onToggle,
}: {
  layers: Record<LayerKey, boolean>;
  onToggle: (k: LayerKey) => void;
}) {
  const { t } = useTranslation();

  return (
    <section className="flex flex-col gap-2" data-layer-toggles="true">
      <h3 className="text-xs font-semibold text-ink-2">{t('layers.title')}</h3>

      {FAMILIES.map((f) => (
        <div key={f.key} className="flex flex-col gap-1">
          <h4 className="text-2xs text-ink-3">{t(`layers.family.${f.key}`)}</h4>
          {f.layers.map((k) => (
            <label
              key={k}
              className="flex items-center gap-2 text-xs"
              // 09: hit areas >= 24px. The visible box is 12px, so the label row
              // carries the target rather than the box being grown.
              style={{ minBlockSize: 24 }}
            >
              <Checkbox.Root
                checked={layers[k]}
                onCheckedChange={() => onToggle(k)}
                data-layer={k}
                className="flex h-3 w-3 shrink-0 items-center justify-center border border-hairline-2 bg-surface data-[state=checked]:border-accent"
              >
                <Checkbox.Indicator className="block h-1.5 w-1.5 bg-accent" />
              </Checkbox.Root>
              <span className="text-ink-2">{t(`layers.${k}`)}</span>
            </label>
          ))}
        </div>
      ))}

      {/* The model grid is the honesty device, so it says what it is for rather
          than sitting in the list as one more layer. */}
      <p className="text-2xs text-ink-3">{t('layers.modelGridNote')}</p>
    </section>
  );
}
