"""
오케스트레이터 라우터
사용자 입력을 분석해서 어떤 에이전트로 보낼지 결정
"""
import os
import re
import json
import ollama

OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ROUTER_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")

_client = ollama.AsyncClient(host=OLLAMA_HOST)

ROUTER_SYSTEM = """당신은 헬스케어 AI의 라우터입니다.
사용자 입력을 분석해서 어떤 에이전트가 응답해야 하는지 결정하세요.

에이전트 종류:
- mental  : 감정, 스트레스, 우울, 불안, 일기, 마음, 힘들다, 외롭다, 기분
- diet    : 음식, 식사, 식단, 칼로리, 뭐 먹을, 영양, 살, 체중, 다이어트
- exercise: 운동, 헬스, 산책, 스트레칭, 근육, 체력, 트레이닝

[출력 규칙]
- JSON만 출력
- agents 배열에 해당하는 에이전트 이름 넣기 (복수 가능)
- 애매하면 mental 포함

예시1: "오늘 너무 힘들어"
{"agents": ["mental"], "reason": "감정 표현"}

예시2: "스트레스받아서 폭식했어"
{"agents": ["mental", "diet"], "reason": "감정+식이 복합"}

예시3: "점심 뭐 먹지"
{"agents": ["diet"], "reason": "식단 질문"}

예시4: "우울한데 운동 추천해줘"
{"agents": ["mental", "exercise"], "reason": "감정+운동 복합"}"""


async def classify_intent(user_input: str) -> dict:
    """입력을 분석해서 라우팅 대상 에이전트 목록 반환."""
    response = await _client.chat(
        model=ROUTER_MODEL,
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM},
            {"role": "user",   "content": user_input},
        ],
        options={"temperature": 0.1},
        format="json",
    )
    raw = response.message.content.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    return json.loads(json_match.group() if json_match else raw)
