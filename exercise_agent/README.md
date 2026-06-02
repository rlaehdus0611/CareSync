# 💪 운동 최적화 에이전트 (김도연)

## 담당
- 운동 최적화 에이전트 개발
- SWOT 분석 (발표 파트)

## 포트
`8002`

## 필수 구현 엔드포인트

```python
POST /exercise
GET  /agent/status
```

## 요청/응답 형식
`docs/API_SPEC.md` 참고

## 실행
```bash
cd exercise_agent
cp .env.example .env
pip install -r requirements.txt
python main.py         # http://localhost:8002
```
