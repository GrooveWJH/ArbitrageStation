import React from 'react';

const overlayStyle = {
  position: 'absolute',
  inset: 0,
  zIndex: 10,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  pointerEvents: 'all',
  cursor: 'not-allowed',
  borderRadius: 'inherit',
  border: '2px dashed rgba(255, 180, 50, 0.7)',
  boxSizing: 'border-box',
  background: `
    repeating-linear-gradient(
      -45deg,
      rgba(30, 30, 30, 0.55),
      rgba(30, 30, 30, 0.55) 6px,
      rgba(50, 50, 50, 0.35) 6px,
      rgba(50, 50, 50, 0.35) 12px
    )
  `,
};

const labelStyle = {
  padding: '4px 14px',
  borderRadius: 6,
  background: 'rgba(0, 0, 0, 0.72)',
  color: '#d4d4d4',
  fontSize: 12,
  fontWeight: 600,
  letterSpacing: 1,
  userSelect: 'none',
  whiteSpace: 'nowrap',
};

export default function DevOverlay({ children, label = '🚧 开发中', style }) {
  return (
    <div style={{ position: 'relative', ...style }}>
      {children}
      <div style={overlayStyle}>
        <span style={labelStyle}>{label}</span>
      </div>
    </div>
  );
}
