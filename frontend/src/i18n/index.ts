import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en/common.json';
import ar from './locales/ar/common.json';

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
    en: { common: en },
    ar: { common: ar },
  },
  lng: 'en',
  fallbackLng: 'en',
  defaultNS: 'common',
  interpolation: {
    // React already escapes. Doing it twice mangles Arabic punctuation.
    escapeValue: false,
  },
});

export default i18n;
