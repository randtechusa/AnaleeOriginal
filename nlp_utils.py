import os
import openai
from typing import Tuple

# Initialize OpenAI client
client = openai.OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

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
        result = response.choices[0].message.content.strip().split('|')
        if len(result) == 3:
            category = result[0].strip().lower()
            confidence = float(result[1].strip())
            explanation = result[2].strip()
            
            # Validate category
            if category not in CATEGORIES:
                category = 'other'
                confidence = 0.5
            
            return category, confidence, explanation
            
    except Exception as e:
        print(f"OpenAI API error: {str(e)}")
        # Fallback to 'other' category with low confidence
        return 'other', 0.1, f"Error in categorization: {str(e)}"
    
    return 'other', 0.1, "Unable to categorize transaction"
