import json
import re
from typing import Dict

def parse_json_report(raw_text: str) -> Dict:
    """
    Safely extracts and parses JSON from AI output, 
    even if it's wrapped in triple backticks.
    """
    try:
        json_match= re.search(r"```json\n(.*?)\n```", raw_text, re.DOTALL)
        if json_match:
            clean_json= json_match.group(1)
        else:
            clean_json= raw_text.strip()

        report= json.loads(clean_json)

        return {
            "status": report.get("status", "unknown"),
            "risk_score": float(report.get("risk_score", 0.5)),
            "confidence_score": int(report.get("confidence_score", 0)),
            "summary": report.get("summary", "No summary provided."),
            "sources": report.get("sources", [])
        }

    except Exception as e:
        return {
            "status": "error",
            "risk_score": 1.0,
            "summary": f"Failed to parse report: {str(e)}",
            "raw_output": raw_text
        }