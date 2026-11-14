from google import genai

def generate_text(
    prompt: str,
    response_schema: dict | None = None,
) -> str:
    config = None

    if response_schema is not None:
        config = {
            "response_mime_type": "application/json",
            "response_json_schema": response_schema,
        }

    with genai.Client() as client:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt,
            config=config,
        )

        if not response.text:
            raise ValueError("Gemini returned no text.")

        return response.text
