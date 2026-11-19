from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MPCDecision(BaseModel):
    meeting_month: str = Field(
        pattern=r"^d{4}-(0[1-9]|1[0-2])$",
        description="Month of the MPC meeting as YYYY-MM, example: 2026-02"
    )
    meeting_date: date | None = Field(
        default=None,
        description="Exact meeting date only if the statement gives one; otherwise null",
    )
    decision: Literal["raised", "lowered", "retained"] = Field(
        description="'reduced' means lowered; 'maintained' means retained"
    )
    change_bps: int = Field(
        description="Change to the Central Bank Rate in basis points; 0 if retained, negative if lowered"  
    )
    cbr_after_pct: float = Field(
        ge=0, le=30, description="Central Bank Rate after this decision, in percent"
    )
    source_page: int = Field(
        ge=1, description="PDF page index (not the printed page number) where the decision is stated"
    )

    @model_validator(mode="after")
    def decision_matches_changes(self):
        if self.decision == "retained" and self.change_bps != 0:
            raise ValueError("decision is 'retained' but change_bps is not 0")
        if self.decision == "raised" and self.change_bps <= 0:
            raise ValueError("decision is 'raised' but change_bps is not positive")
        if self.decision == "lowered" and self.change_bps >= 0:
            raise ValueError("decision is 'lowered' but change_bps is not negative")
        return self

class MonetaryPolicyStatement(BaseModel):
    statement_number: int = Field(description="e.g. 56 for the 56th Monetary Policy Statement")
    period_end_month: str = Field(
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Last month of the review period as YYYY-MM, e.g. 2025-06",
    )
    decisions: list[MPCDecision] = Field(min_length=1)
    overall_inflation_end_pct: float = Field(
        description="Overall (headline) inflation in the last month of the review period, in percent"
    )
    inflation_source_page: int = Field(ge=1, description="PDF page where that figure is stated")

    @model_validator(mode="after")
    def rate_chain_is_consistent(self):
        for prev, cur in zip(self.decisions, self.decisions[1:]):
            expected = round(prev.cbr_after_pct + cur.change_bps / 100, 2)
            if abs(cur.cbr_after_pct - expected) > 0.001:
                raise ValueError(
                    f"{cur.meeting_month}: rate {cur.cbr_after_pct} does not follow from "
                    f"{prev.cbr_after_pct} and change of {cur.change_bps} bps"
                )
        return self