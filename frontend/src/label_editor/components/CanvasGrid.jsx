import React from 'react';
import { Line } from 'react-konva';

export default function CanvasGrid({ width, height, gridSize }) {
  const lines = [];

  for (let x = 0; x <= width; x += gridSize) {
    lines.push(
      <Line key={`v${x}`} points={[x, 0, x, height]}
        stroke="#e0e0e0" strokeWidth={x % (gridSize * 5) === 0 ? 0.8 : 0.4} />
    );
  }
  for (let y = 0; y <= height; y += gridSize) {
    lines.push(
      <Line key={`h${y}`} points={[0, y, width, y]}
        stroke="#e0e0e0" strokeWidth={y % (gridSize * 5) === 0 ? 0.8 : 0.4} />
    );
  }

  return <>{lines}</>;
}
