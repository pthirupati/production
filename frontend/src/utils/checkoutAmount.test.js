import { describe, it, expect } from 'vitest'
import {
  toPaise,
  resolveChargeAmountPaise,
  isOrderUsable,
  hasDisplayableGst,
  resolveDisplayAmountInr,
} from './checkoutAmount'

// Audit Z6-12 — "payment has zero frontend tests; Razorpay checkout can break on
// any frontend merge undetected."
//
// The rule these exist to protect: **the server's amount always wins.** The
// displayed amount arrives via a URL query parameter, which anyone can edit, so it
// is a display value and never an input to what is charged. If that precedence ever
// inverts, a customer is billed a number they chose.

describe('toPaise', () => {
  it('converts rupees to paise', () => {
    expect(toPaise(499)).toBe(49900)
  })

  it('rounds rather than truncates', () => {
    // 499.99 * 100 is 49998.999... in IEEE 754. Truncating undercharges by a
    // paisa on every fractional amount, which is the kind of thing that only
    // surfaces in a reconciliation months later.
    expect(toPaise(499.99)).toBe(49999)
  })

  it('treats junk as zero rather than NaN', () => {
    // NaN would reach Razorpay as `amount: null` and fail with an opaque gateway
    // error instead of a clear one.
    for (const bad of [undefined, null, 'abc', {}, NaN, Infinity]) {
      expect(toPaise(bad)).toBe(0)
    }
  })

  it('refuses negative amounts', () => {
    expect(toPaise(-100)).toBe(0)
  })
})

describe('resolveChargeAmountPaise — the server wins', () => {
  it('uses the server amount when present', () => {
    expect(
      resolveChargeAmountPaise({
        serverAmountPaise: 39900,
        baseAmountInr: 499,
      }),
    ).toBe(39900)
  })

  it('ignores the page amount even when they disagree', () => {
    // The page amount comes from an editable URL parameter. This is the assertion
    // that stops a hand-edited `?amount=1` becoming a ₹1 charge.
    expect(
      resolveChargeAmountPaise({
        serverAmountPaise: 49900,
        baseAmountInr: 1,
      }),
    ).toBe(49900)
  })

  it('ignores the page amount even when the page shows LESS', () => {
    expect(
      resolveChargeAmountPaise({
        serverAmountPaise: 49900,
        baseAmountInr: 99999,
      }),
    ).toBe(49900)
  })

  it('prefers the server amount over a coupon total', () => {
    // The server already applied the coupon and created the order for that figure.
    expect(
      resolveChargeAmountPaise({
        serverAmountPaise: 39900,
        couponApplied: true,
        discountedTotalInr: 250,
        baseAmountInr: 499,
      }),
    ).toBe(39900)
  })
})

describe('resolveChargeAmountPaise — fallbacks', () => {
  it('uses the discounted total when a coupon applies and the server is silent', () => {
    expect(
      resolveChargeAmountPaise({
        couponApplied: true,
        discountedTotalInr: 250,
        baseAmountInr: 499,
      }),
    ).toBe(25000)
  })

  it('uses the base amount when no coupon applies', () => {
    expect(resolveChargeAmountPaise({ baseAmountInr: 499 })).toBe(49900)
  })

  it('falls through to the base amount if the coupon total is unusable', () => {
    // A coupon flag with no total must not produce a zero-rupee charge.
    expect(
      resolveChargeAmountPaise({
        couponApplied: true,
        discountedTotalInr: 0,
        baseAmountInr: 499,
      }),
    ).toBe(49900)
  })

  it('treats a zero server amount as absent, not as free', () => {
    // The server rejects an unpriced technology outright, so 0 means "it did not
    // tell us" rather than "this costs nothing".
    expect(
      resolveChargeAmountPaise({
        serverAmountPaise: 0,
        baseAmountInr: 499,
      }),
    ).toBe(49900)
  })

  it('returns 0 when nothing is known, rather than NaN', () => {
    // 0 fails visibly at the gateway; NaN fails confusingly.
    expect(resolveChargeAmountPaise({})).toBe(0)
    expect(resolveChargeAmountPaise()).toBe(0)
  })
})

describe('isOrderUsable', () => {
  it('accepts a real order', () => {
    expect(isOrderUsable({ order_id: 'order_abc' })).toBe(true)
  })

  it('accepts demo mode', () => {
    expect(isOrderUsable({ demo_mode: true })).toBe(true)
  })

  it('rejects a gateway failure', () => {
    // Proceeding here opens a Razorpay modal with no order behind it, which fails
    // at verification rather than at the point of failure.
    expect(isOrderUsable({ error: 'Payment gateway is unavailable.' })).toBe(false)
  })

  it('rejects an empty or missing response', () => {
    expect(isOrderUsable({})).toBe(false)
    expect(isOrderUsable(null)).toBe(false)
    expect(isOrderUsable(undefined)).toBe(false)
  })
})

describe('hasDisplayableGst', () => {
  it('shows a real tax breakup', () => {
    expect(hasDisplayableGst({ gst_amount: '76.12' })).toBe(true)
  })

  it('hides a zero-tax breakup', () => {
    // Not GST-registered, or an export. Printing "GST ₹0" states something the
    // invoice may contradict.
    expect(hasDisplayableGst({ gst_amount: '0.00' })).toBe(false)
  })

  it('hides an absent breakup', () => {
    // Before an order exists the tax is genuinely unknown. The page used to print
    // a hardcoded "GST (included) ₹0" here (audit Z1-14).
    expect(hasDisplayableGst(null)).toBe(false)
    expect(hasDisplayableGst({})).toBe(false)
  })

  it('hides a malformed breakup rather than rendering NaN', () => {
    expect(hasDisplayableGst({ gst_amount: 'abc' })).toBe(false)
  })
})

describe('resolveDisplayAmountInr', () => {
  it('prefers the server total over an editable URL amount', () => {
    expect(resolveDisplayAmountInr({
      serverTotalInr: 499,
      bootstrapAmountInr: 399,
      urlAmountInr: 1,
    })).toBe(499)
  })

  it('falls back to bootstrap before URL', () => {
    expect(resolveDisplayAmountInr({
      serverTotalInr: null,
      bootstrapAmountInr: 399,
      urlAmountInr: 1,
    })).toBe(399)
  })

  it('uses the URL only as a last-resort hint', () => {
    expect(resolveDisplayAmountInr({
      urlAmountInr: '499',
    })).toBe(499)
  })

  it('returns 0 when nothing is usable', () => {
    expect(resolveDisplayAmountInr({})).toBe(0)
    expect(resolveDisplayAmountInr({ urlAmountInr: 'abc' })).toBe(0)
  })
})
