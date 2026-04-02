/**
 * Shared validation utilities for forms.
 * All validators return { valid: boolean, error?: string }
 */

export const validators = {
  email(value) {
    if (!value) return { valid: false, error: 'Email is required' }
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!re.test(value)) return { valid: false, error: 'Invalid email format' }
    return { valid: true }
  },

  password(value) {
    if (!value) return { valid: false, error: 'Password is required' }
    if (value.length < 8) return { valid: false, error: 'At least 8 characters' }
    if (!/[A-Z]/.test(value)) return { valid: false, error: 'Needs an uppercase letter' }
    if (!/[a-z]/.test(value)) return { valid: false, error: 'Needs a lowercase letter' }
    if (!/[0-9]/.test(value)) return { valid: false, error: 'Needs a number' }
    if (!/[^A-Za-z0-9]/.test(value)) return { valid: false, error: 'Needs a special character' }
    return { valid: true }
  },

  /** Returns a strength score 0-4 and label */
  passwordStrength(value) {
    if (!value) return { score: 0, label: '', color: '' }
    let score = 0
    if (value.length >= 8) score++
    if (value.length >= 12) score++
    if (/[A-Z]/.test(value) && /[a-z]/.test(value)) score++
    if (/[0-9]/.test(value) && /[^A-Za-z0-9]/.test(value)) score++

    const levels = [
      { label: 'Weak', color: 'bg-accent-red' },
      { label: 'Fair', color: 'bg-orange-500' },
      { label: 'Good', color: 'bg-accent-amber' },
      { label: 'Strong', color: 'bg-accent-green' },
      { label: 'Very Strong', color: 'bg-emerald-400' },
    ]
    return { score, ...levels[score] }
  },

  phone(value) {
    if (!value) return { valid: true } // optional
    const re = /^\+?1?\d{9,15}$/
    if (!re.test(value.replace(/[\s\-()]/g, ''))) {
      return { valid: false, error: 'Invalid phone (e.g. +1234567890)' }
    }
    return { valid: true }
  },

  username(value) {
    if (!value) return { valid: false, error: 'Username is required' }
    if (value.length < 3) return { valid: false, error: 'At least 3 characters' }
    if (value.length > 30) return { valid: false, error: 'Max 30 characters' }
    if (!/^[a-zA-Z0-9_.-]+$/.test(value)) {
      return { valid: false, error: 'Letters, numbers, _ . - only' }
    }
    return { valid: true }
  },

  slug(value) {
    if (!value) return { valid: false, error: 'Slug is required' }
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(value)) {
      return { valid: false, error: 'Lowercase letters, numbers, hyphens only' }
    }
    return { valid: true }
  },

  required(value, fieldName = 'Field') {
    if (!value || (typeof value === 'string' && !value.trim())) {
      return { valid: false, error: `${fieldName} is required` }
    }
    return { valid: true }
  },
}

/**
 * Inline validation helper — returns error string or null
 */
export function validate(validatorName, value) {
  const result = validators[validatorName]?.(value)
  return result?.valid ? null : result?.error || 'Invalid'
}
