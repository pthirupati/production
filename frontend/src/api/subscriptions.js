import api from './client'

export const subscriptionApi = {
  async subscribeTechnology(technologyId, amount = 0) {
    const { data } = await api.post('/billing/subscribe/technology/', {
      technology_id: technologyId,
      amount,
    })
    return data
  },

  async createRazorpayOrder(technologyId) {
    const { data } = await api.post('/billing/razorpay/order/', {
      technology_id: technologyId,
    })
    return data
  },

  async verifyRazorpayPayment(paymentData) {
    const { data } = await api.post('/billing/razorpay/verify/', paymentData)
    return data
  },

  async getBillingStatus() {
    const { data } = await api.get('/billing/status/')
    return data
  },

  async getMySubscriptions() {
    const { data } = await api.get('/billing/subscriptions/')
    return data
  },

  async cancelSubscription(subscriptionId) {
    const { data } = await api.post('/billing/subscribe/cancel/', {
      subscription_id: subscriptionId,
    })
    return data
  },

  async confirmPayment(paymentToken, paymentMethod) {
    const { data } = await api.post('/billing/confirm-payment/', {
      payment_token: paymentToken,
      payment_method: paymentMethod,
    })
    return data
  },

  async getCurrencyRate(currency = 'USD', amount = 0) {
    const params = new URLSearchParams({ currency })
    if (amount > 0) params.set('amount', amount)
    const { data } = await api.get(`/billing/currency-rate/?${params}`)
    return data
  },

  async createBatchOrders(technologyIds) {
    const results = []
    for (const techId of technologyIds) {
      try {
        const data = await this.createRazorpayOrder(techId)
        results.push({ techId, success: true, data })
      } catch (err) {
        results.push({ techId, success: false, error: err?.response?.data?.error || 'Failed' })
      }
    }
    return results
  },

}
