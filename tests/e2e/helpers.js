/**
 * Test helpers for authenticated Playwright tests.
 *
 * Generates a JWT via the backend's Python auth module and injects it
 * into localStorage so the React app sees a valid session without
 * requiring a real Google OAuth flow.
 */
import { execSync } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const BACKEND_DIR = path.resolve(__dirname, '../../backend');

/**
 * Generate a valid JWT token using the backend auth module.
 */
export function generateJWT() {
  const script = `
from app.auth import create_session_token
print(create_session_token('leninkumar.sv.ai@gmail.com', 'Lenin'))
  `.trim();
  return execSync(`python3 -c "${script}"`, { cwd: BACKEND_DIR })
    .toString()
    .trim();
}

/**
 * Set up authenticated session in the browser.
 * Must be called before navigating to the app.
 */
export async function authenticate(page, userId = 'Lenin') {
  const token = generateJWT();

  // Navigate first to set the origin for localStorage
  await page.goto('/');
  await page.evaluate(
    ({ token, userId }) => {
      localStorage.setItem('sessionToken', token);
      localStorage.setItem(
        'authUser',
        JSON.stringify({
          email: 'leninkumar.sv.ai@gmail.com',
          name: 'Lenin',
          picture: '',
        })
      );
      localStorage.setItem('selectedUserId', userId);
    },
    { token, userId }
  );

  // Reload so the app picks up the auth state
  await page.goto('/');
}

/**
 * Wait for the dashboard to fully load (auth gate passed + data loaded).
 */
export async function waitForDashboard(page) {
  // Wait for auth gate to pass — the tab bar appears
  await page.getByRole('button', { name: 'Stocks' }).waitFor({ timeout: 30_000 });
}

/**
 * Wait for a specific tab's data to load after clicking it.
 * Checks that the table or content area has rendered.
 */
export async function switchTab(page, tabName) {
  await page.getByRole('button', { name: tabName, exact: true }).click();
  // Wait for table or empty-state to appear
  await page
    .locator('table, [class*="empty"], h3')
    .first()
    .waitFor({ timeout: 10_000 });
}

/**
 * Call a backend API endpoint directly with auth.
 */
export async function apiGet(endpoint) {
  const token = generateJWT();
  const res = await fetch(`http://localhost:8000${endpoint}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}
