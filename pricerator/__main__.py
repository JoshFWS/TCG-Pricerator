import argparse
import sys
import webbrowser
import threading


def main() -> None:
    parser = argparse.ArgumentParser(prog="pricerator")
    sub = parser.add_subparsers(dest="cmd")
    serve = sub.add_parser("serve", help="Start local web server (default)")
    serve.add_argument("--port", type=int, default=5000)
    serve.add_argument("--no-browser", action="store_true")

    args = parser.parse_args()
    if args.cmd is None or args.cmd == "serve":
        port = getattr(args, "port", 5000)
        no_browser = getattr(args, "no_browser", False)
        _serve(port, no_browser)
    else:
        parser.print_help()
        sys.exit(1)


def _serve(port: int, no_browser: bool) -> None:
    from pricerator.db import init_db
    from pricerator.scheduler import start_scheduler
    from pricerator.web import create_app

    init_db()
    app = create_app()
    scheduler = start_scheduler(app)
    app.config["SCHEDULER"] = scheduler

    if not no_browser:
        def _open():
            import time
            time.sleep(0.8)
            webbrowser.open(f"http://localhost:{port}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"TCG Pricerator running at http://localhost:{port}  (Ctrl+C to stop)")
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    main()
