import smtplib
import os
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

def _send_email_task(to_email: str, subject: str, body_html: str):
    """Internal helper to connect to SMTP and send email synchronously in a thread."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print("[SMTP WARN] SMTP_EMAIL or SMTP_PASSWORD is not set in environment variables. Email skipped.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"CuraTera Security <{SMTP_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=12) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())

        print(f"[SMTP SUCCESS] Email successfully sent to {to_email}")
        return True
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send email to {to_email}: {e}")
        return False

def send_email_async(to_email: str, subject: str, body_html: str):
    """Sends email in background thread to prevent blocking API responses."""
    thread = threading.Thread(target=_send_email_task, args=(to_email, subject, body_html))
    thread.daemon = True
    thread.start()

def get_base_template(content_html: str) -> str:
    """Standard professional email wrapper with CuraTera branding."""
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>CuraTera</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background-color: #f1f5f9;
                margin: 0;
                padding: 30px 10px;
                -webkit-font-smoothing: antialiased;
            }}
            .email-wrapper {{
                max-width: 560px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
                border: 1px solid #e2e8f0;
            }}
            .brand-header {{
                background-color: #0A2540;
                padding: 32px 24px;
                text-align: center;
                border-bottom: 3px solid #0284c7;
            }}
            .brand-logo-text {{
                color: #ffffff;
                font-size: 26px;
                font-weight: 800;
                letter-spacing: 1px;
                margin: 0;
            }}
            .brand-tagline {{
                color: #94a3b8;
                font-size: 12px;
                margin-top: 4px;
                font-weight: 500;
                letter-spacing: 0.5px;
            }}
            .email-body {{
                padding: 32px 28px;
                color: #1e293b;
                font-size: 15px;
                line-height: 1.65;
            }}
            .greeting {{
                font-size: 18px;
                font-weight: 700;
                color: #0f172a;
                margin-top: 0;
                margin-bottom: 16px;
            }}
            .footer {{
                background-color: #f8fafc;
                padding: 20px;
                text-align: center;
                border-top: 1px solid #f1f5f9;
                font-size: 12px;
                color: #64748b;
            }}
            .footer-links {{
                margin-top: 8px;
                color: #94a3b8;
            }}
            .badge-secure {{
                display: inline-block;
                background: #ecfdf5;
                color: #047857;
                border: 1px solid #a7f3d0;
                border-radius: 20px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: 600;
                margin-bottom: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="email-wrapper">
            <div class="brand-header">
                <h1 class="brand-logo-text">CuraTera</h1>
                <div class="brand-tagline">Empowering Citizens, Seamlessly</div>
            </div>
            <div class="email-body">
                {content_html}
            </div>
            <div class="footer">
                <div style="font-weight: 600; color: #475569;">CuraTera Platform &copy; 2026</div>
                <div class="footer-links">Powered by Avensoft &bull; Encrypted & Secure</div>
                <div style="margin-top: 10px; font-size: 11px; color: #cbd5e1;">This is an automated system email. Please do not reply directly.</div>
            </div>
        </div>
    </body>
    </html>
    """

def send_welcome_email(to_email: str, user_name: str):
    """Sends a professional welcome email upon new user registration."""
    subject = "Welcome to CuraTera! 🌿 Your Account is Ready"
    content = f"""
    <div class="badge-secure">✓ Account Verified & Created</div>
    <div class="greeting">Welcome aboard, {user_name}!</div>
    <p>Thank you for joining <strong>CuraTera</strong> — your trusted digital assistant for government schemes, citizen welfare, and entitlement tracking.</p>
    <p>With your new account, you can:</p>
    <ul style="padding-left: 20px; color: #334155; line-height: 1.8;">
        <li><strong>Smart Scheme Matching:</strong> Instantly discover eligible central & state government schemes.</li>
        <li><strong>Voice & RAG AI Assistance:</strong> Ask questions in Hindi or English and get accurate policy details.</li>
        <li><strong>Document Vault:</strong> Safely upload and manage required certificates.</li>
    </ul>
    <div style="margin-top: 28px; padding: 16px; background-color: #f0f9ff; border-left: 4px solid #0284c7; border-radius: 6px; font-size: 14px; color: #0369a1;">
        <strong>Quick Tip:</strong> Keep your profile details (income, state, category) updated to get the most accurate scheme recommendations!
    </div>
    <p style="margin-top: 24px;">If you ever have questions or need assistance, our support team is always here to help.</p>
    """
    body_html = get_base_template(content)
    send_email_async(to_email, subject, body_html)

def send_otp_email(to_email: str, otp_code: str, purpose: str = "Password Reset"):
    """Sends a high-security OTP email for verification or password reset."""
    subject = f"{otp_code} is your CuraTera Verification Code"
    content = f"""
    <div class="greeting">Security Verification Request</div>
    <p>You requested a 6-digit One-Time Password (OTP) for <strong>{purpose}</strong> on your CuraTera account (<code>{to_email}</code>).</p>
    
    <div style="background: linear-gradient(135deg, #0A2540 0%, #1e3a8a 100%); border-radius: 12px; padding: 24px; text-align: center; margin: 24px 0; color: #ffffff; box-shadow: 0 4px 15px rgba(10, 37, 64, 0.15);">
        <div style="font-size: 11px; text-transform: uppercase; letter-spacing: 2px; color: #93c5fd; margin-bottom: 8px; font-weight: 700;">YOUR VERIFICATION CODE</div>
        <div style="font-size: 38px; font-weight: 800; letter-spacing: 10px; color: #ffffff; text-shadow: 0 2px 4px rgba(0,0,0,0.2);">{otp_code}</div>
        <div style="font-size: 12px; color: #cbd5e1; margin-top: 10px; font-weight: 500;">⏱ Valid for 10 Minutes Only</div>
    </div>

    <p style="font-size: 13.5px; color: #64748b;">For security reasons, do not share this verification code with anyone, including CuraTera support personnel.</p>
    <div style="margin-top: 20px; padding: 12px 16px; background-color: #fffbebf4; border: 1px solid #fde68a; border-radius: 8px; font-size: 13px; color: #92400e;">
        ⚠️ If you did not request this code, your account is safe — simply ignore this message.
    </div>
    """
    body_html = get_base_template(content)
    send_email_async(to_email, subject, body_html)

def send_account_deleted_email(to_email: str, user_name: str = "User"):
    """Sends a professional notification email when a user account is deleted."""
    subject = "Notice: Your CuraTera Account Has Been Removed"
    content = f"""
    <div style="display: inline-block; background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; border-radius: 20px; padding: 4px 12px; font-size: 11px; font-weight: 600; margin-bottom: 16px;">Notice of Account Deletion</div>
    <div class="greeting">Hello {user_name},</div>
    <p>This email confirms that your CuraTera account associated with <strong>{to_email}</strong> has been permanently removed from our system.</p>
    <p>All your associated profile data, stored documents, and application history have been wiped in compliance with our data privacy guidelines.</p>
    <div style="margin-top: 24px; padding: 16px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 13.5px; color: #475569;">
        If you wish to use CuraTera services again in the future, you are welcome to register a new account at any time.
    </div>
    <p style="margin-top: 20px; font-size: 13px; color: #64748b;">If this action was not initiated by you, please contact support immediately.</p>
    """
    body_html = get_base_template(content)
    send_email_async(to_email, subject, body_html)
