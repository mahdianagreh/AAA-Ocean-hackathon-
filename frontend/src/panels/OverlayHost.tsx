import { useEffect, useRef } from 'react';
import { Dialog } from 'radix-ui';
import { useTranslation } from 'react-i18next';
import { useUi, type Overlay } from '../app/uiStore';
import { ValidationPanel } from './ValidationPanel';
import { ProvenancePanel } from './ProvenancePanel';
import { LimitationsPanel } from './LimitationsPanel';
import { Assistant } from './Assistant';
import { Journey3D } from '../journey/Journey3D';

/** 03 §1: overlays, not routes. The whole product is one screen, and pushing the
 *  limitations text to its own URL would mean leaving the map to read it.
 *
 *  Radix Dialog supplies the focus trap, focus return, Escape handling, scroll lock
 *  and aria-modal semantics. 09 requires a full keyboard path through all eight
 *  scenes; hand-rolling a modal is the fastest way to break that while it still
 *  looks correct.
 */
const PANELS: Record<Exclude<Overlay, null>, () => React.ReactNode> = {
  validation: () => <ValidationPanel />,
  provenance: () => <ProvenancePanel />,
  limitations: () => <LimitationsPanel />,
  assistant: () => <Assistant />,
  journey: () => <Journey3D />,
};

export function OverlayHost() {
  const { t } = useTranslation();
  const overlay = useUi((s) => s.overlay);
  const setOverlay = useUi((s) => s.setOverlay);

  /** Restore focus to whatever opened the panel.
   *
   *  Radix returns focus to its own Dialog.Trigger, and these panels are opened by
   *  buttons in the masthead with a store action instead — one Dialog.Root serving
   *  four overlays cannot have four triggers. So Radix has nothing to restore, and
   *  Escape left focus on the body: a keyboard user was dumped at the top of the
   *  document after every panel. The a11y test caught it.
   *
   *  Captured on open, restored in onCloseAutoFocus with the default prevented. */
  const opener = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (overlay) opener.current = document.activeElement as HTMLElement | null;
  }, [overlay]);

  return (
    <Dialog.Root open={Boolean(overlay)} onOpenChange={(o) => !o && setOverlay(null)}>
      <Dialog.Portal>
        {/* A premium glassmorphic blur background replacing the previous flat color. */}
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/30 backdrop-blur-md data-[state=open]:animate-overlay-show" />
        <Dialog.Content
          data-overlay={overlay ?? undefined}
          onCloseAutoFocus={(e) => {
            e.preventDefault();
            opener.current?.focus();
          }}
          className="fixed inset-3 z-50 flex flex-col overflow-hidden glass-card lg:inset-x-[12%] lg:inset-y-8 data-[state=open]:animate-content-show"
          aria-describedby={undefined}
        >
          <header className="flex items-center justify-between gap-3 border-b border-hairline-2 px-5 py-3">
            <Dialog.Title className="text-lg font-bold premium-gradient-text tracking-wide">
              {overlay ? t(`overlay.${overlay}`) : ''}
            </Dialog.Title>
            <Dialog.Close
              data-overlay-close="true"
              className="rounded-full bg-surface/50 px-4 py-1.5 text-xs font-semibold text-ink-2 border border-hairline-2 transition-all duration-300 hover:bg-surface hover:text-ink hover:scale-105 hover:neon-glow cursor-pointer"
            >
              {t('common.close')}
            </Dialog.Close>
          </header>
          {/* tabIndex + role: a scrollable region with no focusable content is
              unreachable by keyboard, which axe flags and 09's "full keyboard path"
              forbids. */}
          <div
            className="min-h-0 flex-1 overflow-y-auto p-4"
            tabIndex={0}
            role="region"
            aria-label={overlay ? t(`overlay.${overlay}`) : undefined}
          >
            {overlay ? PANELS[overlay]() : null}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
