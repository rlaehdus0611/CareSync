# 🏥 CareSync — 헬스케어 멀티 에이전트 AI

> 자연어처리 팀 프로젝트 | 멘탈 저널링 · 식단 · 운동 통합 AI 시스템

---

## 팀원 & 역할

| 이름 | 에이전트 | 폴더 | 포트 | 발표 파트 |
|------|---------|------|------|---------|
| 임예원 | 🧠 멘탈 저널링 | `mental_journal_agent/` | 8000 | PPT 총괄 |
| 조우현 | 🥗 식단 최적화 | `diet_agent/` | 8001 | 사업화 모델 |
| 김도연 | 💪 운동 최적화 | `exercise_agent/` | 8002 | SWOT 분석 |
| 이채현 | 🔀 통합 오케스트레이터 + UI | `orchestrator/` | 9000 | 시장성 분석 |

---

## 핵심 일정

| 날짜 | 내용 | 담당 |
|------|------|------|
| **~6/3 (수)** | 에이전트 개발 완료 | 예원·도연·우현 |
| **~6/5 (금)** | 통합 시스템 + UI 완성 | 채현 |
| **~6/8 (월)** | PPT 완성 | 전체 |
| **6/12 (금)** | 발표 | 전체 |

---

## 프로젝트 구조

```
caresync/
├── mental_journal_agent/   # 임예원
├── diet_agent/             # 조우현
├── exercise_agent/         # 김도연
├── orchestrator/           # 이채현
└── docs/
    └── API_SPEC.md         # ← 반드시 읽기!
```

---

## 브랜치 전략

```
main              ← PR 머지만 (직접 푸시 금지)
feature/mental    ← 임예원
feature/diet      ← 조우현
feature/exercise  ← 김도연
feature/integrate ← 이채현
```

---

## 시작하기

```bash
git clone https://github.com/Lim-yewon/repository-exercise.git caresync
cd caresync
git checkout feature/본인브랜치
```

> **⚠️ 중요:** `.env` 파일은 절대 커밋하지 마세요. `.env.example`만 올리세요.
> 에이전트 API 스펙은 반드시 `docs/API_SPEC.md`를 따르세요.
