"""Start the explorer app:  .venv\\Scripts\\python.exe -m app  [--port 8765]

Then open http://127.0.0.1:8765 in a browser. Press Ctrl+C in this window to stop it.
"""
import argparse

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="Fly brain explorer web app")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1", help="127.0.0.1 = only this computer can open it")
    ap.add_argument("--no-warm", action="store_true",
                    help="do not build the brain networks at start-up (the first run builds them)")
    args = ap.parse_args()
    from .main import create_app
    app = create_app()
    st = app.state.adapter.status()
    print(f"Engine: {st['engine']['name']}  (fake: {st['engine']['is_fake']})")
    for snap, info in st["neurons"].items():
        print(f"Neuron list, snapshot {snap}: {info['source']}  ({info['count']} neurons)")
    if app.state.adapter.runs_enabled and not args.no_warm:
        print("Building the brain network for each snapshot (once, a few seconds each)...")
        try:
            from .engine_adapter import variant_label
            for snap, secs in app.state.adapter.warm_up().items():
                v, why = app.state.adapter.default_variant(snap)
                print(f"  snapshot {snap} ({variant_label(v)}): ready in {secs:.1f} s")
                if why:
                    print(f"    note: the page opens on the published model here: {why}")
        except Exception as exc:  # noqa: BLE001 - shown, and the page banner shows it too
            print(f"WARNING: could not build the network: {type(exc).__name__}: {exc}")
    st = app.state.adapter.status()
    if st["banner"]:
        print("WARNING: " + st["banner"])
    print(f"Open http://{args.host}:{args.port} in your browser. Ctrl+C stops the app.")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
