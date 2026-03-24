import React, { useEffect, useRef, useState } from 'react';
import { googleLoginWithCode } from '../services/api';

export default function GoogleLogin({ clientId, onSuccess }) {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const clientRef = useRef(null);

  useEffect(() => {
    if (!clientId) return;

    const initGoogle = () => {
      if (!window.google?.accounts?.oauth2) return;
      clientRef.current = window.google.accounts.oauth2.initCodeClient({
        client_id: clientId,
        scope: 'openid email profile',
        ux_mode: 'popup',
        select_account: true,
        callback: async (response) => {
          if (response.error) {
            setError(response.error);
            return;
          }
          setError('');
          setLoading(true);
          try {
            const result = await googleLoginWithCode(response.code);
            // Clear stale persona if email changed
            const prevUser = JSON.parse(localStorage.getItem('authUser') || '{}');
            if (prevUser.email && prevUser.email !== result.email) {
              localStorage.removeItem('selectedUserId');
            }
            localStorage.setItem('sessionToken', result.session_token);
            localStorage.setItem('authUser', JSON.stringify({
              email: result.email,
              name: result.name,
              picture: result.picture,
            }));
            onSuccess(result);
          } catch (err) {
            const msg = err.response?.data?.detail || 'Login failed';
            setError(msg);
          } finally {
            setLoading(false);
          }
        },
      });
    };

    if (window.google?.accounts?.oauth2) {
      initGoogle();
    } else {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = initGoogle;
      document.head.appendChild(script);
    }
  }, [clientId, onSuccess]);

  const handleClick = () => {
    if (clientRef.current) {
      clientRef.current.requestCode();
    }
  };

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', minHeight: '100vh', background: 'var(--bg)', gap: '24px',
    }}>
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: '12px', padding: '48px 40px', textAlign: 'center', maxWidth: '400px',
      }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '8px', color: 'var(--text)' }}>
          Portfolio Dashboard
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '32px' }}>
          Sign in to continue
        </p>
        <button
          onClick={handleClick}
          disabled={loading}
          style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: '12px 24px', fontSize: '14px', fontWeight: 500,
            background: '#fff', color: '#3c4043', border: '1px solid #dadce0',
            borderRadius: '4px', cursor: loading ? 'wait' : 'pointer',
            margin: '0 auto', opacity: loading ? 0.7 : 1,
          }}
        >
          <svg width="18" height="18" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#34A853" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#FBBC05" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          {loading ? 'Signing in...' : 'Sign in with Google'}
        </button>
        {error && (
          <p style={{ color: 'var(--red)', fontSize: '13px', marginTop: '16px' }}>{error}</p>
        )}
      </div>
    </div>
  );
}
