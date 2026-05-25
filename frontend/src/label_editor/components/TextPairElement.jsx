import React, { useRef } from 'react';
import { Group, Rect, Text, Line, Transformer } from 'react-konva';

export default function TextPairElement({ el, isSelected, onSelect, onChange, gridSize }) {
  const groupRef = useRef();
  const trRef = useRef();

  React.useEffect(() => {
    if (isSelected && trRef.current && groupRef.current) {
      trRef.current.nodes([groupRef.current]);
      trRef.current.getLayer().batchDraw();
    }
  }, [isSelected]);

  const snapToGrid = (val) => Math.round(val / gridSize) * gridSize;
  const labelW = Math.round(el.width * el.labelRatio);
  const valueW = el.width - labelW;

  return (
    <>
      <Group
        ref={groupRef}
        x={el.x} y={el.y}
        rotation={el.rotation}
        opacity={el.opacity}
        draggable={!el.locked}
        onClick={onSelect}
        onTap={onSelect}
        onDragEnd={(e) => {
          onChange({ x: snapToGrid(e.target.x()), y: snapToGrid(e.target.y()) });
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
            width: snapToGrid(Math.max(80, node.width() * scaleX)),
            height: snapToGrid(Math.max(20, node.height() * scaleY)),
            rotation: node.rotation(),
          });
        }}
      >
        {/* 전체 외곽 테두리 */}
        <Rect
          width={el.width} height={el.height}
          fill={el.backgroundColor}
          stroke={el.borderColor}
          strokeWidth={el.borderWidth}
          cornerRadius={el.cornerRadius}
        />
        {/* 왼쪽 라벨 배경 */}
        <Rect
          x={el.borderWidth / 2}
          y={el.borderWidth / 2}
          width={labelW - el.borderWidth / 2}
          height={el.height - el.borderWidth}
          fill={el.labelBackgroundColor}
          cornerRadius={[el.cornerRadius, 0, 0, el.cornerRadius]}
        />
        {/* 구분선 */}
        <Line
          points={[labelW, 0, labelW, el.height]}
          stroke={el.dividerColor}
          strokeWidth={el.dividerWidth}
        />
        {/* 왼쪽 텍스트 (필드명) */}
        <Text
          x={el.padding}
          y={el.padding}
          width={labelW - el.padding * 2}
          height={el.height - el.padding * 2}
          text={el.labelText}
          fontSize={el.fontSize}
          fontFamily={el.fontFamily}
          fontStyle={el.fontStyle}
          fill={el.textColor}
          align="center"
          verticalAlign="middle"
          lineHeight={el.lineHeight}
          wrap="none"
          ellipsis
        />
        {/* 오른쪽 텍스트 (값) */}
        <Text
          x={labelW + el.padding}
          y={el.padding}
          width={valueW - el.padding * 2}
          height={el.height - el.padding * 2}
          text={el.valueText}
          fontSize={el.fontSize}
          fontFamily={el.fontFamily}
          fontStyle="normal"
          fill={el.textColor}
          align="left"
          verticalAlign="middle"
          lineHeight={el.lineHeight}
          wrap="word"
        />
      </Group>
      {isSelected && (
        <Transformer
          ref={trRef}
          rotateEnabled={true}
          enabledAnchors={['top-left','top-center','top-right','middle-left','middle-right','bottom-left','bottom-center','bottom-right']}
          boundBoxFunc={(oldBox, newBox) =>
            newBox.width < 80 || newBox.height < 20 ? oldBox : newBox
          }
        />
      )}
    </>
  );
}
