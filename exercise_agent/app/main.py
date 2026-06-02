from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app.exercise_agent import MentalStatus, recommend_exercise


app = FastAPI(
    title="CareSync Exercise Agent",
    description="Exercise optimization agent for CareSync multi-agent healthcare AI.",
    version="0.1.0",
)


HOME_PAGE = """
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>CareSync Exercise Agent</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, "Malgun Gothic", sans-serif;
      background: #f6f8fb;
      color: #172033;
    }
    main {
      width: min(920px, 100%);
      margin: 0 auto;
      padding: 32px 18px;
    }
    header {
      margin-bottom: 22px;
    }
    h1 {
      margin: 0 0 8px;
      font-size: 28px;
      letter-spacing: 0;
    }
    p {
      margin: 0;
      color: #5f6f85;
      line-height: 1.55;
    }
    section {
      background: #ffffff;
      border: 1px solid #dce3ee;
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 8px 22px rgba(23, 32, 51, 0.06);
    }
    label {
      display: block;
      margin: 14px 0 7px;
      font-weight: 700;
      color: #26344d;
    }
    textarea, select, input {
      width: 100%;
      border: 1px solid #c9d4e4;
      border-radius: 6px;
      padding: 11px 12px;
      font: inherit;
      background: #ffffff;
    }
    textarea {
      min-height: 108px;
      resize: vertical;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
    }
    .check {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      font-weight: 400;
    }
    .check input {
      width: 18px;
      height: 18px;
    }
    button {
      margin-top: 18px;
      width: 100%;
      border: 0;
      border-radius: 6px;
      padding: 13px 16px;
      background: #1d6f8f;
      color: white;
      font-weight: 700;
      font-size: 16px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.65;
      cursor: wait;
    }
    #result {
      margin-top: 16px;
      display: none;
      border-left: 4px solid #1d6f8f;
      background: #eef7fa;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .tag {
      border: 1px solid #b9d8e3;
      border-radius: 999px;
      padding: 5px 9px;
      color: #24556a;
      background: #ffffff;
      font-size: 13px;
    }
    @media (max-width: 680px) {
      .grid { grid-template-columns: 1fr; }
      main { padding: 22px 14px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>CareSync 운동 에이전트</h1>
      <p>사용자 입력과 멘탈 상태를 참고해 운동 루틴을 추천합니다.</p>
    </header>

    <section>
      <form id="exercise-form">
        <label for="content">운동 요청</label>
        <textarea id="content" name="content">우울한데 운동 추천해줘</textarea>

        <div class="grid">
          <div>
            <label for="emotion">감정</label>
            <select id="emotion" name="emotion">
              <option value="">없음</option>
              <option value="우울" selected>우울</option>
              <option value="불안">불안</option>
              <option value="스트레스">스트레스</option>
              <option value="분노">분노</option>
              <option value="기쁨">기쁨</option>
            </select>
          </div>
          <div>
            <label for="intensity">감정 강도</label>
            <input id="intensity" name="intensity" type="number" min="1" max="10" value="8" />
          </div>
          <div>
            <label for="requires-care">주의 필요</label>
            <label class="check" for="requires-care">
              <input id="requires-care" name="requires-care" type="checkbox" checked />
              requires_care
            </label>
          </div>
        </div>

        <button id="submit" type="submit">추천 받기</button>
      </form>
    </section>

    <section id="result">
      <p id="response"></p>
      <div class="meta">
        <span class="tag" id="intent"></span>
        <span class="tag" id="level"></span>
        <span class="tag" id="exercise-intensity"></span>
      </div>
    </section>
  </main>

  <script>
    const form = document.querySelector("#exercise-form");
    const button = document.querySelector("#submit");
    const result = document.querySelector("#result");

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      button.textContent = "추천 생성 중";

      const emotion = document.querySelector("#emotion").value;
      const intensityValue = document.querySelector("#intensity").value;
      const payload = {
        content: document.querySelector("#content").value,
        mental_status: emotion ? {
          primary_emotion: emotion,
          intensity: Number(intensityValue || 1),
          requires_care: document.querySelector("#requires-care").checked,
          is_crisis: false
        } : null
      };

      try {
        const res = await fetch("/exercise", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        document.querySelector("#response").textContent = data.response;
        document.querySelector("#intent").textContent = "intent: " + data.intent;
        document.querySelector("#level").textContent = "level: " + data.level;
        document.querySelector("#exercise-intensity").textContent = "intensity: " + data.intensity;
        result.style.display = "block";
      } catch (error) {
        document.querySelector("#response").textContent = "요청 중 오류가 발생했습니다.";
        result.style.display = "block";
      } finally {
        button.disabled = false;
        button.textContent = "추천 받기";
      }
    });
  </script>
</body>
</html>
"""


class MentalStatusPayload(BaseModel):
    primary_emotion: str | None = None
    intensity: int | None = Field(default=None, ge=1, le=10)
    requires_care: bool = False
    is_crisis: bool = False


class ExerciseRequest(BaseModel):
    content: str = Field(..., min_length=1, description="User exercise request in Korean natural language.")
    mental_status: MentalStatusPayload | None = None


class ExerciseResponse(BaseModel):
    response: str
    intent: str
    level: str
    intensity: str
    routine: list[str]
    agent_signal: dict[str, object]


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return HOME_PAGE


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "agent": "exercise"}


@app.get("/agent/status")
async def agent_status() -> dict[str, object]:
    return {
        "agent": "exercise",
        "status": "ok",
        "data": {
            "port": 8002,
            "endpoint": "/exercise",
        },
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }


@app.post("/exercise", response_model=ExerciseResponse)
async def exercise(request: ExerciseRequest) -> ExerciseResponse:
    status = request.mental_status
    recommendation = recommend_exercise(
        request.content,
        MentalStatus(
            primary_emotion=status.primary_emotion,
            intensity=status.intensity,
            requires_care=status.requires_care,
            is_crisis=status.is_crisis,
        )
        if status
        else None,
    )

    return ExerciseResponse(
        response=recommendation.response,
        intent=recommendation.intent,
        level=recommendation.level,
        intensity=recommendation.intensity,
        routine=_routine_from_response(recommendation.response),
        agent_signal={
            "agent": "exercise",
            "intensity": recommendation.intensity,
            "requires_care": recommendation.intensity == "low",
        },
    )


def _routine_from_response(response: str) -> list[str]:
    return [part.strip() for part in response.split(".") if part.strip()]
