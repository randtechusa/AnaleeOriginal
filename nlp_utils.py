import os
import openai
import logging
from typing import Tuple, Optional
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client with better error handling
def get_openai_client() -> Optional[OpenAI]:
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            return None
        return OpenAI(api_key=api_key)
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {str(e)}")
        return None

CATEGORIES = [
    'income', 'groceries', 'utilities', 'transportation', 'entertainment',
    'shopping', 'healthcare', 'housing', 'education', 'investments',
    'dining', 'travel', 'insurance', 'personal_care', 'other'
]

def get_category_prompt(description: str) -> str:
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
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial transaction categorization expert. Categorize transactions accurately and explain your reasoning briefly."},
                {"role": "user", "content": get_category_prompt(description)}
            ],
            temperature=0.3,
            max_tokens=150
        )
        
        # Parse response
        if not response.choices:
            logger.error("Empty response from OpenAI API")
            return 'other', 0.1, "Service returned empty response"
            
        result = response.choices[0].message.content.strip().split('|')
        if len(result) == 3:
            category = result[0].strip().lower()
            try:
                confidence = float(result[1].strip())
                confidence = max(0.0, min(1.0, confidence))  # Ensure confidence is between 0 and 1
            except ValueError:
                logger.warning(f"Invalid confidence value: {result[1]}")
                confidence = 0.5
            explanation = result[2].strip()
            
            # Validate category
            if category not in CATEGORIES:
                logger.warning(f"Invalid category returned: {category}")
                category = 'other'
                confidence = 0.5
            
            return category, confidence, explanation
            
    except openai.RateLimitError as e:
        logger.error(f"Rate limit exceeded: {str(e)}")
        raise  # Let retry handle this
    except openai.APIError as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return 'other', 0.1, f"Service error: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error in categorization: {str(e)}")
        return 'other', 0.1, f"Error in categorization: {str(e)}"
    
    logger.warning("Failed to parse categorization response")
    return 'other', 0.1, "Unable to categorize transaction"
