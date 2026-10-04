import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)
load_dotenv(Path(__file__).resolve().with_name(".env"))

api_key = os.getenv("GEMINI_API_KEY", "").strip()
client = None
if api_key:
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=15000,
                # Keep retry timing in the explicit loop below.
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
    except Exception:
        logger.warning("Gemini client initialization failed; using fallback explanations.")
else:
    logger.warning("GEMINI_API_KEY is missing; using fallback explanations.")

RETRY_DELAYS = (1, 2)
TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def generate_financing_explanation(
    company_name,
    industry,
    annual_revenue,
    employees,
    requested_amount,
    financing_purpose,
    eligibility,
    recommendation
):
    prompt = f"""
You are an AI assistant for an SME financing platform.

Analyze the following financing request.

Company: {company_name}
Industry: {industry}
Annual revenue: €{annual_revenue}
Employees: {employees}
Requested amount: €{requested_amount}
Purpose: {financing_purpose}

Demo eligibility result:
{eligibility}

Possible financing category:
{recommendation}

Explain the result clearly in 3-4 sentences.

Important rules:
- Do not claim that financing is guaranteed.
- Do not make a final lending decision.
- Explain that this is an initial assessment.
- Recommend human review when appropriate.
"""

    fallback = (
        "The AI explanation is currently unavailable. "
        f"{eligibility['message']} "
        + (f"The initial suggested financing category is {recommendation}. "
           if recommendation else "This request requires human review. ")
        + "This is an initial assessment, not a lending decision or a guarantee of financing."
    )
    if client is None:
        return fallback

    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
            )
            explanation = response.text
            if explanation and explanation.strip():
                return explanation.strip()
            logger.warning("Gemini returned no explanation; using fallback.")
            return fallback
        except errors.APIError as exc:
            # Do not log raw exceptions, prompts, or credentials.
            logger.warning("Gemini API request failed (HTTP %s).", exc.code)
            if exc.code not in TRANSIENT_STATUS_CODES:
                return fallback
        except httpx.TransportError:
            logger.warning("Gemini connection or timeout failure.")
        except Exception:
            logger.warning("Gemini explanation failed; using fallback.")
            return fallback

        if attempt < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[attempt])

    return fallback
