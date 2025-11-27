# app/services/llm_client.py
import os
import json
import logging
import aiohttp

logger = logging.getLogger(__name__)

HF_GEMMA_URL = os.getenv("HF_GEMMA_URL")  # e.g. https://router.huggingface.co/v1/chat/completions
HF_GEMMA_KEY = os.getenv("HF_GEMMA_KEY")  # Hugging Face token
HF_GEMMA_MODEL = os.getenv("HF_GEMMA_MODEL", "google/gemma-2-9b-it")

last_llm_used = "gemma"

async def call_gpt_model(prompt: str) -> str:
    """
    Sends the prompt to Gemma-2-9B-Instruct via Hugging Face API.
    Returns the generated text response.
    """
    if not HF_GEMMA_KEY or not HF_GEMMA_URL:
        logger.error("❌ Missing HF_GEMMA_KEY or HF_GEMMA_URL in environment variables.")
        return "LLM call failed: missing Hugging Face credentials."

    headers = {
        "Authorization": f"Bearer {HF_GEMMA_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": HF_GEMMA_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "max_tokens": 400,
        "temperature": 0.5
    }

    try:
        logger.info("🧠 Sending prompt to Gemma (Hugging Face API)...")

        async with aiohttp.ClientSession() as session:
            async with session.post(HF_GEMMA_URL, headers=headers, json=payload, timeout=90) as response:
                result_text = await response.text()

                if response.status != 200:
                    logger.error(f"❌ Gemma API Error {response.status}: {result_text}")
                    return f"LLM call failed ({response.status})"

                result = json.loads(result_text)
                logger.info("✅ Got response from Gemma model.")

                # Extract the text response
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"].strip()
                return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"❌ Gemma request failed: {e}")
        return f"LLM call failed: {str(e)}"
