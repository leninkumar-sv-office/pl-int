import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import UserSelector from './UserSelector';

vi.mock('../services/api', () => ({
  getUsers: vi.fn().mockResolvedValue([
    { id: 'Lenin', name: 'Lenin', avatar: '', color: '#4fc3f7' },
    { id: 'Appa', name: 'Appa', avatar: '', color: '#81c784' },
  ]),
  addUser: vi.fn(),
}));

describe('UserSelector', () => {
  beforeEach(() => {
    localStorage.setItem('sessionToken', 'test-token');
    localStorage.setItem('authUser', JSON.stringify({ name: 'Test User', email: 'test@example.com' }));
  });

  it('renders current user name after loading', async () => {
    render(<UserSelector currentUserId="Lenin" onUserChange={vi.fn()} />);
    await waitFor(() => {
      expect(screen.getByText('Lenin')).toBeTruthy();
    });
  });

  it('opens dropdown on button click', async () => {
    render(<UserSelector currentUserId="Lenin" onUserChange={vi.fn()} />);
    await waitFor(() => screen.getByText('Lenin'));
    fireEvent.click(screen.getAllByText('Lenin')[0]);
    await waitFor(() => {
      expect(screen.getByText('Appa')).toBeTruthy();
    });
  });

  it('calls onUserChange when another user is selected', async () => {
    const onUserChange = vi.fn();
    render(<UserSelector currentUserId="Lenin" onUserChange={onUserChange} />);
    await waitFor(() => screen.getByText('Lenin'));
    fireEvent.click(screen.getAllByText('Lenin')[0]);
    await waitFor(() => screen.getByText('Appa'));
    fireEvent.click(screen.getByText('Appa'));
    expect(onUserChange).toHaveBeenCalledWith('Appa');
  });

  it('shows sign out option when session token exists', async () => {
    render(<UserSelector currentUserId="Lenin" onUserChange={vi.fn()} />);
    await waitFor(() => screen.getByText('Lenin'));
    fireEvent.click(screen.getAllByText('Lenin')[0]);
    await waitFor(() => {
      expect(screen.getByText('Sign out')).toBeTruthy();
    });
  });

  it('shows add user button in dropdown', async () => {
    render(<UserSelector currentUserId="Lenin" onUserChange={vi.fn()} />);
    await waitFor(() => screen.getByText('Lenin'));
    fireEvent.click(screen.getAllByText('Lenin')[0]);
    await waitFor(() => {
      expect(screen.getByText('+ Add user')).toBeTruthy();
    });
  });
});
