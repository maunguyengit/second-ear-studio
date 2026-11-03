import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class StaleAttempt(RuntimeError):
    pass


class Store:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs = self.root / "recordings"
        self.jobs.mkdir(exist_ok=True)
        self.path = self.root / "library.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL,
                status TEXT NOT NULL, phase TEXT NOT NULL DEFAULT '', progress REAL NOT NULL DEFAULT 0,
                error TEXT, model TEXT NOT NULL, language TEXT, vocabulary TEXT NOT NULL DEFAULT '',
                duration REAL, waveform TEXT NOT NULL DEFAULT '[]', playback_ready INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
                elapsed REAL, model_revision TEXT
            );
            CREATE TABLE IF NOT EXISTS segments (
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                n INTEGER NOT NULL, start REAL NOT NULL, end REAL NOT NULL,
                text TEXT NOT NULL, original_text TEXT NOT NULL, words TEXT NOT NULL DEFAULT '[]',
                uncertain INTEGER NOT NULL DEFAULT 0, reviewed INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (session_id, n)
            );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, id, title, filename, model, language, vocabulary):
        timestamp = now()
        with self.connect() as db:
            db.execute("""INSERT INTO sessions(id,title,filename,status,model,language,vocabulary,created_at,updated_at)
                VALUES (?,?,?,'queued',?,?,?,?,?)""", (id,title,filename,model,language,vocabulary,timestamp,timestamp))

    def get(self, id, include_segments=True):
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["waveform"] = json.loads(result["waveform"])
            if include_segments:
                result["segments"] = []
                for item in db.execute("SELECT * FROM segments WHERE session_id=? ORDER BY n", (id,)):
                    segment = dict(item)
                    segment["words"] = json.loads(segment["words"])
                    segment["edited"] = segment["text"] != segment["original_text"]
                    result["segments"].append(segment)
            return result

    def list(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute("""SELECT s.id,s.title,s.filename,s.status,s.phase,s.progress,s.error,
                s.duration,s.created_at,s.updated_at,s.model,s.language,s.revision,
                (SELECT count(*) FROM segments g WHERE g.session_id=s.id) AS segment_count,
                (SELECT count(*) FROM segments g WHERE g.session_id=s.id AND g.uncertain=1 AND g.reviewed=0) AS review_count
                FROM sessions s ORDER BY s.created_at DESC""")]

    def update(self, id, **fields):
        allowed = {"status","phase","progress","error","duration","waveform","playback_ready","elapsed","language","model_revision"}
        if not set(fields) <= allowed:
            raise ValueError("Unsupported update")
        fields["updated_at"] = now()
        columns = ",".join(f"{key}=?" for key in fields)
        with self.connect() as db:
            db.execute(f"UPDATE sessions SET {columns} WHERE id=?", (*fields.values(),id))

    def worker_update(self, id, revision, **fields):
        allowed={"status","phase","progress","error","duration","waveform","playback_ready","elapsed","language","model_revision"}
        if not set(fields)<=allowed:raise ValueError("Unsupported worker update")
        fields["updated_at"]=now()
        columns=",".join(f"{key}=?" for key in fields)
        with self.connect() as db:
            cursor=db.execute(f"UPDATE sessions SET {columns} WHERE id=? AND revision=? AND status IN ('queued','running')",(*fields.values(),id,revision))
            if cursor.rowcount!=1:raise StaleAttempt("This transcription attempt is no longer active")

    def append(self, id, n, start, end, text, words, uncertain, expected_revision=None):
        with self.connect() as db:
            if expected_revision is not None:
                db.execute("BEGIN IMMEDIATE")
                current=db.execute("SELECT revision,status FROM sessions WHERE id=?",(id,)).fetchone()
                if not current or current["revision"]!=expected_revision or current["status"]!="running":
                    raise StaleAttempt("This transcription attempt is no longer active")
            db.execute("""INSERT INTO segments(session_id,n,start,end,text,original_text,words,uncertain)
                VALUES (?,?,?,?,?,?,?,?)""", (id,n,start,end,text,text,json.dumps(words),int(uncertain)))

    def edit(self, id, revision, title, changes):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT revision,status FROM sessions WHERE id=?", (id,)).fetchone()
            if row is None:
                raise KeyError("Recording no longer exists")
            if row["status"] != "completed":
                raise ValueError("Wait until transcription finishes before editing")
            if row["revision"] != revision:
                raise ValueError("This transcript changed in another window. Reload before saving; your draft is still here.")
            for item in changes:
                cursor = db.execute("UPDATE segments SET text=?,reviewed=? WHERE session_id=? AND n=?",
                                    (item["text"].strip(),int(item["reviewed"]),id,item["n"]))
                if cursor.rowcount != 1:
                    raise ValueError("Unknown transcript segment")
            db.execute("UPDATE sessions SET title=COALESCE(?,title),revision=revision+1,updated_at=? WHERE id=?", (title,now(),id))

    def reset(self, id):
        with self.connect() as db:
            db.execute("DELETE FROM segments WHERE session_id=?", (id,))
            db.execute("""UPDATE sessions SET status='queued',phase='',progress=0,error=NULL,elapsed=NULL,
                       revision=revision+1,updated_at=? WHERE id=?""", (now(),id))

    def delete(self, id):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (id,))
