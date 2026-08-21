import json
import ollama


def extract_impact_with_llm(text: str) -> dict:

    prompt = f"""
You are extracting structured information from an industrial
laboratory impact test report.

Extract ONLY information explicitly present in the document.

Return valid JSON only.

Required format:

{{
    "readings": [],
    "average": null,
    "single_minimum": null,
    "average_minimum": null,
    "temperature_c": null
}}

Rules:
- readings must contain the individual impact energy readings.
- Do not invent missing values.
- Use numbers only.
- If a value cannot be determined, use null.
- Do not explain anything.
- Do not decide PASS or FAIL.

DOCUMENT:

{text}
"""

    response = ollama.chat(
        model="gemma3:1b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        format="json"
    )

    try:
        return json.loads(
            response["message"]["content"]
        )

    except Exception:
        return {
            "readings": [],
            "average": None,
            "single_minimum": None,
            "average_minimum": None,
            "temperature_c": None
        }