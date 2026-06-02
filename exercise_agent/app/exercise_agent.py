from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


Intensity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class MentalStatus:
    primary_emotion: str | None = None
    intensity: int | None = None
    requires_care: bool = False
    is_crisis: bool = False


@dataclass(frozen=True)
class ExerciseRecommendation:
    intent: str
    level: str
    intensity: Intensity
    response: str


LOW_INTENSITY_EMOTIONS = {"불안", "우울", "슬픔", "무기력", "스트레스", "분노"}
BEGINNER_WORDS = {"초보", "처음", "입문", "운동부족", "체력없", "힘들", "약해"}
ADVANCED_WORDS = {"고강도", "상급", "빡세", "강하게", "근성장", "벌크", "인터벌"}
WEIGHT_LOSS_WORDS = {"살", "다이어트", "감량", "체중", "지방", "뱃살"}
STRENGTH_WORDS = {"근력", "근육", "웨이트", "헬스", "스쿼트", "푸쉬업", "푸시업"}
CARDIO_WORDS = {"유산소", "심폐", "달리기", "러닝", "걷기", "산책"}
PAIN_WORDS = {"통증", "아파", "다쳤", "부상", "삐었", "무릎", "허리"}


def recommend_exercise(content: str, mental_status: MentalStatus | None = None) -> ExerciseRecommendation:
    normalized = content.replace(" ", "").lower()
    mental_status = mental_status or MentalStatus()

    if mental_status.is_crisis:
        return ExerciseRecommendation(
            intent="mental_care",
            level="safety_first",
            intensity="low",
            response=(
                "지금은 운동 목표보다 안전과 안정이 먼저예요. "
                "격한 운동 대신 3분 동안 천천히 호흡하고, 가능하면 가까운 사람이나 전문 상담 기관에 바로 도움을 요청해 주세요."
            ),
        )

    if _contains_any(normalized, PAIN_WORDS):
        return ExerciseRecommendation(
            intent="injury_care",
            level="recovery",
            intensity="low",
            response=(
                "통증이나 부상이 느껴질 때는 무리한 운동을 쉬는 것이 좋아요. "
                "오늘은 5~10분 가벼운 걷기와 통증 없는 범위의 스트레칭만 하고, 통증이 계속되면 전문가 상담을 권장해요."
            ),
        )

    care_mode = _requires_gentle_plan(mental_status)
    level = _detect_level(normalized)
    intent = _detect_intent(normalized)
    intensity = _choose_intensity(level, intent, care_mode)
    response = _build_response(intent, level, intensity, care_mode, mental_status)

    return ExerciseRecommendation(
        intent=intent,
        level=level,
        intensity=intensity,
        response=response,
    )


def _requires_gentle_plan(status: MentalStatus) -> bool:
    emotion = status.primary_emotion or ""
    return status.requires_care or emotion in LOW_INTENSITY_EMOTIONS or (status.intensity or 0) >= 7


def _detect_level(text: str) -> str:
    if _contains_any(text, ADVANCED_WORDS):
        return "advanced"
    if _contains_any(text, BEGINNER_WORDS):
        return "beginner"
    return "intermediate"


def _detect_intent(text: str) -> str:
    if _contains_any(text, WEIGHT_LOSS_WORDS):
        return "weight_loss"
    if _contains_any(text, STRENGTH_WORDS):
        return "strength"
    if _contains_any(text, CARDIO_WORDS):
        return "cardio"
    return "general"


def _choose_intensity(level: str, intent: str, care_mode: bool) -> Intensity:
    if care_mode:
        return "low"
    if level == "advanced" and intent in {"strength", "weight_loss", "cardio"}:
        return "high"
    if level == "beginner":
        return "low"
    return "medium"


def _build_response(
    intent: str,
    level: str,
    intensity: Intensity,
    care_mode: bool,
    mental_status: MentalStatus,
) -> str:
    if care_mode:
        emotion_note = f"현재 {mental_status.primary_emotion} 신호가 있어 " if mental_status.primary_emotion else ""
        return (
            f"{emotion_note}몸을 몰아붙이기보다 긴장을 낮추는 루틴을 추천해요. "
            "오늘은 10분 산책, 목·어깨 스트레칭 5분, 깊은 호흡 3세트를 해보세요. "
            "끝난 뒤 몸이 조금 가벼우면 하체 스트레칭을 5분만 추가하면 충분해요."
        )

    plans = {
        "weight_loss": {
            "low": "20분 빠르게 걷기와 전신 스트레칭 5분으로 시작해요. 익숙해지면 걷기 시간을 5분씩 늘려주세요.",
            "medium": "빠르게 걷기 25분, 스쿼트 12회 3세트, 플랭크 30초 3세트를 추천해요.",
            "high": "인터벌 러닝 20분, 스쿼트 15회 4세트, 버피 10회 3세트로 진행해요.",
        },
        "strength": {
            "low": "스쿼트 10회 2세트, 벽 푸쉬업 10회 2세트, 브릿지 12회 2세트로 기초 근력을 깨워보세요.",
            "medium": "스쿼트 12회 3세트, 푸쉬업 8~12회 3세트, 런지 10회 3세트를 추천해요.",
            "high": "스쿼트 15회 4세트, 푸쉬업 15회 4세트, 런지 12회 4세트, 플랭크 60초 3세트로 가보세요.",
        },
        "cardio": {
            "low": "가벼운 산책 15~20분과 종아리 스트레칭으로 심박을 천천히 올려보세요.",
            "medium": "조깅 20분, 빠르게 걷기 10분, 마무리 스트레칭 5분을 추천해요.",
            "high": "러닝 30분 또는 1분 빠르게 달리기와 1분 걷기를 10라운드 반복해요.",
        },
        "general": {
            "low": "전신 스트레칭 10분, 산책 15분, 가벼운 스쿼트 10회 2세트가 좋아요.",
            "medium": "걷기 20분, 스쿼트 12회 3세트, 플랭크 30초 3세트로 균형 있게 시작해요.",
            "high": "전신 서킷으로 스쿼트, 푸쉬업, 런지, 플랭크를 각 4세트 진행해요.",
        },
    }

    level_label = {"beginner": "초보자", "intermediate": "중간 수준", "advanced": "상급자"}[level]
    intensity_label = {"low": "가벼운", "medium": "보통 강도", "high": "높은 강도"}[intensity]
    return f"{level_label}에게 맞는 {intensity_label} 운동으로 추천할게요. {plans[intent][intensity]}"


def _contains_any(text: str, words: set[str]) -> bool:
    return any(word in text for word in words)
