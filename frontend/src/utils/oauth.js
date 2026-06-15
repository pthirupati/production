/**
 * OAuth — always use server-built start URLs so redirect_uri matches GitHub/Google app settings.
 */

export function startOAuth(provider, intent = 'login') {
  const params = new URLSearchParams()
  if (intent && intent !== 'login') params.set('intent', intent)
  const qs = params.toString()
  window.location.href = `/api/auth/social/start/${provider}${qs ? `?${qs}` : ''}`
}

/** @deprecated Prefer startOAuth — kept for tests/fallback */
export function getOAuthRedirectUri(socialConfig, provider) {
  const cfg = socialConfig?.[provider]
  if (cfg?.callback_url) return cfg.callback_url
  const base = (socialConfig?.frontend_url || window.location.origin).replace(/\/$/, '')
  return `${base}/auth/callback/${provider}`
}

export function buildOAuthAuthorizeUrl(socialConfig, provider, intent = 'login') {
  const cfg = socialConfig?.[provider]
  if (cfg?.login_url && intent === 'login') return cfg.login_url
  if (!cfg?.enabled || !cfg.client_id) return null
  const redirectUri = getOAuthRedirectUri(socialConfig, provider)
  const scopes = provider === 'github' ? 'user:email' : 'openid email profile'
  const state = encodeURIComponent(intent)
  if (provider === 'github') {
    return `${cfg.authorize_url}?client_id=${cfg.client_id}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scopes)}&state=${state}`
  }
  return `${cfg.authorize_url}?client_id=${cfg.client_id}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scopes)}&access_type=offline&prompt=consent&state=${state}`
}
