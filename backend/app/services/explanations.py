from app.domain.common.enums import Classification, Language
from app.domain.decision.models import DecisionResult
from app.domain.liquidity.models import LiquidityProjection


def deterministic_explanation(
    language: Language,
    decision: DecisionResult,
    projection: LiquidityProjection,
) -> str:
    eta = (
        "unknown"
        if projection.shortage_eta_low_minutes is None
        else f"{projection.shortage_eta_low_minutes}-{projection.shortage_eta_high_minutes}"
    )
    confidence = round(decision.confidence * 100)

    if language == Language.BANGLA:
        if decision.classification == Classification.NORMAL_OPERATION:
            return f"বর্তমান ডেটায় তাৎক্ষণিক চাপ নেই। বিশ্বাসযোগ্যতা {confidence}%। পর্যবেক্ষণ চালিয়ে যান।"
        return (
            f"{decision.affected_resource} ব্যালেন্সে চাপের সংকেত পাওয়া গেছে; সম্ভাব্য সময়সীমা "
            f"{eta} মিনিট। বিশ্বাসযোগ্যতা {confidence}%। এটি জালিয়াতির সিদ্ধান্ত নয়; "
            "মানব পর্যালোচনা প্রয়োজন।"
        )
    if language == Language.BANGLISH:
        if decision.classification == Classification.NORMAL_OPERATION:
            return f"Current data-te immediate pressure nei. Confidence {confidence}%. Monitoring continue korun."
        return (
            f"{decision.affected_resource} balance-e pressure signal ache; estimated window "
            f"{eta} minute. Confidence {confidence}%. Eta fraud verdict na; human review proyojon."
        )
    if decision.classification == Classification.NORMAL_OPERATION:
        return f"No immediate pressure is visible. Confidence is {confidence}%. Continue monitoring."
    return (
        f"Pressure is visible in {decision.affected_resource}; the estimated window is {eta} "
        f"minutes. Confidence is {confidence}%. This is not a fraud verdict; human review is required."
    )
