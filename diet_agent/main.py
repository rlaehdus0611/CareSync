from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import requests
import os
from pathlib import Path


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "gemma3:4b")
BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="CareSync Diet Agent",
    description="식단 추천 에이전트 API",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


class DietRequest(BaseModel):
    content: str

    # 아래 값들은 선택 사항입니다.
    # 통합 UI에서 보내주면 더 정확한 분석 가능
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    goal: Optional[str] = None
    activity_level: Optional[str] = None
    food_style: Optional[str] = None
    restrictions: Optional[str] = None


def calc_bmi(height_cm: float, weight_kg: float) -> float:
    height_m = height_cm / 100
    return weight_kg / (height_m ** 2)


def calc_bmr(age: int, gender: str, height_cm: float, weight_kg: float) -> float:
    if gender == "남성":
        return 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        return 10 * weight_kg + 6.25 * height_cm - 5 * age - 161


def get_activity_factor(activity_level: Optional[str]) -> float:
    factors = {
        "거의 운동 안 함": 1.2,
        "가벼운 활동": 1.375,
        "보통 활동": 1.55,
        "활동 많음": 1.725,
        "매우 활동적": 1.9
    }
    return factors.get(activity_level, 1.2)


def get_bmi_status(bmi: float):
    if bmi < 18.5:
        return "저체중", "18.5 미만"
    elif bmi < 23:
        return "정상", "18.5 이상 ~ 23 미만"
    elif bmi < 25:
        return "과체중", "23 이상 ~ 25 미만"
    elif bmi < 30:
        return "비만", "25 이상 ~ 30 미만"
    else:
        return "고도비만", "30 이상"


def calc_target_calorie(tdee: float, goal: Optional[str], bmi_label: Optional[str]) -> float:
    if bmi_label == "저체중" and goal in ["체중 감량", "체지방 감량"]:
        return tdee + 200

    if goal == "체중 감량":
        return tdee - 400
    elif goal == "체지방 감량":
        return tdee - 300
    elif goal == "근육량 증가":
        return tdee + 250
    elif goal == "체중 유지":
        return tdee
    else:
        return tdee


def get_goal_safety_message(bmi_label: Optional[str], goal: Optional[str]) -> str:
    if bmi_label == "저체중" and goal in ["체중 감량", "체지방 감량"]:
        return """
[목표 안전 확인 필요]
현재 사용자는 BMI 기준 저체중입니다.
그런데 목표가 체중 감량 또는 체지방 감량으로 설정되어 있습니다.

응답 지침:
- 먼저 "현재 BMI 기준으로는 저체중에 해당합니다. 정말 체중 감량이 목표가 맞나요?"라고 확인하세요.
- 체중 감량 식단은 제공하지 마세요.
- "현재 상태에서는 체중 감량 식단을 안내하기 어렵습니다"라고 말하세요.
- 대신 식사량을 늘리고 단백질과 탄수화물을 충분히 섭취하는 균형 잡힌 식단을 제시하세요.
"""

    if bmi_label in ["비만", "고도비만"] and goal == "체중 유지":
        return """
[목표 안전 안내]
현재 사용자는 BMI 기준 비만 또는 고도비만에 해당합니다.
현재 목표는 체중 유지이지만, 건강 관리를 위해서는 완만한 체중 감량 방향이 더 권장됩니다.

응답 지침:
- "현재 BMI 기준으로는 체중 유지보다 완만한 체중 감량 식단이 더 권장됩니다"라고 안내하세요.
- 사용자의 목표가 체중 유지라는 점은 존중하세요.
- 식단은 과식 방지, 칼로리 조절, 단백질 유지, 채소 섭취 증가 방향으로 제시하세요.
- 반드시 음식명, 양, 단위를 포함하세요.
"""

    return ""


def build_profile_context(request: DietRequest) -> str:
    if not all([request.age, request.gender, request.height_cm, request.weight_kg]):
        return """
사용자 프로필:
- 상세 신체 정보 없음
- BMI, BMR, 목표 칼로리는 계산하지 않음
"""

    bmi = calc_bmi(request.height_cm, request.weight_kg)
    bmi_label, bmi_range = get_bmi_status(bmi)

    bmr = calc_bmr(
        request.age,
        request.gender,
        request.height_cm,
        request.weight_kg
    )

    tdee = bmr * get_activity_factor(request.activity_level)
    target_kcal = calc_target_calorie(tdee, request.goal, bmi_label)
    safety_message = get_goal_safety_message(bmi_label, request.goal)

    return f"""
사용자 프로필:
- 나이: {request.age}
- 성별: {request.gender}
- 키: {request.height_cm}cm
- 몸무게: {request.weight_kg}kg
- BMI: {bmi:.1f} ({bmi_label}, {bmi_range})
- 목표: {request.goal if request.goal else "입력 없음"}
- 활동량: {request.activity_level if request.activity_level else "입력 없음"}
- 주요 식사 형태: {request.food_style if request.food_style else "입력 없음"}
- 알레르기/제한 음식: {request.restrictions if request.restrictions else "없음"}
- 기초대사량 BMR: {bmr:.0f} kcal
- 유지 칼로리 TDEE: {tdee:.0f} kcal
- 목표 칼로리: {target_kcal:.0f} kcal

{safety_message}
"""


SYSTEM_PROMPT = """
당신은 20대 유능한 전문 식단관리자입니다.
사용자의 식단을 분석하고 목표에 맞는 식단 개선 방향을 제시합니다.

중요 규칙:
1. 사용자가 입력하지 않은 음식, 재료, 반찬, 음료, 조리법은 절대 추측하지 마세요.
2. "샌드위치"만 입력되면 햄, 치즈, 야채, 소스 등을 임의로 추가하지 마세요.
3. "불고기"만 입력되면 밥, 김치, 반찬, 국 등을 임의로 추가하지 마세요.
4. 정보가 부족하면 "정확한 계산은 어렵습니다"라고 말하고 추가 질문을 하세요.
5. 식단 추천은 반드시 음식명 + 양 + 단위로 제시하세요.
6. 예: 닭가슴살 100g, 삶은 달걀 2개, 두부 150g, 밥 1/2공기, 샐러드 채소 100g, 물 500ml.
7. "단백질을 늘리세요", "탄수화물을 줄이세요"처럼 추상적으로만 말하지 마세요.
8. BMI 상태와 목표가 충돌하면 안전 안내를 우선하세요.
9. 저체중 사용자가 체중 감량을 목표로 하면 체중 감량 식단은 제공하지 마세요.
10. 비만 또는 고도비만 사용자가 체중 유지를 목표로 하면 완만한 감량 방향의 식단을 권장하세요.
11. 의료 진단, 치료, 약물 처방처럼 말하지 마세요.
12. 답변은 자연스러운 한국어로 작성하세요.
13. 의미 없는 영어 문자열, 깨진 문자, 자음/모음 반복을 출력하지 마세요.

답변 형식:
1. 입력된 식단 요약
2. 현재 식단 평가
3. 정확한 계산 가능 여부
4. 개선 추천
5. 오늘의 작은 실천 미션
"""


def clean_response(text: str) -> str:
    replacements = {
        "복수해야 합니다": "보수적으로 추정해야 합니다",
        "복수 해야 합니다": "보수적으로 추정해야 합니다",
        "말씀 희석입니다": "참고해 주세요",
        "말씀 희석": "참고",
        "희석입니다": "참고해 주세요",
        "유지시므로": "유지이므로",
        "감량시므로": "감량이므로",
        "추천드리겠습니다": "추천드립니다",
        "말씀드리겠습니다": "안내드립니다",
        "yto": "",
        "asdf": "",
        "undefined": "",
        "null": "",
        "ㅠㅠ": "",
        "ㅋㅋㅋ": "",
        "ㅎㅎㅎ": "",
    }

    for wrong, right in replacements.items():
        text = text.replace(wrong, right)

    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if stripped in ["-", "•", "*"]:
            continue

        if stripped.lower() in ["yto", "asdf", "undefined", "null", "none"]:
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def ask_ollama(request: DietRequest) -> str:
    profile_context = build_profile_context(request)

    user_prompt = f"""
{profile_context}

사용자 식단 입력:
{request.content}

요청:
위 정보를 바탕으로 식단을 분석해 주세요.

반드시 지킬 것:
- 입력하지 않은 음식은 추측하지 마세요.
- 음식 양이 부족하면 추가 질문을 하세요.
- 식단 추천은 음식명 + 양 + 단위로 제시하세요.
- 목표와 BMI 상태가 충돌하면 안전 안내를 먼저 하세요.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL_NAME,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0.15,
                "top_p": 0.75,
                "num_predict": 500
            }
        },
        timeout=300
    )

    response.raise_for_status()
    answer = response.json()["message"]["content"]

    return clean_response(answer)


@app.get("/")
def root():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/interaction-preview")
def interaction_preview():
    return {
        "agent": "diet",
        "purpose": "식단 담당 영역에서 미리 확인하는 멀티 에이전트 연동 화면 예시",
        "steps": [
            {
                "from_agent": "mental",
                "to_agent": "diet",
                "title": "멘탈 상태 기반 식단 조정",
                "summary": "멘탈 에이전트가 스트레스나 폭식 위험을 감지하면 식단 에이전트는 자극적인 음식보다 속이 편한 균형식 중심으로 추천 방향을 조정합니다.",
                "recommendations": [
                    "맵고 기름진 음식 줄이기",
                    "죽, 국, 두부, 바나나처럼 부담 적은 음식 우선",
                    "굶기보다 소량씩 규칙적으로 먹기"
                ],
            },
            {
                "from_agent": "mental",
                "to_agent": "exercise",
                "title": "멘탈 상태 기반 운동 강도 조정",
                "summary": "멘탈 에이전트가 피로감, 스트레스, 무기력 정도를 전달하면 운동 에이전트는 고강도 운동보다 회복형 활동을 우선하도록 추천 강도를 조정합니다.",
                "recommendations": [
                    "20분 가벼운 걷기",
                    "목과 어깨 스트레칭 10분",
                    "숨 고르기나 명상 5분"
                ],
            },
            {
                "from_agent": "exercise + diet",
                "to_agent": "orchestrator",
                "title": "식단과 운동 응답 최종 조율",
                "summary": "통합 단계에서는 식단과 운동 응답을 함께 보고 식사 리듬 회복과 가벼운 활동을 우선하는 방향으로 최종 결과를 정리합니다.",
                "recommendations": [
                    "운동은 가벼운 강도부터 시작하기",
                    "식사는 거르지 않고 적정량 유지하기",
                    "자기 전 수분 섭취와 휴식 챙기기"
                ],
            },
        ],
        "final_summary": "이 화면은 실제 멘탈/운동 에이전트 호출 결과가 아니라, 식단 담당 영역에서 준비해둔 통합 연동 미리보기입니다.",
    }


# ---------------------------------------------------------------------------
# 오케스트레이터 담당자 참고용: 실제 멀티 에이전트 연동 예시
# ---------------------------------------------------------------------------
# 아래 코드는 diet_agent에서 실행하려는 코드가 아니라, 나중에 orchestrator/main.py의
# /chat 처리 흐름에 붙일 수 있는 참고용 설계 코드입니다.
#
# 핵심 아이디어:
# 1. 오케스트레이터가 기존처럼 mental / diet / exercise 에이전트를 호출합니다.
# 2. 성공한 응답만 모읍니다.
# 3. mental 응답의 emotions 또는 agent_signal을 보고 식단/운동 조정 이유를 만듭니다.
# 4. diet, exercise 응답을 함께 보고 interaction_steps와 final_summary를 만듭니다.
# 5. 프론트는 interaction_steps가 있으면 카드로 보여주고, 없으면 기존 응답만 보여주면 됩니다.
#
# 예시 응답 구조:
# {
#   "routed_to": ["mental", "diet", "exercise"],
#   "reason": "감정+식단+운동 복합 요청",
#   "results": [...기존 개별 에이전트 응답...],
#   "interaction_steps": [
#       {
#           "from_agent": "mental",
#           "to_agent": "diet",
#           "title": "멘탈 상태 기반 식단 조정",
#           "summary": "스트레스 상태를 반영해 자극적인 음식보다 속이 편한 식단으로 조정합니다.",
#           "recommendations": ["맵고 기름진 음식 줄이기", "소량씩 규칙적으로 먹기"]
#       }
#   ],
#   "final_summary": "오늘은 회복 중심의 식단과 가벼운 활동이 적절합니다."
# }
#
# 실제 orchestrator 쪽에 넣을 수 있는 형태의 의사 코드:
#
# class InteractionStep(BaseModel):
#     from_agent: str
#     to_agent: str
#     title: str
#     summary: str
#     recommendations: list[str] = []
#
#
# class ChatResponse(BaseModel):
#     routed_to: list[str]
#     reason: str
#     results: list[AgentResult]
#     interaction_steps: list[InteractionStep] = []
#     final_summary: str | None = None
#
#
# def build_interaction_steps(results: list[AgentResult]):
#     ok_results = {r.agent: r.response for r in results if r.status == "ok" and r.response}
#     steps = []
#
#     mental = ok_results.get("mental")
#     diet = ok_results.get("diet")
#     exercise = ok_results.get("exercise")
#
#     # mental 응답 예시:
#     # mental["emotions"]["primary"] == "불안"
#     # mental["emotions"]["intensity"] == 8
#     # mental["agent_signal"]["requires_care"] == True
#     if mental:
#         emotions = mental.get("emotions", {})
#         signal = mental.get("agent_signal", {})
#         primary = emotions.get("primary") or signal.get("primary_emotion")
#         intensity = emotions.get("intensity") or signal.get("intensity")
#         mental_status = f"{primary} {intensity}/10" if primary and intensity else "멘탈 상태 참고"
#     else:
#         mental_status = "멘탈 상태 정보 없음"
#
#     if mental and diet:
#         steps.append({
#             "from_agent": "mental",
#             "to_agent": "diet",
#             "title": "멘탈 상태 기반 식단 조정",
#             "summary": f"{mental_status} 상태를 반영해 식단 추천을 균형식 중심으로 조정합니다.",
#             "recommendations": [
#                 "자극적인 음식보다 속이 편한 음식 우선",
#                 "굶기보다 소량씩 규칙적으로 먹기",
#             ],
#         })
#
#     if mental and exercise:
#         steps.append({
#             "from_agent": "mental",
#             "to_agent": "exercise",
#             "title": "멘탈 상태 기반 운동 강도 조정",
#             "summary": f"{mental_status} 상태를 반영해 고강도보다 회복형 운동을 우선합니다.",
#             "recommendations": [
#                 "20분 가벼운 걷기",
#                 "목과 어깨 스트레칭",
#             ],
#         })
#
#     if exercise and diet:
#         steps.append({
#             "from_agent": "exercise + diet",
#             "to_agent": "orchestrator",
#             "title": "식단과 운동 응답 최종 조율",
#             "summary": "식단 응답과 운동 응답을 함께 보고 사용자가 바로 실천할 수 있는 방향으로 정리합니다.",
#             "recommendations": [
#                 "식사는 거르지 않고 적정량 유지",
#                 "운동은 낮은 강도부터 시작",
#             ],
#         })
#
#     final_summary = None
#     if len(ok_results) >= 2:
#         final_summary = "여러 에이전트 응답을 종합한 결과, 오늘은 무리한 변화보다 회복 중심 관리가 적절합니다."
#
#     return steps, final_summary
#
#
# # orchestrator의 /chat 마지막 부분 예시:
# results = await asyncio.gather(*[call_agent(agent, req.message) for agent in agents])
# interaction_steps, final_summary = build_interaction_steps(list(results))
# return ChatResponse(
#     routed_to=agents,
#     reason=reason,
#     results=list(results),
#     interaction_steps=interaction_steps,
#     final_summary=final_summary,
# )


@app.get("/agent/status")
def agent_status():
    return {
        "agent": "diet",
        "status": "running",
        "model": MODEL_NAME
    }


@app.post("/diet")
def diet_recommend(request: DietRequest):
    answer = ask_ollama(request)

    return {
        "response": answer
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
