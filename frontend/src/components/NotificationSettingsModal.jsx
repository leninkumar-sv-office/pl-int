import React, { useState, useEffect } from 'react';
import useEscapeKey from '../hooks/useEscapeKey';
import { getNotificationPrefs, saveNotificationPrefs, testEmailNotification } from '../services/api';

export default function NotificationSettingsModal({ onClose }) {
  useEscapeKey(onClose);

  const [emails, setEmails] = useState([]);
  const [newEmail, setNewEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [smtpConfigured, setSmtpConfigured] = useState(false);
  const [message, setMessage] = useState(null); // {type: 'success'|'error', text: '...'}

  useEffect(() => {
    getNotificationPrefs()
      .then((prefs) => {
        setEmails(prefs.emails || []);
        setSmtpConfigured(prefs.smtp_configured || false);
      })
      .catch(() => setMessage({ type: 'error', text: 'Failed to load preferences' }))
      .finally(() => setLoading(false));
  }, []);

  const addEmail = () => {
    const e = newEmail.trim().toLowerCase();
    if (!e || !e.includes('@') || !e.includes('.')) {
      setMessage({ type: 'error', text: 'Please enter a valid email address' });
      return;
    }
    if (emails.includes(e)) {
      setMessage({ type: 'error', text: 'Email already added' });
      return;
    }
    const updated = [...emails, e];
    setEmails(updated);
    setNewEmail('');
    setMessage(null);
    doSave(updated);
  };

  const removeEmail = (idx) => {
    const updated = emails.filter((_, i) => i !== idx);
    setEmails(updated);
    doSave(updated);
  };

  const doSave = async (emailList) => {
    setSaving(true);
    try {
      const result = await saveNotificationPrefs(emailList);
      setEmails(result.emails || emailList);
      setMessage({ type: 'success', text: 'Saved' });
      setTimeout(() => setMessage(null), 2000);
    } catch {
      setMessage({ type: 'error', text: 'Failed to save' });
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setMessage(null);
    try {
      const result = await testEmailNotification();
      if (result.success) {
        setMessage({ type: 'success', text: `Test email sent to ${result.recipients.join(', ')}` });
      } else {
        setMessage({ type: 'error', text: 'Test email failed — check SMTP config' });
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Test failed' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '480px', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', color: 'var(--text)' }}>Notification Settings</h3>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '18px', cursor: 'pointer' }}>&times;</button>
        </div>

        {!smtpConfigured && (
          <div style={{ padding: '10px 14px', marginBottom: '16px', background: 'rgba(255,190,0,0.1)', border: '1px solid rgba(255,190,0,0.3)', borderRadius: '6px', fontSize: '12px', color: 'var(--yellow)' }}>
            SMTP not configured. Add NOTIFICATION_EMAIL and NOTIFICATION_EMAIL_APP_PASSWORD to .env to enable email sending.
          </div>
        )}

        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Notification Email Addresses
          </label>
          <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px', marginBottom: '8px' }}>
            Alerts and notifications will be sent to these emails.
          </div>

          {loading ? (
            <div style={{ color: 'var(--text-muted)', fontSize: '13px', padding: '12px 0' }}>Loading...</div>
          ) : (
            <>
              {/* Email list */}
              {emails.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '10px' }}>
                  {emails.map((email, idx) => (
                    <div key={idx} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 12px', background: 'var(--bg)', border: '1px solid var(--border)',
                      borderRadius: '6px', fontSize: '13px',
                    }}>
                      <span style={{ color: 'var(--text)' }}>{email}</span>
                      <button onClick={() => removeEmail(idx)}
                        style={{
                          background: 'none', border: 'none', color: 'var(--red)',
                          cursor: 'pointer', fontSize: '16px', padding: '0 4px', lineHeight: 1,
                        }}>&times;</button>
                    </div>
                  ))}
                </div>
              )}

              {/* Add new email */}
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addEmail()}
                  placeholder="Add email address..."
                  style={{
                    flex: 1, padding: '8px 12px', fontSize: '13px',
                    background: 'var(--bg)', border: '1px solid var(--border)',
                    borderRadius: '6px', color: 'var(--text)', outline: 'none',
                  }}
                />
                <button onClick={addEmail} disabled={saving}
                  style={{
                    padding: '8px 16px', fontSize: '13px', fontWeight: 600,
                    background: 'var(--green)', color: '#000', border: 'none',
                    borderRadius: '6px', cursor: 'pointer', opacity: saving ? 0.5 : 1,
                  }}>
                  Add
                </button>
              </div>
            </>
          )}
        </div>

        {/* Test button */}
        {emails.length > 0 && smtpConfigured && (
          <button onClick={handleTest} disabled={testing}
            style={{
              width: '100%', padding: '10px', fontSize: '13px', fontWeight: 600,
              background: 'transparent', color: 'var(--text)', border: '1px solid var(--border)',
              borderRadius: '6px', cursor: 'pointer', marginBottom: '12px',
              opacity: testing ? 0.5 : 1,
            }}>
            {testing ? 'Sending...' : 'Send Test Email'}
          </button>
        )}

        {/* Status message */}
        {message && (
          <div style={{
            padding: '8px 12px', borderRadius: '6px', fontSize: '12px',
            background: message.type === 'success' ? 'rgba(0,210,106,0.1)' : 'rgba(255,71,87,0.1)',
            color: message.type === 'success' ? 'var(--green)' : 'var(--red)',
            border: `1px solid ${message.type === 'success' ? 'rgba(0,210,106,0.3)' : 'rgba(255,71,87,0.3)'}`,
          }}>
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}
