# Bass Separator

YouTube URL 또는 로컬 오디오 파일을 **보컬 / 기타 / 드럼 / 베이스 / 피아노** 로 분리합니다.  
Facebook Research의 [Demucs](https://github.com/facebookresearch/demucs) 모델 사용.

---

## 빠른 시작

### 1. 의존성 설치

```bash
# Python 패키지
pip install demucs yt-dlp

# ffmpeg (오디오 변환)
brew install ffmpeg          # macOS
sudo apt install ffmpeg      # Ubuntu / WSL
choco install ffmpeg         # Windows
```

### 2. 실행

```bash
python app.py
```

브라우저에서 → **http://localhost:7860**

---

## 기능

| 기능 | 설명 |
|------|------|
| YouTube URL 입력 | yt-dlp로 오디오 자동 다운로드 |
| 로컬 파일 경로 | MP3, WAV, FLAC, M4A 등 |
| 4 stems | 보컬 · 드럼 · 베이스 · 기타(other) |
| 6 stems (추천) | + 기타 · 피아노 따로 분리 |
| Two-stems | 특정 악기만 분리 (나머지는 accompaniment) |
| 출력 형식 | WAV (무손실) / MP3 / FLAC |
| 브라우저 미리듣기 | 분리 즉시 audio 플레이어로 확인 |
| 다운로드 | 스템별 파일 다운로드 |

---

## 모델 선택 가이드

| 모델 | 스템 | 특징 |
|------|------|------|
| `htdemucs_6s` | 6개 | 기타·피아노 별도 분리, 추천 |
| `htdemucs` | 4개 | 빠르고 안정적 |
| `mdx_extra` | 4개 | 보컬 분리 최고 품질 |
| `htdemucs_ft` | 4개 | 각 악기 파인튜닝 버전 |

---

## 출력 파일

분리된 파일은 `separated_output/` 폴더에 저장됩니다.

```
separated_output/
└── htdemucs_6s/
    └── 곡이름/
        ├── bass.wav
        ├── vocals.wav
        ├── drums.wav
        ├── guitar.wav
        ├── piano.wav
        └── other.wav
```

---

## 시스템 요구사항

- Python 3.8+
- RAM: 최소 8GB (16GB 권장)
- GPU: NVIDIA CUDA 선택사항 (있으면 10배 빠름)
- 디스크: 모델 첫 다운로드 시 ~1–2GB

### GPU 가속 (선택)

```bash
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu118
```

---

## 문제 해결

**`demucs: command not found`**
```bash
pip install demucs
```

**`yt-dlp` 오류 (YouTube 차단)**
```bash
yt-dlp --update   # 최신 버전으로 업데이트
```

**처리 속도가 너무 느림**
- GPU 없이 CPU만 사용 시 5–15분 소요
- `--two-stems bass` 옵션으로 베이스만 분리하면 2배 빠름

**모델 첫 실행 시 느림**
- Demucs가 자동으로 모델 가중치를 다운로드합니다 (~500MB)
- 이후 실행은 캐시되어 빠릅니다
