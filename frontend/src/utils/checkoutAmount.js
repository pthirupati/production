// Money resolution for the Razorpay checkout (audit Z6-12).
//
// This was a single inline expression inside a 700-line component:
//
//   amountPaise = orderData.amount_paise
//     || (appliedCoupon ? finalAmountINR * 100 : amountPaise)
//
// which decides **what the customer is actually charged**, and was untestable
// without rendering the whole page with a router, an auth store and the Razorpay
// script. The audit's concern is exactly this: "Razorpay checkout can break on any
// frontend merge undetected."
//
// Extracted as pure functions so the rules can be stated and tested directly.
// Nothing about the behaviour changed — the tests pin the existing rules first.
//
// The rule that matters most: **the server's amount always wins.** The displayed
// amount arrives via a URL query parameter, which is editable, so it is a display
// value and never an input to what is charged. The server recomputes the price from
// the catalog and returns `amount_paise`; that is the number sent to Razorpay.

/** Rupees → paise, the unit Razorpay bills in. */
export function toPaise(rupees) {
  const n = Number(rupees)
  if (!Number.isFinite(n) || n < 0) return 0
  // Round rather than truncate: 499.99 * 100 is 49998.999... in floating point,
  // and truncating would undercharge by a paisa on every fractional amount.
  return Math.round(n * 100)
}

/**
 * The amount to send to Razorpay, in paise.
 *
 * Precedence, strongest first:
 *   1. `orderData.amount_paise` — the server computed it from the catalog price
 *      and has already created the Razorpay order for exactly this figure. Sending
 *      anything else produces a signature/amount mismatch at verification.
 *   2. the coupon-discounted total, when a coupon is applied but the server did
 *      not return a figure.
 *   3. the page's base amount.
 *
 * `0` is treated as absent deliberately: a zero-paise order is never valid here
 * (the server rejects an unpriced technology outright), so it means "the server
 * did not tell us" rather than "this is free".
 */
export function resolveChargeAmountPaise({
  serverAmountPaise,
  couponApplied,
  discountedTotalInr,
  baseAmountInr,
} = {}) {
  const fromServer = Number(serverAmountPaise)
  if (Number.isFinite(fromServer) && fromServer > 0) return fromServer

  if (couponApplied) {
    const discounted = toPaise(discountedTotalInr)
    if (discounted > 0) return discounted
  }

  return toPaise(baseAmountInr)
}

/**
 * Whether the create-order response is usable.
 *
 * A response with no `order_id` and no `demo_mode` means the gateway could not
 * create an order — proceeding would open a Razorpay modal with no order behind
 * it, which fails confusingly at verification rather than at the point of failure.
 */
export function isOrderUsable(orderData) {
  if (!orderData) return false
  return Boolean(orderData.order_id) || Boolean(orderData.demo_mode)
}

/**
 * Whether the GST breakup from the server is worth displaying.
 *
 * Before an order exists we do not know the tax, and the page previously printed a
 * hardcoded "GST (included) ₹0" — a false statement the moment GST is switched on
 * (audit Z1-14). Absent is different from zero, and both are different from "we
 * are not GST-registered", so this only returns true when there is real tax to show.
 */
export function hasDisplayableGst(gst) {
  if (!gst) return false
  const amount = Number(gst.gst_amount)
  return Number.isFinite(amount) && amount > 0
}
