import { useState, useCallback } from 'react';

export function useHistory(initialState) {
  const [history, setHistory] = useState([initialState]);
  const [index, setIndex] = useState(0);

  const current = history[index];

  const push = useCallback((newState) => {
    setHistory((prev) => {
      const next = prev.slice(0, index + 1);
      next.push(newState);
      if (next.length > 50) next.shift();
      return next;
    });
    setIndex((prev) => Math.min(prev + 1, 49));
  }, [index]);

  const undo = useCallback(() => {
    setIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const redo = useCallback(() => {
    setIndex((prev) => Math.min(prev + 1, history.length - 1));
  }, [history.length]);

  const canUndo = index > 0;
  const canRedo = index < history.length - 1;

  return { current, push, undo, redo, canUndo, canRedo };
}
