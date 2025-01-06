from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from models import User, db
import jwt
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user, remember=True)
            user.is_online = True
            db.session.commit()
            return redirect(url_for('chat'))
        flash('Invalid email or password')
    return render_template('login.html')

@auth_bp.route('/test-login', methods=['POST'])
def test_login():
    # Create test user if doesn't exist
    email = 'silas.pusateri@gauntletAI.com'
    test_user = User.query.filter_by(email=email).first()

    if not test_user:
        test_user = User(
            username='silas',
            email=email
        )
        test_user.set_password('test')
        db.session.add(test_user)
        db.session.commit()

    # Log in the test user
    login_user(test_user, remember=True)
    test_user.is_online = True
    db.session.commit()

    return redirect(url_for('chat'))

@auth_bp.route('/logout')
@login_required
def logout():
    current_user.is_online = False
    db.session.commit()
    logout_user()
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = User(
            username=request.form.get('username'),
            email=request.form.get('email')
        )
        user.set_password(request.form.get('password'))
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('auth.login'))
    return render_template('login.html', register=True)