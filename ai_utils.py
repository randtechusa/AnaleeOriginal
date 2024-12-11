import openai
from datetime import datetime
import logging
import json
import os
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

def detect_transaction_anomalies(transactions, historical_data=None):
    """
    Detect anomalies in transactions using AI analysis of Description and Explanation fields.
    
    Args:
        transactions: List of current transactions to analyze
        historical_data: Optional historical transaction data for baseline comparison
        
    Returns:
        List of dictionaries containing anomaly details
    """
    try:
        # Format transaction data for analysis
        transaction_text = "\n".join([
            f"Transaction {idx + 1}:\n"
            f"- Amount: ${t.amount}\n"
            f"- Description: {t.description}\n"
            f"- Explanation: {t.explanation or 'No explanation provided'}\n"
            f"- Date: {t.date.strftime('%Y-%m-%d')}\n"
            f"- Account: {t.account.name if t.account else 'Uncategorized'}"
            for idx, t in enumerate(transactions)
        ])

        prompt = f"""Analyze these transactions for potential anomalies and unusual patterns. Consider:

1. Amount patterns:
   - Unusually large or small amounts
   - Irregular payment patterns
   - Unexpected changes in regular amounts

2. Description & Explanation analysis:
   - Inconsistencies between description and explanation
   - Unusual or unexpected descriptions
   - Missing or vague explanations
   - Semantic mismatches with account categories

3. Timing patterns:
   - Unusual transaction timing
   - Irregular frequencies
   - Unexpected date patterns

4. Account usage:
   - Unusual account assignments
   - Inconsistent categorization
   - Pattern deviations

Transactions to analyze:
{transaction_text}

Provide analysis in this JSON structure:
{{
    "anomalies": [
        {{
            "transaction_index": <index>,
            "anomaly_type": "amount|description|timing|account",
            "confidence": <float between 0-1>,
            "reason": "detailed explanation",
            "severity": "high|medium|low",
            "recommendation": "suggested action"
        }}
    ],
    "pattern_insights": {{
        "identified_patterns": ["string"],
        "unusual_deviations": ["string"]
    }}
}}"""

        # Make API call for anomaly detection
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst specialized in detecting transaction anomalies and patterns. Focus on providing detailed, actionable insights while maintaining high accuracy."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more consistent analysis
            max_tokens=1000,
            response_format={"type": "json_object"}
        )

        # Parse and return the analysis
        import json
        analysis = json.loads(response.choices[0].message.content)
        return analysis

    except Exception as e:
        logger.error(f"Error detecting transaction anomalies: {str(e)}")
        return {
            "error": "Failed to analyze transactions for anomalies",
            "details": str(e)
        }

def generate_financial_advice(transactions, accounts):
    """
    Generate comprehensive financial advice based on transaction patterns and account usage.
    
    Args:
        transactions: List of transaction dictionaries with amount, description, and account info
        accounts: List of available accounts with categories and balances
        
    Returns:
        Dictionary containing financial insights and recommendations
    """
    try:
        # Format transaction data for the prompt
        transaction_summary = "\n".join([
            f"- Amount: ${t['amount']}, Description: {t['description']}, "
            f"Account: {t['account_name'] if 'account_name' in t else 'Uncategorized'}"
            for t in transactions[:10]  # Limit to recent transactions for context
        ])
        
        # Format account balances
        account_summary = "\n".join([
            f"- {acc['name']}: ${acc.get('balance', 0):.2f} ({acc['category']})"
            for acc in accounts
        ])
        
        prompt = f"""Analyze these financial transactions and account balances to provide comprehensive natural language insights and predictive advice:

Transaction History:
{transaction_summary}

Account Balances:
{account_summary}

Instructions:
1. Perform Detailed Pattern Analysis
   - Identify and explain recurring transaction patterns
   - Calculate and interpret growth rates with context
   - Analyze seasonal variations and their business impact
   - Evaluate account utilization efficiency with recommendations
   - Provide natural language explanations for each pattern

2. Generate In-depth Financial Health Assessment
   - Analyze cash flow stability with detailed commentary
   - Track and explain account balance trends
   - Break down spending patterns by category
   - Assess revenue diversification opportunities
   - Highlight key financial ratios and their implications

3. Create Forward-looking Analysis
   - Project growth trajectories with supporting data
   - Conduct comprehensive risk assessment
   - Generate detailed cash flow forecasts
   - Identify specific budget optimization opportunities
   - Explain market and industry context

4. Develop Actionable Recommendations
   - Provide specific short-term actions (next 30 days)
   - Outline medium-term strategy (3-6 months)
   - Detail long-term planning (6-12 months)
   - Include implementation steps for each recommendation
   - Explain expected outcomes and success metrics

Provide a detailed financial analysis in this JSON structure:
{
    "key_insights": [
        {
            "category": "string",
            "finding": "string",
            "impact_level": "high|medium|low",
            "trend": "increasing|stable|decreasing"
        }
    ],
    "risk_factors": [
        {
            "risk_type": "string",
            "probability": "high|medium|low",
            "potential_impact": "string",
            "mitigation_strategy": "string"
        }
    ],
    "optimization_opportunities": [
        {
            "area": "string",
            "potential_benefit": "string",
            "implementation_difficulty": "high|medium|low",
            "recommended_timeline": "string"
        }
    ],
    "strategic_recommendations": [
        {
            "timeframe": "short|medium|long",
            "action": "string",
            "expected_outcome": "string",
            "priority": "high|medium|low"
        }
    ],
    "cash_flow_analysis": {
        "current_status": "string",
        "projected_trend": "string",
        "key_drivers": ["string"],
        "improvement_suggestions": ["string"]
    }
}
"""

        # Make API call for financial advice
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using gpt-3.5-turbo for consistent API support
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert financial advisor specializing in business accounting, financial strategy, and predictive analysis. Focus on providing actionable insights and quantitative metrics. Format your response as valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more focused and consistent advice
            max_tokens=1000
        )
        
        # Parse and return the financial advice
        try:
            import json
            advice = json.loads(response.choices[0].message.content)
            
            # Enhance the advice with more detailed natural language summaries
            enhanced_advice = {
                "key_insights": advice.get("key_insights", []),
                "risk_factors": advice.get("risk_factors", []),
                "optimization_opportunities": advice.get("optimization_opportunities", []),
                "strategic_recommendations": advice.get("strategic_recommendations", []),
                "cash_flow_analysis": {
                    "current_status": advice.get("cash_flow_analysis", {}).get("current_status", ""),
                    "projected_trend": advice.get("cash_flow_analysis", {}).get("projected_trend", ""),
                    "key_drivers": advice.get("cash_flow_analysis", {}).get("key_drivers", []),
                    "improvement_suggestions": advice.get("cash_flow_analysis", {}).get("improvement_suggestions", [])
                }
            }
            
            return enhanced_advice
        except json.JSONDecodeError:
            # If JSON parsing fails, return the raw text in a structured format
            raw_advice = response.choices[0].message.content
            return {
                "key_insights": raw_advice,
                "risk_factors": [],
                "optimization_opportunities": [],
                "strategic_recommendations": [],
                "cash_flow_analysis": {
                    "current_status": "",
                    "projected_trend": "",
                    "key_drivers": [],
                    "improvement_suggestions": []
                }
            }
            
    except Exception as e:
        logger.error(f"Error generating financial advice: {str(e)}")
        return {
            "error": "Failed to generate financial advice",
            "details": str(e)
        }

def forecast_expenses(transactions, accounts, forecast_months=12):
    """
    Generate expense forecasts based on historical transaction patterns.
    
    Args:
        transactions: List of transaction dictionaries with amount, description, and dates
        accounts: List of available accounts with categories and balances
        forecast_months: Number of months to forecast (default 12)
        
    Returns:
        Dictionary containing expense forecasts and confidence metrics
    """
    try:
        # Format transaction data for analysis
        transaction_summary = "\n".join([
            f"- Amount: ${t['amount']}, Description: {t['description']}, "
            f"Date: {t.get('date', 'N/A')}, Account: {t.get('account_name', 'Uncategorized')}"
            for t in transactions[:50]  # Use recent transactions for pattern analysis
        ])
        
        # Format account information
        account_summary = "\n".join([
            f"- {acc['name']}: ${acc.get('balance', 0):.2f} ({acc['category']})"
            for acc in accounts
        ])
        
        prompt = f"""Analyze these financial transactions and accounts to generate detailed expense forecasts:

Transaction History:
{transaction_summary}

Account Balances:
{account_summary}

Instructions:
1. Analyze Historical Patterns
   - Identify recurring expenses and their frequencies
   - Calculate growth rates and seasonal variations
   - Consider account-specific trends
   - Factor in both Description and Explanation fields for pattern recognition

2. Generate Expense Forecasts
   - Project monthly expenses for next {forecast_months} months
   - Break down by expense categories
   - Include confidence intervals
   - Account for seasonality and trends
   - Consider economic factors and business context

3. Provide Risk Analysis
   - Identify potential expense risks
   - Calculate variance in projections
   - Assess forecast reliability
   - Consider external factors

Format your response as a JSON object with this structure:
{{
    "monthly_forecasts": [
        {{
            "month": "YYYY-MM",
            "total_expenses": float,
            "confidence": float,
            "breakdown": [
                {{
                    "category": string,
                    "amount": float,
                    "trend": "increasing|stable|decreasing"
                }}
            ]
        }}
    ],
    "forecast_factors": {{
        "key_drivers": [string],
        "risk_factors": [string],
        "assumptions": [string]
    }},
    "confidence_metrics": {{
        "overall_confidence": float,
        "variance_range": {{
            "min": float,
            "max": float
        }},
        "reliability_score": float
    }},
    "recommendations": [
        {{
            "action": string,
            "potential_impact": string,
            "implementation_timeline": string
        }}
    ]
}}"""

        # Make API call
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Using gpt-3.5-turbo for consistent API support
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst specializing in expense forecasting and predictive analysis. Focus on providing accurate, actionable forecasts with detailed supporting analysis. Format your response as valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        # Parse and return the forecast
        import json
        forecast = json.loads(response.choices[0].message.content)
        
        # Add metadata about the forecast
        forecast["generated_at"] = datetime.utcnow().isoformat()
        forecast["forecast_period_months"] = forecast_months
        forecast["data_points_analyzed"] = len(transactions)
        
        return forecast
        
    except Exception as e:
        logger.error(f"Error generating expense forecast: {str(e)}")
        return {
            "error": "Failed to generate expense forecast",
            "details": str(e)
        }