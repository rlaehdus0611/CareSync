# CareSync 에이전트 공통 API 명세

> 모든 팀원이 이 스펙을 반드시 준수해야 오케스트레이터와 연동됩니다.

---

## 공통 규칙

- 모든 요청/응답은 `Content-Type: application/json`
- 포트: mental=8000, diet=8001, exercise=8002, orchestrator=9000
- 요청 본문의 입력 키는 반드시 `"content"`

---

## 1. 메인 요청 엔드포인트

### 멘탈 저널링 (임예원)
```
POST http://localhost:8000/journal
Body: { "content": "오늘 너무 힘들었어" }

Response:
{
  "id": 1,
  "emotions": {
    "primary": "불안",
    "scores": { "기쁨":5, "슬픔":40, "불안":60, ... },
    "intensity": 8,
    "summary": "..."
  },
  "keywords": ["외로움", "피곤함"],
  "empathy_response": "많이 힘드셨겠어요...",
  "agent_signal": {
    "agent": "mental_journal",
    "primary_emotion": "불안",
    "intensity": 8,
    "requires_care": true
  }
}
```

### 식단 (조우현)
```
POST http://localhost:8001/diet
Body: { "content": "점심 뭐 먹지" }

Response:
{
  "response": "오늘 점심은 닭가슴살 샐러드를 추천드려요.",
  "recommendation": [...],   // 선택
  "agent_signal": {
    "agent": "diet",
    "calories": 500,          // 선택
    "requires_care": false
  }
}
```

### 운동 (김도연)
```
POST http://localhost:8002/exercise
Body: { "content": "살 빼고 싶어" }

Response:
{
  "response": "유산소 30분 + 근력 20분 루틴을 추천해요.",
  "routine": [...],           // 선택
  "agent_signal": {
    "agent": "exercise",
    "intensity": "medium",    // 선택
    "requires_care": false
  }
}
```

---

## 2. 상태 조회 엔드포인트 (공통 필수)

```
GET /agent/status

Response:
{
  "agent": "mental_journal",   // 또는 "diet", "exercise"
  "status": "ok",
  "data": { ... },             // 에이전트별 최근 데이터
  "recorded_at": "2026-06-02T14:00:00"
}
```

---

## 3. 오케스트레이터 호출 방식

오케스트레이터(`orchestrator/main.py`)에서 각 에이전트를 아래처럼 호출합니다:

```python
AGENT_ENDPOINTS = {
    "mental":   "/journal",
    "diet":     "/diet",
    "exercise": "/exercise",
}
# 공통 payload key
AGENT_PAYLOAD_KEY = {
    "mental":   "content",
    "diet":     "content",
    "exercise": "content",
}
```

**채현 선배에게:** 위 엔드포인트 이름/키가 바뀌면 `orchestrator/main.py`의 `AGENT_ENDPOINTS`와 `AGENT_PAYLOAD_KEY`만 수정하면 됩니다.
