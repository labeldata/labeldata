const PX_PER_MM = 3.7795275591;

export const pxToMm = (px) => (px / PX_PER_MM).toFixed(1);
export const pxToCm = (px) => (px / PX_PER_MM / 10).toFixed(2);
export const mmToPx = (mm) => Math.round(mm * PX_PER_MM);

export const formatUnit = (px) => `${px}px (${pxToMm(px)}mm)`;
