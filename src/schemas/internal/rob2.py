"""ROB2 question schemas for planner output."""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALLOWED_ANSWERS = {"Y", "PY", "PN", "N", "NI", "NA"}


class QuestionDependency(BaseModel):
    """Dependency on another signaling question's answers."""

    question_id: str
    allowed_answers: List[str]

    model_config = ConfigDict(extra="forbid")

    @field_validator("allowed_answers")
    @classmethod
    def _validate_allowed_answers(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("allowed_answers must not be empty")
        invalid = [answer for answer in value if answer not in ALLOWED_ANSWERS]
        if invalid:
            raise ValueError(f"Invalid answers: {invalid}")
        return value


class QuestionCondition(BaseModel):
    """Logical condition gating a question."""

    operator: Literal["any", "all"] = "all"
    dependencies: List[QuestionDependency]
    note: Optional[str] = None

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_dependencies(self) -> "QuestionCondition":
        if not self.dependencies:
            raise ValueError("dependencies must not be empty")
        return self


class Rob2Question(BaseModel):
    """ROB2 signaling question definition."""

    question_id: str = Field(description="Unique planner question identifier.")
    rob2_id: Optional[str] = Field(
        default=None, description="Original ROB2 signaling question ID."
    )
    domain: Literal["D1", "D2", "D3", "D4", "D5"]
    effect_type: Optional[Literal["assignment", "adherence"]] = None
    text: str
    options: List[str]
    conditions: List[QuestionCondition] = Field(default_factory=list)
    order: int

    model_config = ConfigDict(extra="forbid")

    @field_validator("options")
    @classmethod
    def _validate_options(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("options must not be empty")
        invalid = [answer for answer in value if answer not in ALLOWED_ANSWERS]
        if invalid:
            raise ValueError(f"Invalid options: {invalid}")
        return value

    @model_validator(mode="after")
    def _validate_domain_effect_type(self) -> "Rob2Question":
        if self.domain == "D2" and self.effect_type is None:
            raise ValueError("effect_type is required for D2 questions")
        if self.domain != "D2" and self.effect_type is not None:
            raise ValueError("effect_type is only valid for D2 questions")
        return self


class QuestionSet(BaseModel):
    """Collection of ROB2 signaling questions."""

    version: str
    variant: Literal["standard"]
    questions: List[Rob2Question]

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_questions(self) -> "QuestionSet":
        seen: set[str] = set()
        id_to_question = {question.question_id: question for question in self.questions}

        for question in self.questions:
            if question.question_id in seen:
                raise ValueError(f"Duplicate question_id: {question.question_id}")
            seen.add(question.question_id)

        for question in self.questions:
            for condition in question.conditions:
                for dependency in condition.dependencies:
                    target = id_to_question.get(dependency.question_id)
                    if target is None:
                        raise ValueError(
                            f"Unknown dependency question_id: {dependency.question_id}"
                        )
                    invalid = [
                        answer
                        for answer in dependency.allowed_answers
                        if answer not in target.options
                    ]
                    if invalid:
                        raise ValueError(
                            "Dependency answers must exist in target options: "
                            f"{dependency.question_id} -> {invalid}"
                        )

        return self


__all__ = [
    "ALLOWED_ANSWERS",
    "QuestionDependency",
    "QuestionCondition",
    "Rob2Question",
    "QuestionSet",
]
