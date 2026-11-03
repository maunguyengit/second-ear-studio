import asyncio
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from . import __version__
from .exports import export
from .models import MODELS, model_path, download
from .store import Store

MAX_UPLOAD = 250 * 1024 * 1024
WEB = Path(__file__).parent / "web"
SAMPLE = Path(__file__).parent / "sample" / "jfk.wav"


class SegmentEdit(BaseModel):
    n: int = Field(ge=0, le=100000)
    text: str = Field(max_length=20000)
    reviewed: bool


class TranscriptEdit(BaseModel):
    revision: int = Field(ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=180)
    changes: list[SegmentEdit] = Field(default_factory=list, max_length=5000)


class RequestLimits:
    def __init__(self, app, max_upload=MAX_UPLOAD):
        self.app=app;self.max_upload=max_upload

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope,receive,send)
        headers={k.decode().lower():v.decode() for k,v in scope["headers"]}
        unsafe=scope["method"] in {"POST","PATCH","DELETE","PUT"}
        if unsafe:
            origin=headers.get("origin")
            expected=f"{scope.get('scheme','http')}://{headers.get('host','')}"
            if headers.get("x-second-ear") != "1" or origin and origin != expected:
                return await JSONResponse({"detail":"Use the Second Ear app on this computer."},status_code=403)(scope,receive,send)
        limit=self.max_upload+1024*1024 if scope["path"]=="/api/sessions" else 1024*1024
        try:
            size=int(headers.get("content-length","0"))
        except ValueError:
            return await JSONResponse({"detail":"Invalid request length"},status_code=400)(scope,receive,send)
        if size>limit:
            return await JSONResponse({"detail":"This upload is too large. The limit is 250 MB."},status_code=413)(scope,receive,send)
        consumed=0
        async def limited_receive():
            nonlocal consumed
            message=await receive()
            consumed+=len(message.get("body",b""))
            if consumed>limit:
                raise HTTPException(413,"Request is too large")
            return message
        async def secure_send(message):
            if message["type"]=="http.response.start":
                message["headers"] += [
                    (b"x-content-type-options",b"nosniff"),
                    (b"referrer-policy",b"no-referrer"),
                    (b"cache-control",b"no-store"),
                    (b"content-security-policy",b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]
            await send(message)
        await self.app(scope,limited_receive,secure_send)


class Runner:
    def __init__(self, store):
        self.store=store;self.stop=threading.Event();self.lock=threading.RLock();self.current=None;self.process=None
        self.thread=threading.Thread(target=self.loop,daemon=True,name="second-ear-queue")

    def start(self):
        for row in self.store.list():
            if row["status"]=="running":
                self.store.update(row["id"],status="failed",phase="Interrupted",error="The app closed during transcription. Retry this recording to start again.")
        self.thread.start()

    def loop(self):
        while not self.stop.wait(0.35):
            with self.lock:
                pending=[r for r in reversed(self.store.list()) if r["status"]=="queued"]
                if not pending:
                    continue
                id=pending[0]["id"]
                self.store.update(id,status="running",phase="Starting local transcription",progress=0)
                command=([sys.executable,"--worker"] if getattr(sys,"frozen",False) else [sys.executable,"-m","second_ear.worker"])+[str(self.store.root),id,str(os.getpid())]
                environment=os.environ.copy()
                # Source checkouts and installed wheels both work in the child.
                if not getattr(sys,"frozen",False):
                    environment["PYTHONPATH"]=str(Path(__file__).parent.parent)+os.pathsep+environment.get("PYTHONPATH","")
                log=(self.store.jobs/id/"worker.log").open("wb")
                try:
                    self.process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=environment)
                    self.current=id
                except OSError as exc:
                    self.store.update(id,status="failed",error=f"Could not start the transcription process: {exc}")
                    log.close();continue
            self.process.wait()
            log.close()
            with self.lock:
                row=self.store.get(id,False)
                if row and row["status"]=="running":
                    self.store.update(id,status="failed",phase="Stopped unexpectedly",error="The speech engine stopped. Retry with the Quick model or a shorter recording. Diagnostic details are in the recording's worker.log.")
                self.current=None;self.process=None

    def cancel(self,id):
        with self.lock:
            row=self.store.get(id,False)
            if not row:
                raise KeyError(id)
            if row["status"] not in ("queued","running"):
                return
            self.store.update(id,status="cancelled",phase="Cancelled")
            if self.current==id and self.process:
                self.process.terminate()
                try:self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait()

    def close(self):
        self.stop.set()
        with self.lock:
            if self.current:
                self.cancel(self.current)
        if self.thread.is_alive():self.thread.join(timeout=8)


def create_app(root, run_worker=True, on_shutdown=None, max_upload=MAX_UPLOAD):
    store=Store(root);runner=Runner(store);downloads={};download_lock=threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        if run_worker:runner.start()
        yield
        runner.close()

    app=FastAPI(title="Second Ear",version=__version__,lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.state.store=store;app.state.runner=runner
    app.add_middleware(RequestLimits,max_upload=max_upload)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost","[::1]","testserver"])

    def recording(id):
        try:canonical=str(uuid.UUID(id))
        except ValueError:raise HTTPException(404,"Recording not found")
        row=store.get(canonical)
        if row is None:raise HTTPException(404,"Recording not found")
        return row

    @app.get("/api/health")
    def health():
        return {"product":"second-ear","version":__version__,"status":"ready"}

    @app.get("/api/state")
    def state():
        with download_lock:
            choices=[{"id":name,**meta,"ready":model_path(root,name) is not None,**downloads.get(name,{})} for name,meta in MODELS.items()]
        return {"models":choices,"max_upload_mb":250,"max_duration_hours":2,"offline_after_setup":True,
                "sample_available":SAMPLE.exists(),"free_disk_mb":shutil.disk_usage(root).free//(1024*1024),"version":__version__}

    @app.post("/api/models/{name}/download",status_code=202)
    def install_model(name:str):
        if name not in MODELS:raise HTTPException(404,"Unknown speech model")
        if model_path(root,name):return {"state":"ready"}
        with download_lock:
            if downloads.get(name,{}).get("state")=="downloading":return {"state":"downloading"}
            downloads[name]={"state":"downloading","error":None}
        def install():
            try:
                download(root,name)
                with download_lock:downloads[name]={"state":"ready","error":None}
            except Exception as exc:
                with download_lock:downloads[name]={"state":"failed","error":"The model could not be downloaded. Check your connection and free disk space, then retry. "+str(exc)[:250]}
        threading.Thread(target=install,daemon=True,name="second-ear-model-download").start()
        return {"state":"downloading"}

    @app.get("/api/sessions")
    def sessions():return store.list()

    async def save_upload(file,model,language,vocabulary):
        if model not in MODELS:raise HTTPException(422,"Choose a supported speech model")
        if model_path(root,model) is None:raise HTTPException(409,"Download the selected speech model in Settings before importing a recording.")
        if len(vocabulary)>1000:raise HTTPException(422,"Keep vocabulary hints under 1,000 characters")
        if language and language not in {"en","vi","es","fr","de","ja","ko","zh","pt","it","ru","ar","hi","nl","pl","tr","uk","id","th"}:
            raise HTTPException(422,"Choose Auto or one of the supported language options")
        if model=="tiny.en" and language not in (None,"en"):raise HTTPException(422,"The Quick model is English-only. Choose a multilingual model.")
        filename=Path((file.filename or "Recording").replace("\\","/")).name
        filename="".join(c for c in filename if c.isprintable())[:180] or "Recording"
        id=str(uuid.uuid4());directory=store.jobs/id;directory.mkdir()
        length=0
        try:
            with (directory/"original").open("wb") as handle:
                while chunk:=await file.read(1024*1024):
                    length+=len(chunk)
                    if length>max_upload:raise HTTPException(413,"This upload is too large. The limit is 250 MB.")
                    if shutil.disk_usage(root).free<256*1024*1024:raise HTTPException(507,"There is not enough free disk space. Free some space and try again.")
                    handle.write(chunk)
            if length==0:raise HTTPException(422,"This file is empty. Choose a recording with audio.")
            title=Path(filename).stem.replace("_"," ").strip() or "Untitled recording"
            store.create(id,title,filename,model,language,vocabulary)
            return store.get(id)
        except BaseException:
            shutil.rmtree(directory,ignore_errors=True)
            raise
        finally:
            await file.close()

    @app.post("/api/sessions",status_code=201)
    async def upload(file:Annotated[UploadFile,File()],model:Annotated[str,Form()]="tiny.en",
                     language:Annotated[str,Form()]="",vocabulary:Annotated[str,Form()]=""):
        return await save_upload(file,model,language or None,vocabulary)

    @app.post("/api/sample",status_code=201)
    async def sample():
        if not SAMPLE.exists():raise HTTPException(404,"Sample recording is not bundled")
        from starlette.datastructures import UploadFile as StarletteUpload
        with SAMPLE.open("rb") as handle:
            return await save_upload(StarletteUpload(filename="JFK — real speech sample.wav",file=handle),"tiny.en","en","")

    @app.get("/api/sessions/{id}")
    def detail(id:str):return recording(id)

    @app.patch("/api/sessions/{id}")
    def edit(id:str,body:TranscriptEdit):
        row=recording(id)
        if len({s.n for s in body.changes})!=len(body.changes):raise HTTPException(422,"A segment may only appear once in a save")
        title=body.title.strip() if body.title is not None else None
        if title is not None and not title:raise HTTPException(422,"Give this recording a title")
        try:store.edit(row["id"],body.revision,title,[s.model_dump() for s in body.changes])
        except ValueError as exc:raise HTTPException(409,str(exc))
        return store.get(row["id"])

    @app.post("/api/sessions/{id}/cancel")
    def cancel(id:str):
        row=recording(id);runner.cancel(row["id"])
        return store.get(row["id"])

    @app.post("/api/sessions/{id}/retry")
    def retry(id:str):
        row=recording(id)
        with runner.lock:
            if row["status"] not in {"failed","cancelled"}:raise HTTPException(409,"Only a failed or cancelled recording can be retried")
            if not model_path(root,row["model"]):raise HTTPException(409,"Download this recording's model first")
            store.reset(row["id"])
        return store.get(row["id"])

    @app.delete("/api/sessions/{id}",status_code=204)
    def delete(id:str):
        row=recording(id)
        with runner.lock:
            runner.cancel(row["id"])
            # Move into a tombstone first so a failed filesystem operation does not discard the DB row.
            original=store.jobs/row["id"];tombstone=store.jobs/(row["id"]+".deleting")
            try:
                if original.exists():original.rename(tombstone)
                store.delete(row["id"])
            except Exception as exc:
                if tombstone.exists() and not original.exists():
                    tombstone.rename(original)
                raise HTTPException(500,"Could not remove the recording. Close audio players and retry.") from exc
            try:
                shutil.rmtree(tombstone)
            except OSError as exc:
                raise HTTPException(500,"The library entry was removed, but local files could not be erased. Close the app and remove the .deleting folder inside the library's recordings folder.") from exc
        return Response(status_code=204)

    @app.get("/api/sessions/{id}/media")
    def media(id:str):
        row=recording(id)
        path=store.jobs/row["id"]/"playback.wav"
        if not path.exists():raise HTTPException(409,"Audio is still being prepared")
        return FileResponse(path,media_type="audio/wav")

    @app.get("/api/sessions/{id}/export/{kind}")
    def output(id:str,kind:str):
        row=recording(id)
        if row["status"]!="completed":raise HTTPException(409,"Wait until transcription finishes before exporting")
        try:content,media_type=export(row,kind)
        except ValueError as exc:raise HTTPException(404,str(exc))
        return Response(content,media_type=media_type,headers={"Content-Disposition":f'attachment; filename="transcript-{row["id"][:8]}.{kind}"'})

    @app.post("/api/shutdown")
    async def shutdown(background:BackgroundTasks):
        async def stop():
            await asyncio.sleep(0.3)
            if on_shutdown:on_shutdown()
        background.add_task(stop)
        return {"message":"Second Ear is closing. You can close this tab."}

    @app.get("/")
    def index():return FileResponse(WEB/"index.html")
    app.mount("/assets",StaticFiles(directory=WEB),name="assets")
    return app
