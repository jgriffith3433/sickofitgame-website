import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"
SITE_NAME = os.environ.get("SITE_NAME", "Sick Of It")
SITE_URL = os.environ.get("SITE_URL", "https://localhost")


def send_access_code_email(to_email, access_code, product_id="default"):
    """Send an access code to the buyer via email."""
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP credentials not configured, skipping email send")
        return False

    redeem_url = f"{SITE_URL}/paywall/redeem?code={access_code}&product={product_id}"

    subject = f"Your {SITE_NAME} Access Code"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #0a0a0a; color: #e0e0e0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background-color: #1a1a2e; border-radius: 12px; padding: 40px; border: 1px solid #333; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            .header h1 {{ color: #ff6b35; margin: 0; font-size: 28px; }}
            .code-box {{ background-color: #16213e; border: 2px solid #ff6b35; border-radius: 8px; padding: 20px; text-align: center; margin: 25px 0; }}
            .code {{ font-family: 'Courier New', monospace; font-size: 14px; color: #00ff88; word-break: break-all; letter-spacing: 1px; }}
            .btn {{ display: inline-block; background-color: #ff6b35; color: #ffffff; padding: 14px 32px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 16px; margin: 15px 0; }}
            .warning {{ background-color: #2a1a0a; border-left: 4px solid #ff6b35; padding: 15px; margin: 20px 0; border-radius: 0 8px 8px 0; }}
            .footer {{ text-align: center; margin-top: 30px; color: #888; font-size: 12px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{SITE_NAME}</h1>
                <p>Thank you for your purchase!</p>
            </div>
            
            <p>Here is your access code:</p>
            
            <div class="code-box">
                <div class="code">{access_code}</div>
            </div>
            
            <div style="text-align: center;">
                <a href="{redeem_url}" class="btn">Activate Access Now</a>
            </div>
            
            <div class="warning">
                <strong>Info:</strong>
                <ul style="margin: 8px 0; padding-left: 20px;">
                    <li>Use this code to unlock access.</li>
                    <li>After activation, a secure cookie will keep you logged in.</li>
                    <li>If you clear your cookies or switch browsers, just use the code again.</li>
                    <li>Want to share this code with a friend? Go for it. That's your call.</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>If you did not make this purchase, please ignore this email.</p>
                <p>&copy; {SITE_NAME}</p>
            </div>
        </div>
    </body>
    </html>
    """

    text_body = f"""
{SITE_NAME} - Your Access Code

Thank you for your purchase!

Your access code: {access_code}

Click here to activate: {redeem_url}

INFO:
- Use this code to unlock access.
- After activation, a secure cookie will keep you logged in.
- If you clear your cookies or switch browsers, just use the code again.
- Want to share this code with a friend? Go for it. That's your call.

If you did not make this purchase, please ignore this email.
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = to_email

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30)

        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()

        logger.info("Access code email sent to %s", to_email)
        return True
    except smtplib.SMTPAuthenticationError as e:
        logger.error("SMTP authentication failed: %s", e)
        return False
    except smtplib.SMTPRecipientsRefused as e:
        logger.error("Recipient refused: %s", e)
        return False
    except smtplib.SMTPException as e:
        logger.error("SMTP error sending email: %s", e)
        return False
    except Exception as e:
        logger.error("Unexpected error sending email: %s", e)
        return False
