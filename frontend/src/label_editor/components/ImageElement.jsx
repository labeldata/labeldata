import React, { useRef } from 'react';
import { Group, Image as KonvaImage, Rect, Transformer } from 'react-konva';
import useImage from 'use-image';

function ImageContent({ el }) {
  const [image] = useImage(el.imageUrl, 'anonymous');
  return (
    <KonvaImage
      image={image}
      width={el.width} height={el.height}
      cornerRadius={el.cornerRadius}
      opacity={el.opacity}
    />
  );
}

export default function ImageElement({ el, isSelected, onSelect, onChange, gridSize }) {
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
            width: snapToGrid(Math.max(20, node.width() * scaleX)),
            height: snapToGrid(Math.max(20, node.height() * scaleY)),
            rotation: node.rotation(),
          });
        }}
      >
        <ImageContent el={el} />
        {el.borderWidth > 0 && (
          <Rect
            width={el.width} height={el.height}
            stroke={el.borderColor} strokeWidth={el.borderWidth}
            cornerRadius={el.cornerRadius} fill="transparent"
          />
        )}
      </Group>
      {isSelected && (
        <Transformer
          ref={trRef}
          rotateEnabled={true}
          enabledAnchors={['top-left','top-center','top-right','middle-left','middle-right','bottom-left','bottom-center','bottom-right']}
          boundBoxFunc={(oldBox, newBox) =>
            newBox.width < 20 || newBox.height < 20 ? oldBox : newBox
          }
        />
      )}
    </>
  );
}
