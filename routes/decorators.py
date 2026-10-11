from functools import wraps
from flask import session, redirect, url_for, flash, request

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to access this page.", "warning")
                return redirect(url_for("auth.login", next=request.path))
            
            user_role = session.get("role")
            # super_admin can access admin pages as well
            effective_roles = set(allowed_roles)
            if "admin" in effective_roles and user_role == "super_admin":
                return f(*args, **kwargs)

            if user_role not in effective_roles:
                flash(f"Access denied: This page is restricted to {', '.join(allowed_roles)} accounts.", "danger")
                if user_role == "super_admin":
                    return redirect(url_for("admin.super_overview"))
                elif user_role == "admin":
                    return redirect(url_for("admin.dashboard"))
                elif user_role == "volunteer":
                    return redirect(url_for("volunteer.visits"))
                elif user_role == "resident":
                    return redirect(url_for("resident.dashboard"))
                return redirect(url_for("auth.home"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator
