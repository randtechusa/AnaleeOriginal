"""
NLP utilities module for handling natural language processing tasks
Enhanced with proper type checking, validation, and comprehensive features
"""
import os
import sys
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta
import time
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Global client instance with proper error tracking
_openai_client = None
_last_client_error = None
_last_client_init = None
_client_error_count = 0
MAX_ERROR_COUNT = 3
CLIENT_RETRY_INTERVAL = 300  # 5 minutes

def get_openai_client() -> Optional[OpenAI]:
    """Get OpenAI client with improved error handling and state tracking"""
    global _openai_client, _last_client_error, _last_client_init, _client_error_count

    try:
        # Use existing client if available and working
        if _openai_client is not None:
            return _openai_client

        # Check if we need to wait before retrying
        if _last_client_error and _client_error_count >= MAX_ERROR_COUNT:
            if _last_client_init:
                wait_time = CLIENT_RETRY_INTERVAL - (time.time() - _last_client_init)
                if wait_time > 0:
                    logger.warning(f"Rate limit cooldown: waiting {wait_time:.0f}s")
                    return None

        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found")
            return None

        # Initialize client with required configuration
        _openai_client = OpenAI(api_key=api_key)
        _last_client_init = time.time()
        _client_error_count = 0  # Reset error count on successful initialization
        logger.info("OpenAI client initialized successfully")

        return _openai_client

    except Exception as e:
        _last_client_error = str(e)
        _client_error_count += 1
        logger.error(f"OpenAI client initialization failed: {str(e)}")
        return None

# Rate limiting configuration
RATE_LIMIT_REQUESTS = 50  # requests per minute
RATE_LIMIT_WINDOW = 60  # seconds
request_times = deque(maxlen=RATE_LIMIT_REQUESTS)

def wait_for_rate_limit():
    """Implement token bucket rate limiting"""
    now = datetime.now()
    while len(request_times) >= RATE_LIMIT_REQUESTS:
        window_start = now - timedelta(seconds=RATE_LIMIT_WINDOW)
        if request_times[0] < window_start:
            request_times.popleft()
        else:
            sleep_time = (request_times[0] + timedelta(seconds=RATE_LIMIT_WINDOW) - now).total_seconds()
            if sleep_time > 0:
                logger.info(f"Rate limit reached, waiting for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            break
    request_times.append(now)

# Transaction categories
CATEGORIES = [
    'income', 'groceries', 'utilities', 'transportation', 'entertainment',
    'shopping', 'healthcare', 'housing', 'education', 'investments',
    'dining', 'travel', 'insurance', 'personal_care', 'other'
]

def get_category_prompt(description: str) -> str:
    """Generate prompt for transaction categorization"""
    return f"""Analyze this financial transaction and categorize it:
Transaction: {description}

Categories to choose from:
{', '.join(CATEGORIES)}

Please respond with:
1. The most appropriate category from the list above
2. Confidence score (0-1)
3. Brief explanation of why this category was chosen

Format: category|confidence|explanation"""

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    reraise=True
)
def categorize_transaction(description: str) -> Tuple[str, float, str]:
    """
    Use OpenAI to categorize a financial transaction with explanation
    Returns: (category, confidence, explanation)
    """
    if not description:
        logger.warning("Empty description provided for categorization")
        return 'other', 0.1, "No description provided"

    client = get_openai_client()
    if not client:
        logger.error("Failed to initialize OpenAI client")
        return 'other', 0.1, "Service unavailable"

    try:
        # Apply rate limiting
        wait_for_rate_limit()

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial transaction categorization expert. Categorize transactions accurately and explain your reasoning briefly."},
                {"role": "user", "content": get_category_prompt(description)}
            ],
            temperature=0.3,
            max_tokens=150
        )

        if not response.choices:
            logger.error("Empty response from OpenAI API")
            return 'other', 0.1, "Service returned empty response"

        result = response.choices[0].message.content.strip().split('|')
        if len(result) == 3:
            category = result[0].strip().lower()
            try:
                confidence = float(result[1].strip())
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                logger.warning(f"Invalid confidence value: {result[1]}")
                confidence = 0.5
            explanation = result[2].strip()

            if category not in CATEGORIES:
                logger.warning(f"Invalid category returned: {category}")
                category = 'other'
                confidence = 0.5

            return category, confidence, explanation

        logger.warning("Unexpected response format")
        return 'other', 0.1, "Unable to parse service response"

    except Exception as e:
        logger.error(f"Error in transaction categorization: {str(e)}")
        return 'other', 0.1, f"Service error: {str(e)}"