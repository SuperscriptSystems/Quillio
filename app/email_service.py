from flask import url_for, render_template_string, current_app
from app.configuration import app
import smtplib
import ssl
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_verification_email(user):
    """Send email verification email using SMTP with App Password"""
    try:
        # Use existing verification code (should already be generated)
        verification_code = user.verification_token
        
        if not verification_code:
            logging.error(f"No verification code found for user {user.email}")
            return False
            
        # Print verification code to console for development
        print(f"\n=== DEVELOPMENT MODE ===")
        print(f"Verification code for {user.email}: {verification_code}")
        print("======================\n")
        
        # Get SMTP configuration from environment variables
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        port = int(os.getenv('MAIL_PORT', 587))
        sender_email = os.getenv('MAIL_USERNAME')
        app_password = os.getenv('MAIL_PASSWORD')
        
        if not all([smtp_server, sender_email, app_password]):
            logging.warning("Email configuration is incomplete. Please check your environment variables.")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Verify Your Quillio Account"
        msg['From'] = sender_email
        msg['To'] = user.email
        
        # Email content
        html = f"""
        <!DOCTYPE html>
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
                    font-size: 24px; 
                    font-weight: bold; 
                    margin: 20px 0;
                    border-radius: 5px;
                }}
                .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #eee; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Quillio!</h1>
                </div>
                <div class="content">
                    <p>Thank you for registering. Please use the following verification code to verify your email address:</p>
                    <div class="verification-code">{verification_code}</div>
                    <p>This code will expire in 24 hours.</p>
                    <p>If you didn't create an account with Quillio, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p> 2025 Quillio. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply to this message.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach both HTML and plain text versions
        part1 = MIMEText(f"Your verification code is: {verification_code}", 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Connect to server and send email with TLS
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
        
        logging.info(f"Verification email sent to {user.email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"SMTP authentication failed: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"Error sending verification email: {str(e)}")
        return False

def send_resend_verification_email(user):
    """Resend verification email to user"""
    return send_verification_email(user)

def send_password_reset_email(user, reset_code):
    """Send password reset email with verification code"""
    try:
        # Get SMTP configuration from environment variables
        smtp_server = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        port = int(os.getenv('MAIL_PORT', 587))
        sender_email = os.getenv('MAIL_USERNAME')
        app_password = os.getenv('MAIL_PASSWORD')
        
        if not all([smtp_server, sender_email, app_password]):
            logging.warning("Email configuration is incomplete. Please check your environment variables.")
            return False
        
        # Get the absolute path to the template
        template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates', 'reset_password_email.html')
        
        # Read the template content
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
        except Exception as e:
            logging.error(f"Failed to read email template: {str(e)}")
            return False
        
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Password Reset Verification - Quillio"
        msg['From'] = sender_email
        msg['To'] = user.email
        
        # Render email template with verification code
        html = render_template_string(
            template_content,
            user=user,
            reset_code=reset_code
        )
        
        # Create plain text version
        text = f"""
        Password Reset Verification - Quillio
        -----------------------------------
        
        Hello{user.full_name if user.full_name else ''},
        
        We received a request to reset the password for your Quillio account.
        
        Your verification code is: {reset_code}
        
        Enter this code in the password reset form to verify your identity.
        
        This code will expire in 1 hour for security reasons.
        
        If you didn't request this, please ignore this email.
        """
        
        # Attach both HTML and plain text versions
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Create secure connection with server and send email
        with smtplib.SMTP(smtp_server, port) as server:
            server.starttls()
            server.login(sender_email, app_password)
            server.send_message(msg)
            
        logging.info(f"Password reset verification email sent to {user.email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"SMTP authentication failed: {str(e)}")
        return False
    except Exception as e:
        logging.error(f"Failed to send password reset email to {user.email}: {str(e)}")
        import traceback
        logging.error(traceback.format_exc())
        return False
