import openai
from datetime import datetime
import logging
import json
import os
from typing import List, Dict

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize OpenAI client function to ensure fresh client on each request
def get_openai_client():
    try:
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            raise ValueError("OpenAI API key not configured")
        
        client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Error initializing OpenAI client: {str(e)}")
        raise

def predict_account(description: str, explanation: str, available_accounts: List[Dict]) -> List[Dict]:
    """
    Account Suggestion Feature (ASF): AI-powered account suggestions based on transaction description
    and existing Chart of Accounts structure. The function learns from the available accounts to make
    intelligent suggestions for transaction categorization.
    """
    try:
        logger.debug(f"ASF: Starting account prediction for description: {description}")
        
        # Initialize OpenAI client
        client = get_openai_client()
        
        # Format available accounts with enhanced structure
        account_info = "\n".join([
            f"- {acc['name']}\n  Category: {acc['category']}\n  Code: {acc['link']}\n  Purpose: Standard {acc['category']} account for {acc['name'].lower()} transactions"
            for acc in available_accounts
        ])
        
        logger.debug(f"ASF: Analyzing {len(available_accounts)} accounts from Chart of Accounts")
        
        # Enhanced prompt for better account matching
        prompt = f"""As an expert financial analyst, analyze this transaction and suggest the most appropriate account classification from the Chart of Accounts:

Transaction to Analyze:
- Description: {description}
- Additional Context: {explanation}

Available Chart of Accounts:
{account_info}

Task:
Analyze the transaction and suggest appropriate accounts based on:
1. Semantic matching between transaction description and account purposes
2. Standard accounting principles and best practices
3. Transaction nature (income, expense, asset, liability)
4. Account categories and hierarchies

Consider:
- Account category alignment
- Transaction type matching
- Industry standard practices
- Semantic relevance
- Historical accounting patterns

Format response as a JSON list with this structure:
[
    {{
        "account_name": "exact account name from Chart of Accounts",
        "confidence": 0.0-1.0,
        "reasoning": "detailed explanation of the match",
        "financial_insight": "impact on financial reporting",
        "category_match": "explanation of category fit"
    }}
]

Return 1-3 suggestions, ranked by confidence. Only suggest accounts that exist in the provided Chart of Accounts."""

        # Make API call with error handling
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial accounting assistant helping to classify transactions into the correct accounts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            logger.debug("Successfully received response from OpenAI")
            
            # Parse response
            content = response.choices[0].message.content.strip()
            suggestions = []
            
            # Safely evaluate the response content
            if content.startswith('[') and content.endswith(']'):
                suggestions = json.loads(content)
            else:
                logger.error("Invalid response format from AI")
                
            # Validate and format suggestions
            valid_suggestions = []
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
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing AI suggestions: {str(e)}")
            logger.debug(f"Raw content received: {content}")
            raise ValueError("Failed to parse AI response")
            
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error in account prediction: {str(e)}")
        return []

def detect_transaction_anomalies(transactions, historical_data=None):
    """Detect anomalies in transactions using AI analysis."""
    try:
        client = get_openai_client()
        
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

        # Make API call
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst specialized in detecting transaction anomalies and patterns."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )

            # Parse response
            content = response.choices[0].message.content.strip()
            try:
                analysis = json.loads(content)
                return analysis
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing anomaly detection response: {str(e)}")
                return {
                    "error": "Failed to parse anomaly detection results",
                    "details": str(e)
                }

        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            raise

    except Exception as e:
        logger.error(f"Error in anomaly detection: {str(e)}")
        return {
            "error": "Failed to analyze transactions for anomalies",
            "details": str(e)
        }

def forecast_expenses(transactions, accounts, forecast_months=12):
    """Generate expense forecasts based on historical transaction patterns."""
    try:
        client = get_openai_client()
        
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
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert financial analyst specializing in expense forecasting and predictive analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000
            )
            
            # Parse and validate the forecast
            try:
                content = response.choices[0].message.content.strip()
                if not content:
                    logger.error("Empty response from AI model")
                    return {
                        "error": "Empty response from AI model",
                        "monthly_forecasts": [],
                        "forecast_factors": {"key_drivers": [], "risk_factors": [], "assumptions": []},
                        "confidence_metrics": {"overall_confidence": 0, "variance_range": {"min": 0, "max": 0}, "reliability_score": 0},
                        "recommendations": []
                    }

                forecast = json.loads(content)
                return forecast
                
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error in forecast: {str(je)}")
                return {
                    "error": "Invalid forecast format",
                    "details": str(je),
                    "monthly_forecasts": [],
                    "forecast_factors": {"key_drivers": [], "risk_factors": [], "assumptions": []},
                    "confidence_metrics": {"overall_confidence": 0, "variance_range": {"min": 0, "max": 0}, "reliability_score": 0},
                    "recommendations": []
                }
            
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error generating expense forecast: {str(e)}")
        return {
            "error": "Failed to generate expense forecast",
            "details": str(e),
            "monthly_forecasts": [],
            "forecast_factors": {"key_drivers": [], "risk_factors": [], "assumptions": []},
            "confidence_metrics": {"overall_confidence": 0, "variance_range": {"min": 0, "max": 0}, "reliability_score": 0},
            "recommendations": []
        }

def generate_financial_advice(transactions, accounts):
    """
    Generate comprehensive financial advice based on transaction patterns and account usage.
    """
    try:
        client = get_openai_client()
        
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
{{
    "key_insights": [
        {{
            "category": "string",
            "finding": "string",
            "impact_level": "high|medium|low",
            "trend": "increasing|stable|decreasing"
        }}
    ],
    "risk_factors": [
        {{
            "risk_type": "string",
            "probability": "high|medium|low",
            "potential_impact": "string",
            "mitigation_strategy": "string"
        }}
    ],
    "optimization_opportunities": [
        {{
            "area": "string",
            "potential_benefit": "string",
            "implementation_difficulty": "high|medium|low",
            "recommended_timeline": "string"
        }}
    ],
    "strategic_recommendations": [
        {{
            "timeframe": "short|medium|long",
            "action": "string",
            "expected_outcome": "string",
            "priority": "high|medium|low"
        }}
    ],
    "cash_flow_analysis": {{
        "current_status": "string",
        "projected_trend": "string",
        "key_drivers": ["string"],
        "improvement_suggestions": ["string"]
    }}
}}"""

        # Make API call with error handling
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert financial advisor specializing in business accounting, financial strategy, and predictive analysis. Focus on providing actionable insights and quantitative metrics."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )

            # Parse and validate the response
            try:
                advice = json.loads(response.choices[0].message.content.strip())
                
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
                
            except json.JSONDecodeError as je:
                logger.error(f"Error parsing financial advice: {str(je)}")
                return {
                    "error": "Failed to parse financial advice",
                    "details": str(je)
                }
                
        except Exception as e:
            logger.error(f"Error in OpenAI API call: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error generating financial advice: {str(e)}")
        return {
            "error": "Failed to generate financial advice",
            "details": str(e)
        }

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity between two strings."""
    try:
        # Initialize OpenAI client
        client = get_openai_client()
        
        prompt = f"""Compare these two transaction descriptions and return their similarity score:
        Text 1: {text1}
        Text 2: {text2}
        
        Consider both textual and semantic similarity. Return a single float between 0 and 1.
        A score of 1 means identical or semantically equivalent descriptions.
        A score of 0 means completely different descriptions.
        
        Format: Return only the numerical score, e.g. "0.85"
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a text similarity analyzer. Provide similarity scores based on both textual and semantic similarity."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        
        similarity = float(response.choices[0].message.content.strip())
        return min(max(similarity, 0.0), 1.0)  # Ensure score is between 0 and 1
        
    except Exception as e:
        logger.error(f"Error calculating text similarity: {str(e)}")
        return 0.0

def find_similar_transactions(transaction_description: str, transactions: list, text_threshold: float = 0.7, semantic_threshold: float = 0.95) -> list:
    """
    Find transactions with similar descriptions based on ERF requirements:
    - 70% text similarity OR
    - 95% semantic similarity
    """
    if not transaction_description or not transactions:
        logger.warning("Empty transaction description or transactions list")
        return []
        
    similar_transactions = []
    logger.info(f"Finding similar transactions for description: {transaction_description}")
    
    try:
        for transaction in transactions:
            if not transaction.description:
                continue
                
            try:
                # Calculate similarity
                similarity = calculate_text_similarity(
                    transaction_description.strip(),
                    transaction.description.strip()
                )
                
                logger.debug(f"Similarity score: {similarity} for transaction: {transaction.description}")
                
                # Add transaction if it meets either threshold
                if similarity >= text_threshold or similarity >= semantic_threshold:
                    similar_transactions.append({
                        'transaction': transaction,
                        'similarity': similarity
                    })
            except Exception as calc_error:
                logger.error(f"Error calculating similarity for transaction {transaction.id}: {str(calc_error)}")
                continue
        
        # Sort by similarity score in descending order
        similar_transactions.sort(key=lambda x: x['similarity'], reverse=True)
        logger.info(f"Found {len(similar_transactions)} similar transactions")
        return similar_transactions
        
    except Exception as e:
        logger.error(f"Error in find_similar_transactions: {str(e)}")
        return []

def suggest_explanation(description: str, similar_transactions: list = None) -> dict:
    """Generate explanation suggestions based on transaction description and similar transactions."""
    try:
        client = get_openai_client()
        
        # Format similar transactions for context
        similar_context = ""
        if similar_transactions:
            similar_context = "\nSimilar transactions and their explanations:\n" + "\n".join([
                f"- Description: {t['transaction'].description}\n  Explanation: {t['transaction'].explanation}"
                for t in similar_transactions[:3] if t['transaction'].explanation
            ])
        
        prompt = f"""Analyze this financial transaction and suggest an explanation:
        
        Transaction Description: {description}
        {similar_context}
        
        Based on the transaction description and any similar transactions, provide:
        1. A clear, professional explanation
        2. The confidence level in this suggestion
        3. Key factors considered in generating this explanation
        
        Format your response as a JSON object with this structure:
        {{
            "suggested_explanation": "string",
            "confidence": float,
            "factors_considered": ["string"]
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial transaction analyzer specializing in generating clear, professional explanations."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=250
        )
        
        suggestion = json.loads(response.choices[0].message.content.strip())
        return suggestion
        
    except Exception as e:
        logger.error(f"Error generating explanation suggestion: {str(e)}")
        return {
            "suggested_explanation": "",
            "confidence": 0.0,
            "factors_considered": [f"Error: {str(e)}"]
        }