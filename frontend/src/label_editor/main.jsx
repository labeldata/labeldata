import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';

const container = document.getElementById('label-editor-root');
if (container) {
  const labelId = container.dataset.labelId;
  createRoot(container).render(<App labelId={labelId} />);
}
