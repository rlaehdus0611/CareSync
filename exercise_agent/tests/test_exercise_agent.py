from app.exercise_agent import MentalStatus, recommend_exercise


def test_recommends_gentle_exercise_when_user_is_depressed() -> None:
    result = recommend_exercise(
        "우울한데 운동 추천해줘",
        MentalStatus(primary_emotion="우울", intensity=8, requires_care=True),
    )

    assert result.intensity == "low"
    assert "산책" in result.response
    assert "몸을 몰아붙이기보다" in result.response


def test_detects_weight_loss_intent() -> None:
    result = recommend_exercise("살 빼고 싶어. 운동 루틴 추천해줘")

    assert result.intent == "weight_loss"
    assert result.intensity == "medium"
    assert "스쿼트" in result.response


def test_prioritizes_pain_safety() -> None:
    result = recommend_exercise("무릎 통증이 있는데 운동해도 돼?")

    assert result.intent == "injury_care"
    assert result.intensity == "low"
    assert "전문가 상담" in result.response
