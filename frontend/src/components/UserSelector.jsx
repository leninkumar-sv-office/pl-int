import React, { useState, useEffect, useRef } from 'react';
import { getUsers, addUser } from '../services/api';

export default function UserSelector({ currentUserId, onUserChange }) {
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState('');
  const ref = useRef(null);

  useEffect(() => {
    getUsers().then(setUsers).catch(() => {});
  }, []);

  // Close dropdown on outside click or Escape key
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) { setOpen(false); setAdding(false); } };
    const escHandler = (e) => { if (e.key === 'Escape') { setOpen(false); setAdding(false); } };
    document.addEventListener('mousedown', handler);
    document.addEventListener('keydown', escHandler);
    return () => { document.removeEventListener('mousedown', handler); document.removeEventListener('keydown', escHandler); };
  }, []);

  const currentUser = users.find(u => u.id === currentUserId) || users[0];

  const handleSelect = (user) => {
    onUserChange(user.id);
    setOpen(false);
  };

  const handleAdd = async () => {
    if (!newName.trim()) return;
    try {
      const user = await addUser(newName.trim());
      setUsers(prev => [...prev, user]);
      onUserChange(user.id);
      setNewName('');
      setAdding(false);
      setOpen(false);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to add user');
    }
  };

  if (!currentUser) return null;

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {/* Avatar button */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          height: '32px', borderRadius: '16px',
          background: currentUser.color || 'var(--blue)',
          color: '#fff', border: '2px solid transparent',
          fontSize: '12px', fontWeight: 600, cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '0 12px', whiteSpace: 'nowrap',
          transition: 'border-color 0.2s',
          borderColor: open ? 'var(--text)' : 'transparent',
        }}
        title={currentUser.name}
      >
        {currentUser.name}
      </button>

      {/* Dropdown */}
      {open && (
        <div style={{
          position: 'absolute', top: '40px', right: 0, zIndex: 1000,
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius-sm)', boxShadow: 'var(--shadow)',
          minWidth: '180px', overflow: 'hidden',
        }}>
          {/* User list */}
          {users.map(u => (
            <button
              key={u.id}
              onClick={() => handleSelect(u)}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                width: '100%', padding: '10px 14px', border: 'none',
                background: u.id === currentUserId ? 'var(--bg-card-hover)' : 'transparent',
                color: 'var(--text)', cursor: 'pointer', fontSize: '13px',
                textAlign: 'left',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-card-hover)'}
              onMouseLeave={e => e.currentTarget.style.background = u.id === currentUserId ? 'var(--bg-card-hover)' : 'transparent'}
            >
              <span style={{
                width: '26px', height: '26px', borderRadius: '50%',
                background: u.color || 'var(--blue)', color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '12px', fontWeight: 700, flexShrink: 0,
              }}>
                {u.avatar || u.name[0]}
              </span>
              <span style={{ fontWeight: u.id === currentUserId ? 600 : 400 }}>{u.name}</span>
              {u.id === currentUserId && (
                <span style={{ marginLeft: 'auto', color: 'var(--green)', fontSize: '11px' }}>●</span>
              )}
            </button>
          ))}

          {/* Divider + Add user */}
          <div style={{ borderTop: '1px solid var(--border)', padding: '8px 14px' }}>
            {adding ? (
              <div style={{ display: 'flex', gap: '6px' }}>
                <input
                  autoFocus
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdd()}
                  placeholder="Name"
                  style={{
                    flex: 1, padding: '5px 8px', fontSize: '12px',
                    background: 'var(--bg-input)', border: '1px solid var(--border)',
                    borderRadius: '4px', color: 'var(--text)', outline: 'none',
                  }}
                />
                <button onClick={handleAdd} style={{
                  padding: '5px 10px', fontSize: '11px', fontWeight: 600,
                  background: 'var(--blue)', color: '#fff', border: 'none',
                  borderRadius: '4px', cursor: 'pointer',
                }}>Add</button>
              </div>
            ) : (
              <button
                onClick={() => setAdding(true)}
                style={{
                  background: 'none', border: 'none', color: 'var(--text-muted)',
                  fontSize: '12px', cursor: 'pointer', padding: 0,
                }}
              >+ Add user</button>
            )}
          </div>

          {/* Auth user + Sign out */}
          {localStorage.getItem('sessionToken') && (() => {
            const authUser = JSON.parse(localStorage.getItem('authUser') || '{}');
            return authUser.name ? (
              <div style={{ borderTop: '1px solid var(--border)', padding: '10px 14px' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text)' }}>{authUser.name}</div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>{authUser.email}</div>
                <button
                  onClick={() => {
                    localStorage.removeItem('sessionToken');
                    localStorage.removeItem('authUser');
                    window.location.reload();
                  }}
                  style={{
                    background: 'none', border: 'none', color: 'var(--red, #ff4757)',
                    fontSize: '12px', cursor: 'pointer', padding: 0, fontWeight: 500,
                  }}
                >Sign out</button>
              </div>
            ) : null;
          })()}
        </div>
      )}
    </div>
  );
}
