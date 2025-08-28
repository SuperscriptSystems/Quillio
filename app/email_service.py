from flask import url_for, render_template_string
from app.configuration import app
import smtplib
import ssl
import os
import logging

def send_verification_email(user):
    """Send email verification email using Gmail SMTP with App Password"""
    try:
        # Use existing verification code (should already be generated)
        verification_code = user.verification_token
        
        if not verification_code:
            logging.error(f"No verification code found for user {user.email}")
            return False
        
        # Gmail SMTP configuration
        port = 465  # For SSL
        smtp_server = "smtp.gmail.com"
        sender_email = "alex@shmulevich.com"
        app_password = os.environ.get("GMAIL_APP_PASSWORD")
        
        # For development/testing - if email is not configured, just log the code
        if not sender_email or not app_password:
            logging.warning(f"Gmail credentials not configured. Verification code for {user.email}: {verification_code}")
            print(f"DEVELOPMENT MODE - Verification code for {user.email}: {verification_code}")
            print("To enable email sending, set GMAIL_USERNAME and GMAIL_APP_PASSWORD environment variables")
            return True
        
        # Always show backup code
        print(f"BACKUP CODE - Verification code for {user.email}: {verification_code}")
        
        # Create HTML email message
        html_body = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Verify Your Email - Quillio</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f8f9fa; }}
        .verification-code {{ 
            display: inline-block; 
            padding: 20px 30px; 
            background-color: #007bff; 
            color: white; 
            font-size: 32px; 
            font-weight: bold; 
            letter-spacing: 8px; 
            border-radius: 8px; 
            margin: 20px 0; 
            font-family: 'Courier New', monospace;
        }}
        .code-container {{ text-align: center; margin: 30px 0; }}
        .footer {{ padding: 20px; text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Welcome to Quillio!</h1>
        </div>
        <div class="content">
            <h2>Verify Your Email Address</h2>
            <p>Hi {user.full_name or user.email},</p>
            <p>Thank you for registering with Quillio! To complete your registration and start creating personalized courses, please enter the following verification code:</p>
            
            <div class="code-container">
                <div class="verification-code">{verification_code}</div>
            </div>
            
            <p style="text-align: center; font-size: 18px; margin: 20px 0;">
                <strong>Your verification code: {verification_code}</strong>
            </p>
            
            <p><strong>This verification code will expire in 24 hours.</strong></p>
            <p>If you didn't create an account with Quillio, please ignore this email.</p>
        </div>
        <div class="footer">
            <p>© 2025 Quillio. All rights reserved.</p>
            <p>This is an automated email. Please do not reply to this message.</p>
        </div>
    </div>
</body>
</html>"""
        
        # Create email message
        message = f"""From: Quillio <{sender_email}>
To: {user.email}
Subject: Verify Your Email - Quillio
MIME-Version: 1.0
Content-Type: text/html; charset=utf-8

{html_body}"""
        
        # Send email using Gmail SMTP
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, port, context=context) as server:
                server.login(sender_email, app_password)
                server.sendmail(sender_email, user.email, message.encode('utf-8'))
                logging.info(f"Verification email sent successfully to {user.email}")
                print(f"[SUCCESS] Email sent successfully to {user.email}!")
                return True
                
        except smtplib.SMTPAuthenticationError as e:
            logging.error(f"Gmail authentication failed for {user.email}: {str(e)}")
            print(f"[ERROR] Authentication failed - Gmail rejected the App Password")
            print(f"Details: {e}")
            print("\nTroubleshooting:")
            print("1. Verify 2-Factor Authentication is enabled on your Gmail account")
            print("2. Generate a NEW App Password from Google Account Security")
            print("3. Make sure you're using the correct Gmail address")
            print("4. Check that the App Password has no spaces")
            print(f"FALLBACK - Verification code for {user.email}: {verification_code}")
            return True  # Return True so registration flow continues
            
        except Exception as e:
            logging.error(f"Gmail connection error for {user.email}: {str(e)}")
            print(f"[ERROR] Connection error: {e}")
            print(f"FALLBACK - Verification code for {user.email}: {verification_code}")
            return True  # Return True so registration flow continues
        
    except Exception as e:
        logging.error(f"Failed to send verification email to {user.email}: {str(e)}")
        print(f"FALLBACK - Verification code for {user.email}: {verification_code}")
        return True  # Return True so registration flow continues

def send_resend_verification_email(user):
    """Resend verification email to user"""
    return send_verification_email(user)
