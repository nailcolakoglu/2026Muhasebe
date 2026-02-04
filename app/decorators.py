# app/decorators.py

from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user

def permission_required(permission):
    """
    Route'u yetkiye göre korur.
    Kullanım: @permission_required('fatura.delete')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Login değilse login'e at
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            
            # 2. Yetki kontrolü (User modelindeki can metodunu çağırır)
            if not current_user.can(permission):
                flash(f"⛔ Bu işlem için yetkiniz yok! (Gereken: {permission})", "danger")
                # Geldiği yere geri gönder, yoksa ana sayfaya
                return redirect(request.referrer or url_for('main.index'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator