// AuthPage — Page Object for authentication flows
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';

class AuthPage {
  constructor(page) {
    this.page = page;
    this.baseUrl = BASE_URL;
  }

  // ── OTP-based registration ───────────────────────────────────────────────
  async sendOtp(email) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/send-otp/`, {
      data: { email },
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    return resp;
  }

  async verifyOtp(sessionToken, code) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/verify-otp/`, {
      data: { session_token: sessionToken, code },
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    return resp;
  }

  async register({ email, password, sessionToken, firstName = 'E2E', lastName = 'User' }) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/register/`, {
      data: {
        email,
        password,
        session_token: sessionToken,
        first_name: firstName,
        last_name: lastName,
        accepted_legal: true,
      },
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    return resp;
  }

  async login({ email, password }) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/login/`, {
      data: { email, password },
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    const body = await resp.json();
    return { resp, access: body.access, refresh: body.refresh };
  }

  async refreshToken(refresh) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/token/refresh/`, {
      data: { refresh },
      headers: { 'X-Forwarded-Proto': 'https' },
    });
    return resp;
  }

  async logout(access) {
    const resp = await this.page.request.post(`${this.baseUrl}/api/auth/logout/`, {
      headers: {
        Authorization: `Bearer ${access}`,
        'X-Forwarded-Proto': 'https',
      },
    });
    return resp;
  }

  // ── Authenticated API helper ─────────────────────────────────────────────
  async api(method, path, { body, token } = {}) {
    return this.page.request.fetch(`${this.baseUrl}${path}`, {
      method,
      data: body,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        'X-Forwarded-Proto': 'https',
        'Content-Type': 'application/json',
      },
    });
  }
}

module.exports = { AuthPage };
