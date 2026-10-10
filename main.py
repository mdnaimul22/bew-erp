import os
import sys
from flask_babel import Babel, _
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, send_from_directory, jsonify

basedir = os.path.abspath(os.path.dirname(__file__))
if basedir not in sys.path:
    sys.path.append(basedir)

# ── src imports ──────────────────────────────────────────────
from src.config import Settings, setup_logger, ensure_dir
logger = setup_logger(Settings.LOG_DIR / "app.log", name="bew.app")

from src.db.database import db
from src.extensions import limiter

from src.routers.sales import sales_bp
from src.routers.shops import shops_bp
from src.routers.buyers import buyers_bp
from src.routers.purchases import purchases_bp
from src.routers.inventory import inventory_bp
from src.routers.work_orders import work_orders_bp
from src.routers.core import core_bp
from src.helpers.utils import expand_designation, parse_contact_info

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
app.config.update(
    SECRET_KEY=Settings.SECRET_KEY,
    SQLALCHEMY_DATABASE_URI=Settings.DATABASE_URL,
    SQLALCHEMY_TRACK_MODIFICATIONS=Settings.SQLALCHEMY_TRACK_MODIFICATIONS,
    BABEL_DEFAULT_LOCALE=Settings.BABEL_DEFAULT_LOCALE,
    BABEL_TRANSLATION_DIRECTORIES=Settings.BABEL_TRANSLATION_DIRECTORIES,
    UPLOAD_FOLDER=str(Settings.UPLOAD_DIR),
    SALES_VOUCHER_FOLDER=str(Settings.SALES_VOUCHER_DIR),
    PURCHASE_VOUCHER_FOLDER=str(Settings.PURCHASE_VOUCHER_DIR),
    WORK_ORDER_FOLDER=str(Settings.WORK_ORDER_DIR),
    GALLERY_FOLDER=str(Settings.GALLERY_DIR),
)

# Ensure upload directories exist
for dir_path in (
    Settings.UPLOAD_DIR, Settings.SALES_VOUCHER_DIR,
    Settings.PURCHASE_VOUCHER_DIR, Settings.WORK_ORDER_DIR,
    Settings.GALLERY_DIR, Settings.UPLOAD_DIR / "visiting_card",
):
    ensure_dir(dir_path)

def get_locale():
    if 'lang' in session:
        return session['lang']
    return request.accept_languages.best_match(['bn', 'en'])

babel = Babel(app, locale_selector=get_locale)
limiter.init_app(app)

@limiter.request_filter
def _no_limit_static():
    return request.path.startswith('/static/')

from src.routers.auth import auth_bp
from src.routers.dashboard import dashboard_bp

# ── Extensions & Blueprints ──────────────────────────────────
db.init_app(app)

@app.before_request
def log_analytics():
    # Exclude static files and assets. Dashboard/API traffic is
    # high-volume internal use, not public-page analytics — skip it.
    excluded_prefixes = ['/static/', '/shop_img/', '/favicon.ico', '/robots.txt',
                         '/dashboard/', '/api/']
    if any(request.path.startswith(prefix) for prefix in excluded_prefixes):
        return
    
    try:
        db.log_visit(
            url=request.url,
            ip=request.remote_addr,
            user_agent=request.user_agent.string
        )
    except Exception as e:
        logger.warning(f"Failed to log visit: {e}")

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(buyers_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(shops_bp)
app.register_blueprint(work_orders_bp)
app.register_blueprint(purchases_bp)
app.register_blueprint(sales_bp)
app.register_blueprint(core_bp)

@app.route('/robots.txt')
def static_from_root():
    return send_from_directory(app.static_folder, request.path[1:])

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Resource not found'}), 404
    return render_template('web/errors/404.html'), 404

@app.errorhandler(500)
def server_error(e):
    logger.error(f"Unhandled server error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('web/errors/500.html'), 500

@app.errorhandler(405)
def method_not_allowed(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Method not allowed'}), 405
    return redirect(url_for('shops.index'))

@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Rate limit exceeded', 'retry_after': e.description}), 429
    flash(_('Too many requests. Please wait a moment.'), 'error')
    return redirect(request.referrer or url_for('shops.index'))

# ── DB setup ─────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    # Backfill merge-safe guards on legacy DB files (additive; never fails startup).
    from src.db.database import ensure_merge_safe_columns
    _merge_summary = ensure_merge_safe_columns()
    for _skipped in _merge_summary.get('skipped', []):
        app.logger.warning(
            'UNIQUE guard %s NOT enforced (legacy duplicates) — '
            'dedupe first, see docs/transfer-protocol.md', _skipped)
    if _merge_summary.get('error'):
        app.logger.warning(
            'ensure_merge_safe_columns incomplete: %s',
            _merge_summary['error'])

# ── Set language route ───────────────────────────────────────
@app.route('/set_lang/<lang>')
def set_language(lang):
    if lang in ('bn', 'en'):
        session['lang'] = lang
    return redirect(request.referrer or url_for('shops.index'))

# ── Serve uploaded images ────────────────────────────────────
@app.route('/shop_img/<path:filename>')
def shop_img(filename):
    return send_from_directory(str(Settings.UPLOAD_DIR), filename)

# ── Template globals ─────────────────────────────────────────
@app.context_processor
def inject_globals():
    return dict(
        categories=db.get_all_categories(),
        settings=Settings,
    )

# ── Jinja2 filters ───────────────────────────────────────────
app.jinja_env.filters['expand_designation'] = expand_designation
app.jinja_env.filters['parse_contact_info'] = parse_contact_info

# ── Entry point ──────────────────────────────────────────────
if __name__ == '__main__':
    app.run(debug=True, host=Settings.APP_HOST, port=Settings.APP_PORT)
