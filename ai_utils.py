import os
import openai
import logging
from typing import List, Dict

# Configure logging
logger = logging.getLogger(__name__)

def predict_account(description: str, explanation: str, available_accounts: List[Dict]) -> List[Dict]:
    """
    Predict the most likely account classifications for a transaction based on its description and explanation.
    
    Args:
        description: Transaction description
        explanation: User-provided explanation
        available_accounts: List of available account dictionaries with 'name', 'category', and 'link' keys
    
    Returns:
        List of predicted account matches with confidence scores
    """
    try:
        # Format available accounts for the prompt
        account_info = "\n".join([
            f"- {acc['name']} (Category: {acc['category']}, Code: {acc['link']})"
            for acc in available_accounts
        ])
        
        # Construct the prompt
        prompt = f"""Analyze this financial transaction and provide comprehensive account classification with financial insights:

Transaction Details:
- Description: {description}
- Additional Context/Explanation: {explanation}

Available Chart of Accounts:
{account_info}

Instructions:
1. Analyze both transaction description and explanation with equal weight for classification
2. Consider account categories, sub-categories, and accounting principles
3. Evaluate patterns and financial implications
4. Provide confidence scores based on:
   - Semantic similarity with account purposes
   - Clarity and completeness of transaction information
   - Historical accounting patterns
   - Compliance with accounting principles
5. Generate detailed reasoning that includes:
   - Specific matching criteria met
   - Financial implications
   - Accounting principle alignment
   - Alternative considerations

Format your response as a JSON list with exactly this structure:
[
    {{
        "account_name": "suggested account name",
        "confidence": 0.95,
        "reasoning": "detailed explanation including category fit, accounting principles, and financial implications",
        "financial_insight": "broader financial context and impact analysis"
    }},
    {{
        "account_name": "alternative account",
        "confidence": 0.75,
        "reasoning": "explanation of alternative classification",
        "financial_insight": "additional financial implications for this classification"
    }}
]

Provide up to 3 suggestions, ranked by confidence (0 to 1). Focus on accuracy and detailed financial insights."""

        # Make API call
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial accounting assistant helping to classify transactions into the correct accounts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        suggestions = []
        try:
            # Safely evaluate the response content
            import json
            if content.startswith('[') and content.endswith(']'):
                suggestions = json.loads(content)
            else:
                logger.error("Invalid response format from AI")
        except Exception as e:
            logger.error(f"Error parsing AI suggestions: {str(e)}")
            logger.debug(f"Raw content received: {content}")
        
        # Validate and format suggestions
        valid_suggestions = []
        try:
            for suggestion in suggestions:
                # Only include suggestions that match existing accounts
                matching_accounts = [acc for acc in available_accounts if acc['name'].lower() == suggestion['account_name'].lower()]
                if matching_accounts:
                    # Extract financial insight or use reasoning if insight not provided
                    financial_insight = suggestion.get('financial_insight', suggestion.get('reasoning', ''))
                    
                    valid_suggestions.append({
                        **suggestion,
                        'account': matching_accounts[0],
                        'financial_insight': financial_insight
                    })
            
            return valid_suggestions[:3]  # Return top 3 suggestions
        except Exception as e:
            logger.error(f"Error processing suggestions: {str(e)}")
            return []
        
    except Exception as e:
        logger.error(f"Error in account prediction: {str(e)}")
        return []
