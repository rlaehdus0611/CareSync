# CareSync Exercise Agent

CareSync 팀 프로젝트의 운동 최적화 에이전트입니다.

## 담당 범위

- 운동 루틴 추천
- 체력 수준별 맞춤 운동 제안
- 멘탈 에이전트 신호를 참고해 불안, 우울, 위기 상태에서는 가벼운 스트레칭과 산책 중심으로 추천

## API

### `POST /exercise`

요청:

```json
{
  "content": "우울한데 운동 추천해줘",
  "mental_status": {
    "primary_emotion": "우울",
    "intensity": 8,
    "requires_care": true,
    "is_crisis": false
  }
}
```

응답:

```json
{
  "response": "현재 우울 신호가 있어 몸을 몰아붙이기보다 긴장을 낮추는 루틴을 추천해요...",
  "intent": "general",
  "level": "intermediate",
  "intensity": "low"
}
```

문서의 공통 규격에 맞춰 `content`를 받고 `response`를 반환합니다. 팀 통합 시 오케스트레이터는 응답의 추가 필드인 `intent`, `level`, `intensity`를 카드 UI 표시나 로그에 활용할 수 있습니다.

## 실행

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

## 테스트

```bash
pytest
```
