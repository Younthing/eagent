from pipelines.graphs.nodes.locators.rule_based import rule_based_locate
from rob2.locator_rules import get_locator_rules
from schemas.internal.documents import DocStructure, SectionSpan
from schemas.internal.locator import (
    DomainLocatorRule,
    LocatorDefaults,
    LocatorRules,
    QuestionLocatorOverride,
)
from schemas.internal.rob2 import QuestionSet, Rob2Question


def test_locator_rules_load() -> None:
    rules = get_locator_rules()

    assert rules.variant == "standard"
    assert rules.defaults.top_k == 5
    assert set(rules.domains.keys()) == {"D1", "D2", "D3", "D4", "D5"}


def test_rule_based_locator_ranks_randomization() -> None:
    doc = DocStructure(
        body="",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods > Participants",
                page=1,
                text="Participants were recruited from outpatient clinics.",
            ),
            SectionSpan(
                paragraph_id="p2",
                title="Methods > Randomization",
                page=2,
                text=(
                    "A computer-generated random number sequence was used for "
                    "allocation."
                ),
            ),
            SectionSpan(
                paragraph_id="p3",
                title="Methods > Allocation concealment",
                page=2,
                text="Allocation was concealed using sealed opaque envelopes.",
            ),
        ],
    )
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q1_1",
                rob2_id="q1_1",
                domain="D1",
                text="Was the allocation sequence random?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )
    rules = LocatorRules(
        version="test",
        variant="standard",
        defaults=LocatorDefaults(top_k=5),
        domains={
            "D1": DomainLocatorRule(
                section_priors=["random", "methods"],
                keywords=["random", "random number"],
            ),
            "D2": DomainLocatorRule(),
            "D3": DomainLocatorRule(),
            "D4": DomainLocatorRule(),
            "D5": DomainLocatorRule(),
        },
        question_overrides={
            "q1_1": QuestionLocatorOverride(keywords=["computer-generated"])
        },
    )

    candidates_by_q, bundles = rule_based_locate(doc, question_set, rules, top_k=5)

    assert bundles[0].question_id == "q1_1"
    assert candidates_by_q["q1_1"][0].paragraph_id == "p2"
    assert bundles[0].items[0].paragraph_id == "p2"


def test_rule_based_locator_short_token_word_boundary() -> None:
    doc = DocStructure(
        body="",
        sections=[
            SectionSpan(
                paragraph_id="p1",
                title="Methods",
                page=1,
                text="Participants were sitting quietly before assessment.",
            ),
            SectionSpan(
                paragraph_id="p2",
                title="Methods",
                page=2,
                text="We performed an ITT analysis including all randomized participants.",
            ),
        ],
    )
    question_set = QuestionSet(
        version="test",
        variant="standard",
        questions=[
            Rob2Question(
                question_id="q2a_6",
                rob2_id="q2_6",
                domain="D2",
                effect_type="assignment",
                text="Was an appropriate analysis used to estimate the effect of assignment to intervention?",
                options=["Y", "PY", "PN", "N", "NI"],
                order=1,
            )
        ],
    )
    rules = LocatorRules(
        version="test",
        variant="standard",
        defaults=LocatorDefaults(top_k=5),
        domains={
            "D1": DomainLocatorRule(),
            "D2": DomainLocatorRule(section_priors=[], keywords=["itt"]),
            "D3": DomainLocatorRule(),
            "D4": DomainLocatorRule(),
            "D5": DomainLocatorRule(),
        },
    )

    candidates_by_q, bundles = rule_based_locate(doc, question_set, rules, top_k=5)
    candidates = candidates_by_q["q2a_6"]

    assert len(bundles[0].items) == 1
    assert len(candidates) == 1
    assert candidates[0].paragraph_id == "p2"
