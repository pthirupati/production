/**
 * Contact addresses — single source of truth.
 *
 * These were previously string literals repeated across six pages, which is how a
 * privacy policy ends up naming one address while the contact page names another.
 * For ordinary support that is untidy; for the grievance contact it is a compliance
 * problem, because the address published in the policy is the one a regulator holds
 * you to.
 *
 * Kept in sync with the backend by `tests/test_public_contact_details.py` — the
 * backend needs the same values for transactional email and templates, and two
 * hand-maintained copies drift.
 */

/**
 * DPDP grievance / data-protection contact.
 *
 * SPELLING IS DELIBERATE — "piracy", not "privacy". This is the literal mailbox that
 * exists; confirmed with the owner precisely because it reads like a typo. Do not
 * "correct" it: mail to a non-existent alias bounces silently, and this is the
 * address a data-principal complaint and a Data Protection Board notice arrive at.
 */
export const PRIVACY_EMAIL = 'piracy.fixitlab@gmail.com'

/** General enquiries and sales. */
export const PRIMARY_EMAIL = 'fixitlab.admin@gmail.com'

/** Technical support, account and lab issues. */
export const SUPPORT_EMAIL = 'fixitlab.techsupport@gmail.com'

/** Billing, refunds and payment disputes. */
export const PAYMENT_EMAIL = 'fixitlab.payment@gmail.com'

/** Security vulnerability reports — must match `.well-known/security.txt`. */
export const SECURITY_EMAIL = 'security@fixitlab.in'
