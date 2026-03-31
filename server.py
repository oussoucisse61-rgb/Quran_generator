"""
🕌 Quran TikTok Generator — Web Server
Backend Flask : génère les vidéos et les sert via une interface web
"""

import os, random, requests, subprocess, uuid, threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "VOTRE_CLE_PEXELS_ICI")
OUTPUT_DIR     = Path("output")
TEMP_DIR       = Path("temp")
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

RECITERS = {
    "1": {"nom": "Maher Al-Muaiqly",     "server": "https://server8.mp3quran.net/maher/"},
    "2": {"nom": "Mishary Al-Afasy",      "server": "https://server8.mp3quran.net/afs/"},
    "3": {"nom": "Abdurrahman Al-Sudais", "server": "https://server11.mp3quran.net/sds/"},
    "4": {"nom": "Saad Al-Ghamdi",        "server": "https://server7.mp3quran.net/s_gmd/"},
    "5": {"nom": "Nasser Al-Qatami",      "server": "https://server6.mp3quran.net/qtm/"},
    "6": {"nom": "Yasser Al-Dosari",      "server": "https://server11.mp3quran.net/yasser/"},
}

SOURATES = {
    1:"Al-Fatiha", 2:"Al-Baqara", 3:"Al-Imran", 4:"An-Nisa", 5:"Al-Maida",
    6:"Al-Anam", 7:"Al-Araf", 8:"Al-Anfal", 9:"At-Tawba", 10:"Yunus",
    11:"Hud", 12:"Yusuf", 13:"Ar-Rad", 14:"Ibrahim", 15:"Al-Hijr",
    16:"An-Nahl", 17:"Al-Isra", 18:"Al-Kahf", 19:"Maryam", 20:"Ta-Ha",
    21:"Al-Anbiya", 36:"Ya-Sin", 55:"Ar-Rahman", 56:"Al-Waqia",
    67:"Al-Mulk", 78:"An-Naba", 112:"Al-Ikhlas", 113:"Al-Falaq", 114:"An-Nas",
}

VISUAL_KEYWORDS = [
    "mosque architecture", "islamic calligraphy", "nature sky clouds",
    "desert sunset", "forest river water", "night stars sky",
    "mountains landscape", "ocean waves",
]

# Stockage des jobs en cours { job_id: { status, progress, videos, error } }
jobs = {}

# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html", reciters=RECITERS, sourates=SOURATES)

@app.route("/api/generate", methods=["POST"])
def generate():
    data        = request.json
    recitant_id = str(data.get("recitant", "1"))
    sourate_num = int(data.get("sourate", 1))
    seg_dur     = int(data.get("duration", 55))

    if recitant_id not in RECITERS:
        return jsonify({"error": "Récitant invalide"}), 400
    if sourate_num < 1 or sourate_num > 114:
        return jsonify({"error": "Sourate invalide"}), 400

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "status":   "starting",
        "progress": 0,
        "message":  "Démarrage...",
        "videos":   [],
        "error":    None,
        "total":    0,
    }

    thread = threading.Thread(
        target=run_pipeline,
        args=(job_id, recitant_id, sourate_num, seg_dur),
        daemon=True
    )
    thread.start()

    return jsonify({"job_id": job_id})

@app.route("/api/status/<job_id>")
def status(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job introuvable"}), 404
    return jsonify(job)

@app.route("/api/download/<filename>")
def download(filename):
    path = OUTPUT_DIR / filename
    if not path.exists():
        return jsonify({"error": "Fichier introuvable"}), 404
    return send_file(str(path), as_attachment=True)

# ─── PIPELINE ─────────────────────────────────────────────────────────────────
def run_pipeline(job_id, recitant_id, sourate_num, seg_dur):
    job      = jobs[job_id]
    recitant = RECITERS[recitant_id]
    nom_srt  = SOURATES.get(sourate_num, f"Sourate {sourate_num}")
    uid      = job_id

    try:
        # 1. Télécharger audio
        update(job_id, 5, "Téléchargement de la récitation...")
        audio = download_audio(recitant, sourate_num, uid)

        # 2. Durée
        update(job_id, 15, "Analyse de l'audio...")
        duree = get_duration(audio)

        # 3. Traduction
        update(job_id, 20, "Récupération de la traduction française...")
        versets = get_traduction(sourate_num)

        # 4. Découpage
        update(job_id, 25, "Découpage en segments TikTok...")
        segments = decouper(audio, duree, seg_dur, uid)
        total    = len(segments)
        job["total"] = total

        # 5. Générer chaque vidéo
        videos = []
        for i, (seg_path, seg_dur_reel, idx, debut, fin) in enumerate(segments):
            pct = 25 + int((i / total) * 70)
            update(job_id, pct, f"Génération vidéo {idx}/{total}...")

            versets_seg = get_versets_segment(versets, debut, fin, duree)
            srt_path    = generer_srt(versets_seg, seg_dur_reel, uid, idx)
            bg          = download_background(seg_dur_reel)
            title       = f"{nom_srt} — {recitant['nom'].split()[0]}"
            vp          = assemble(bg, seg_path, seg_dur_reel, title, idx, total, srt_path, uid)

            if vp:
                videos.append({
                    "filename": vp.name,
                    "label":    f"Partie {idx}/{total} — {int(debut//60)}:{int(debut%60):02d}→{int(fin//60)}:{int(fin%60):02d}",
                })
            try: bg.unlink()
            except: pass

        job["videos"]  = videos
        job["status"]  = "done"
        job["progress"] = 100
        job["message"] = f"{len(videos)} vidéos prêtes !"

    except Exception as e:
        job["status"]  = "error"
        job["error"]   = str(e)
        job["message"] = f"Erreur : {e}"

def update(job_id, progress, message):
    jobs[job_id]["progress"] = progress
    jobs[job_id]["message"]  = message
    jobs[job_id]["status"]   = "running"

# ─── FONCTIONS CORE ───────────────────────────────────────────────────────────
def download_audio(recitant, sourate_num, uid):
    num_str = str(sourate_num).zfill(3)
    url     = recitant["server"] + f"{num_str}.mp3"
    path    = TEMP_DIR / f"audio_{uid}.mp3"
    resp    = requests.get(url, stream=True, timeout=60)
    if resp.status_code != 200:
        raise Exception(f"Sourate introuvable pour ce récitant (HTTP {resp.status_code})")
    with open(path, "wb") as f:
        for chunk in resp.iter_content(8192): f.write(chunk)
    return path

def get_duration(audio):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(audio)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return float(r.stdout.strip())

def get_traduction(sourate_num):
    try:
        url  = f"https://api.alquran.cloud/v1/surah/{sourate_num}/fr.hamidullah"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return [a["text"] for a in resp.json()["data"]["ayahs"]]
    except: pass
    return []

def decouper(audio, duree_totale, seg_dur, uid):
    segments = []
    debut, idx = 0, 1
    while debut < duree_totale - 10:
        fin     = min(debut + seg_dur, duree_totale)
        dur_seg = fin - debut
        out     = TEMP_DIR / f"seg_{uid}_{idx:02d}.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", str(audio),
            "-ss", str(debut), "-t", str(dur_seg),
            "-c:a", "copy", str(out)], capture_output=True)
        segments.append((out, dur_seg, idx, debut, fin))
        debut += seg_dur
        idx   += 1
    return segments

def get_versets_segment(versets, debut, fin, duree_totale):
    if not versets: return []
    n     = len(versets)
    i0    = int((debut / duree_totale) * n)
    i1    = int((fin   / duree_totale) * n)
    return versets[max(0,i0):min(n, max(i0+1, i1))]

def generer_srt(versets, duration, uid, idx):
    path = TEMP_DIR / f"sub_{uid}_{idx:02d}.srt"
    if not versets:
        path.write_text("", encoding="utf-8")
        return path
    nb, dur = len(versets), duration / len(versets)
    lines = []
    for i, v in enumerate(versets):
        d, f = i*dur, (i+1)*dur - 0.3
        mots = v.split()
        txt  = (" ".join(mots[:len(mots)//2]) + "\n" + " ".join(mots[len(mots)//2:])) if len(mots)>8 else v
        def fmt(t):
            return f"{int(t//3600):02d}:{int((t%3600)//60):02d}:{int(t%60):02d},{int((t-int(t))*1000):03d}"
        lines += [str(i+1), f"{fmt(d)} --> {fmt(f)}", txt, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def download_background(duration):
    kw      = random.choice(VISUAL_KEYWORDS)
    headers = {"Authorization": PEXELS_API_KEY}
    params  = {"query": kw, "orientation": "portrait", "per_page": 15}
    try:
        resp   = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=15)
        videos = resp.json().get("videos", []) if resp.status_code == 200 else []
        if videos:
            long_e = [v for v in videos if v["duration"] >= max(duration*0.5, 5)]
            chosen = random.choice(long_e if long_e else videos)
            files  = sorted(chosen["video_files"], key=lambda f: f.get("width",0)*f.get("height",0))
            port   = [f for f in files if f.get("height",0) >= f.get("width",999)]
            vf     = port[-1] if port else files[-1]
            vp     = TEMP_DIR / f"bg_{uuid.uuid4().hex[:6]}.mp4"
            with requests.get(vf["link"], stream=True) as r:
                with open(vp, "wb") as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            return vp
    except: pass
    return create_placeholder(duration)

def create_placeholder(duration):
    vp = TEMP_DIR / f"ph_{uuid.uuid4().hex[:6]}.mp4"
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
        "-i", f"color=c=black:size=1080x1920:rate=25:duration={duration}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vp)], capture_output=True)
    return vp

def assemble(bg, audio, duration, title, idx, total, srt_path, uid):
    out        = OUTPUT_DIR / f"video_{uid}_{idx:02d}.mp4"
    safe_title = title.replace("'","").replace(":","").replace("\\","").replace("/","")
    safe_label = f"Partie {idx} sur {total}"
    has_subs   = srt_path.exists() and srt_path.stat().st_size > 10
    srt_esc    = str(srt_path.resolve()).replace("\\","/").replace(":","\\:")
    fade_dur   = min(1.5, duration * 0.1)

    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos",
        "crop=1080:1920", "setsar=1",
        f"fade=t=in:st=0:d={fade_dur}:alpha=0",
        f"fade=t=out:st={duration-fade_dur}:d={fade_dur}:alpha=0",
        f"drawtext=text='{safe_title}':fontfile='C\\:/Windows/Fonts/arialbd.ttf':fontsize=50:fontcolor=white:x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.5:boxborderw=16",
        f"drawtext=text='{safe_label}':fontfile='C\\:/Windows/Fonts/arial.ttf':fontsize=30:fontcolor=white@0.8:x=(w-text_w)/2:y=148:box=1:boxcolor=black@0.35:boxborderw=10",
    ]
    if has_subs:
        vf_parts.append(
            f"subtitles='{srt_esc}':force_style='FontName=Palatino Linotype,FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Shadow=1,Italic=1,MarginV=860,Alignment=8,WrapStyle=1'"
        )

    af  = f"afade=t=in:st=0:d={fade_dur},afade=t=out:st={duration-fade_dur}:d={fade_dur}"
    cmd = [
        "ffmpeg", "-y", "-stream_loop", "-1",
        "-i", str(bg), "-i", str(audio),
        "-vf", ",".join(vf_parts), "-af", af,
        "-map", "0:v", "-map", "1:a",
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high",
        "-level", "4.0", "-pix_fmt", "yuv420p", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
        "-movflags", "+faststart", "-shortest", str(out)
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return out if r.returncode == 0 else None

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
