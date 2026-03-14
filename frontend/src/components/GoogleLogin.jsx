import React, { useEffect, useRef, useState } from 'react';
import { googleLogin } from '../services/api';

export default function GoogleLogin({ clientId, onSuccess }) {
  const btnRef = useRef(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!clientId) return;

    const initGoogle = () => {
      if (!window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({
        client_id: clientId,
        callback: async (response) => {
          setError('');
          try {
            const result = await googleLogin(response.credential);
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
          }
        },
      });
      if (btnRef.current) {
        window.google.accounts.id.renderButton(btnRef.current, {
          theme: 'outline',
          size: 'large',
          text: 'signin_with',
          shape: 'rectangular',
          width: 300,
        });
      }
    };

    // Google script might already be loaded
    if (window.google?.accounts?.id) {
      initGoogle();
    } else {
      // Load the script
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = initGoogle;
      document.head.appendChild(script);
    }
  }, [clientId, onSuccess]);

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: 'var(--bg)',
      gap: '24px',
    }}>
      <div style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '48px 40px',
        textAlign: 'center',
        maxWidth: '400px',
      }}>
        <h1 style={{ fontSize: '24px', fontWeight: 700, marginBottom: '8px', color: 'var(--text)' }}>
          Portfolio Dashboard
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '32px' }}>
          Sign in to continue
        </p>
        <div ref={btnRef} style={{ display: 'flex', justifyContent: 'center' }} />
        {error && (
          <p style={{ color: 'var(--red)', fontSize: '13px', marginTop: '16px' }}>{error}</p>
        )}
      </div>
    </div>
  );
}
