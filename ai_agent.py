import logging

import agent
from google.genai import types
from models import FinancingRequest
from orchestrator import assessment_result, process_financing_request
from tools import check_eligibility as eligibility_tool, recommend_financing as recommendation_tool

logger = logging.getLogger(__name__)


def process_agent_request(request: FinancingRequest) -> dict:
    """Let Gemini choose tools; accept only observed, request-bound tool results."""
    trace = []
    state = {}

    # No model-supplied financial arguments: closures bind tools to validated input.
    def check_eligibility() -> dict:
        """Check this request against the educational 30%-of-revenue heuristic."""
        logger.info("Agent called: check_eligibility")
        trace.append("check_eligibility")
        state["eligibility"] = eligibility_tool(request.annual_revenue, request.requested_amount)
        return state["eligibility"]

    def recommend_financing() -> dict:
        """Suggest a category for this request only after successful eligibility."""
        logger.info("Agent called: recommend_financing")
        trace.append("recommend_financing")
        if not state.get("eligibility", {}).get("eligible"):
            return {"error": "Check eligibility first; ineligible requests require human review."}
        state["recommendation"] = recommendation_tool(request.financing_purpose)
        return {"recommended_financing": state["recommendation"]}

    def run_chat():
        state.clear()
        chat = agent.client.chats.create(
            model=agent.MODEL,
            config=types.GenerateContentConfig(
                system_instruction=agent.SYSTEM_INSTRUCTION + """
Call check_eligibility first. If eligible, call recommend_financing next.
If ineligible, stop tool use and return amount_review. Unknown purposes require
purpose_review. Use the tool results to choose the final assessment code.
""",
                tools=[check_eligibility, recommend_financing],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=4),
            ),
        )
        # The SDK executes model-requested Python calls and sends their results back.
        return chat.send_message(request.model_dump_json())

    response = agent.call_gemini(run_chat)
    complete = "eligibility" in state and (
        not state["eligibility"]["eligible"] or "recommendation" in state)
    result = assessment_result(state["eligibility"], state.get("recommendation")) if complete else None
    fallback = result is None or not agent.valid_response(response, result)
    if fallback:
        result = process_financing_request(request)
    return {
        "company": request.company_name, **result,
        "ai_explanation": agent.render_explanation(result, fallback),
        "workflow": "agentic",
        "execution_mode": "deterministic_fallback" if fallback else "gemini_tool_calling",
        "llm_fallback": fallback,
        "tool_calls": trace,
    }
