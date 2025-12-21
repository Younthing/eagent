from rob2.question_bank import get_question_bank


def test_question_bank_counts() -> None:
    question_set = get_question_bank()

    assert question_set.variant == "standard"
    assert len(question_set.questions) == 28

    assignment = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "assignment"
    ]
    adherence = [
        question
        for question in question_set.questions
        if question.domain == "D2" and question.effect_type == "adherence"
    ]

    assert len(assignment) == 7
    assert len(adherence) == 6


def test_question_bank_order_and_ids() -> None:
    question_set = get_question_bank()

    ids = [question.question_id for question in question_set.questions]
    assert len(ids) == len(set(ids))

    orders = [question.order for question in question_set.questions]
    assert orders == list(range(1, len(orders) + 1))

    assert question_set.questions[0].question_id == "q1_1"
    assert question_set.questions[-1].question_id == "q5_3"
