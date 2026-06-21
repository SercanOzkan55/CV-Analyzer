import os
from loguru import logger


def get_ai_client_and_model():
    """Unified factory for AI Client (OpenAI-compatible) and the target Model Name.
    Supports OpenAI, Gemini Flash (direct or compatibility layer), and Mock/Dev modes.

    Returns:
        (client, model) or (None, None) if mock or unconfigured.
    """
    try:
        from openai import OpenAI
    except ImportError:
        logger.error("openai package not installed or failed to import")
        return None, None

    # Determine provider: gemini, openai, openai-compatible, or mock
    provider = os.getenv("REWRITE_PROVIDER", "").strip().lower()

    # Auto-detect if not specified but GEMINI_API_KEY is available
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not provider:
        if gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        else:
            provider = "mock"

    if provider == "mock":
        return None, None

    # Handle Gemini Flash
    if provider == "gemini":
        if not gemini_key:
            logger.warning(
                "Gemini provider selected but GEMINI_API_KEY/GOOGLE_API_KEY not found. Falling back to OpenAI key if present."
            )
            gemini_key = openai_key

        if not gemini_key:
            return None, None

        base_url = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai/")
        model = os.getenv("REWRITE_MODEL", "gemini-2.5-flash").strip()

        logger.info(f"Initializing Gemini client via OpenAI compatibility layer (model: {model})")
        client = OpenAI(api_key=gemini_key, base_url=base_url)
        return client, model

    # Handle OpenAI / OpenAI-compatible
    if not openai_key:
        return None, None

    base_url = os.getenv("OPENAI_API_BASE") or None
    model = os.getenv("REWRITE_MODEL", "gpt-4o-mini").strip()

    logger.info(f"Initializing OpenAI client (model: {model}, base_url: {base_url})")
    client = OpenAI(api_key=openai_key, base_url=base_url)
    return client, model


def get_embedding_client_and_model():
    """Unified factory for Embeddings. Supports OpenAI and Gemini/Google.

    Returns:
        (client, model) or (None, None)
    """
    try:
        from openai import OpenAI
    except ImportError:
        return None, None

    provider = os.getenv("REWRITE_PROVIDER", "").strip().lower()
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if not provider:
        if gemini_key:
            provider = "gemini"
        elif openai_key:
            provider = "openai"
        else:
            provider = "mock"

    if provider == "gemini" and gemini_key:
        base_url = os.getenv("GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta/openai/")
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-004").strip()
        client = OpenAI(api_key=gemini_key, base_url=base_url)
        return client, model

    if openai_key:
        base_url = os.getenv("OPENAI_API_BASE") or None
        model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()
        client = OpenAI(api_key=openai_key, base_url=base_url)
        return client, model

    return None, None
