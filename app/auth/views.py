from flask import render_template, redirect, request, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from . import auth
from .. import db
from ..models import User, Document
from .forms import LoginForm, RegistrationForm, EditProfileForm, ChangePasswordForm

@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        else:
            flash('无效的邮箱或密码')
    
    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        # 检查用户是否已存在
        if User.query.filter_by(email=form.email.data).first():
            flash('该邮箱已被注册')
            return render_template('auth/register.html', form=form)
        
        if User.query.filter_by(username=form.username.data).first():
            flash('该用户名已被使用')
            return render_template('auth/register.html', form=form)
        
        # 创建新用户
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('注册成功，请登录')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已成功退出登录')
    return redirect(url_for('main.index'))

@auth.route('/profile')
@login_required
def profile():
    latest_documents = Document.query.order_by(Document.created_at.desc()).limit(6).all()
    return render_template('auth/profile.html', documents=latest_documents)

@auth.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.email = form.email.data
        db.session.commit()
        flash('您的资料已更新')
        return redirect(url_for('auth.profile'))
    
    # Pre-populate form with current user data
    form.username.data = current_user.username
    form.email.data = current_user.email
    return render_template('auth/edit_profile.html', form=form)

@auth.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        # Check if old password is correct
        if not current_user.check_password(form.old_password.data):
            flash('当前密码不正确')
            return render_template('auth/change_password.html', form=form)
        
        # Check if new password and confirmation match
        if form.new_password.data != form.confirm_password.data:
            flash('新密码和确认密码不匹配')
            return render_template('auth/change_password.html', form=form)
        
        # Update password
        current_user.set_password(form.new_password.data)
        db.session.commit()
        flash('您的密码已更新')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html', form=form)
