import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import GoogleLogin from './GoogleLogin';

vi.mock('../services/api', () => ({
  googleLoginWithCode: vi.fn(),
}));

describe('GoogleLogin', () => {
  it('renders Portfolio Dashboard title', () => {
    render(<GoogleLogin clientId="test-client-id" onSuccess={vi.fn()} />);
    expect(screen.getByText('Portfolio Dashboard')).toBeTruthy();
  });

  it('renders Sign in with Google button', () => {
    render(<GoogleLogin clientId="test-client-id" onSuccess={vi.fn()} />);
    expect(screen.getByText('Sign in with Google')).toBeTruthy();
  });

  it('renders sign in subtitle', () => {
    render(<GoogleLogin clientId="test-client-id" onSuccess={vi.fn()} />);
    expect(screen.getByText('Sign in to continue')).toBeTruthy();
  });

  it('button is not disabled by default', () => {
    render(<GoogleLogin clientId="test-client-id" onSuccess={vi.fn()} />);
    const btn = screen.getByRole('button');
    expect(btn.disabled).toBe(false);
  });
});
