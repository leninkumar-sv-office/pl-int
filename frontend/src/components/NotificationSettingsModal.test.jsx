import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NotificationSettingsModal from './NotificationSettingsModal';

vi.mock('../services/api', () => ({
  getNotificationPrefs: vi.fn().mockResolvedValue({ emails: [], smtp_configured: true }),
  saveNotificationPrefs: vi.fn().mockResolvedValue({ emails: ['test@example.com'] }),
  testEmailNotification: vi.fn().mockResolvedValue({ success: true, recipients: ['test@example.com'] }),
}));

const defaultProps = {
  onClose: vi.fn(),
};

describe('NotificationSettingsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders modal title', () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    expect(screen.getByText('Notification Settings')).toBeTruthy();
  });

  it('renders email addresses label', () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    expect(screen.getByText('Notification Email Addresses')).toBeTruthy();
  });

  it('renders description text', () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    expect(screen.getByText(/Alerts and notifications will be sent/)).toBeTruthy();
  });

  it('renders loading state initially', () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    expect(screen.getByText('Loading...')).toBeTruthy();
  });

  it('renders email input after loading', async () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Add email address...')).toBeTruthy();
    });
  });

  it('renders Add button', async () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('Add')).toBeTruthy();
    });
  });

  it('renders close button', () => {
    render(<NotificationSettingsModal {...defaultProps} />);
    const closeBtn = screen.getByText('\u00D7');
    expect(closeBtn).toBeTruthy();
  });

  it('shows SMTP warning when not configured', async () => {
    const { getNotificationPrefs } = await import('../services/api');
    getNotificationPrefs.mockResolvedValueOnce({ emails: [], smtp_configured: false });
    render(<NotificationSettingsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText(/SMTP not configured/)).toBeTruthy();
    });
  });

  it('shows existing emails after load', async () => {
    const { getNotificationPrefs } = await import('../services/api');
    getNotificationPrefs.mockResolvedValueOnce({ emails: ['user@test.com'], smtp_configured: true });
    render(<NotificationSettingsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('user@test.com')).toBeTruthy();
    });
  });

  it('shows Send Test Email button when emails exist and SMTP configured', async () => {
    const { getNotificationPrefs } = await import('../services/api');
    getNotificationPrefs.mockResolvedValueOnce({ emails: ['user@test.com'], smtp_configured: true });
    render(<NotificationSettingsModal {...defaultProps} />);
    await waitFor(() => {
      expect(screen.getByText('Send Test Email')).toBeTruthy();
    });
  });
});
