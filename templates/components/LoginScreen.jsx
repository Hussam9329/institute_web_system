import React, { useState } from 'react';

export default function LoginScreen({ onLogin }) {
  const [code, setCode] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (onLogin(code)) {
      setError('');
    } else {
      setError('رمز غير صحيح');
      setCode('');
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
      fontFamily: 'inherit',
      direction: 'rtl'
    }}>
      <div style={{
        background: 'rgba(255,255,255,0.05)',
        backdropFilter: 'blur(20px)',
        borderRadius: '20px',
        padding: '40px',
        width: '100%',
        maxWidth: '380px',
        textAlign: 'center',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
      }}>
        <div style={{
          width: '70px',
          height: '70px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, #e94560, #0f3460)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto 24px',
          fontSize: '28px'
        }}>🔒</div>
        <h2 style={{ color: '#fff', margin: '0 0 8px', fontSize: '22px' }}>نظام إدارة المعهد</h2>
        <p style={{ color: 'rgba(255,255,255,0.5)', margin: '0 0 30px', fontSize: '14px' }}>أدخل رمز الدخول</p>
        <form onSubmit={handleSubmit}>
          <input
            type="password"
            value={code}
            onChange={(e) => { setCode(e.target.value); setError(''); }}
            placeholder="الرمز"
            maxLength={10}
            autoFocus
            style={{
              width: '100%',
              padding: '14px 18px',
              borderRadius: '12px',
              border: '1px solid rgba(255,255,255,0.15)',
              background: 'rgba(255,255,255,0.08)',
              color: '#fff',
              fontSize: '18px',
              textAlign: 'center',
              letterSpacing: '8px',
              outline: 'none',
              boxSizing: 'border-box',
              marginBottom: '16px'
            }}
          />
          {error && <p style={{ color: '#e94560', fontSize: '13px', margin: '0 0 12px' }}>{error}</p>}
          <button
            type="submit"
            style={{
              width: '100%',
              padding: '14px',
              borderRadius: '12px',
              border: 'none',
              background: 'linear-gradient(135deg, #e94560, #c23152)',
              color: '#fff',
              fontSize: '16px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'all 0.3s'
            }}
          >دخول</button>
        </form>
      </div>
    </div>
  );
}
