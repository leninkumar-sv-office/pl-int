import { render } from '@testing-library/react';

export function renderComponent(ui, options = {}) {
  return render(ui, { ...options });
}

export function setupAuth(userId = 'TestUser') {
  localStorage.setItem('sessionToken', 'test-jwt-token');
  localStorage.setItem('authUser', JSON.stringify({
    email: 'test@example.com',
    name: 'TestUser',
    picture: '',
  }));
  localStorage.setItem('selectedUserId', userId);
}

export function mockStockData(overrides = {}) {
  return {
    symbol: 'RELIANCE', company: 'Reliance Industries', exchange: 'NSE',
    quantity: 10, buy_price: 2500, current_price: 2800, buy_date: '2024-01-15',
    gain: 3000, gain_pct: 12.0, ...overrides,
  };
}

export function mockMFData(overrides = {}) {
  return {
    fund_code: 'INF846K01EW2', fund_name: 'Axis Bluechip Direct Growth',
    units: 100.5, avg_nav: 45.0, current_nav: 52.0,
    invested: 4522.5, current_value: 5226.0, gain: 703.5, gain_pct: 15.56,
    ...overrides,
  };
}
