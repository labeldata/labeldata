import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Stage, Layer, Rect } from 'react-konva';
import jsPDF from 'jspdf';
import CanvasGrid from './components/CanvasGrid';
import TextBoxElement from './components/TextBoxElement';
import TextPairElement from './components/TextPairElement';
import ImageElement from './components/ImageElement';
import PropertiesPanel from './components/PropertiesPanel';
import Toolbar from './components/Toolbar';
import { useHistory } from './hooks/useHistory';
import { createTextBox, createTextPair, createImageBox } from './utils/elements';

const INITIAL_CANVAS = {
  canvas_width: 800,
  canvas_height: 600,
  grid_size: 10,
  background_color: '#ffffff',
  elements: [],
};

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

export default function App({ labelId }) {
  const [canvas, setCanvas] = useState(INITIAL_CANVAS);
  const { current: elements, push, undo, redo, canUndo, canRedo } = useHistory([]);
  const [selectedId, setSelectedId] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [clipboard, setClipboard] = useState(null);
  const stageRef = useRef();

  // 초기 데이터 로드
  useEffect(() => {
    fetch(`/api/label-editor/${labelId}/layout/`)
      .then(r => r.json())
      .then(res => {
        if (res.success) {
          const { elements: els, ...canvasData } = res.data;
          setCanvas(canvasData);
          push(els || []);
        }
      });
  }, [labelId]);

  // 키보드 단축키
  useEffect(() => {
    const handler = (e) => {
      const tag = e.target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'z') { e.preventDefault(); undo(); }
      if ((e.ctrlKey || e.metaKey) && (e.key === 'y' || (e.shiftKey && e.key === 'z'))) { e.preventDefault(); redo(); }
      if ((e.ctrlKey || e.metaKey) && e.key === 'c' && selectedId) {
        const el = elements.find(el => el.id === selectedId);
        if (el) setClipboard(el);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'v' && clipboard) {
        const newEl = { ...clipboard, id: `el_${Date.now()}`, x: clipboard.x + 20, y: clipboard.y + 20 };
        push([...elements, newEl]);
        setSelectedId(newEl.id);
      }
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (selectedId) { push(elements.filter(el => el.id !== selectedId)); setSelectedId(null); }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [selectedId, elements, clipboard, undo, redo]);

  const updateElement = useCallback((id, changes) => {
    push(elements.map(el => el.id === id ? { ...el, ...changes } : el));
  }, [elements, push]);

  const addText = () => {
    const el = createTextBox(80, 80);
    el.zIndex = elements.length;
    push([...elements, el]);
    setSelectedId(el.id);
  };

  const addPair = () => {
    const el = createTextPair(80, 80);
    el.zIndex = elements.length;
    push([...elements, el]);
    setSelectedId(el.id);
  };

  const addImage = (url, filename) => {
    const el = createImageBox(80, 80, url, filename);
    el.zIndex = elements.length;
    push([...elements, el]);
    setSelectedId(el.id);
  };

  const deleteSelected = () => {
    if (!selectedId) return;
    push(elements.filter(el => el.id !== selectedId));
    setSelectedId(null);
  };

  const handleCanvasChange = (key, value) => {
    setCanvas(prev => ({ ...prev, [key]: value }));
  };

  const save = async () => {
    setIsSaving(true);
    try {
      await fetch(`/api/label-editor/${labelId}/layout/save/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ ...canvas, elements }),
      });
    } finally {
      setIsSaving(false);
    }
  };

  const exportImage = () => {
    const uri = stageRef.current.toDataURL({ pixelRatio: 2 });
    const a = document.createElement('a');
    a.href = uri;
    a.download = `label_${labelId}.png`;
    a.click();
  };

  const exportPdf = () => {
    const uri = stageRef.current.toDataURL({ pixelRatio: 2 });
    const pdf = new jsPDF({
      orientation: canvas.canvas_width > canvas.canvas_height ? 'landscape' : 'portrait',
      unit: 'px',
      format: [canvas.canvas_width, canvas.canvas_height],
    });
    pdf.addImage(uri, 'PNG', 0, 0, canvas.canvas_width, canvas.canvas_height);
    pdf.save(`label_${labelId}.pdf`);
  };

  const selectedElement = elements.find(el => el.id === selectedId) || null;
  const sortedElements = [...elements].sort((a, b) => a.zIndex - b.zIndex);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', fontFamily: 'sans-serif' }}>
      <Toolbar
        onAddText={addText}
        onAddPair={addPair}
        onAddImage={addImage}
        onDelete={deleteSelected}
        onUndo={undo} onRedo={redo}
        canUndo={canUndo} canRedo={canRedo}
        hasSelection={!!selectedId}
        onSave={save} isSaving={isSaving}
        onExportImage={exportImage}
        onExportPdf={exportPdf}
        canvasWidth={canvas.canvas_width}
        canvasHeight={canvas.canvas_height}
        gridSize={canvas.grid_size}
        backgroundColor={canvas.background_color}
        onCanvasChange={handleCanvasChange}
        labelId={labelId}
      />

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* 캔버스 영역 */}
        <div style={{ flex: 1, overflow: 'auto', background: '#e8eaed', padding: 20 }}>
          <div style={{
            display: 'inline-block',
            boxShadow: '0 2px 12px rgba(0,0,0,0.15)',
            background: canvas.background_color,
          }}>
            <Stage
              ref={stageRef}
              width={canvas.canvas_width}
              height={canvas.canvas_height}
              onMouseDown={(e) => {
                if (e.target === e.target.getStage()) setSelectedId(null);
              }}
            >
              <Layer>
                <Rect
                  x={0} y={0}
                  width={canvas.canvas_width}
                  height={canvas.canvas_height}
                  fill={canvas.background_color}
                />
                <CanvasGrid
                  width={canvas.canvas_width}
                  height={canvas.canvas_height}
                  gridSize={canvas.grid_size}
                />
              </Layer>
              <Layer>
                {sortedElements.map(el => {
                  const props = {
                    key: el.id,
                    el,
                    isSelected: el.id === selectedId,
                    onSelect: () => setSelectedId(el.id),
                    onChange: (changes) => updateElement(el.id, changes),
                    gridSize: canvas.grid_size,
                  };
                  if (el.type === 'image') return <ImageElement {...props} />;
                  if (el.type === 'text_pair') return <TextPairElement {...props} />;
                  return <TextBoxElement {...props} />;
                })}
              </Layer>
            </Stage>
          </div>
        </div>

        {/* 속성 패널 */}
        <div style={{
          width: 240, borderLeft: '1px solid #e0e0e0',
          background: '#fff', overflowY: 'auto',
        }}>
          <PropertiesPanel
            element={selectedElement}
            onChange={(updated) => updateElement(updated.id, updated)}
          />
        </div>
      </div>
    </div>
  );
}
