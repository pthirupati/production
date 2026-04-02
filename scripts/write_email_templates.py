#!/usr/bin/env python3
"""Rewrite all 5 email templates with modern KodeKloud-inspired design."""
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), '..', 'backend', 'templates', 'emails')

# Shared components
LOGO_BLOCK = """<tr><td style="text-align:center;padding:24px 0 20px;">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto;"><tr>
      <td style="width:44px;height:44px;border-radius:12px;background:linear-gradient(135deg,#06b6d4,#8b5cf6);text-align:center;line-height:44px;"><span style="color:#fff;font-weight:800;font-size:20px;">F</span></td>
      <td style="padding-left:12px;"><span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.5px;">FixitLab</span></td>
    </tr></table>
  </td></tr>"""

FOOTER = """<tr><td style="padding:0 40px;"><div style="height:1px;background:linear-gradient(90deg,transparent,#1e293b,transparent);"></div></td></tr>
  <tr><td style="text-align:center;padding:24px 0 8px;">
    <p style="color:#334155;font-size:11px;margin:0;">&#169; 2025 FixitLab &#8212; Build. Break. Fix. Learn.</p>
    <p style="color:#1e293b;font-size:11px;margin:8px 0 0;">
      <a href="https://fixitlab.com/privacy" style="color:#475569;text-decoration:none;">Privacy</a> &#183;
      <a href="https://fixitlab.com/terms" style="color:#475569;text-decoration:none;">Terms</a> &#183;
      <a href="mailto:kubelearn464@gmail.com" style="color:#475569;text-decoration:none;">Support</a>
    </p>
  </td></tr>"""

GRADIENT_BAR = '<tr><td style="height:6px;background:linear-gradient(90deg,#06b6d4,#8b5cf6,#ec4899);"></td></tr>'

def wrap_email(title, card_content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{title}</title></head>
<body style="margin:0;padding:0;background-color:#0a0e1a;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#0a0e1a;padding:32px 16px;"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
  {LOGO_BLOCK}
  <tr><td>
    <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(180deg,#141b2d 0%,#1a2235 100%);border-radius:16px;border:1px solid #1e293b;overflow:hidden;">
      {GRADIENT_BAR}
      {card_content}
    </table>
  </td></tr>
  {FOOTER}
</table>
</td></tr></table>
</body></html>"""

# ── 1. Welcome ──────────────────────────────────────────────
welcome_card = """
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(6,182,212,0.15),rgba(139,92,246,0.15));border:2px solid rgba(6,182,212,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128640;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Welcome aboard, {{ username }}!</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Your account is ready. Start fixing broken servers, containers, and networks in real terminal environments.</p>
      </td></tr>
      <tr><td style="padding:0 32px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#128187;</div><div style="color:#06b6d4;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Hands-on Labs</div><div style="color:#64748b;font-size:12px;margin-top:4px;">Real Docker containers with pre-broken scenarios</div></td></tr></table></td>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#127942;</div><div style="color:#8b5cf6;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Compete</div><div style="color:#64748b;font-size:12px;margin-top:4px;">Earn scores, badges and climb the leaderboard</div></td></tr></table></td>
          </tr>
          <tr>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#9889;</div><div style="color:#10b981;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Real Terminal</div><div style="color:#64748b;font-size:12px;margin-top:4px;">Full bash shell in your browser via WebSocket</div></td></tr></table></td>
            <td style="padding:8px;width:50%;"><table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;padding:20px;"><tr><td style="text-align:center;"><div style="font-size:28px;margin-bottom:8px;">&#128274;</div><div style="color:#f59e0b;font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;">Safe Sandbox</div><div style="color:#64748b;font-size:12px;margin-top:4px;">Isolated environments &#8212; break anything safely</div></td></tr></table></td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 40px;">
        <a href="{{ scenarios_url }}" style="display:inline-block;background:linear-gradient(135deg,#06b6d4,#3b82f6);color:#ffffff;text-decoration:none;padding:16px 40px;border-radius:12px;font-weight:700;font-size:16px;box-shadow:0 4px 24px rgba(6,182,212,0.3);">Start Your First Challenge &#8594;</a>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#475569;font-size:12px;margin:0;">If you did not create this account, you can safely ignore this email.</p>
      </td></tr>
"""

# ── 2. OTP Verification ────────────────────────────────────
otp_card = """
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(139,92,246,0.15),rgba(236,72,153,0.15));border:2px solid rgba(139,92,246,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128272;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">Verify Your Email</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">Hi {{ username }}, use the code below to verify your email address and activate your FixitLab account.</p>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 12px;">
        <div style="display:inline-block;background:linear-gradient(135deg,rgba(6,182,212,0.08),rgba(139,92,246,0.08));border:2px dashed rgba(6,182,212,0.4);border-radius:16px;padding:24px 48px;">
          <div style="color:#06b6d4;font-size:42px;font-weight:800;letter-spacing:12px;font-family:'Courier New',monospace;">{{ otp_code }}</div>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:8px 40px 24px;">
        <div style="display:inline-block;background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#f59e0b;font-size:13px;">&#9889; This code expires in <strong>{{ expiry_minutes }} minutes</strong></span>
        </div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <p style="color:#475569;font-size:12px;margin:0;">If you did not request this code, please ignore this email or contact support.</p>
      </td></tr>
"""

# ── 3. Password Reset ──────────────────────────────────────
password_reset_card = """
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
          <span style="color:#f59e0b;font-size:13px;">&#128337; This link expires in <strong>{{ expiry_hours }} hours</strong></span>
        </div>
      </td></tr>
      <tr><td style="padding:12px 40px 8px;">
        <p style="color:#64748b;font-size:12px;margin:0;">Or copy this link:</p>
        <p style="color:#475569;font-size:11px;word-break:break-all;background:#0f172a;border-radius:8px;padding:10px;margin:6px 0 0;border:1px solid #1e293b;">{{ reset_url }}</p>
      </td></tr>
      <tr><td style="text-align:center;padding:12px 40px 32px;">
        <div style="display:inline-block;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);border-radius:8px;padding:10px 20px;">
          <span style="color:#ef4444;font-size:12px;">&#9888;&#65039; If you did not request this, your account is still secure. No action needed.</span>
        </div>
      </td></tr>
"""

# ── 4. Subscription Confirmation ────────────────────────────
subscription_card = """
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
              <td style="color:#64748b;font-size:13px;">Technology</td>
              <td style="color:#06b6d4;font-size:14px;font-weight:700;text-align:right;">{{ technology }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Plan</td>
              <td style="color:#8b5cf6;font-size:14px;font-weight:700;text-align:right;">{{ plan_name }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Amount</td>
              <td style="color:#10b981;font-size:14px;font-weight:700;text-align:right;">{{ amount }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Valid Until</td>
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
"""

# ── 5. Subscription Admin Notification ──────────────────────
admin_card = """
      <tr><td style="text-align:center;padding:40px 40px 16px;">
        <div style="display:inline-block;width:72px;height:72px;border-radius:50%;background:linear-gradient(135deg,rgba(245,158,11,0.15),rgba(239,68,68,0.15));border:2px solid rgba(245,158,11,0.3);line-height:72px;text-align:center;"><span style="font-size:36px;">&#128176;</span></div>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 8px;">
        <h1 style="color:#ffffff;font-size:26px;font-weight:700;margin:0;">New Subscription</h1>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 24px;">
        <p style="color:#94a3b8;font-size:15px;line-height:1.6;margin:0;">A new subscription payment has been received. Details below.</p>
      </td></tr>
      <tr><td style="padding:0 40px 24px;">
        <table width="100%" style="background:#0f172a;border-radius:12px;border:1px solid #1e293b;overflow:hidden;">
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">User</td>
              <td style="color:#ffffff;font-size:14px;font-weight:600;text-align:right;">{{ username }} ({{ email }})</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Technology</td>
              <td style="color:#06b6d4;font-size:14px;font-weight:700;text-align:right;">{{ technology }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Plan</td>
              <td style="color:#8b5cf6;font-size:14px;font-weight:700;text-align:right;">{{ plan_name }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Amount</td>
              <td style="color:#10b981;font-size:14px;font-weight:700;text-align:right;">{{ amount }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;border-bottom:1px solid #1e293b;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Payment ID</td>
              <td style="color:#f59e0b;font-size:13px;font-weight:600;text-align:right;font-family:'Courier New',monospace;">{{ payment_id }}</td>
            </tr></table>
          </td></tr>
          <tr><td style="padding:16px 20px;">
            <table width="100%"><tr>
              <td style="color:#64748b;font-size:13px;">Date</td>
              <td style="color:#94a3b8;font-size:14px;text-align:right;">{{ payment_date }}</td>
            </tr></table>
          </td></tr>
        </table>
      </td></tr>
      <tr><td style="text-align:center;padding:0 40px 32px;">
        <a href="{{ admin_url }}" style="display:inline-block;background:linear-gradient(135deg,#f59e0b,#ef4444);color:#ffffff;text-decoration:none;padding:14px 40px;border-radius:12px;font-weight:700;font-size:15px;box-shadow:0 4px 24px rgba(245,158,11,0.3);">View in Admin Panel &#8594;</a>
      </td></tr>
"""

# Write all templates
templates = {
    'welcome.html': wrap_email('Welcome to FixitLab', welcome_card),
    'otp_verification.html': wrap_email('Verify Your Email - FixitLab', otp_card),
    'password_reset.html': wrap_email('Reset Your Password - FixitLab', password_reset_card),
    'subscription_confirmation.html': wrap_email('Subscription Confirmed - FixitLab', subscription_card),
    'subscription_admin_notification.html': wrap_email('New Subscription - FixitLab Admin', admin_card),
}

os.makedirs(TEMPLATE_DIR, exist_ok=True)
for name, content in templates.items():
    path = os.path.join(TEMPLATE_DIR, name)
    with open(path, 'w') as f:
        f.write(content)
    print(f"  [OK] {name} ({len(content)} bytes)")

print(f"\nAll {len(templates)} email templates rewritten successfully!")
