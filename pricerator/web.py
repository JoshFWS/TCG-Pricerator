"""Flask application — routes and app factory."""
from __future__ import annotations

import io
import time
import threading
import logging
from datetime import datetime, timezone

from flask import (
    Flask, jsonify, redirect, render_template, request,
    url_for, flash, g
)

from pricerator import config, csv_parser, db
from pricerator.price_math import cents_to_display

log = logging.getLogger(__name__)

_scheduler = None  # set by create_app


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "tcg-pricerator-local"
    app.config["LAST_REFRESH_RESULT"] = None
    app.config["REFRESH_IN_PROGRESS"] = False

    app.jinja_env.globals["cents_to_display"] = cents_to_display
    app.jinja_env.globals["now_ts"] = lambda: int(time.time())

    @app.context_processor
    def inject_globals():
        settings = config.load()
        return {
            "settings": settings,
            "theme": settings.theme,
            "is_kawaii": settings.theme == "kawaii",
        }

    @app.route("/")
    def index():
        settings = config.load()
        rows = db.cards_with_latest_price()
        cards = [dict(r) for r in rows]
        for c in cards:
            lp = c.get("latest_price_cents")
            c["above_threshold"] = (
                lp is not None and lp >= settings.threshold_for(c["foil_type"])
            )
            c["price_display"] = cents_to_display(lp)
        cards.sort(key=lambda c: (not c["above_threshold"], c["name"].lower()))
        last_result = app.config.get("LAST_REFRESH_RESULT")
        return render_template("index.html", cards=cards, last_result=last_result,
                               refresh_in_progress=app.config.get("REFRESH_IN_PROGRESS"))

    @app.route("/import", methods=["GET", "POST"])
    def import_csv():
        if request.method == "POST":
            f = request.files.get("csv_file")
            if not f or not f.filename:
                flash("No file selected.", "error")
                return redirect(url_for("import_csv"))
            try:
                result = csv_parser.parse(io.BytesIO(f.read()))
                if result.skipped:
                    flash(f"Skipped {len(result.skipped)} rows with errors.", "warning")
                cards_data = [
                    {
                        "name": c.name,
                        "set_code": c.set_code,
                        "collector_number": c.collector_number,
                        "foil_type": c.foil_type,
                        "language": c.language,
                        "condition": c.condition,
                        "quantity": c.quantity,
                    }
                    for c in result.cards
                ]
                mode = request.form.get("import_mode", "merge")
                if mode == "replace":
                    db.delete_all_cards()
                db.upsert_cards(cards_data)
                verb = "Replaced collection with" if mode == "replace" else "Imported"
                flash(f"{verb} {len(result.cards)} cards.", "success")
                return redirect(url_for("index"))
            except Exception as exc:
                flash(f"Import failed: {exc}", "error")
                return redirect(url_for("import_csv"))
        return render_template("import.html")

    @app.route("/refresh", methods=["POST"])
    def trigger_refresh():
        if app.config.get("REFRESH_IN_PROGRESS"):
            flash("A refresh is already running.", "warning")
            return redirect(url_for("index"))

        sched = app.config.get("SCHEDULER")
        if sched:
            from pricerator import scheduler as _sched
            _sched.trigger_oneshot(sched, app)
            flash("Price refresh started in background.", "info")
        else:
            # Fallback: run in a thread
            def _run():
                from pricerator import refresh as _refresh
                app.config["REFRESH_IN_PROGRESS"] = True
                try:
                    result = _refresh.refresh_all_prices()
                    app.config["LAST_REFRESH_RESULT"] = result
                finally:
                    app.config["REFRESH_IN_PROGRESS"] = False
            threading.Thread(target=_run, daemon=True).start()
            flash("Price refresh started in background.", "info")
        return redirect(url_for("index"))

    @app.route("/card/<int:card_id>")
    def card_detail(card_id: int):
        card = db.card_by_id(card_id)
        if card is None:
            flash("Card not found.", "error")
            return redirect(url_for("index"))
        snapshots = db.recent_snapshots(card_id, limit=30)
        snap_list = [dict(s) for s in reversed(snapshots)]  # oldest first for chart
        settings = config.load()
        threshold = settings.threshold_for(card["foil_type"])
        tcgplayer_url = (
            f"https://www.tcgplayer.com/search/magic/{card['set_code']}"
            f"?productLineName=magic&q={card['name'].replace(' ', '+')}"
        )
        return render_template(
            "detail.html",
            card=dict(card),
            snapshots=snap_list,
            threshold_cents=threshold,
            threshold_display=cents_to_display(threshold),
            tcgplayer_url=tcgplayer_url,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings_view():
        if request.method == "POST":
            s = config.load()
            s.theme = request.form.get("theme", "light")
            try:
                s.threshold_nonfoil_cents = max(0, int(float(request.form.get("threshold_nonfoil", "1")) * 100))
                s.threshold_foil_cents = max(0, int(float(request.form.get("threshold_foil", "1")) * 100))
                s.threshold_etched_cents = max(0, int(float(request.form.get("threshold_etched", "1")) * 100))
            except (ValueError, TypeError):
                flash("Invalid threshold value.", "error")
                return redirect(url_for("settings_view"))
            s.refresh_interval = request.form.get("refresh_interval", "24h")
            s.notifications_enabled = "notifications_enabled" in request.form

            config.save(s)

            sched = app.config.get("SCHEDULER")
            if sched:
                from pricerator import scheduler as _sched
                _sched.reschedule(sched, app)

            flash("Settings saved.", "success")
            return redirect(url_for("settings_view"))

        s = config.load()
        return render_template("settings.html",
                               threshold_nonfoil=s.threshold_nonfoil_cents / 100,
                               threshold_foil=s.threshold_foil_cents / 100,
                               threshold_etched=s.threshold_etched_cents / 100,
                               refresh_intervals=list(config.REFRESH_HOURS.keys()))

    @app.route("/api/refresh-status")
    def refresh_status():
        return jsonify({
            "in_progress": app.config.get("REFRESH_IN_PROGRESS", False),
            "last_refreshed_at": config.load().last_refreshed_at,
        })

    @app.route("/delete-collection", methods=["POST"])
    def delete_collection():
        db.delete_all_cards()
        flash("Collection deleted.", "info")
        return redirect(url_for("index"))

    return app
