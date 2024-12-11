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
        prompt = f"""Given a financial transaction with:
Description: {description}
Additional Explanation: {explanation}

Available accounts:
{account_info}

Based on the transaction details and available accounts, suggest the most appropriate account classification.
Format your response as a JSON list with the following structure:
[
    {{"account_name": "suggested account name", "confidence": 0.95, "reasoning": "brief explanation"}},
    {{"account_name": "alternative account", "confidence": 0.75, "reasoning": "brief explanation"}}
]
Limit to top 3 most likely matches. Confidence should be between 0 and 1."""

        # Make API call
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial accounting assistant helping to classify transactions into the correct accounts."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse response
        suggestions = eval(response.choices[0].message.content)
        
        # Validate and format suggestions
        valid_suggestions = []
        for suggestion in suggestions:
            # Only include suggestions that match existing accounts
            matching_accounts = [acc for acc in available_accounts if acc['name'].lower() == suggestion['account_name'].lower()]
            if matching_accounts:
                valid_suggestions.append({
                    **suggestion,
                    'account': matching_accounts[0]
                })
        
        return valid_suggestions[:3]  # Return top 3 suggestions
        
    except Exception as e:
        logger.error(f"Error in account prediction: {str(e)}")
        return []
