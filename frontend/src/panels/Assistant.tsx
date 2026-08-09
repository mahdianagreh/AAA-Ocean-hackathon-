import { useTranslation } from 'react-i18next';
import { useUi } from '../app/uiStore';
import { Link } from '../components/Link';

/** Repointed to the dedicated /assistant route in Phase 6.
 *
 *  The assistant is now a full page to support deep-linking to answers
 *  and sharing, rather than trapping the knowledge in an ephemeral overlay.
 */
export function Assistant() {
  const { t } = useTranslation();
  const setOverlay = useUi((s) => s.setOverlay);

  return (
    <div className="flex flex-col gap-4" data-panel="assistant">
      <p className="text-xs text-ink-2">
        The assistant has moved to its own page to support deep-linking and sharing.
      </p>
      <Link
        to="/assistant"
        onClick={() => setOverlay(null)}
        className="rule self-start bg-ink px-4 py-2 text-xs font-bold text-ink-inverse"
      >
        {t('assistant.title', { defaultValue: 'Open Assistant' })}
      </Link>
    </div>
  );
}
