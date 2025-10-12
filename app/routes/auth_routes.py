from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from flask_wtf.csrf import generate_csrf
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import secrets
from app.configuration import app, db
from app.forms import LoginForm, RegistrationForm, VerificationForm, ForgotPasswordForm, ResetPasswordForm
from app.email_service import send_verification_email, send_password_reset_email
from app.models import User

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if not user.is_verified:
                flash('Please verify your email before logging in. Check your inbox for the verification code.', 'warning')
                return redirect(url_for('auth.verify_code', email=form.email.data))
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('course.course_dashboard'))
        flash('Invalid email or password. Please try again.', 'danger')
    return render_template('login.html', title='Login', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        lesson_length = request.form.get('lesson_length')
        age = request.form.get('age')
        bio = request.form.get('bio')

        if not email or not password or not full_name or not lesson_length:
            flash('Please fill in all required fields.', 'warning')
            return redirect(url_for('auth.register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists.', 'warning')
            return redirect(url_for('auth.register'))

        try:
            lesson_length_val = int(lesson_length)
        except (TypeError, ValueError):
            flash('Lesson length must be a number.', 'warning')
            return redirect(url_for('auth.register'))

        new_user = User(
            email=email,
            full_name=full_name.strip(),
            preferred_lesson_length=lesson_length_val,
            age=int(age) if age else None,
            bio=bio
        )
        new_user.set_password(password)
        new_user.generate_verification_code()

        db.session.add(new_user)
        db.session.commit()

        if send_verification_email(new_user):
            flash('Registration successful! Please check your email for a 6-digit verification code.', 'success')
            return redirect(url_for('auth.verify_code', email=email))
        else:
            flash('Registration successful, but we could not send the verification email. Please contact support.', 'warning')
            return redirect(url_for('auth.login'))
    return render_template('register.html')


@auth_bp.route('/verify_code', methods=['GET', 'POST'])
def verify_code():
    form = VerificationForm()
    email = request.args.get('email')
    if email:
        form.email.data = email
    if form.validate_on_submit():
        email = form.email.data
        verification_code = form.verification_code.data
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Invalid verification request.', 'danger')
            return redirect(url_for('auth.login'))
        if user.is_verified:
            flash('Your email is already verified. You can log in.', 'info')
            return redirect(url_for('auth.login'))
        if user.verify_email_code(verification_code):
            db.session.commit()
            flash('Email verified successfully! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    return render_template('verify_code.html', email=email, verification_type='registration', form=form)


@auth_bp.route('/login_verify_code', methods=['GET', 'POST'])
def login_verify_code():
    form = VerificationForm()
    email = request.args.get('email')
    if email:
        form.email.data = email
    user = User.query.filter_by(email=email).first() if email else None
    if not user:
        flash('Invalid login request.', 'danger')
        return redirect(url_for('auth.login'))
    if form.validate_on_submit():
        verification_code = form.verification_code.data
        if user.verify_email_code(verification_code):
            db.session.commit()
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('course_dashboard'))
        else:
            flash('Invalid verification code. Please try again.', 'danger')
    return render_template('verify_code.html', email=email, verification_type='login', form=form)


@auth_bp.route('/resend_verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user and not user.is_verified:
            user.generate_verification_code()
            db.session.commit()
            send_verification_email(user)
            flash('Verification code sent! Please check your inbox.', 'success')
            return redirect(url_for('auth.verify_code', email=email))
        flash('If an account exists with this email, a verification code has been sent.', 'info')
        return redirect(url_for('auth.login'))
    email = current_user.email if current_user.is_authenticated else ''
    return render_template('resend_verification.html', email=email)


@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    resp = make_response(redirect(url_for('auth.login')))
    cookie_names = [
        'session',
        'remember_token',
        'session-',
        'flask',
        app.config.get('SESSION_COOKIE_NAME', 'session'),
        app.config.get('REMEMBER_COOKIE_NAME', 'remember_token')
    ]
    for name in cookie_names:
        resp.set_cookie(name, '', expires=0, path='/', httponly=True)
    cookie_domains = [None, app.config.get('SESSION_COOKIE_DOMAIN')]
    for domain in cookie_domains:
        resp.set_cookie(
            app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'),
            '',
            expires=0,
            path=app.config.get('REMEMBER_COOKIE_PATH', '/'),
            domain=domain,
            secure=app.config.get('REMEMBER_COOKIE_SECURE', False),
            httponly=True
        )
        resp.set_cookie(
            app.config.get('SESSION_COOKIE_NAME', 'session'),
            '',
            expires=0,
            path=app.config.get('SESSION_COOKIE_PATH', '/'),
            domain=domain,
            secure=app.config.get('SESSION_COOKIE_SECURE', False),
            httponly=True
        )
    logout_user()
    from flask import session as flask_session
    flask_session.clear()
    flash('You have been successfully logged out.', 'info')
    return resp


@auth_bp.route('/change_password', methods=['POST'])
@login_required
def change_password():
    from app.configuration import db
    # Check if user's email is verified
    if not current_user.is_verified:
        flash('Please verify your email before changing your password.', 'error')
        return redirect(url_for('course.settings'))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    # Validate current password
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'error')
        return redirect(url_for('course.settings'))

    # Validate new password
    if len(new_password) < 6:
        flash('New password must be at least 6 characters long.', 'error')
        return redirect(url_for('course.settings'))

    # Validate password confirmation
    if new_password != confirm_password:
        flash('New passwords do not match.', 'error')
        return redirect(url_for('course.settings'))

    # Update password
    current_user.set_password(new_password)
    db.session.commit()

    flash('Your password has been changed successfully!', 'success')
    return redirect(url_for('course.settings'))


@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    from app.configuration import db
    from app.models import User
    from app.forms import ForgotPasswordForm
    from app.email_service import send_password_reset_email
    
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    
    form = ForgotPasswordForm()
    
    if form.validate_on_submit():
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a 6-digit verification code
            reset_code = user.generate_password_reset_code()
            db.session.commit()
            
            # Send password reset email with verification code
            if send_password_reset_email(user, reset_code):
                # Store user email in session for verification
                session['reset_email'] = user.email
                flash('We\'ve sent a 6-digit verification code to your email. Please check your inbox.', 'info')
                return redirect(url_for('auth.verify_reset_code'))
            else:
                flash('Failed to send verification code. Please try again.', 'danger')
        else:
            # Don't reveal that the email doesn't exist for security reasons
            flash('If an account exists with this email, you will receive a verification code.', 'info')
            return redirect(url_for('auth.login'))
            
    return render_template('forgot_password.html', form=form)


@auth_bp.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    """Verify the password reset code and redirect to password reset if valid"""
    from app.configuration import db
    from app.models import User
    from app.forms import VerificationForm
    import secrets
    from datetime import datetime, timedelta
    
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    
    # Check if user has an active password reset request
    if 'reset_email' not in session:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        return redirect(url_for('auth.forgot_password'))
    
    user = User.query.filter_by(email=session['reset_email']).first()
    if not user:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        session.pop('reset_email', None)
        return redirect(url_for('auth.forgot_password'))
    
    form = VerificationForm()
    
    if form.validate_on_submit():
        code = form.verification_code.data
        
        if user.verify_reset_code(code):
            # Generate a one-time token for the actual password reset
            reset_token = secrets.token_urlsafe(32)
            user.reset_token = reset_token
            user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
            db.session.commit()
            
            # Store the token in the session for the next step
            session['reset_token'] = reset_token
            return redirect(url_for('auth.reset_password', token=reset_token))
        else:
            flash('Invalid or expired verification code. Please try again.', 'danger')
    
    # For GET requests or failed form validation
    return render_template('verify_code.html',
                         email=user.email,
                         verification_type='password_reset',
                         form=form)


@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    from app.configuration import db, app
    from app.models import User
    from app.forms import ResetPasswordForm
    from flask_wtf.csrf import generate_csrf
    from datetime import datetime
    
    if current_user.is_authenticated:
        return redirect(url_for('course.course_dashboard'))
    
    # Check if the token in the URL matches the one in the session
    if 'reset_token' not in session or session['reset_token'] != token:
        flash('Invalid or expired password reset request. Please try again.', 'danger')
        session.pop('reset_token', None)
        session.pop('reset_email', None)
        return redirect(url_for('auth.forgot_password'))
    
    # Get the user and verify the token is still valid
    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expires < datetime.utcnow():
        flash('The password reset link is invalid or has expired.', 'danger')
        session.pop('reset_token', None)
        session.pop('reset_email', None)
        return redirect(url_for('auth.forgot_password'))
    
    # Initialize the form
    form = ResetPasswordForm()
    
    if form.validate_on_submit():
        try:
            # Update password and clear reset token
            user.set_password(form.password.data)
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            
            # Clear the session
            session.pop('reset_token', None)
            session.pop('reset_email', None)
            
            flash('Your password has been reset successfully! You can now log in with your new password.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while resetting your password. Please try again.', 'danger')
            app.logger.error(f'Error resetting password: {str(e)}')
    
    # Generate CSRF token for the form
    csrf_token = generate_csrf()
    return render_template('reset_password.html', form=form, token=token, csrf_token=csrf_token)
