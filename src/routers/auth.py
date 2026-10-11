import hmac
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_babel import _
from src.config import Settings

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/admin-secret-login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username') or ''
        password = request.form.get('password') or ''
        
        if (
            hmac.compare_digest(username, Settings.ADMIN_USERNAME) and
            hmac.compare_digest(password, Settings.ADMIN_PASSWORD)
        ):
            session['is_admin'] = True
            flash(_('Login successful!'), 'success')
            return redirect(url_for('dashboard_home.index'))
        else:
            flash(_('Invalid username or password.'), 'error')
            
    return render_template('dashboard/login.html')

@auth_bp.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash(_('You have been logged out.'), 'info')
    return redirect(url_for('shops.index'))
