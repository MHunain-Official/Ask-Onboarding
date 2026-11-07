from app.services.query_router import route_question


def test_greeting_variants() -> None:
    assert route_question("Hey there!", 1000).action == "small_talk"
    assert route_question("thanks a lot", 1000).action == "small_talk"


def test_explain_simpler_intent() -> None:
    assert route_question("explain in easier wording", 1000).action == "explain_simpler"


def test_conversation_meta_intent() -> None:
    assert route_question("what did we talk about?", 1000).action == "conversation_meta"


def test_real_question_not_small_talk() -> None:
    assert route_question("hi-vis vest policy", 1000).action == "continue"
