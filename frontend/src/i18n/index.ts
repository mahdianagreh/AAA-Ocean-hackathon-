import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en/common.json';
import ar from './locales/ar/common.json';
import enPages from './locales/en/pages.json';
import arPages from './locales/ar/pages.json';
import enNav from './locales/en/nav.json';
import arNav from './locales/ar/nav.json';
import enTools from './locales/en/tools.json';
import arTools from './locales/ar/tools.json';

/** Resources are bundled, not fetched.
 *
 *  i18next-http-backend would be one more network request the wifi-off
 *  requirement cannot afford, and two JSON files are a few KB. Bundling also
 *  means a missing key is a type error rather than a runtime blank.
 *
 *  No key holds a sentence assembled from fragments — 06 §6. Arabic word order
 *  is not English word order, so composition happens inside the translation
 *  string with interpolation, and the translator controls the order. That is why
 *  the API is asked for SHAP drivers and confidence as structured components
 *  rather than pre-rendered sentences: a formatted English string cannot be
 *  translated at render time.
 */
void i18n.use(initReactI18next).init({
  resources: {
    en: { common: en, pages: enPages, tools: enTools, nav: enNav },
    ar: { common: ar, pages: arPages, tools: arTools, nav: arNav },
  },
  // `common` stays the default namespace so no existing t('rail.x') call
  // changes. The route-level pages added by the rebrand live in `pages`, split
  // out purely so several people can add copy at once without every edit
  // landing in the same two files and colliding. Reach it with
  // useTranslation('pages') or t('pages:key').
  ns: ['common', 'pages', 'tools', 'nav'],
  lng: 'en',
  fallbackLng: 'en',
  defaultNS: 'common',
  interpolation: {
    // React already escapes. Doing it twice mangles Arabic punctuation.
    escapeValue: false,
  },
});

export default i18n;
