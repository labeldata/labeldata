import React from 'react';
import { formatUnit } from '../utils/units';

const KO_FONTS = ['Noto Sans KR','나눔고딕','나눔명조','나눔바른고딕','프리텐다드','맑은 고딕','돋움','굴림','고딕A1','검은고딕'];
const EN_FONTS = ['Arial','Helvetica','Times New Roman','Georgia','Courier New','Roboto','Open Sans','Lato','Montserrat','Playfair Display'];
const ALL_FONTS = [...KO_FONTS, ...EN_FONTS];

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ fontSize: 11, color: '#888', marginBottom: 2 }}>{label}</div>
      {children}
    </div>
  );
}

function Input({ type = 'text', value, onChange, ...rest }) {
  return (
    <input
      type={type} value={value}
      onChange={(e) => onChange(type === 'number' ? Number(e.target.value) : e.target.value)}
      style={{ width: '100%', padding: '3px 6px', fontSize: 13, border: '1px solid #ddd', borderRadius: 4 }}
      {...rest}
    />
  );
}

function Select({ value, onChange, options }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      style={{ width: '100%', padding: '3px 6px', fontSize: 13, border: '1px solid #ddd', borderRadius: 4 }}>
      {options.map(o => <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>)}
    </select>
  );
}

export default function PropertiesPanel({ element, onChange }) {
  if (!element) {
    return (
      <div style={{ padding: 16, color: '#999', fontSize: 13 }}>
        개체를 선택하면 속성이 표시됩니다.
      </div>
    );
  }

  const set = (key, val) => onChange({ ...element, [key]: val });

  return (
    <div style={{ padding: 12, fontSize: 13, overflowY: 'auto', height: '100%' }}>
      <div style={{ fontWeight: 600, marginBottom: 12, fontSize: 14 }}>속성</div>

      <Field label="이름">
        <Input value={element.name} onChange={(v) => set('name', v)} />
      </Field>

      <Field label="위치">
        <div style={{ display: 'flex', gap: 4 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#aaa' }}>X {formatUnit(element.x)}</div>
            <Input type="number" value={element.x} onChange={(v) => set('x', v)} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#aaa' }}>Y {formatUnit(element.y)}</div>
            <Input type="number" value={element.y} onChange={(v) => set('y', v)} />
          </div>
        </div>
      </Field>

      <Field label="크기">
        <div style={{ display: 'flex', gap: 4 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#aaa' }}>W {formatUnit(element.width)}</div>
            <Input type="number" value={element.width} min={20} onChange={(v) => set('width', v)} />
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 10, color: '#aaa' }}>H {formatUnit(element.height)}</div>
            <Input type="number" value={element.height} min={20} onChange={(v) => set('height', v)} />
          </div>
        </div>
      </Field>

      <Field label="회전 (°)">
        <Input type="number" value={element.rotation} onChange={(v) => set('rotation', v)} />
      </Field>

      <Field label="투명도">
        <input type="range" min={0} max={1} step={0.05} value={element.opacity}
          onChange={(e) => set('opacity', Number(e.target.value))}
          style={{ width: '100%' }} />
        <div style={{ fontSize: 11, color: '#888' }}>{Math.round(element.opacity * 100)}%</div>
      </Field>

      <hr style={{ margin: '8px 0', borderColor: '#eee' }} />

      <Field label="배경색">
        <input type="color" value={element.backgroundColor || '#ffffff'}
          onChange={(e) => set('backgroundColor', e.target.value)}
          style={{ width: '100%', height: 32, padding: 2, border: '1px solid #ddd', borderRadius: 4 }} />
      </Field>

      <Field label="테두리 색">
        <input type="color" value={element.borderColor || '#000000'}
          onChange={(e) => set('borderColor', e.target.value)}
          style={{ width: '100%', height: 32, padding: 2, border: '1px solid #ddd', borderRadius: 4 }} />
      </Field>

      <Field label="테두리 두께">
        <Input type="number" value={element.borderWidth} min={0} onChange={(v) => set('borderWidth', v)} />
      </Field>

      <Field label="테두리 스타일">
        <Select value={element.borderStyle} onChange={(v) => set('borderStyle', v)}
          options={[{value:'solid',label:'실선'},{value:'dashed',label:'점선'},{value:'dotted',label:'점점선'}]} />
      </Field>

      <Field label="모서리 둥글기">
        <Input type="number" value={element.cornerRadius} min={0} onChange={(v) => set('cornerRadius', v)} />
      </Field>

      {(element.type === 'text_box' || element.type === 'text_pair') && (
        <>
          <hr style={{ margin: '8px 0', borderColor: '#eee' }} />

          {element.type === 'text_box' && (
            <Field label="텍스트">
              <textarea value={element.text}
                onChange={(e) => set('text', e.target.value)}
                style={{ width: '100%', minHeight: 60, padding: '3px 6px', fontSize: 13,
                  border: '1px solid #ddd', borderRadius: 4, resize: 'vertical' }} />
            </Field>
          )}

          {element.type === 'text_pair' && (
            <>
              <Field label="필드명 (왼쪽)">
                <Input value={element.labelText} onChange={(v) => set('labelText', v)} />
              </Field>
              <Field label="값 (오른쪽)">
                <Input value={element.valueText} onChange={(v) => set('valueText', v)} />
              </Field>
              <Field label="필드명 너비 비율">
                <input type="range" min={0.1} max={0.7} step={0.05} value={element.labelRatio}
                  onChange={(e) => set('labelRatio', Number(e.target.value))}
                  style={{ width: '100%' }} />
                <div style={{ fontSize: 11, color: '#888' }}>{Math.round(element.labelRatio * 100)}%</div>
              </Field>
              <Field label="필드명 배경색">
                <input type="color" value={element.labelBackgroundColor}
                  onChange={(e) => set('labelBackgroundColor', e.target.value)}
                  style={{ width: '100%', height: 32, padding: 2, border: '1px solid #ddd', borderRadius: 4 }} />
              </Field>
              <Field label="구분선 색">
                <input type="color" value={element.dividerColor}
                  onChange={(e) => set('dividerColor', e.target.value)}
                  style={{ width: '100%', height: 32, padding: 2, border: '1px solid #ddd', borderRadius: 4 }} />
              </Field>
            </>
          )}

          <Field label="폰트">
            <Select value={element.fontFamily} onChange={(v) => set('fontFamily', v)}
              options={ALL_FONTS} />
          </Field>

          <Field label="글자 크기 (px)">
            <Input type="number" value={element.fontSize} min={6} onChange={(v) => set('fontSize', v)} />
          </Field>

          <Field label="볼드">
            <button
              onClick={() => {
                const isBold = element.fontStyle.includes('bold');
                const isItalic = element.fontStyle.includes('italic');
                const next = isBold
                  ? (isItalic ? 'italic' : 'normal')
                  : (isItalic ? 'bold italic' : 'bold');
                set('fontStyle', next);
              }}
              style={{
                padding: '4px 16px', fontSize: 13, fontWeight: 'bold',
                border: '1px solid #ddd', borderRadius: 4, cursor: 'pointer',
                background: element.fontStyle.includes('bold') ? '#1976d2' : '#fff',
                color: element.fontStyle.includes('bold') ? '#fff' : '#333',
              }}>
              B
            </button>
          </Field>

          <Field label="글자 색">
            <input type="color" value={element.textColor}
              onChange={(e) => set('textColor', e.target.value)}
              style={{ width: '100%', height: 32, padding: 2, border: '1px solid #ddd', borderRadius: 4 }} />
          </Field>

          {element.type === 'text_box' && (
            <Field label="정렬">
              <Select value={element.textAlign} onChange={(v) => set('textAlign', v)}
                options={[{value:'left',label:'왼쪽'},{value:'center',label:'가운데'},{value:'right',label:'오른쪽'}]} />
            </Field>
          )}

          <Field label="기울임">
            <button
              onClick={() => {
                const isBold = element.fontStyle.includes('bold');
                const isItalic = element.fontStyle.includes('italic');
                const next = isItalic
                  ? (isBold ? 'bold' : 'normal')
                  : (isBold ? 'bold italic' : 'italic');
                set('fontStyle', next);
              }}
              style={{
                padding: '4px 16px', fontSize: 13, fontStyle: 'italic',
                border: '1px solid #ddd', borderRadius: 4, cursor: 'pointer',
                background: element.fontStyle.includes('italic') ? '#1976d2' : '#fff',
                color: element.fontStyle.includes('italic') ? '#fff' : '#333',
              }}>
              I
            </button>
          </Field>

          <Field label="줄 간격">
            <Input type="number" value={element.lineHeight} min={0.8} step={0.1} onChange={(v) => set('lineHeight', v)} />
          </Field>

          <Field label="자간 (px)">
            <Input type="number" value={element.letterSpacing} onChange={(v) => set('letterSpacing', v)} />
          </Field>

          <Field label="내부 여백 (px)">
            <Input type="number" value={element.padding} min={0} onChange={(v) => set('padding', v)} />
          </Field>
        </>
      )}

      <hr style={{ margin: '8px 0', borderColor: '#eee' }} />

      <Field label="위치 잠금">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input type="checkbox" checked={element.locked} onChange={(e) => set('locked', e.target.checked)} />
          잠금
        </label>
      </Field>
    </div>
  );
}
