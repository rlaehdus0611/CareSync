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

BINGE_OR_RECOVERY_KEYWORDS = [
    "폭식", "과식", "많이 먹", "너무 먹", "배불", "소화", "체했", "더부룩",
    "야식", "스트레스먹", "스트레스 먹", "먹고 후회", "먹었는데 운동"
]

WEIGHT_DISTRESS_KEYWORDS = [
    "살쪘", "살 쪘", "살찐", "살 찐", "살이 쪘", "살이쪘",
    "체중 늘", "몸무게 늘", "살 빼", "살빼", "다이어트",
    "말랐", "너무 말", "마른", "뚱뚱", "통통", "몸매", "체형"
]

BODY_SHAMING_KEYWORDS = [
    "놀림", "놀리", "놀렸", "놀림받", "비웃", "무시", "한소리",
    "말랐다고", "살쪘다고", "뚱뚱하다고", "몸매로", "체형으로",
    "외모로", "보기 싫", "말라서", "살쪄서"
]

RECOVERY_MOVEMENT_HINTS = [
    "한숨", "숨 돌", "기분 전환", "걷", "산책", "움직", "풀어", "가볍게"
]

POSITIVE_EMOTION_KEYWORDS = [
    "신나", "기뻐", "기쁘", "행복", "설레", "뿌듯", "즐거", "기분 좋",
    "기분이 좋", "기대돼", "기대되", "들떠", "신났", "기분 최고"
]

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
{"agents": ["mental", "diet", "exercise"], "reason": "감정+식이+회복 운동 복합"}

예시3: "점심 뭐 먹지"
{"agents": ["diet"], "reason": "식단 질문"}

예시4: "우울한데 운동 추천해줘"
{"agents": ["mental", "exercise"], "reason": "감정+운동 복합"}

예시5: "나 살쪘다고 한소리 들어서 슬퍼"
{"agents": ["mental", "diet", "exercise"], "reason": "감정+체중 걱정+회복 운동 복합"}

예시6: "나 너무 말랐다고 놀리더라"
{"agents": ["mental", "diet", "exercise"], "reason": "몸 관련 놀림+멘탈 케어+건강 관리 복합"}

예시7: "너무 신나는데 뭐 하면 좋을까"
{"agents": ["mental", "exercise"], "reason": "긍정 감정+활동 추천 복합"}"""


def _normalize_routing(user_input: str, routing: dict) -> dict:
    agents = routing.get("agents", ["mental"])
    if isinstance(agents, str):
        agents = [agents]

    valid = {"mental", "diet", "exercise"}
    agents = [agent for agent in agents if agent in valid]
    if not agents:
        agents = ["mental"]

    compact = user_input.replace(" ", "")
    needs_recovery_exercise = any(keyword.replace(" ", "") in compact for keyword in BINGE_OR_RECOVERY_KEYWORDS)
    has_weight_distress = any(keyword.replace(" ", "") in compact for keyword in WEIGHT_DISTRESS_KEYWORDS)
    has_body_shaming = any(keyword.replace(" ", "") in compact for keyword in BODY_SHAMING_KEYWORDS)
    has_recovery_movement_hint = any(keyword.replace(" ", "") in compact for keyword in RECOVERY_MOVEMENT_HINTS)
    has_positive_emotion = any(keyword.replace(" ", "") in compact for keyword in POSITIVE_EMOTION_KEYWORDS)
    has_food_context = any(word in user_input for word in ["식단", "식사", "음식", "점심", "저녁", "아침", "먹"])
    has_emotion_context = has_positive_emotion or any(word in user_input for word in ["스트레스", "우울", "힘들", "불안", "폭식", "후회", "슬프", "속상", "상처", "한소리", "혼났", "자책", "놀리", "비웃", "무시"])

    if has_emotion_context and "mental" not in agents:
        agents.insert(0, "mental")

    if has_positive_emotion and not has_body_shaming and not has_weight_distress:
        if "exercise" in agents:
            routing["reason"] = "긍정 감정+활동 추천 복합"
        else:
            routing["reason"] = "긍정 감정 표현+멘탈 케어"

    if needs_recovery_exercise:
        for agent in ["diet", "exercise"]:
            if agent not in agents:
                agents.append(agent)
        if has_emotion_context and "mental" not in agents:
            agents.insert(0, "mental")

        reason = routing.get("reason", "")
        if "운동" not in reason:
            routing["reason"] = "감정+식이+회복 운동 복합"

    if has_food_context and has_emotion_context and "diet" not in agents:
        agents.append("diet")

    if has_body_shaming:
        for agent in ["mental", "diet", "exercise"]:
            if agent not in agents:
                agents.append(agent)
        routing["reason"] = "몸 관련 놀림+멘탈 케어+건강 관리 복합"

    if has_weight_distress and has_emotion_context and not has_body_shaming:
        for agent in ["mental", "diet", "exercise"]:
            if agent not in agents:
                agents.append(agent)
        routing["reason"] = "감정+체중 걱정+회복 운동 복합"

    if has_recovery_movement_hint and has_emotion_context and "exercise" not in agents:
        agents.append("exercise")
        if "운동" not in routing.get("reason", ""):
            routing["reason"] = "감정+회복 운동 복합"

    ordered = [agent for agent in ["mental", "diet", "exercise"] if agent in agents]
    routing["agents"] = ordered
    return routing


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
    routing = json.loads(json_match.group() if json_match else raw)
    return _normalize_routing(user_input, routing)
