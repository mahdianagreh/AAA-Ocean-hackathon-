import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './styles/index.css';
import './i18n';
// Imported for its side effects, at boot, before any map can be constructed:
// setWorkerUrl and setRTLTextPlugin both have to run exactly once and eagerly.
// See src/map/rtl.ts — this import order is the fix, not an accident.
import './map/rtl';
import { App } from './App';
import { AuthProvider } from './app/AuthContext';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <App />
    </AuthProvider>
  </StrictMode>,
);
