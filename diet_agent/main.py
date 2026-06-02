from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests


app = FastAPI(
    title="CareSync Diet Agent",
    description="식단 추천 에이전트 API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DietRequest(BaseModel):
    content: str


SYSTEM_PROMPT = """
당신은 20대 유능한 전문 식단관리자입니다.
사용자가 입력한 식단을 바탕으로 식단을 분석하고 개선 방향을 제안합니다.

규칙:
- 사용자가 입력하지 않은 음식, 재료, 반찬, 음료, 조리법은 절대 추측하지 마세요.
- 사용자가 "샌드위치"만 입력했다면 햄, 치즈, 야채, 소스 등을 임의로 추가하지 마세요.
- 사용자가 "불고기"만 입력했다면 밥, 김치, 국, 반찬 등을 임의로 추가하지 마세요.
- 정보가 부족하면 "정확한 계산은 어렵습니다"라고 말하고 추가 질문을 하세요.
- 식단 추천은 반드시 음식명 + 양 + 단위로 제시하세요.
- 예: 닭가슴살 100g, 삶은 달걀 2개, 밥 1/2공기, 두부 150g, 물 500ml.
- "단백질을 늘리세요", "탄수화물을 줄이세요"처럼 추상적으로만 말하지 마세요.
- 답변은 자연스러운 한국어로 작성하세요.
- 의료 진단이나 치료처럼 말하지 마세요.
"""


def ask_ollama(content: str) -> str:
    ollama_url = "http://localhost:11434/api/chat"

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": content
        }
    ]

    response = requests.post(
        ollama_url,
        json={
            "model": "gemma3:4b",
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.8,
                "num_predict": 500
            }
        },
        timeout=300
    )

    response.raise_for_status()
    return response.json()["message"]["content"]


@app.get("/agent/status")
def agent_status():
    return {
        "agent": "diet",
        "status": "running"
    }


@app.post("/diet")
def diet_recommend(request: DietRequest):
    answer = ask_ollama(request.content)

    return {
        "response": answer
    }