# Lexisub User Stories

End-user stories for verifying Lexisub against real-world workflows. Each story has explicit acceptance criteria so you can run it through `scripts/run_demo.py` and check the report.

The first story (U1) is the canonical "happy path" and should always pass on the bundled test fixture. The rest require user-provided video files (placed under `demos/videos/`) — see `demos/README.md` for sourcing guidance.

---

## U1: 영문 BJJ/MMA 강의 영상에 한국어 자막 입히기 (canonical)

**페르소나**: 한국인 MMA 트레이너. 외국 코치의 영상을 본인 수강생에게 한국어 자막과 함께 보여주려 함.

**입력**
- 영상: 5–15분, 깔끔한 영어 발음, MMA 도메인 어휘 포함
- 용어집: `tests/fixtures/glossary.csv` (4개 그래플링 용어) 또는 `demos/glossaries/bjj.csv`

**워크플로우**
1. 용어집 탭에서 CSV 가져오기
2. 영상을 영상 처리 탭에 드롭
3. [자막 생성 시작]
4. 진행률이 음성 추출 → 음성 인식 → 번역 → 자막 mux → 완료 순으로 흐름
5. 영상 옆에 `.ko.srt`와 `.subbed.mkv` 생성

**Acceptance Criteria**
- [ ] `.subbed.mkv`가 생성되고 VLC에서 한국어 자막 트랙이 켜진다
- [ ] 입력 영상의 비디오 코덱(`h264`, `hevc` 등)이 출력에서 동일하게 유지된다 (재인코딩 없음)
- [ ] 입력 큐 개수와 출력 큐 개수가 같다 (타임스탬프 보존)
- [ ] 등록한 용어집 용어가 영상에서 등장하면 100% 한국어 용어집대로 번역된다 (예: "guard pass" → "가드 패스")
- [ ] 자막 텍스트가 자연스러운 한국어 강의체 (`-입니다`, `-합니다`)로 끝난다 (어색한 영어식 어순 최소)

**자동 검증** (`scripts/run_demo.py`로 측정)
- 출력 파일 존재 여부
- ffprobe로 비디오 코덱 동일성
- 입출력 큐 카운트 일치
- 용어집 hit rate (등록 용어 중 결과 자막에 등장한 용어 비율)

**이미 자동화됨**: `tests/integration/test_pipeline.py::test_end_to_end_produces_srt_and_mkv` (heavy)

---

## U2: 인도식 영어 영상

**페르소나**: 인도 출신 코치(예: Mahesh Manohar)의 BJJ 강의를 보는 한국 트레이너.

**입력**
- 영상: 5–15분, 인도식 영어 (rhotic, retroflex 자음, 빠른 발화)
- 용어집: U1과 동일

**Acceptance Criteria**
- [ ] STT 인식이 70% 이상의 단어를 정확히 추출 (수동 평가; 너무 깨지면 N/A 처리)
- [ ] 명백한 오인식이 발생해도 번역이 자연스러운 한국어 흐름을 유지 (Gemma 3가 문맥 보정)
- [ ] 용어집 용어 hit rate ≥ 80%

**자동 검증**: hit rate. 인식 정확도는 사람 평가.

**리스크**: Whisper large-v3-turbo가 인도식 영어에서 평이한 미국식보다 5-15% 떨어지는 경향이 있음. 용어집이 후처리 안전망 역할.

---

## U3: 다국어 입력 (포르투갈어 BJJ)

**페르소나**: 브라질 BJJ 챔피언의 포르투갈어 영상을 학습용으로 시청.

**입력**
- 영상: 포르투갈어 음성
- 용어집: 포르투갈어 키 포함 (예: `passagem de guarda` → `가드 패스`). 기본 fixture가 `pt` 행 1개 포함.

**Acceptance Criteria**
- [ ] 자동 언어 감지가 `pt`로 분류
- [ ] `build_system_prompt(source_lang="pt")` 결과로 포르투갈어 → 한국어 직접 번역 (영어 경유 X)
- [ ] 등록한 pt 용어 hit rate ≥ 80%
- [ ] 한국어 출력이 자연스러움

---

## U4: 긴 영상 (1시간 마스터클래스)

**페르소나**: John Danaher 식 1시간짜리 마스터클래스 1편을 한국어 자막으로 뽑아두려는 트레이너.

**입력**
- 영상: ~60분
- 용어집: 50–100 entries

**Acceptance Criteria**
- [ ] 8GB 메모리에서 OOM 없이 완료 (사전: 무거운 앱 종료)
- [ ] 처리 시간 ≤ 영상 길이 × 2 (즉, 1시간 영상 → 2시간 이내). M1 Air 기준 목표.
- [ ] 진행률 콜백이 stage별로 정상 호출
- [ ] 출력 SRT 큐 수가 입력 영상의 음성 활동 구간 추정치(분당 ~10–20 큐)와 합리적으로 일치

**리스크**: M1 Air 8GB는 일부 큰 청크에서 swap 가능성 있음. `gc.collect()`로 mlx-whisper 언로드 후 mlx-lm 로드하므로 직렬 운영. 만약 OOM이 일어나면 `chunk_size` 축소(25 → 15) 또는 4-bit 양자화 더 작은 모델로 다운그레이드 검토.

---

## U5: 사용자 정의 용어집 강제 적용

**페르소나**: 트레이너가 본인 수업에서 일관되게 쓰는 어휘로 자막을 통일하고 싶음.

**입력**
- 영상: U1의 짧은 영상
- 용어집: 사용자 정의 (예: `kimura → 키무라`, `triangle choke → 트라이앵글 초크`, `mount → 마운트`)

**워크플로우**
1. 용어집 탭에서 사용자 정의 CSV 가져오기
2. 일부 용어를 `pending` 상태로 두고 일부만 `approved`
3. 영상 처리

**Acceptance Criteria**
- [ ] `approved` 용어 100%가 결과 자막에 그대로 등장 (영상에서 해당 영어 표현이 등장한 경우)
- [ ] `pending` 용어는 시스템 프롬프트에 들어가지 않음 → Gemma가 자유 번역 (의도된 동작)
- [ ] 사용자가 GUI에서 더블클릭으로 status 토글 후 다시 처리하면 결과가 즉시 반영됨

**자동 검증**: 처리 전후 `repository.list_terms(status="approved")` 비교 + 출력 SRT 텍스트에서 정확 매칭 검색.

---

## 자동 검증 지표 정의

`scripts/run_demo.py`가 다음을 측정해 리포트:

| 지표 | 정의 | 목표 |
|---|---|---|
| **stt_cue_count** | Whisper 출력 큐 개수 | 영상 길이 분당 10–20 |
| **stt_lang** | 감지된 언어 | 의도한 언어와 일치 |
| **translation_cue_count** | 번역 후 큐 개수 | stt_cue_count와 동일 |
| **glossary_hit_rate** | 영상 텍스트에서 등장한 용어 중 출력에 한국어 용어집대로 등장한 비율 | ≥ 80% (U2) / 100% (U5) |
| **video_codec_preserved** | 입력/출력 비디오 코덱 동일 | True |
| **wall_time_seconds** | 전체 처리 시간 | 영상 길이 × 2 이하 |
| **peak_memory_mb** | (선택) RSS 피크 | 6GB 이하 |

수동 평가 항목 (사람이 보고 결정):
- 자막 자연스러움 (1–5점)
- 어조 일관성 (강의체 유지)
- 명백한 오역 개수
