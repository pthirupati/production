// LabPage — Page Object for lab runner interactions
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const LAB_WAIT_TIMEOUT = parseInt(process.env.LAB_WAIT_TIMEOUT || '120', 10) * 1000;

class LabPage {
  constructor(page) {
    this.page = page;
    this.baseUrl = BASE_URL;
  }

  async startLab(scenarioSlug, token) {
    const resp = await this.page.request.post(
      `${this.baseUrl}/api/labs/start/`,
      {
        data: { scenario: scenarioSlug },
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async stopLab(sessionId, token) {
    const resp = await this.page.request.post(
      `${this.baseUrl}/api/labs/${sessionId}/stop/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async getLabStatus(sessionId, token) {
    const resp = await this.page.request.get(
      `${this.baseUrl}/api/labs/${sessionId}/status/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async waitForRunning(sessionId, token) {
    const deadline = Date.now() + LAB_WAIT_TIMEOUT;
    while (Date.now() < deadline) {
      const resp = await this.getLabStatus(sessionId, token);
      const body = await resp.json();
      if (body.status === 'RUNNING') return body;
      if (['FAILED', 'STOPPED', 'ERROR'].includes(body.status)) {
        throw new Error(`Lab entered terminal state: ${body.status}`);
      }
      await new Promise((r) => setTimeout(r, 2000));
    }
    throw new Error(`Lab did not reach RUNNING within ${LAB_WAIT_TIMEOUT / 1000}s`);
  }

  async getHints(sessionId, token) {
    const resp = await this.page.request.get(
      `${this.baseUrl}/api/labs/${sessionId}/hints/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async submitHint(sessionId, token) {
    const resp = await this.page.request.post(
      `${this.baseUrl}/api/labs/${sessionId}/hints/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async validateLab(sessionId, token) {
    const resp = await this.page.request.post(
      `${this.baseUrl}/api/labs/${sessionId}/validate/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async getReplay(sessionId, token) {
    const resp = await this.page.request.get(
      `${this.baseUrl}/api/labs/${sessionId}/replay/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async getActiveLabs(token) {
    const resp = await this.page.request.get(
      `${this.baseUrl}/api/labs/active/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }

  async getLabHistory(token) {
    const resp = await this.page.request.get(
      `${this.baseUrl}/api/labs/history/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
    return resp;
  }
}

module.exports = { LabPage };
