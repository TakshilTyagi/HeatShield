import os
from flask import Flask, render_template, session, request
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from database import init_db, seed_db
from translations import get_text
from routes.auth import auth_bp
from routes.resident import resident_bp
from routes.volunteer import volunteer_bp
from routes.admin import admin_bp
from routes.api import api_bp

def create_app():
    """Application factory for HeatShield."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable ProxyFix to correctly handle HTTPS behind AWS App Runner load balancer
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1
    )

    # Initialize SQLite database and seed demo data on first run
    init_db()
    seed_db(pass_level=2)

    # Health check endpoint for AWS App Runner
    @app.route("/health")
    def health_check():
        return {"status": "ok", "service": "heatshield"}, 200

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(resident_bp, url_prefix="/resident")
    app.register_blueprint(volunteer_bp, url_prefix="/volunteer")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Global template context processor for translation, active role, and city settings
    @app.context_processor
    def inject_globals():
        lang = session.get("lang", "en")
        large_text = session.get("large_text", False)
        user_city = session.get("city_name") or "Your City"
        return {
            "t": lambda key: get_text(key, lang),
            "current_lang": lang,
            "large_text": large_text,
            "city_name": user_city,
            "current_user_role": session.get("role"),
            "current_user_name": session.get("name"),
            "current_user_city_id": session.get("city_id")
        }

    # Error handling pages (clean, informative, no crashes)
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template("500.html"), 500

    return app

app = create_app()

if __name__ == "__main__":
    print("==================================================================")
    print(" HEATSHIELD PAN-INDIA HEATWAVE RESPONSE NETWORK")
    print(" Active Climate Zones: Plains, Coastal, Hill")
    print(" Demo Logins:")
    print("   • Super Admin (All India): username 'superadmin'    / password 'admin123'")
    print("   • Bareilly Ward Admin:     username 'admin'         / password 'admin123'")
    print("   • Jaipur Ward Admin:       username 'admin_jaipur'  / password 'admin123'")
    print("   • Volunteer (Bareilly):    username 'vol_amit'      / password 'vol123'")
    print("   • Volunteer (Jaipur):      username 'vol_vikram'    / password 'vol123'")
    print("   • Resident (Ram Prasad):   username 'res_ram'       / password 'res123' (Unchecked High-Risk)")
    print("   • Resident (Shanti Devi):  username 'res_shanti'    / password 'res123' (Ready to check in)")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    print(f" Server starting on http://0.0.0.0:{port} (debug={debug}) ...")
    print("==================================================================")
    app.run(host="0.0.0.0", port=port, debug=debug)
