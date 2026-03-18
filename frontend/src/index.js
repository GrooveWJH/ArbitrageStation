import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// Suppress chrome-extension errors from being shown in the React error overlay
const _origOnError = window.onerror;
window.onerror = (msg, src, ...rest) => {
  if (typeof src === 'string' && src.startsWith('chrome-extension://')) return true;
  return _origOnError ? _origOnError(msg, src, ...rest) : false;
};
const _origOnUnhandled = window.onunhandledrejection;
window.addEventListener('unhandledrejection', (e) => {
  const stack = e?.reason?.stack || '';
  if (stack.includes('chrome-extension://')) e.stopImmediatePropagation();
}, true);

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
