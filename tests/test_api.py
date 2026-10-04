import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from google import genai
from google.genai import errors, types

import agent
from main import app

REQUEST = dict(company_name="ABC Software", industry="Technology", annual_revenue=100000,
               employees=8, requested_amount=20000, financing_purpose="Buy new equipment")


def model_response(code=None, tool=None):
    part = (types.Part(function_call=types.FunctionCall(name=tool, args={})) if tool else
            types.Part(text='{"assessment": "' + code + '"}'))
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[part]))])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.api = TestClient(app)
        self.no_key = patch.object(agent, "client", None)
        self.no_key.start()
        self.addCleanup(self.no_key.stop)

    def post(self, path="/evaluate", **changes):
        return self.api.post(path, json={**REQUEST, **changes})

    def test_health(self):
        self.assertEqual(self.api.get("/health").status_code, 200)

    def test_frontend_and_static_assets(self):
        response = self.api.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('id="assessment-form"', response.text)
        for asset in ("app.js", "styles.css"):
            self.assertEqual(self.api.get(f"/static/{asset}").status_code, 200)
        self.assertEqual(self.api.get("/.env").status_code, 404)

    def test_eligible_and_fallback_both_endpoints(self):
        for path in ("/evaluate", "/agent-evaluate"):
            response = self.post(path)
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data["eligibility"]["eligible"])
            self.assertFalse(data["requires_human_review"])
            self.assertEqual(data["recommended_financing"], "Equipment financing or leasing")
            self.assertTrue(data["llm_fallback"])
            self.assertIn("not real underwriting", data["ai_explanation"])

    def test_review_and_unknown_purpose(self):
        for path in ("/evaluate", "/agent-evaluate"):
            for change in ({"requested_amount": 50000}, {"financing_purpose": "Other"}):
                data = self.post(path, **change).json()
                self.assertTrue(data["requires_human_review"])
                self.assertIsNone(data["recommended_financing"])

    def test_invoice_and_boundary(self):
        data = self.post(requested_amount=30000,
                         financing_purpose="Improve short-term cash flow from unpaid invoices").json()
        self.assertTrue(data["eligibility"]["eligible"])
        self.assertEqual(data["recommended_financing"], "Invoice financing or factoring")
        self.assertTrue(self.post(requested_amount=30000.01).json()["requires_human_review"])

    def test_validation(self):
        for path in ("/evaluate", "/agent-evaluate"):
            for change in ({"requested_amount": 0}, {"requested_amount": -1},
                           {"annual_revenue": 0}, {"employees": 0}, {"employees": 1.5},
                           {"company_name": "  "}, {"annual_revenue": "NaN"},
                           {"requested_amount": "Infinity"}):
                self.assertEqual(self.post(path, **change).status_code, 422)

    def test_errors_retry_and_still_return_json(self):
        for failure, calls in ((errors.ServerError(503, {"error": {"message": "unavailable"}}), 3),
                               (errors.ClientError(404, {"error": {"message": "missing"}}), 1),
                               (httpx.ConnectError("offline"), 3)):
            with patch.object(agent, "client") as fake, patch.object(agent.time, "sleep"):
                fake.models.generate_content.side_effect = failure
                response = self.post()
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["llm_fallback"])
                self.assertEqual(fake.models.generate_content.call_count, calls)

    def test_malformed_empty_and_unsafe_output(self):
        for text in ("", "approved guaranteed 99%", '{"assessment":"amount_review"}', '{}'):
            with patch.object(agent, "client") as fake:
                fake.models.generate_content.return_value = types.GenerateContentResponse(
                    candidates=[types.Candidate(content=types.Content(parts=[types.Part(text=text)]))])
                self.assertTrue(self.post().json()["llm_fallback"])

    def test_valid_deterministic_explanation(self):
        with patch.object(agent, "client") as fake:
            fake.models.generate_content.return_value = model_response("potential_match")
            self.assertFalse(self.post().json()["llm_fallback"])

    def test_real_sdk_automatic_function_call_loop(self):
        # Use real SDK Chat.send_message; replace only its model/network boundary.
        with genai.Client(api_key="test-placeholder") as sdk:
            for amount, purpose, final_code, expected_tools in (
                (20000, "equipment", "potential_match", ["check_eligibility", "recommend_financing"]),
                (50000, "equipment", "amount_review", ["check_eligibility"]),
                (20000, "other", "purpose_review", ["check_eligibility", "recommend_financing"]),
            ):
                replies = [model_response(tool=name) for name in expected_tools] + [model_response(final_code)]
                with patch.object(agent, "client", sdk), patch.object(
                    sdk.models, "generate_content", side_effect=replies
                ) as network:
                    data = self.post("/agent-evaluate", requested_amount=amount,
                                     financing_purpose=purpose).json()
                    self.assertEqual(data["execution_mode"], "gemini_tool_calling")
                    self.assertEqual(data["tool_calls"], expected_tools)
                    self.assertEqual(data["requires_human_review"], final_code != "potential_match")
                    contents = network.call_args.kwargs["contents"]
                    self.assertTrue(any(p.function_response for c in contents for p in c.parts))

    def test_agent_missing_calls_or_limit_falls_back(self):
        with genai.Client(api_key="test-placeholder") as sdk:
            for replies in ([model_response("potential_match")],
                            [model_response(tool="check_eligibility")] * 4,
                            [model_response(tool="recommend_financing"), model_response("potential_match")]):
                with patch.object(agent, "client", sdk), patch.object(
                    sdk.models, "generate_content", side_effect=replies
                ):
                    data = self.post("/agent-evaluate").json()
                    self.assertEqual(data["execution_mode"], "deterministic_fallback")


if __name__ == "__main__":
    unittest.main()
