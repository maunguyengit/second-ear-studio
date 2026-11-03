import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path


def default_data():
    if sys.platform=="darwin":
        return Path.home()/"Library"/"Application Support"/"Second Ear"
    return Path(os.environ.get("XDG_DATA_HOME",str(Path.home()/".local/share")))/"second-ear"


def main():
    if len(sys.argv)>1 and sys.argv[1]=="--worker":
        from .worker import transcribe, watch_parent
        if len(sys.argv)>4:watch_parent(int(sys.argv[4]))
        raise SystemExit(transcribe(Path(sys.argv[2]),sys.argv[3]))
    parser=argparse.ArgumentParser(description="Second Ear — local recordings, editable transcripts, useful subtitles.")
    parser.add_argument("--data-dir",type=Path,default=None)
    parser.add_argument("--port",type=int,default=8767)
    parser.add_argument("--no-browser",action="store_true")
    parser.add_argument("--version",action="store_true")
    args=parser.parse_args()
    if args.version:
        from . import __version__
        print(__version__);return
    root=(args.data_dir or default_data()).expanduser().resolve()
    root.mkdir(parents=True,exist_ok=True)
    if sys.platform=="win32":
        parser.error("This release supports macOS and Linux. Windows is not yet verified.")
    import fcntl
    lock=(root/"server.lock").open("a+")
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        import json
        import urllib.request
        try:
            lock.seek(0);port=int(lock.read().strip())
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health",timeout=3) as response:
                if json.load(response).get("product")!="second-ear":raise ValueError("Unexpected server")
            if not args.no_browser:webbrowser.open(f"http://127.0.0.1:{port}")
            return
        except Exception:
            parser.error("Second Ear is already running for this library. Open its existing window.")
    lock.seek(0);lock.truncate();lock.write(str(args.port));lock.flush()
    if sys.stdout is None or sys.stderr is None:
        log=(root/"application.log").open("a",buffering=1)
        if sys.stdout is None:sys.stdout=log
        if sys.stderr is None:sys.stderr=log
    import uvicorn
    from .app import create_app
    server=None
    def stop():
        if server:server.should_exit=True
    app=create_app(root,on_shutdown=stop)
    config=uvicorn.Config(app,host="127.0.0.1",port=args.port,log_level="warning")
    server=uvicorn.Server(config)
    if not args.no_browser:
        def open_when_ready():
            import urllib.request
            import time
            for _ in range(60):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/health",timeout=0.3) as response:
                        if response.status==200:
                            webbrowser.open(f"http://127.0.0.1:{args.port}");return
                except Exception:time.sleep(0.25)
        threading.Thread(target=open_when_ready,daemon=True).start()
    print(f"Second Ear: http://127.0.0.1:{args.port}\nLibrary: {root}\nQuit from Settings or press Ctrl+C.",flush=True)
    try:server.run()
    finally:lock.close()


if __name__=="__main__":main()
