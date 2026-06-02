# 🥗 식단 최적화 에이전트 (조우현)

## 담당
- 식단 최적화 에이전트 개발
- 사업화 모델 분석 (발표 파트)

## 포트
`8001`

## 필수 구현 엔드포인트

```python
# main.py 에 아래 두 엔드포인트 반드시 구현

POST /diet
GET  /agent/status
```

## 요청/응답 형식
`docs/API_SPEC.md` 참고

## 실행
```bash
cd diet_agent
cp .env.example .env   # API 키 입력
pip install -r requirements.txt
python main.py         # http://localhost:8001
```
