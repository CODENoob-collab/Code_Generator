"""
Bass Separator — YouTube URL → Demucs 오디오 분리
실행: python app.py
브라우저: http://localhost:7860
"""

import os
import sys
import subprocess
import threading
import time
import json
import shutil
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import tempfile

OUTPUT_DIR = Path("separated_output")
OUTPUT_DIR.mkdir(exist_ok=True)

JOBS: dict = {}  # job_id -> {status, progress, message, files}

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bass Separator</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0f0f0f; color: #e8e8e8; min-height: 100vh; }
  .wrap { max-width: 720px; margin: 0 auto; padding: 3rem 1.5rem; }
  h1 { font-size: 22px; font-weight: 600; color: #fff; margin-bottom: 6px; }
  .tagline { font-size: 13px; color: #888; margin-bottom: 2.5rem; }
  .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px;
          padding: 1.5rem; margin-bottom: 1.25rem; }
  label { font-size: 13px; color: #aaa; display: block; margin-bottom: 6px; }
  input[type=text], select {
    width: 100%; padding: 10px 14px; font-size: 14px;
    background: #111; border: 1px solid #333; border-radius: 8px;
    color: #e8e8e8; outline: none; transition: border-color 0.15s;
  }
  input[type=text]:focus, select:focus { border-color: #4a9eff; }
  .row { display: flex; gap: 12px; margin-top: 12px; flex-wrap: wrap; }
  .opt-g { flex: 1; min-width: 140px; }
  .btn { padding: 11px 28px; font-size: 14px; font-weight: 600;
         background: #185FA5; color: #fff; border: none; border-radius: 8px;
         cursor: pointer; transition: background 0.15s; margin-top: 14px; }
  .btn:hover { background: #1a6fc2; }
  .btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .progress-wrap { display: none; }
  .progress-label { font-size: 13px; color: #aaa; margin-bottom: 8px; }
  .progress-bar { height: 6px; background: #2a2a2a; border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; background: #4a9eff; width: 0%; transition: width 0.4s; }
  .log { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px;
         color: #6a9f6a; background: #111; border-radius: 6px;
         padding: 10px 12px; margin-top: 10px; max-height: 160px;
         overflow-y: auto; white-space: pre-wrap; word-break: break-all; display: none; }
  .stems { display: none; flex-direction: column; gap: 10px; margin-top: 4px; }
  .stem-row { display: flex; align-items: center; justify-content: space-between;
              background: #111; border: 1px solid #2a2a2a; border-radius: 8px;
              padding: 12px 16px; }
  .stem-name { font-size: 14px; font-weight: 600; }
  .stem-name.bass { color: #4a9eff; }
  .stem-name.vocals { color: #ff7a9a; }
  .stem-name.drums { color: #ffb84a; }
  .stem-name.other { color: #7affb8; }
  .stem-name.guitar { color: #c084fc; }
  .stem-name.piano { color: #f9a8d4; }
  .stem-desc { font-size: 12px; color: #666; margin-top: 2px; }
  .dl-btn { padding: 7px 18px; font-size: 12px; font-weight: 600;
            background: transparent; border: 1px solid #333;
            border-radius: 6px; color: #aaa; cursor: pointer; transition: all 0.15s; }
  .dl-btn:hover { border-color: #4a9eff; color: #4a9eff; }
  .dl-btn.bass-btn:hover { border-color: #4a9eff; color: #4a9eff; }
  .error-box { display: none; background: #2a1010; border: 1px solid #5a2020;
               border-radius: 8px; padding: 12px 16px; margin-top: 10px;
               font-size: 13px; color: #ff8080; }
  .badge { display: inline-block; font-size: 11px; padding: 2px 8px;
           border-radius: 20px; font-weight: 600; margin-left: 8px; }
  .badge-blue { background: #0d2a4a; color: #4a9eff; }
  .badge-green { background: #0a2a1a; color: #4aff9a; }
  .footer { font-size: 12px; color: #555; margin-top: 2.5rem; line-height: 1.6; }
  .model-info { font-size: 12px; color: #555; margin-top: 6px; }
  audio { width: 100%; margin-top: 8px; filter: invert(0.85); border-radius: 4px; }
</style>
</head>
<body>
<div class="wrap">
  <h1>Bass Separator <span class="badge badge-blue">Demucs htdemucs_6s</span></h1>
  <p class="tagline">YouTube URL 또는 로컬 파일 경로를 입력하면 보컬·기타·드럼·베이스·피아노로 분리합니다</p>

  <div class="card">
    <label>YouTube URL 또는 로컬 오디오 파일 경로</label>
    <input type="text" id="urlInput" placeholder="https://www.youtube.com/watch?v=... 또는 /path/to/audio.mp3" />
    <div class="row">
      <div class="opt-g">
        <label>모델</label>
        <select id="model">
          <option value="htdemucs_6s">htdemucs_6s — 6 stems (추천)</option>
          <option value="htdemucs">htdemucs — 4 stems</option>
          <option value="mdx_extra">mdx_extra — 고품질 4 stems</option>
          <option value="htdemucs_ft">htdemucs_ft — 파인튜닝</option>
        </select>
      </div>
      <div class="opt-g">
        <label>출력 형식</label>
        <select id="fmt">
          <option value="wav">WAV (무손실)</option>
          <option value="mp3">MP3 (320kbps)</option>
          <option value="flac">FLAC (무손실 압축)</option>
        </select>
      </div>
      <div class="opt-g">
        <label>Two-stems (선택)</label>
        <select id="twostems">
          <option value="">전체 분리</option>
          <option value="bass">베이스만 분리</option>
          <option value="vocals">보컬만 분리</option>
          <option value="drums">드럼만 분리</option>
        </select>
      </div>
    </div>
    <button class="btn" id="startBtn" onclick="startJob()">분리 시작</button>
  </div>

  <div class="card progress-wrap" id="progressCard">
    <div class="progress-label" id="progressLabel">준비 중...</div>
    <div class="progress-bar"><div class="progress-fill" id="progFill"></div></div>
    <div class="log" id="logBox"></div>
  </div>

  <div class="error-box" id="errorBox"></div>

  <div class="card" id="resultCard" style="display:none">
    <div style="font-size:14px;font-weight:600;color:#fff;margin-bottom:1rem">
      분리 완료 <span class="badge badge-green">Done</span>
    </div>
    <div class="stems" id="stemsDiv"></div>
  </div>

  <div class="footer">
    <strong>필요 패키지:</strong> demucs, yt-dlp, ffmpeg<br>
    설치: <code>pip install demucs yt-dlp</code> + <code>brew install ffmpeg</code> (macOS) / <code>apt install ffmpeg</code> (Linux)<br>
    출력 폴더: <code>separated_output/</code>
  </div>
</div>

<script>
let jobId = null, pollTimer = null;

async function startJob() {
  const url = document.getElementById('urlInput').value.trim();
  if (!url) { showError('URL 또는 파일 경로를 입력해주세요.'); return; }

  const model = document.getElementById('model').value;
  const fmt = document.getElementById('fmt').value;
  const twostems = document.getElementById('twostems').value;

  document.getElementById('startBtn').disabled = true;
  document.getElementById('errorBox').style.display = 'none';
  document.getElementById('resultCard').style.display = 'none';
  document.getElementById('progressCard').style.display = 'block';
  document.getElementById('logBox').style.display = 'block';
  document.getElementById('logBox').textContent = '';
  setProgress(5, '작업 생성 중...');

  try {
    const resp = await fetch('/api/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, model, fmt, twostems })
    });
    const data = await resp.json();
    if (data.error) { showError(data.error); return; }
    jobId = data.job_id;
    pollTimer = setInterval(pollJob, 1500);
  } catch(e) {
    showError('서버 연결 실패: ' + e.message);
    document.getElementById('startBtn').disabled = false;
  }
}

async function pollJob() {
  if (!jobId) return;
  try {
    const resp = await fetch('/api/status/' + jobId);
    const data = await resp.json();
    appendLog(data.message);
    setProgress(data.progress, data.message);
    if (data.status === 'done') {
      clearInterval(pollTimer);
      setProgress(100, '분리 완료!');
      renderStems(data.files, data.song_title);
      document.getElementById('startBtn').disabled = false;
    } else if (data.status === 'error') {
      clearInterval(pollTimer);
      showError(data.message);
      document.getElementById('startBtn').disabled = false;
    }
  } catch(e) { /* 일시적 연결 오류 무시 */ }
}

function appendLog(msg) {
  if (!msg) return;
  const box = document.getElementById('logBox');
  const last = box.textContent.split('\n').pop();
  if (last === msg) return;
  box.textContent += (box.textContent ? '\n' : '') + msg;
  box.scrollTop = box.scrollHeight;
}

function setProgress(pct, label) {
  document.getElementById('progFill').style.width = pct + '%';
  if (label) document.getElementById('progressLabel').textContent = label;
}

const STEM_META = {
  bass:   { label: '베이스',  desc: '베이스 기타 트랙', cls: 'bass' },
  vocals: { label: '보컬',    desc: '메인 보컬 + 백킹 보컬', cls: 'vocals' },
  drums:  { label: '드럼',    desc: '드럼 & 퍼커션', cls: 'drums' },
  other:  { label: '기타/기타', desc: '리드·리듬 기타 등', cls: 'other' },
  guitar: { label: '기타',    desc: '기타 스템', cls: 'guitar' },
  piano:  { label: '피아노',  desc: '피아노 & 건반', cls: 'piano' },
  no_bass:   { label: 'No Bass',   desc: '베이스 제거 믹스', cls: 'other' },
  no_vocals: { label: 'No Vocals', desc: '보컬 제거 (Karaoke)', cls: 'other' },
  no_drums:  { label: 'No Drums',  desc: '드럼 제거 믹스', cls: 'other' },
};

function renderStems(files, title) {
  const div = document.getElementById('stemsDiv');
  div.innerHTML = '';
  if (title) {
    const t = document.createElement('div');
    t.style.cssText = 'font-size:13px;color:#888;margin-bottom:12px';
    t.textContent = '곡: ' + title;
    div.before(t);
  }
  files.forEach(f => {
    const stemKey = Object.keys(STEM_META).find(k => f.name.toLowerCase().includes(k)) || 'other';
    const meta = STEM_META[stemKey] || { label: f.name, desc: '', cls: 'other' };
    const row = document.createElement('div');
    row.className = 'stem-row';
    row.innerHTML = `
      <div>
        <div class="stem-name ${meta.cls}">${meta.label}</div>
        <div class="stem-desc">${meta.desc} · ${f.size}</div>
        <audio controls src="/download/${encodeURIComponent(f.name)}"></audio>
      </div>
      <button class="dl-btn ${meta.cls}-btn" onclick="download('${f.name}')">다운로드</button>`;
    div.appendChild(row);
  });
  div.style.display = 'flex';
  document.getElementById('resultCard').style.display = 'block';
  document.getElementById('resultCard').scrollIntoView({ behavior: 'smooth' });
}

function download(name) {
  const a = document.createElement('a');
  a.href = '/download/' + encodeURIComponent(name);
  a.download = name;
  a.click();
}

function showError(msg) {
  const box = document.getElementById('errorBox');
  box.textContent = '오류: ' + msg;
  box.style.display = 'block';
  document.getElementById('progressCard').style.display = 'none';
}
</script>
</body>
</html>
"""


def run_separation(job_id: str, url: str, model: str, fmt: str, twostems: str):
    job = JOBS[job_id]
    tmp_dir = Path(tempfile.mkdtemp(prefix="bass_sep_"))
    try:
        # ── Step 1: 오디오 취득 ──────────────────────────────
        is_youtube = url.startswith("http://") or url.startswith("https://")
        if is_youtube:
            job["progress"] = 10
            job["message"] = "YouTube에서 오디오 다운로드 중..."
            audio_path = tmp_dir / "input.%(ext)s"
            cmd = [
                "yt-dlp",
                "--extract-audio",
                "--audio-format", "wav",
                "--audio-quality", "0",
                "--output", str(audio_path),
                "--no-playlist",
                "--no-warnings",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"yt-dlp 오류: {result.stderr.strip()[:300]}")

            # 실제 다운로드된 파일 찾기
            audio_files = list(tmp_dir.glob("input.*"))
            if not audio_files:
                raise RuntimeError("오디오 파일 다운로드 실패")
            audio_file = audio_files[0]

            # 곡 제목 추출
            title_cmd = ["yt-dlp", "--get-title", "--no-playlist", url]
            title_res = subprocess.run(title_cmd, capture_output=True, text=True)
            job["song_title"] = title_res.stdout.strip() if title_res.returncode == 0 else "Unknown"
        else:
            audio_file = Path(url)
            if not audio_file.exists():
                raise RuntimeError(f"파일을 찾을 수 없습니다: {url}")
            job["song_title"] = audio_file.stem

        job["progress"] = 30
        job["message"] = f"Demucs 모델 로딩 중 ({model})..."

        # ── Step 2: Demucs 분리 ────────────────────────────────
        demucs_cmd = [
            sys.executable, "-m", "demucs",
            "--name", model,
            "--out", str(OUTPUT_DIR),
        ]
        if fmt != "wav":
            demucs_cmd += ["--mp3" if fmt == "mp3" else "--flac"]
        if twostems:
            demucs_cmd += ["--two-stems", twostems]
        demucs_cmd.append(str(audio_file))

        job["progress"] = 35
        job["message"] = "분리 진행 중... (수 분 소요될 수 있습니다)"

        proc = subprocess.Popen(
            demucs_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # 진행률 파싱 (Demucs stderr에서 %)
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            job["message"] = line[:120]
            # "Separating track X/Y" 패턴
            if "%" in line:
                try:
                    pct_str = [t for t in line.split() if "%" in t][0].replace("%", "")
                    pct = float(pct_str)
                    job["progress"] = 35 + int(pct * 0.55)
                except Exception:
                    pass

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"Demucs 실패 (코드 {proc.returncode})")

        # ── Step 3: 결과 파일 수집 ─────────────────────────────
        job["progress"] = 95
        job["message"] = "결과 파일 정리 중..."

        stem_files = []
        song_name = audio_file.stem
        search_dirs = list(OUTPUT_DIR.rglob("*.wav")) + \
                      list(OUTPUT_DIR.rglob("*.mp3")) + \
                      list(OUTPUT_DIR.rglob("*.flac"))

        for f in search_dirs:
            size_mb = f.stat().st_size / 1024 / 1024
            stem_files.append({
                "name": f.name,
                "path": str(f),
                "size": f"{size_mb:.1f} MB",
            })

        if not stem_files:
            raise RuntimeError("분리된 파일을 찾을 수 없습니다")

        job["files"] = stem_files
        job["status"] = "done"
        job["progress"] = 100
        job["message"] = "분리 완료!"

    except Exception as e:
        job["status"] = "error"
        job["message"] = str(e)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # 콘솔 로그 억제

    def send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path)

        if p.path == "/":
            body = HTML_PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif p.path.startswith("/api/status/"):
            job_id = p.path.split("/")[-1]
            job = JOBS.get(job_id)
            if not job:
                self.send_json({"error": "job not found"}, 404)
                return
            self.send_json({
                "status": job["status"],
                "progress": job["progress"],
                "message": job["message"],
                "files": job.get("files", []),
                "song_title": job.get("song_title", ""),
            })

        elif p.path.startswith("/download/"):
            from urllib.parse import unquote
            fname = unquote(p.path[len("/download/"):])
            # 보안: OUTPUT_DIR 내부만 서빙
            matches = list(OUTPUT_DIR.rglob(fname))
            if not matches:
                self.send_response(404)
                self.end_headers()
                return
            fpath = matches[0]
            data = fpath.read_bytes()
            ext = fpath.suffix.lower()
            ctype = {"wav": "audio/wav", "mp3": "audio/mpeg", "flac": "audio/flac"}.get(ext[1:], "application/octet-stream")
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Content-Disposition", f'attachment; filename="{fpath.name}"')
            self.end_headers()
            self.wfile.write(data)

        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/start":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            url = body.get("url", "").strip()
            model = body.get("model", "htdemucs_6s")
            fmt = body.get("fmt", "wav")
            twostems = body.get("twostems", "")

            if not url:
                self.send_json({"error": "URL이 비어 있습니다"})
                return

            job_id = str(int(time.time() * 1000))
            JOBS[job_id] = {
                "status": "running",
                "progress": 0,
                "message": "시작 중...",
                "files": [],
                "song_title": "",
            }
            t = threading.Thread(
                target=run_separation,
                args=(job_id, url, model, fmt, twostems),
                daemon=True,
            )
            t.start()
            self.send_json({"job_id": job_id})
        else:
            self.send_response(404)
            self.end_headers()


def check_deps():
    missing = []
    for cmd in [["demucs", "--help"], ["yt-dlp", "--version"], ["ffmpeg", "-version"]]:
        try:
            subprocess.run(cmd, capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            missing.append(cmd[0])
    return missing


if __name__ == "__main__":
    print("=" * 52)
    print("  Bass Separator  —  Demucs + yt-dlp")
    print("=" * 52)

    missing = check_deps()
    if missing:
        print(f"\n[경고] 누락된 패키지: {', '.join(missing)}")
        print("  pip install demucs yt-dlp")
        print("  brew install ffmpeg  (macOS)")
        print("  apt install ffmpeg   (Linux/WSL)\n")
    else:
        print("\n[OK] 모든 의존성 확인 완료\n")

    host, port = "localhost", 7860
    server = HTTPServer((host, port), Handler)
    print(f"  브라우저 열기: http://{host}:{port}")
    print("  종료: Ctrl+C\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버 종료")
