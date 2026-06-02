"""
멘탈 저널링 에이전트 — Claude API (Anthropic) 버전

적용된 NLP 최적화:
  1. Few-shot + Chain-of-Thought 프롬프트
  2. RAG — 최근 일기를 컨텍스트로 주입
  3. KoNLPy 형태소 전처리 → 프롬프트 힌트 제공
  4. 프롬프트 캐싱 (시스템 프롬프트 캐시)
"""
import json
import os
import re

from anthropic import AsyncAnthropic
from preprocessor import preprocess, format_hint

client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

ANALYSIS_MODEL = "claude-haiku-4-5-20251001"   # 빠르고 저렴 (분석용)
EMPATHY_MODEL  = "claude-sonnet-4-6"            # 자연스러운 공감 응답용

# ── 1. Few-shot + CoT 감정 분석 프롬프트 (캐싱 적용) ─────────────────

ANALYSIS_SYSTEM = [
    {
        "type": "text",
        "text": """당신은 심리상담 전문 AI입니다. 사용자의 일기를 읽고 감정을 분석합니다.

[분석 방법 — Chain of Thought]
1. 표면 감정: 텍스트에 직접 드러난 감정 단어 파악
2. 맥락 감정: 상황·사건에서 유추되는 숨은 감정 파악
3. 강도 판단: 강도 부사, 반복 표현, 문장 부호(!?…) 가중치 적용
4. 최종 통합: 표면+맥락을 합산해 primary_emotion 결정

[예시 1]
일기: "발표를 완전히 망쳤어. 아무도 내 말을 안 듣는 것 같았어."
추론:
  표면 감정 → "망쳤어" = 실패감
  맥락 감정 → 타인 시선 의식 = 수치심, 타인과의 단절 = 외로움
  강도 → "완전히" = 고강도
결과:
{
  "primary_emotion": "불안",
  "emotion_scores": {"기쁨":2,"슬픔":40,"불안":60,"분노":10,"무기력":30,"외로움":45,"평온":5,"혼란":20},
  "intensity": 8,
  "keywords": ["실패감", "타인시선", "단절", "수치심"],
  "summary": "발표 실패로 인한 수치심과 고립감이 복합적으로 나타남"
}

[예시 2]
일기: "오늘 오랜 친구를 만났다. 별로 한 것도 없는데 기분이 좋았어."
추론:
  표면 감정 → "기분이 좋았어" = 기쁨
  맥락 감정 → 관계 회복 = 소속감, 일상의 소소함 = 평온
  강도 → 잔잔한 서술체 = 저강도
결과:
{
  "primary_emotion": "기쁨",
  "emotion_scores": {"기쁨":75,"슬픔":5,"불안":5,"분노":0,"무기력":0,"외로움":5,"평온":60,"혼란":0},
  "intensity": 4,
  "keywords": ["친구", "소속감", "일상", "평온"],
  "summary": "오랜 친구와의 만남으로 소소하지만 따뜻한 기쁨을 느낌"
}

[출력 규칙]
- JSON만 출력, 다른 텍스트 절대 금지
- primary_emotion: 기쁨/슬픔/불안/분노/무기력/외로움/평온/혼란 중 하나
- emotion_scores 합계 제한 없음 (복합 감정 허용)
- intensity: 1(매우 잔잔)~10(극도로 강렬)""",
        "cache_control": {"type": "ephemeral"},
    }
]

# ── 2. 공감 응답 프롬프트 (캐싱 적용) ───────────────────────────────

EMPATHY_SYSTEM = [
    {
        "type": "text",
        "text": """당신은 따뜻하고 공감적인 멘탈 헬스케어 상담사입니다.

[응답 구조 — 3단계]
1. 감정 인정: 상대방이 느낀 감정을 구체적 키워드로 반영 ("~하셨군요")
2. 공감 확장: 그 감정이 자연스러운 이유를 짧게 설명
3. 부드러운 제안: 강요 없이 가벼운 셀프케어 한 가지 (없어도 됨)

[예시]
감정: 불안 / 강도: 8 / 키워드: 실패감, 타인시선
응답: "발표가 생각대로 되지 않아 많이 속상하고 불안하셨겠어요. 열심히 준비했는데 결과가 기대와 달랐을 때의 그 무너지는 느낌, 충분히 이해해요. 오늘 하루 수고하셨으니 잠들기 전에 좋아하는 음악을 잠깐 들어보시는 건 어떨까요?"

[제약]
- 3~5문장, 존댓말
- "괜찮아질 거예요" 같은 근거 없는 위로 금지
- 감정을 바꾸거나 부정하지 말 것
- 과거 패턴이 주어지면 반드시 연속성 있게 언급""",
        "cache_control": {"type": "ephemeral"},
    }
]


# ── 핵심 함수 ────────────────────────────────────────────────────────

async def analyze_emotions(journal_text: str, preprocess_hint: str = "") -> dict:
    user_content = (
        f"[형태소 분석 힌트]\n{preprocess_hint}\n\n[일기]\n{journal_text}"
        if preprocess_hint else f"[일기]\n{journal_text}"
    )

    message = await client.messages.create(
        model=ANALYSIS_MODEL,
        max_tokens=600,
        system=ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = message.content[0].text.strip()
    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    return json.loads(json_match.group() if json_match else raw)


async def generate_empathy_response(
    journal_text: str,
    emotion_analysis: dict,
    past_context: str = "",
) -> str:
    parts = []
    if past_context:
        parts.append(f"[최근 감정 흐름 — 참고]\n{past_context}")
    parts.append(
        f"[오늘 일기]\n{journal_text}\n\n"
        f"[감정 분석]\n"
        f"주요 감정: {emotion_analysis['primary_emotion']} / "
        f"강도: {emotion_analysis['intensity']}/10\n"
        f"핵심 키워드: {', '.join(emotion_analysis['keywords'])}\n"
        f"요약: {emotion_analysis['summary']}"
    )

    message = await client.messages.create(
        model=EMPATHY_MODEL,
        max_tokens=512,
        system=EMPATHY_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(parts)}],
    )
    return message.content[0].text.strip()


def build_rag_context(past_entries: list[dict]) -> str:
    if not past_entries:
        return ""
    lines = []
    for e in past_entries:
        date = e["created_at"][:10]
        emotion = e["emotions"]["primary"]
        intensity = e["intensity"]
        keywords = ", ".join(e["keywords"][:3])
        lines.append(f"  {date} | {emotion}(강도 {intensity}) | {keywords}")
    return "\n".join(lines)


# ── 메인 파이프라인 ──────────────────────────────────────────────────

async def process_journal(journal_text: str, past_entries: list[dict] = None) -> dict:
    # 0. 전처리
    preprocessed = preprocess(journal_text)
    hint = format_hint(preprocessed)

    # 1. 감정 분석
    emotion_data = await analyze_emotions(journal_text, preprocess_hint=hint)

    # 2. RAG 컨텍스트
    past_context = build_rag_context(past_entries or [])

    # 3. 공감 응답
    empathy_response = await generate_empathy_response(
        journal_text, emotion_data, past_context=past_context
    )

    return {
        "emotions": {
            "primary": emotion_data["primary_emotion"],
            "scores": emotion_data["emotion_scores"],
            "intensity": emotion_data["intensity"],
            "summary": emotion_data["summary"],
        },
        "keywords": emotion_data["keywords"],
        "empathy_response": empathy_response,
        "preprocess_method": preprocessed["method"],
        "agent_signal": {
            "agent": "mental_journal",
            "primary_emotion": emotion_data["primary_emotion"],
            "intensity": emotion_data["intensity"],
            "requires_care": (
                emotion_data["intensity"] >= 7
                and emotion_data["primary_emotion"]
                in ["슬픔", "불안", "분노", "무기력", "외로움"]
            ),
        },
    }
