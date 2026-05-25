import React, { useRef } from 'react';
import { Group, Rect, Text, Transformer } from 'react-konva';

export default function TextBoxElement({ el, isSelected, onSelect, onChange, gridSize }) {
  const groupRef = useRef();
  const trRef = useRef();

  React.useEffect(() => {
    if (isSelected && trRef.current && groupRef.current) {
      trRef.current.nodes([groupRef.current]);
      trRef.current.getLayer().batchDraw();
    }
  }, [isSelected]);

  const snapToGrid = (val) => Math.round(val / gridSize) * gridSize;

  return (
    <>
      <Group
        ref={groupRef}
        x={el.x} y={el.y}
        width={el.width} height={el.height}
        rotation={el.rotation}
        opacity={el.opacity}
        draggable={!el.locked}
        onClick={onSelect}
        onTap={onSelect}
        onDragEnd={(e) => {
          onChange({
            x: snapToGrid(e.target.x()),
            y: snapToGrid(e.target.y()),
          });
        }}
        onTransformEnd={() => {
          const node = groupRef.current;
          const scaleX = node.scaleX();
          const scaleY = node.scaleY();
          node.scaleX(1);
          node.scaleY(1);
          onChange({
            x: snapToGrid(node.x()),
            y: snapToGrid(node.y()),
            width: snapToGrid(Math.max(40, node.width() * scaleX)),
            height: snapToGrid(Math.max(20, node.height() * scaleY)),
            rotation: node.rotation(),
          });
        }}
      >
        <Rect
          width={el.width} height={el.height}
          fill={el.backgroundColor}
          stroke={el.borderColor}
          strokeWidth={el.borderWidth}
          cornerRadius={el.cornerRadius}
          dash={el.borderStyle === 'dashed' ? [6, 3] : el.borderStyle === 'dotted' ? [2, 3] : []}
        />
        <Text
          x={el.padding} y={el.padding}
          width={el.width - el.padding * 2}
          height={el.height - el.padding * 2}
          text={el.text}
          fontSize={el.fontSize}
          fontFamily={el.fontFamily}
          fontStyle={el.fontStyle}
          fill={el.textColor}
          align={el.textAlign}
          lineHeight={el.lineHeight}
          letterSpacing={el.letterSpacing}
          wrap="word"
        />
      </Group>
      {isSelected && (
        <Transformer
          ref={trRef}
          rotateEnabled={true}
          enabledAnchors={['top-left','top-center','top-right','middle-left','middle-right','bottom-left','bottom-center','bottom-right']}
          boundBoxFunc={(oldBox, newBox) =>
            newBox.width < 40 || newBox.height < 20 ? oldBox : newBox
          }
        />
      )}
    </>
  );
}
