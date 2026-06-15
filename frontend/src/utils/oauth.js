/**
 * OAuth redirect URIs must match the GitHub/Google app callback exactly.
 * Use server-configured FRONTEND_URL (not window.location.origin) so www vs apex
 * does not break GitHub, which allows only one callback URL.
 */

export function getOAuthRedirectUri(socialConfig, provider) {
  const cfg = socialConfig?.[provider]
  if (cfg?.callback_url) return cfg.callback_url
  const base = (socialConfig?.frontend_url || window.location.origin).replace(/\/$/, '')
  return `${base}/auth/callback/${provider}`
}

export function buildOAuthAuthorizeUrl(socialConfig, provider) {
  const cfg = socialConfig?.[provider]
  if (!cfg?.enabled || !cfg.client_id) return null
  const redirectUri = getOAuthRedirectUri(socialConfig, provider)
  const scopes = provider === 'github' ? 'user:email' : 'openid email profile'
  if (provider === 'github') {
    return `${cfg.authorize_url}?client_id=${cfg.client_id}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=${encodeURIComponent(scopes)}`
  }
  return `${cfg.authorize_url}?client_id=${cfg.client_id}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scopes)}&access_type=offline&prompt=consent`
}
