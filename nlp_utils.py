import os
import openai
import logging
from typing import Tuple
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Initialize OpenAI client with timeout configuration
try:
    client = openai.OpenAI(
        api_key=os.environ.get('OPENAI_API_KEY'),
        timeout=30.0,  # 30 second timeout
        max_retries=2  # Allow 2 retries
    )
    logger.info("OpenAI client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing OpenAI client: {str(e)}")
    raise

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

def categorize_transaction(description: str) -> Tuple[str, float, str]:
    """
    Use OpenAI to categorize a financial transaction with explanation
    Returns: (category, confidence, explanation)
    """
    # Initialize cache if not exists
    if not hasattr(categorize_transaction, '_cache'):
        categorize_transaction._cache = {}
    
    # Check cache first
    cache_key = description.strip().lower()
    if cache_key in categorize_transaction._cache:
        logger.info(f"Using cached categorization for: {description[:50]}...")
        return categorize_transaction._cache[cache_key]
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial transaction categorization expert. Be concise and precise."},
                {"role": "user", "content": get_category_prompt(description)}
            ],
            temperature=0.2,
            max_tokens=100,  # Reduced for faster response
        )
        
        # Parse response
        result = response.choices[0].message.content.strip().split('|')
        if len(result) == 3:
            category = result[0].strip().lower()
            confidence = float(result[1].strip())
            explanation = result[2].strip()
            
            # Validate category
            if category not in CATEGORIES:
                category = 'other'
                confidence = 0.5
            
            # Cache the result
            categorize_transaction._cache[cache_key] = (category, confidence, explanation)
            return category, confidence, explanation
            
    except Exception as e:
        logger.error(f"OpenAI API error for '{description[:50]}...': {str(e)}")
        # Fallback to 'other' category with low confidence
        return 'other', 0.1, f"Error in categorization: {str(e)}"
    
    return 'other', 0.1, "Unable to categorize transaction"
