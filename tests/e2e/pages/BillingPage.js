// BillingPage — Page Object for billing/subscription flows
const BASE_URL = process.env.BASE_URL || 'http://localhost:8000';
const SITE_URL = process.env.SITE_URL || 'http://localhost:5173';

class BillingPage {
  constructor(page) {
    this.page = page;
    this.baseUrl = BASE_URL;
    this.siteUrl = SITE_URL;
  }

  async getSubscriptions(token) {
    return this.page.request.get(`${this.baseUrl}/api/billing/subscriptions/`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }

  async getPlans(token) {
    return this.page.request.get(`${this.baseUrl}/api/billing/plans/`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }

  async getInvoices(token) {
    return this.page.request.get(`${this.baseUrl}/api/billing/invoices/`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }

  async createRazorpayOrder(token, { plan_id, currency = 'INR' } = {}) {
    return this.page.request.post(`${this.baseUrl}/api/billing/razorpay/order/`, {
      data: { plan_id, currency },
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }

  async getCurrencyRate(token, currency = 'USD') {
    return this.page.request.get(
      `${this.baseUrl}/api/billing/currency-rate/?currency=${currency}`,
      { headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' } }
    );
  }

  async applyCoupon(token, { code, plan_id } = {}) {
    return this.page.request.post(`${this.baseUrl}/api/billing/coupons/validate/`, {
      data: { code, plan_id },
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }

  async getGatewayStatus() {
    return this.page.request.get(`${this.baseUrl}/api/billing/gateway-status/`, {
      headers: { 'X-Forwarded-Proto': 'https' },
    });
  }

  async getSubscriptionLogs(token) {
    return this.page.request.get(`${this.baseUrl}/api/billing/subscription-logs/`, {
      headers: { Authorization: `Bearer ${token}`, 'X-Forwarded-Proto': 'https' },
    });
  }
}

module.exports = { BillingPage };
