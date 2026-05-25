import React, { useRef } from 'react';

export default function Toolbar(props) {
  const {
    onAddText, onAddPair, onAddImage, onDelete, onUndo, onRedo,
    canUndo, canRedo, hasSelection, onSave, isSaving,
    onExportImage, onExportPdf,
    canvasWidth, canvasHeight, gridSize, backgroundColor,
    onCanvasChange, labelId,
  } = props;
  const fileInputRef = useRef();

  const handleImageFile = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('image', file);
    formData.append('csrfmiddlewaretoken', getCookie('csrftoken'));
    fetch(`/api/label-editor/${labelId}/images/upload/`, { method: 'POST', body: formData })
      .then(r => r.json())
      .then(res => {
        if (res.success) onAddImage(res.data.url, res.data.filename);
        else alert('이미지 업로드 실패: ' + res.error);
      });
    e.target.value = '';
  };

  const btn = (label, onClick, disabled = false, title = '') => (
    <button onClick={onClick} disabled={disabled} title={title}
      style={{
        padding: '4px 10px', fontSize: 13, border: '1px solid #ddd',
        borderRadius: 4, background: disabled ? '#f5f5f5' : '#fff',
        cursor: disabled ? 'not-allowed' : 'pointer', color: disabled ? '#bbb' : '#333',
      }}>
      {label}
    </button>
  );

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
      borderBottom: '1px solid #e0e0e0', background: '#fafafa', flexWrap: 'wrap',
    }}>
      {btn('T 텍스트 추가', onAddText)}
      {btn('⊞ 라벨 쌍 추가', onAddPair)}
      <button onClick={() => fileInputRef.current.click()}
        style={{ padding: '4px 10px', fontSize: 13, border: '1px solid #ddd', borderRadius: 4, background: '#fff', cursor: 'pointer' }}>
        🖼 이미지 추가
      </button>
      <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleImageFile} />

      <div style={{ width: 1, height: 20, background: '#ddd', margin: '0 4px' }} />

      {btn('↩ 실행취소', onUndo, !canUndo, 'Ctrl+Z')}
      {btn('↪ 다시실행', onRedo, !canRedo, 'Ctrl+Y')}

      <div style={{ width: 1, height: 20, background: '#ddd', margin: '0 4px' }} />

      {btn('🗑 삭제', onDelete, !hasSelection)}

      <div style={{ flex: 1 }} />

      <label style={{ fontSize: 12, color: '#666' }}>
        W <input type="number" value={canvasWidth} min={100}
          onChange={e => onCanvasChange('canvas_width', Number(e.target.value))}
          style={{ width: 60, padding: '2px 4px', fontSize: 12, border: '1px solid #ddd', borderRadius: 3 }} />px
      </label>
      <label style={{ fontSize: 12, color: '#666' }}>
        H <input type="number" value={canvasHeight} min={100}
          onChange={e => onCanvasChange('canvas_height', Number(e.target.value))}
          style={{ width: 60, padding: '2px 4px', fontSize: 12, border: '1px solid #ddd', borderRadius: 3 }} />px
      </label>
      <label style={{ fontSize: 12, color: '#666' }}>
        격자 <input type="number" value={gridSize} min={2} max={50}
          onChange={e => onCanvasChange('grid_size', Number(e.target.value))}
          style={{ width: 44, padding: '2px 4px', fontSize: 12, border: '1px solid #ddd', borderRadius: 3 }} />px
      </label>
      <label style={{ fontSize: 12, color: '#666' }} title="배경색">
        배경 <input type="color" value={backgroundColor}
          onChange={e => onCanvasChange('background_color', e.target.value)}
          style={{ width: 32, height: 24, padding: 1, border: '1px solid #ddd', borderRadius: 3, verticalAlign: 'middle' }} />
      </label>

      <div style={{ width: 1, height: 20, background: '#ddd', margin: '0 4px' }} />

      {btn('이미지 내보내기', onExportImage)}
      {btn('PDF 내보내기', onExportPdf)}
      <button onClick={onSave} disabled={isSaving}
        style={{
          padding: '4px 14px', fontSize: 13, border: 'none', borderRadius: 4,
          background: isSaving ? '#90caf9' : '#1976d2', color: '#fff',
          cursor: isSaving ? 'not-allowed' : 'pointer', fontWeight: 600,
        }}>
        {isSaving ? '저장 중...' : '💾 저장'}
      </button>
    </div>
  );
}

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}
