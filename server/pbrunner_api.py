"""
=============================================================================
  PBRunner API — FastAPI Backend
  Versiune : 1.0
=============================================================================
  Endpoints:
    POST /analyze          — upload video + parametri atlet → job_id
    GET  /status/{job_id}  — status job (queued/processing/done/error)
    GET  /result/{job_id}  — JSON cu toate rezultatele
    GET  /download/{job_id}/{file} — descarca video/pdf/html/png
    POST /athletes         — salveaza profil atlet
    GET  /athletes         — lista atleți salvati
    GET  /athletes/{id}    — detalii atlet
    DELETE /athletes/{id}  — sterge atlet
    GET  /health           — health check

  Rulare locala:
    uvicorn pbrunner_api:app --host 0.0.0.0 --port 8000 --reload

  Deploy Railway / Render:
    Dockerfile inclus in acelasi folder
=============================================================================
"""

import os
import sys
import uuid
import json
import time
import shutil
import asyncio
import threading
import traceback
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ─── Directoare de lucru ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
JOBS_DIR = BASE_DIR / "jobs"
ATHLETES_DB = BASE_DIR / "athletes.json"
JOBS_DIR.mkdir(exist_ok=True)

# ─── In-memory job store ─────────────────────────────────────────────────────
# Pentru productie, inlocuieste cu Redis sau SQLite
_JOBS: Dict[str, dict] = {}
_JOBS_LOCK = threading.Lock()

# ─── FastAPI app ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="PBRunner API",
    description="API pentru analiza biomecanica sprint cu template IAAF",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # In productie: lista domenii permise
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Modele Pydantic ─────────────────────────────────────────────────────────


class AthleteProfile(BaseModel):
    name: str
    height_cm: float = 184.0
    weight_kg: float = 82.0
    age: int = 21
    sport: str = "sprint_100m"
    notes: str = ""


class JobStatus(BaseModel):
    job_id: str
    status: str          # queued | processing | done | error
    progress: int = 0    # 0-100
    message: str = ""
    created_at: str = ""
    finished_at: str = ""

# ─── Helpers ─────────────────────────────────────────────────────────────────


def load_athletes() -> dict:
    if ATHLETES_DB.exists():
        with open(ATHLETES_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_athletes(data: dict):
    with open(ATHLETES_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def job_dir(job_id: str) -> Path:
    d = JOBS_DIR / job_id
    d.mkdir(exist_ok=True)
    return d


def update_job(job_id: str, **kwargs):
    with _JOBS_LOCK:
        if job_id not in _JOBS:
            _JOBS[job_id] = {}
        _JOBS[job_id].update(kwargs)
        # Persista pe disc pentru restart
        meta_path = job_dir(job_id) / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(_JOBS[job_id], f, ensure_ascii=False, indent=2)


def get_job(job_id: str) -> Optional[dict]:
    with _JOBS_LOCK:
        if job_id in _JOBS:
            return dict(_JOBS[job_id])
    # Incearca sa citeasca de pe disc (dupa restart server)
    meta_path = job_dir(job_id) / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            data = json.load(f)
        with _JOBS_LOCK:
            _JOBS[job_id] = data
        return data
    return None

# ─── Procesare video (background thread) ─────────────────────────────────────


def run_analysis(job_id: str, video_path: str, params: dict):
    """
    Ruleaza pbrunner_coach.process_video intr-un thread separat.
    Actualizeaza statusul job-ului pe parcurs.
    """
    try:
        update_job(job_id,
                   status="processing",
                   progress=5,
                   message="Initializare model MediaPipe...")

        # Import dinamic — pbrunner_coach trebuie sa fie in acelasi folder
        sys.path.insert(0, str(BASE_DIR))
        import pbrunner_coach as coach
        import pbrunner_coach   # asigura re-import daca e necesar

        update_job(job_id, progress=10,
                   message="Model incarcat, incepe analiza...")

        jd = job_dir(job_id)
        base = str(jd / "analysis")

        # Redirectioneaza process_video sa salveze in job_dir
        # process_video foloseste video_path ca baza pentru output-uri
        # Copiem video-ul in job_dir si dam calea noua
        video_in_job = str(jd / "input.mp4")
        if not os.path.exists(video_in_job):
            shutil.copy(video_path, video_in_job)

        # Progress callback prin monkey-patch al print
        original_print = __builtins__["print"] if isinstance(
            __builtins__, dict) else print
        _last_progress = [10]

        def progress_print(*args, **kwargs):
            msg = " ".join(str(a) for a in args)
            original_print(*args, **kwargs)
            # Detecteaza progresul din mesajele existente
            if "%" in msg:
                try:
                    pct_str = [x for x in msg.split() if "%" in x][0]
                    pct = float(pct_str.replace("%", "").replace("(", ""))
                    new_prog = max(_last_progress[0], int(10 + pct * 0.75))
                    _last_progress[0] = new_prog
                    update_job(job_id, progress=new_prog,
                               message=f"Procesare: {pct:.0f}%")
                except Exception:
                    pass
            elif "[DONE]" in msg:
                update_job(job_id, progress=90,
                           message="Finalizare rapoarte...")

        import builtins
        builtins.print = progress_print

        try:
            coach.process_video(
                video_path=video_in_job,
                lang=params.get("lang", "ro"),
                height_cm=float(params.get("height_cm", 184)),
                weight_kg=float(params.get("weight_kg", 82)),
                age=int(params.get("age", 21)),
                slowmo_fps=float(params.get("slowmo_fps", 0.0)),
                athlete_name=params.get("athlete_name", "Atlet"),
            )
        finally:
            builtins.print = original_print

        # Colecteaza output-urile generate
        # process_video salveaza cu prefix "input" in job_dir
        outputs = {}
        for suffix, key in [
            ("_coached.mp4",     "video"),
            ("_coach_report.pdf", "pdf"),
            ("_dashboard.html",  "html"),
            ("_coach_chart.png", "chart"),
            ("_symmetry.png",    "symmetry"),
            ("_coach_data.csv",  "csv"),
            ("_ml_profile.json", "ml"),
        ]:
            path = jd / f"input{suffix}"
            if path.exists():
                outputs[key] = str(path)

        # Citeste JSON-urile pentru raspuns direct in Flutter
        result_data = _collect_results(jd, outputs)

        update_job(job_id,
                   status="done",
                   progress=100,
                   message="Analiza completa!",
                   finished_at=datetime.now(timezone.utc).isoformat(),
                   outputs=outputs,
                   result=result_data)

    except Exception as e:
        tb = traceback.format_exc()
        update_job(job_id,
                   status="error",
                   progress=0,
                   message=f"Eroare: {str(e)}",
                   finished_at=datetime.now(timezone.utc).isoformat(),
                   error=tb)
        print(f"[API ERROR] job {job_id}: {e}\n{tb}")


def _collect_results(jd: Path, outputs: dict) -> dict:
    """
    Colecteaza datele din fisierele generate pentru a le include
    direct in raspunsul JSON al API-ului (pentru Flutter).
    """
    result = {}

    # ML profile
    if "ml" in outputs:
        try:
            with open(outputs["ml"], encoding="utf-8") as f:
                result["ml_profile"] = json.load(f)
        except Exception:
            pass

    # CSV — primele 100 randuri ca sample
    if "csv" in outputs:
        try:
            import pandas as pd
            df = pd.read_csv(outputs["csv"])
            result["frames_sample"] = df.head(100).to_dict(orient="records")
            result["total_frames"] = len(df)

            # Scoruri per faza
            phase_scores = {}
            if "phase" in df.columns:
                for ph in df["phase"].unique():
                    ph_df = df[df["phase"] == ph]
                    # Calcul scor mediu per faza din CSV daca exista
                    phase_scores[ph] = {"frame_count": len(ph_df)}
            result["phase_stats"] = phase_scores

            # Metrici cheie
            angle_cols = ["knee_L", "knee_R", "hip_L",
                          "hip_R", "trunk", "elbow_L", "elbow_R"]
            metrics = {}
            for col in angle_cols:
                if col in df.columns:
                    metrics[col] = {
                        "mean": round(float(df[col].mean()), 1),
                        "min":  round(float(df[col].min()),  1),
                        "max":  round(float(df[col].max()),  1),
                        "std":  round(float(df[col].std()),  1),
                    }
            result["angle_metrics"] = metrics
        except Exception:
            pass

    # Meta jobului
    meta_path = jd / "meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
        # Extrage events din job meta daca exista
        if "result" in meta and "events" in meta["result"]:
            result["critical_events"] = meta["result"]["events"]

    return result


# ─── ENDPOINTS ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check pentru monitoring."""
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "jobs_active": len([j for j in _JOBS.values() if j.get("status") == "processing"]),
    }


@app.post("/analyze")
async def analyze_video(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    athlete_name: str = Form("Atlet"),
    height_cm: float = Form(184.0),
    weight_kg: float = Form(82.0),
    age: int = Form(21),
    lang: str = Form("ro"),
    slowmo_fps: float = Form(0.0),
):
    """
    Upload video si porneste analiza.
    Returneaza job_id pentru polling status.
    """
    # Validare format video
    allowed_ext = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}
    ext = Path(video.filename or "video.mp4").suffix.lower()
    if ext not in allowed_ext:
        raise HTTPException(400, f"Format nesupورت. Acceptat: {allowed_ext}")

    # Validare parametri
    if not (100 <= height_cm <= 220):
        raise HTTPException(400, "Inaltime invalida (100-220cm)")
    if not (30 <= weight_kg <= 150):
        raise HTTPException(400, "Greutate invalida (30-150kg)")
    if not (12 <= age <= 50):
        raise HTTPException(400, "Varsta invalida (12-50 ani)")

    # Creeaza job
    job_id = str(uuid.uuid4())
    jd = job_dir(job_id)

    # Salveaza video
    video_path = str(jd / f"input{ext}")
    with open(video_path, "wb") as f:
        content = await video.read()
        f.write(content)

    file_size_mb = len(content) / (1024 * 1024)

    # Inregistreaza job
    update_job(job_id,
               status="queued",
               progress=0,
               message="In coada de procesare...",
               created_at=datetime.now(timezone.utc).isoformat(),
               finished_at="",
               params={
                   "athlete_name": athlete_name,
                   "height_cm":    height_cm,
                   "weight_kg":    weight_kg,
                   "age":          age,
                   "lang":         lang,
                   "slowmo_fps":   slowmo_fps,
                   "filename":     video.filename,
                   "size_mb":      round(file_size_mb, 2),
               })

    # Porneste procesarea in background thread
    params = {
        "athlete_name": athlete_name,
        "height_cm":    height_cm,
        "weight_kg":    weight_kg,
        "age":          age,
        "lang":         lang,
        "slowmo_fps":   slowmo_fps,
    }
    thread = threading.Thread(
        target=run_analysis,
        args=(job_id, video_path, params),
        daemon=True
    )
    thread.start()

    return {
        "job_id":   job_id,
        "status":   "queued",
        "message":  f"Video primit ({file_size_mb:.1f}MB). Analiza pornita.",
        "poll_url": f"/status/{job_id}",
    }


@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Polleaza statusul unui job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} negasit")

    return {
        "job_id":      job_id,
        "status":      job.get("status", "unknown"),
        "progress":    job.get("progress", 0),
        "message":     job.get("message", ""),
        "created_at":  job.get("created_at", ""),
        "finished_at": job.get("finished_at", ""),
    }


@app.get("/result/{job_id}")
async def get_result(job_id: str):
    """
    Returneaza toate rezultatele unui job completat.
    Include metrici, scoruri, events — tot ce are nevoie Flutter fara download.
    """
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id} negasit")
    if job.get("status") != "done":
        raise HTTPException(400, f"Job nu e gata. Status: {job.get('status')}")

    outputs = job.get("outputs", {})
    result = job.get("result", {})

    # Construieste URL-uri de download
    download_urls = {}
    for key, path in outputs.items():
        if Path(path).exists():
            ext = Path(path).suffix
            download_urls[key] = f"/download/{job_id}/{key}"

    return {
        "job_id":        job_id,
        "status":        "done",
        "params":        job.get("params", {}),
        "created_at":    job.get("created_at", ""),
        "finished_at":   job.get("finished_at", ""),
        "download_urls": download_urls,
        "metrics":       result.get("angle_metrics", {}),
        "phase_stats":   result.get("phase_stats", {}),
        "ml_profile":    result.get("ml_profile", {}),
        "frames_sample": result.get("frames_sample", []),
        "total_frames":  result.get("total_frames", 0),
    }


@app.get("/download/{job_id}/{file_key}")
async def download_file(job_id: str, file_key: str):
    """Descarca un fisier output al unui job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job negasit")
    if job.get("status") != "done":
        raise HTTPException(400, "Job nu e gata")

    outputs = job.get("outputs", {})
    if file_key not in outputs:
        raise HTTPException(404, f"Fisier '{file_key}' negasit in output")

    file_path = Path(outputs[file_key])
    if not file_path.exists():
        raise HTTPException(404, "Fisier sters sau indisponibil")

    # Media type corect per extensie
    media_types = {
        ".mp4": "video/mp4",
        ".pdf": "application/pdf",
        ".html": "text/html",
        ".png": "image/png",
        ".csv": "text/csv",
        ".json": "application/json",
    }
    mt = media_types.get(file_path.suffix.lower(), "application/octet-stream")

    return FileResponse(
        path=str(file_path),
        media_type=mt,
        filename=file_path.name,
    )


@app.get("/jobs")
async def list_jobs(limit: int = 20):
    """Lista ultimelor joburi (pentru debug / admin)."""
    jobs = []
    for jd in sorted(JOBS_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        meta = jd / "meta.json"
        if meta.exists():
            with open(meta) as f:
                data = json.load(f)
            jobs.append({
                "job_id":     data.get("job_id", ""),
                "status":     data.get("status", ""),
                "progress":   data.get("progress", 0),
                "created_at": data.get("created_at", ""),
                "params":     data.get("params", {}),
            })
        if len(jobs) >= limit:
            break
    return {"jobs": jobs, "total": len(jobs)}


@app.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """Sterge un job si fisierele asociate."""
    jd = JOBS_DIR / job_id
    if not jd.exists():
        raise HTTPException(404, "Job negasit")
    shutil.rmtree(jd, ignore_errors=True)
    with _JOBS_LOCK:
        _JOBS.pop(job_id, None)
    return {"deleted": job_id}


# ─── ATLEȚI ──────────────────────────────────────────────────────────────────

@app.post("/athletes")
async def create_athlete(athlete: AthleteProfile):
    """Salveaza un profil de atlet."""
    db = load_athletes()
    aid = str(uuid.uuid4())
    db[aid] = {
        "id":         aid,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **athlete.dict()
    }
    save_athletes(db)
    return {"id": aid, **db[aid]}


@app.get("/athletes")
async def list_athletes():
    """Lista toti atletii salvati."""
    db = load_athletes()
    return {"athletes": list(db.values())}


@app.get("/athletes/{athlete_id}")
async def get_athlete(athlete_id: str):
    """Detalii atlet."""
    db = load_athletes()
    if athlete_id not in db:
        raise HTTPException(404, "Atlet negasit")
    return db[athlete_id]


@app.put("/athletes/{athlete_id}")
async def update_athlete(athlete_id: str, athlete: AthleteProfile):
    """Actualizeaza profil atlet."""
    db = load_athletes()
    if athlete_id not in db:
        raise HTTPException(404, "Atlet negasit")
    db[athlete_id].update(athlete.dict())
    save_athletes(db)
    return db[athlete_id]


@app.delete("/athletes/{athlete_id}")
async def delete_athlete(athlete_id: str):
    """Sterge atlet."""
    db = load_athletes()
    if athlete_id not in db:
        raise HTTPException(404, "Atlet negasit")
    del db[athlete_id]
    save_athletes(db)
    return {"deleted": athlete_id}


# ─── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
