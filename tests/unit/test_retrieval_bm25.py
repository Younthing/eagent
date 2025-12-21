from retrieval.engines.bm25 import build_bm25_index
from retrieval.engines.fusion import rrf_fuse
from retrieval.query_planning.planner import generate_queries_for_question
from schemas.internal.documents import SectionSpan
from schemas.internal.locator import (
    DomainLocatorRule,
    LocatorDefaults,
    LocatorRules,
    QuestionLocatorOverride,
)
from schemas.internal.rob2 import Rob2Question


def test_bm25_search_ranks_expected_doc() -> None:
    spans = [
        SectionSpan(
            paragraph_id="p1",
            title="Methods > Randomization",
            page=1,
            text="A computer-generated random number sequence was used.",
        ),
        SectionSpan(
            paragraph_id="p2",
            title="Methods > Allocation concealment",
            page=1,
            text="Allocation was concealed using sealed opaque envelopes.",
        ),
    ]
    index = build_bm25_index(spans)
    hits = index.search("random number sequence", top_n=5)

    assert hits
    assert hits[0].doc_index == 0


def test_rrf_fuse_promotes_docs_appearing_in_multiple_queries() -> None:
    rankings = {
        "q1": [(0, 10.0), (1, 1.0)],
        "q2": [(0, 9.0), (2, 2.0)],
    }
    fused = rrf_fuse(rankings, k=60)

    assert fused
    assert fused[0].doc_index == 0
    assert fused[0].best_query in {"q1", "q2"}
    assert set(fused[0].query_ranks.keys()) == {"q1", "q2"}


def test_generate_queries_for_question_is_deterministic_and_limited() -> None:
    rules = LocatorRules(
        version="test",
        variant="standard",
        defaults=LocatorDefaults(top_k=5),
        domains={
            "D1": DomainLocatorRule(
                section_priors=["methods"],
                keywords=["randomization", "allocation concealment", "baseline"],
            ),
            "D2": DomainLocatorRule(),
            "D3": DomainLocatorRule(),
            "D4": DomainLocatorRule(),
            "D5": DomainLocatorRule(),
        },
        question_overrides={
            "q1_2": QuestionLocatorOverride(keywords=["sealed opaque envelopes"])
        },
    )
    question = Rob2Question(
        question_id="q1_2",
        rob2_id="q1_2",
        domain="D1",
        text="Was the allocation sequence concealed until participants were enrolled and assigned to interventions?",
        options=["Y", "PY", "PN", "N", "NI"],
        order=1,
    )

    queries = generate_queries_for_question(question, rules, max_queries=5)

    assert queries[0] == question.text
    assert len(queries) <= 5
    assert len(queries) == len({q.casefold() for q in queries})
    assert any("sealed opaque envelopes" in q for q in queries)
