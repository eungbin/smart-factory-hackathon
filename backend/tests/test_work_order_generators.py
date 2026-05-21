import unittest

from app.work_orders.generators import GeminiWorkOrderGenerator, WorkOrderGenerationContext, WorkOrderGenerationError


class WorkOrderGeneratorTests(unittest.TestCase):
    def test_gemini_generator_calls_rest_api_and_maps_structured_json(self) -> None:
        calls: list[dict] = []

        def fake_transport(url: str, api_key: str, payload: dict) -> dict:
            calls.append({"url": url, "api_key": api_key, "payload": payload})
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"title":"3호 사출기 베어링 정비",'
                                        '"steps":[{"no":1,"category":"안전","action":"전원 차단","tool":"LOTO","time":"5분","safety":true}],'
                                        '"parts":[{"name":"베어링 #6205-2RS","qty":"1개","stock":"재고 1개"}],'
                                        '"totalTime":"약 25분","techLevel":"정비 2급 이상","caution":"유압 잔압 해제 후 작업"}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

        generator = GeminiWorkOrderGenerator(
            api_key="test-key",
            model="gemini-2.5-flash",
            transport=fake_transport,
        )
        result = generator.generate(
            WorkOrderGenerationContext(
                equipment_name="3호 사출기",
                fault_type_text="베어링 불량 (78%)",
                root_sensors=["진동 RMS 상승"],
                source_summary="설비 운영 매뉴얼 §4.3",
                rag_sources=[{"heading": "베어링 정비", "body": "유압 잔압 해제"}],
            )
        )

        self.assertEqual("gemini", result.provider)
        self.assertEqual("gemini-2.5-flash", result.model)
        self.assertEqual("3호 사출기 베어링 정비", result.title)
        self.assertEqual("전원 차단", result.steps[0].action)
        self.assertEqual("베어링 #6205-2RS", result.parts[0].name)
        self.assertEqual("약 25분", result.total_time_text)
        self.assertEqual(25, result.total_minutes)
        self.assertEqual(1, len(calls))
        self.assertIn("models/gemini-2.5-flash:generateContent", calls[0]["url"])
        self.assertEqual("test-key", calls[0]["api_key"])
        self.assertEqual("application/json", calls[0]["payload"]["generationConfig"]["responseMimeType"])
        self.assertIn("responseJsonSchema", calls[0]["payload"]["generationConfig"])

    def test_gemini_generator_rejects_unknown_step_category(self) -> None:
        def fake_transport(url: str, api_key: str, payload: dict) -> dict:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": (
                                        '{"title":"3호 사출기 정비",'
                                        '"steps":[{"no":1,"category":"조치","action":"베어링 교체","tool":"렌치","time":"20분","safety":false}],'
                                        '"parts":[{"name":"베어링","qty":"1개","stock":"재고 1개"}],'
                                        '"totalTime":"약 20분","techLevel":"정비 2급 이상","caution":"전원 차단 후 작업"}'
                                    )
                                }
                            ]
                        }
                    }
                ]
            }

        generator = GeminiWorkOrderGenerator(
            api_key="test-key",
            model="gemini-2.5-flash",
            transport=fake_transport,
        )

        with self.assertRaises(WorkOrderGenerationError) as raised:
            generator.generate(
                WorkOrderGenerationContext(
                    equipment_name="3호 사출기",
                    fault_type_text="베어링 불량 (78%)",
                    root_sensors=["진동 RMS 상승"],
                    source_summary="설비 운영 매뉴얼 §4.3",
                    rag_sources=[],
                )
            )

        self.assertEqual("provider_response_invalid", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
