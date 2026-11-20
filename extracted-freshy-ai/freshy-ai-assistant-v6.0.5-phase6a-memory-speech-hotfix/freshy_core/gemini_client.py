import os
import json
from typing import Optional
from config import config
from intents import Intent, RuleBasedIntentParser

class GeminiIntentAnalyzer:
    """
    Gemini integration wrapper.
    If GEMINI_API_KEY is available, calls Gemini to classify user queries into structured JSON intents.
    If GEMINI_API_KEY is missing or fails, gracefully defaults to rule-based offline parser.
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        self.client = None
        if self.api_key and self.api_key != "MY_GEMINI_API_KEY":
            try:
                from google import genai
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"[Freshy Core] Note: Gemini client init skipped or warning: {e}")

    def analyze_intent(self, user_message: str) -> Intent:
        """
        Attempts structured Gemini intent parsing if API key is provided.
        Falls back seamlessly to local RuleBasedIntentParser.
        """
        if not self.client:
            # Fallback directly to offline rule-based parser
            return RuleBasedIntentParser.parse(user_message)

        try:
            prompt = f"""
            You are Freshy AI, an intent classification system for desktop actions.
            Analyze the user input and extract a structured JSON object matching this schema:
            {{
                "name": "GREETING" | "TIME_DATE" | "OPEN_APP" | "OPEN_WEBSITE" | "UNKNOWN",
                "confidence": number (0.0 to 1.0),
                "parameters": {{
                    "app_name": "notepad" | "calculator" (if OPEN_APP),
                    "url": string (if OPEN_WEBSITE)
                }},
                "explanation": string
            }}

            User Input: "{user_message}"
            Respond ONLY with valid JSON, no markdown code block formatting.
            """

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )

            response_text = response.text.strip()
            # Clean json fences if present
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            data = json.loads(response_text.strip())
            return Intent(
                name=data.get("name", "UNKNOWN"),
                confidence=float(data.get("confidence", 0.9)),
                parameters=data.get("parameters", {}),
                explanation=data.get("explanation", "Gemini structured intent classification")
            )
        except Exception as e:
            print(f"[Freshy Core] Gemini parsing fallback due to: {e}")
            return RuleBasedIntentParser.parse(user_message)
