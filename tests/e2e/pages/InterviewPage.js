// InterviewPage — Page Object for Interview Studio
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

class InterviewPage {
  constructor(page) {
    this.page = page;
    this.baseUrl = BASE_URL;
    this.siteUrl = SITE_URL;
  }

  async getPlans() {
    return this.page.request.get(`${this.baseUrl}/api/interviews/plans/`, {
      headers: { 'X-Forwarded-Proto': 'https' },
    });
  }

  async getVoiceConfig() {
    return this.page.request.get(`${this.baseUrl}/api/interviews/voice-config/`, {
      headers: { 'X-Forwarded-Proto': 'https' },
    });
  }

  async getEntitlement(token) {
    return this.page.request.get(`${this.baseUrl}/api/interviews/entitlement/`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Forwarded-Proto': 'https',
      },
    });
  }

  async createCampaign(token, { round_count = 3, ...rest } = {}) {
    return this.page.request.post(`${this.baseUrl}/api/interviews/campaigns/`, {
      data: { round_count, ...rest },
      headers: {
        Authorization: `Bearer ${token}`,
        'X-Forwarded-Proto': 'https',
      },
    });
  }

  async getCampaign(token, campaignId) {
    return this.page.request.get(
      `${this.baseUrl}/api/interviews/campaigns/${campaignId}/`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
  }

  async adminGrantFree(adminToken, userId) {
    return this.page.request.post(
      `${this.baseUrl}/api/admin/interviews/entitlements/${userId}/grant/`,
      {
        headers: {
          Authorization: `Bearer ${adminToken}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
  }

  async adminUpdateSettings(adminToken, settings) {
    return this.page.request.put(
      `${this.baseUrl}/api/admin/interviews/settings/`,
      {
        data: settings,
        headers: {
          Authorization: `Bearer ${adminToken}`,
          'X-Forwarded-Proto': 'https',
        },
      }
    );
  }

  // ── UI navigation ────────────────────────────────────────────────────────
  async navigateToInterviewHub() {
    await this.page.goto(`${this.siteUrl}/interviews`);
  }

  async navigateToInterviewRoom(campaignId) {
    await this.page.goto(`${this.siteUrl}/interviews/room/${campaignId}`);
  }

  // Check that the interview room renders without JS errors
  async assertRoomRendered() {
    await this.page.waitForSelector('[data-testid="interview-room"]', { timeout: 15_000 });
  }

  // Check media permission dialog appears
  async assertMediaPermissionDialog() {
    await this.page.waitForSelector('[data-testid="media-permission-dialog"]', { timeout: 10_000 });
  }

  // Check virtual background toggle exists
  async assertVirtualBackgroundToggle() {
    const toggle = await this.page.locator('[data-testid="virtual-bg-toggle"]');
    return toggle.count() > 0;
  }
}

module.exports = { InterviewPage };
