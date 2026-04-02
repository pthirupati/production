"""
Rewrite all email templates to premium inline-CSS design.
Fixes:
  1. achievement.html, lab_completed.html, lab_expired.html — rewrite as standalone (no base.html)
  2. subscription_confirmation.html — fix context vars (username, plan_name, expiry_date, scenarios_url)
  3. subscription_admin_notification.html — fix context vars
  4. otp_verification.html — fix to use expires_minutes (match view)
  5. password_reset.html — fix to use expires_hours (match view)
  6. welcome.html — update branding, fix footer contrast
  7. All — fix footer contrast, update year to 2026, update tagline
"""
import os

BASE = os.path.join(os.path.dirname(__file__), '..', 'backend', 'templates', 'emails')
os.makedirs(BASE, exist_ok=True)

# Shared header/footer builder
def header():
    return '''<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>FixitLab</title></head>
<body style="margin:0;padding:0;background-color:#0a0e1a;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0e1a;padding:32px 16px;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  <tr><td style="text-align:center;padding:24px 0 20px;">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>
      <td style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);text-align:center;line-height:44px;"><span style="color:#fff;font-weight:800;font-size:20px;">F</span></td>
      <td style="padding-left:12px;"><span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">FixitLab</span></td>
    </tr></table>
  </td></tr>
  <tr><td>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(180deg,#141b2d 0%,#1a2235 100%);border-radius:16px;border:1px solid #1e293b;overflow:hidden;">
      <tr><td style="height:6px;background:linear-gradient(90deg,#06b6d4,#8b5cf6,#ec4899);"></td></tr>'''

def footer():
    return '''    </table>
  </td></tr>
  <tr><td style="padding:0 40px;"><div style="height:1px;background:linear-gradient(90deg,transparent,#1e293b,transparent);"></div></td></tr>
  <tr><td style="text-align:center;padding:24px 0 8px;">
    <p style="color:#64748b;font-size:11px;margin:0;">&#169; 2026 FixitLab &#8212; Learn by Doing.</p>
    <p style="color:#475569;font-size:11px;margin:8px 0 0;">
      <a href="https://fixitlab.com/privacy" style="color:#94a3b8;text-decoration:none;">Privacy</a> &#183;
      <a href="https://fixitlab.com/terms" style="color:#94a3b8;text-decoration:none;">Terms</a> &#183;
      <a href="mailto:kubelearn464@gmail.com" style="color:#94a3b8;text-decoration:none;">Support</a>
    </p>
  </td></tr>
</table>
</td></tr></table>
</body></html>'''

def write(name, content):
    path = os.path.join(BASE, name)
    with open(path, 'w') as f:
        f.write(content)
    print(f"  Wrote {name} ({len(content)} bytes)")


# ─── 1. welcome.html ────────────────────────────────────────────────
write('welcome.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(6,182,212,0.15),rgba(139,92,246,0.15));border:2px solid rgba(6,182,212,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128640;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Welcome aboard, {{ username }}!</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Your account is ready. Start solving real-world challenges across Linux, Docker, Kubernetes, networking, databases, and more &#8212; all in live terminal environments.</p>
      </td></tr>
      <tr><td style="padding:0 32px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#128187;</div><div style="color:#06b6d4;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Hands-on Labs</div><div style="color:#94a3b8;font-size:12px;margin-top:4px;">Real environments with pre-broken scenarios</div></td></tr></table></td>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#127942;</div><div style="color:#8b5cf6;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Compete</div><div style="color:#94a3b8;font-size:12px;margin-top:4px;">Earn scores, badges and climb the leaderboard</div></td></tr></table></td>
          </tr>
          <tr>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#9889;</div><div style="color:#10b981;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Real Terminal</div><div style="color:#94a3b8;font-size:12px;margin-top:4px;">Full shell in your browser via WebSocket</div></td></tr></table></td>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#128274;</div><div style="color:#f59e0b;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Safe Sandbox</div><div style="color:#94a3b8;font-size:12px;margin-top:4px;">Isolated environments &#8212; break anything safely</div></td></tr></table></td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 40px;">
        <a href="{{ scenarios_url }}" style="display:inline-block;background:linear-gradient(135deg,#06b6d4,#3b82f6);color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(6,182,212,0.3);">Start Your First Challenge &#8594;</a>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#64748b;font-size:12px;margin:0;">If you did not create this account, you can safely ignore this email.</p>
      </td></tr>

''' + footer())


# ─── 2. otp_verification.html ───────────────────────────────────────
# Uses {{ expires_minutes }} to match the view context
write('otp_verification.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(139,92,246,0.15),rgba(236,72,153,0.15));border:2px solid rgba(139,92,246,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128272;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Verify Your Email</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Use the code below to verify your email address and create your FixitLab account.</p>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 12px;">
        <div style="display:inline-block;background:linear-gradient(135deg,rgba(6,182,212,0.08),rgba(139,92,246,0.08));border:2px dashed rgba(6,182,212,0.4);border-radius:16px;padding:24px 48px;">
          <div style="color:#06b6d4;font-size:42px;font-weight:800;letter-spacing:12px;font-family:'Courier New',monospace;">{{ otp_code }}</div>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:8px 40px 24px;">
        <div style="display:inline-block;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#f59e0b;font-size:13px;">&#9889; This code expires in <strong>{{ expires_minutes }} minutes</strong></span>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <p style="color:#64748b;font-size:12px;margin:0;">If you did not request this code, please ignore this email or contact support.</p>
      </td></tr>

''' + footer())


# ─── 3. password_reset.html ─────────────────────────────────────────
# Uses {{ expires_hours }} to match the view context
write('password_reset.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(236,72,153,0.15),rgba(245,158,11,0.15));border:2px solid rgba(236,72,153,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128273;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Reset Your Password</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Hi {{ username }}, we received a request to reset your password. Click below to choose a new one.</p>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <a href="{{ reset_url }}" style="display:inline-block;background:linear-gradient(135deg,#ec4899,#8b5cf6);color:#ffffff;text-decoration:none;padding:16px 48px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(236,72,153,0.3);">Reset Password &#8594;</a>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 12px;">
        <div style="display:inline-block;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#f59e0b;font-size:13px;">&#128337; This link expires in <strong>{{ expires_hours }} hour{{ expires_hours|pluralize }}</strong></span>
        </div>
      </td></tr>
      <tr><td style="padding:12px 40px 8px;">
        <p style="color:#94a3b8;font-size:12px;margin:0;">Or copy this link:</p>
        <p style="color:#64748b;font-size:11px;word-break:break-all;background:#0f172a;border-radius:8px;padding:10px;margin:6px 0 0;border:1px solid #1e293b;">{{ reset_url }}</p>
      </td></tr>
      <tr><td style="text-align:center;padding:12px 40px 32px;">
        <div style="display:inline-block;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#ef4444;font-size:12px;">&#9888;&#65039; If you did not request this, your account is still secure. No action needed.</span>
        </div>
      </td></tr>

''' + footer())


# ─── 4. subscription_confirmation.html ──────────────────────────────
# Context: username, technology, plan_name, amount, expiry_date, scenarios_url
write('subscription_confirmation.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(6,182,212,0.15));border:2px solid rgba(16,185,129,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#127881;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Subscription Confirmed!</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Hi {{ username }}, your subscription is now active. You have full access to all scenarios in your plan.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;overflow:hidden;">
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Technology</td>
              <td style="color:#06b6d4;font-size:14px;font-weight:700;text-align:right;">{{ technology }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Plan</td>
              <td style="color:#8b5cf6;font-size:14px;font-weight:700;text-align:right;">{{ plan_name }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Amount</td>
              <td style="color:#10b981;font-size:14px;font-weight:700;text-align:right;">{{ amount }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Valid Until</td>
              <td style="color:#f59e0b;font-size:14px;font-weight:700;text-align:right;">{{ expiry_date }}</td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <div style="background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(6,182,212,0.08));border:1px solid rgba(16,185,129,0.2);border-radius:12px;padding:16px 20px;text-align:center;">
          <span style="color:#10b981;font-size:14px;font-weight:600;">&#9989; You now have access to all {{ technology }} scenarios</span>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <a href="{{ scenarios_url }}" style="display:inline-block;background:linear-gradient(135deg,#10b981,#06b6d4);color:#ffffff;text-decoration:none;padding:16px 48px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(16,185,129,0.3);">Browse Scenarios &#8594;</a>
      </td></tr>

''' + footer())


# ─── 5. subscription_admin_notification.html ─────────────────────────
# Context: username, email, technology, plan_name, amount, payment_id, payment_date, admin_url
write('subscription_admin_notification.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(239,68,68,0.15));border:2px solid rgba(245,158,11,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128176;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">New Subscription &#127881;</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">A new technology subscription has been created on FixitLab.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;overflow:hidden;">
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">User</td>
              <td style="color:#ffffff;font-size:14px;font-weight:600;text-align:right;">{{ username }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Email</td>
              <td style="color:#06b6d4;font-size:14px;text-align:right;">{{ email }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Technology</td>
              <td style="color:#8b5cf6;font-size:14px;font-weight:700;text-align:right;">{{ technology }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Plan</td>
              <td style="color:#f59e0b;font-size:14px;font-weight:700;text-align:right;">{{ plan_name }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Amount</td>
              <td style="color:#10b981;font-size:14px;font-weight:700;text-align:right;">{{ amount }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Subscription ID</td>
              <td style="color:#06b6d4;font-size:13px;font-family:'Courier New',monospace;text-align:right;">{{ subscription_id }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;">
            <table width="100%"><tr>
              <td style="color:#94a3b8;font-size:13px;">Date</td>
              <td style="color:#cbd5e1;font-size:14px;text-align:right;">{{ payment_date }}</td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <p style="color:#64748b;font-size:12px;margin:0;">This is an automated notification from FixitLab.</p>
      </td></tr>

''' + footer())


# ─── 6. achievement.html ────────────────────────────────────────────
# Context: username, achievement_icon, achievement_name, achievement_description, dashboard_url
write('achievement.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(234,179,8,0.15));border:2px solid rgba(245,158,11,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#127942;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Achievement Unlocked!</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Congratulations {{ username }}! You&#8217;ve earned a new achievement.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" style="background:linear-gradient(135deg,#1e293b,#0f172a);border-radius:16px;border:1px solid rgba(245,158,11,0.2);overflow:hidden;">
          <tr><td style="text-align:center;padding:32px 24px;">
            <div style="font-size:56px;margin-bottom:16px;">{{ achievement_icon }}</div>
            <div style="color:#f59e0b;font-size:22px;font-weight:700;margin-bottom:8px;">{{ achievement_name }}</div>
            <div style="color:#94a3b8;font-size:14px;line-height:1.5;">{{ achievement_description }}</div>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 16px;">
        <div style="display:inline-block;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#f59e0b;font-size:13px;">&#11088; Keep going to unlock more badges!</span>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <a href="{{ dashboard_url }}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b,#ec4899);color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(245,158,11,0.3);">View Your Achievements &#8594;</a>
      </td></tr>

''' + footer())


# ─── 7. lab_completed.html ──────────────────────────────────────────
# Context: username, scenario_title, score, time_taken, hints_used, scenarios_url
# Using table layout instead of flexbox (Outlook doesn't support flex)
write('lab_completed.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(16,185,129,0.15),rgba(6,182,212,0.15));border:2px solid rgba(16,185,129,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#127881;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Challenge Solved!</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Great job {{ username }}! You successfully completed <strong style="color:#06b6d4;">{{ scenario_title }}</strong>.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;overflow:hidden;">
          <tr>
            <td style="width:33.3%;text-align:center;padding:20px 12px;border-right:1px solid #1e293b;">
              <div style="color:#f59e0b;font-size:30px;font-weight:800;">{{ score }}</div>
              <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Score</div>
            </td>
            <td style="width:33.3%;text-align:center;padding:20px 12px;border-right:1px solid #1e293b;">
              <div style="color:#06b6d4;font-size:30px;font-weight:800;">{{ time_taken }}</div>
              <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Time</div>
            </td>
            <td style="width:33.3%;text-align:center;padding:20px 12px;">
              <div style="color:#8b5cf6;font-size:30px;font-weight:800;">{{ hints_used }}</div>
              <div style="color:#94a3b8;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-top:4px;">Hints</div>
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 16px;">
        <div style="display:inline-block;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#10b981;font-size:13px;">&#9989; Your progress has been saved to the leaderboard</span>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <a href="{{ scenarios_url }}" style="display:inline-block;background:linear-gradient(135deg,#06b6d4,#3b82f6);color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(6,182,212,0.3);">Try More Challenges &#8594;</a>
      </td></tr>

''' + footer())


# ─── 8. lab_expired.html ────────────────────────────────────────────
# Context: username, scenario_title, duration_minutes, scenario_url
write('lab_expired.html', header() + '''
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(239,68,68,0.15));border:2px solid rgba(245,158,11,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#9200;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Lab Session Expired</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Hi {{ username }}, your lab session for <strong style="color:#06b6d4;">{{ scenario_title }}</strong> has expired after {{ duration_minutes }} minutes.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" style="background:linear-gradient(135deg,rgba(245,158,11,0.06),rgba(239,68,68,0.06));border-radius:12px;border:1px solid rgba(245,158,11,0.2);border-left:4px solid #f59e0b;overflow:hidden;">
          <tr><td style="padding:20px 24px;">
            <div style="color:#f59e0b;font-size:15px;font-weight:700;margin-bottom:8px;">Don&#8217;t worry &#8212; you can try again!</div>
            <div style="color:#94a3b8;font-size:13px;line-height:1.6;">Each attempt creates a fresh environment. Use hints if you get stuck. Practice makes perfect!</div>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <a href="{{ scenario_url }}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b,#ef4444);color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(245,158,11,0.3);">Try Again &#8594;</a>
      </td></tr>

''' + footer())

print("\nAll 8 email templates written successfully!")
