import openai
from datetime import datetime
import logging
import json
import os
from typing import List, Dict
import time

def handle_rate_limit(func, max_retries=3, base_delay=1):
    """
    Enhanced decorator to handle rate limiting with proper retry-after handling
    """
    def wrapper(*args, **kwargs):
        remaining_retries = max_retries
        while remaining_retries > 0:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if isinstance(e, openai.RateLimitError) or "rate limit" in str(e).lower():
                    if remaining_retries > 1:
                        # Extract retry-after if available, otherwise use exponential backoff
                        if hasattr(e, 'response') and e.response.headers.get('retry-after'):
                            delay = float(e.response.headers['retry-after'])
                        else:
                            delay = base_delay * (2 ** (max_retries - remaining_retries))
                        
                        logger.info(f"Rate limit hit, waiting {delay} seconds before retry {max_retries - remaining_retries + 1}/{max_retries}")
                        time.sleep(delay)
                        remaining_retries -= 1
                        continue
                logger.error(f"Rate limit exceeded after {max_retries} retries: {str(e)}")
                raise
        return None
    return wrapper

def process_in_batches(items, process_func, batch_size=5):
    """
    Process items in batches to avoid hitting rate limits
    """
    results = []
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        for item in batch:
            try:
                result = handle_rate_limit(process_func)(item)
                if result is not None:
                    results.append(result)
            except Exception as e:
                logger.error(f"Error processing batch item: {str(e)}")
        time.sleep(1)  # Small delay between batches
    return results
# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize OpenAI client function to ensure fresh client on each request
# Global client instance
_openai_client = None
_last_client_error = None
_client_error_threshold = 3

def get_openai_client():
    """
    Get or create OpenAI client with improved error handling and caching
    """
    global _openai_client, _last_client_error, _client_error_threshold
    
    try:
        # Return existing client if available
        if _openai_client is not None:
            return _openai_client
            
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            raise ValueError("OpenAI API key not configured")
        
        _openai_client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
        return _openai_client
        
    except Exception as e:
        _last_client_error = str(e)
        logger.error(f"Error initializing OpenAI client: {_last_client_error}")
        
        # Check if we need to verify the API key
        if "invalid api key" in str(e).lower():
            logger.critical("Invalid API key detected - please verify your OpenAI API key")
        
        raise

def predict_account(description: str, explanation: str, available_accounts: List[Dict]) -> List[Dict]:
    """
    Account Suggestion Feature (ASF): AI-powered account suggestions based on transaction description
    """
    if not description or not available_accounts:
        logger.error("Missing required parameters for account prediction")
        return []

    logger.info(f"ASF: Predicting account for description: {description}")
    
    # Initialize OpenAI client
    client = get_openai_client()
    
    try:
        # Format available accounts
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

        @handle_rate_limit
        def get_account_suggestions():
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial accounting assistant helping to classify transactions into the correct accounts."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content.strip()

        try:
            content = get_account_suggestions()
            if not content:
                logger.error("Empty response from AI service")
                return rule_based_account_matching(description, available_accounts)
                
            # Validate JSON structure
            if not (content.startswith('[') and content.endswith(']')):
                logger.error("Invalid JSON format in AI response")
                return rule_based_account_matching(description, available_accounts)
                
            try:
                suggestions = json.loads(content)
            except json.JSONDecodeError as je:
                logger.error(f"JSON parsing error: {str(je)}")
                return rule_based_account_matching(description, available_accounts)
            
            # Enhanced validation and formatting
            valid_suggestions = []
            for suggestion in suggestions:
                try:
                    # Validate required fields
                    if not all(k in suggestion for k in ['account_name', 'confidence']):
                        logger.warning(f"Skipping suggestion due to missing required fields: {suggestion}")
                        continue
                        
                    # Match with available accounts
                    matching_accounts = [
                        acc for acc in available_accounts 
                        if acc['name'].lower() == suggestion['account_name'].lower()
                    ]
                    
                    if matching_accounts:
                        # Enhanced suggestion with additional validations
                        financial_insight = suggestion.get('financial_insight', 
                                                        suggestion.get('reasoning', 'No detailed insight available'))
                        valid_suggestion = {
                            'account_name': suggestion['account_name'],
                            'confidence': min(max(float(suggestion['confidence']), 0.0), 1.0),  # Ensure valid confidence range
                            'account': matching_accounts[0],
                            'financial_insight': financial_insight,
                            'reasoning': suggestion.get('reasoning', 'No reasoning provided')
                        }
                        valid_suggestions.append(valid_suggestion)
                        
                except Exception as suggestion_error:
                    logger.warning(f"Error processing suggestion: {str(suggestion_error)}")
                    continue
            
            if not valid_suggestions:
                logger.warning("No valid suggestions found from AI response")
                return rule_based_account_matching(description, available_accounts)
                
            # Sort by confidence and return top 3
            valid_suggestions.sort(key=lambda x: x['confidence'], reverse=True)
            return valid_suggestions[:3]
                
        except Exception as e:
            logger.error(f"Error processing AI response: {str(e)}")
            return rule_based_account_matching(description, available_accounts)
            
    except Exception as e:
        logger.error(f"Critical error in predict_account: {str(e)}")
        return rule_based_account_matching(description, available_accounts)

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

def rule_based_account_matching(description: str, available_accounts: List[Dict]) -> List[Dict]:
    """Fallback method for account matching using rule-based approach"""
    try:
        matches = []
        description_lower = description.lower()
        
        for account in available_accounts:
            score = 0
            account_terms = set(account['name'].lower().split() + 
                             account['category'].lower().split())
            
            # Check for exact matches in name or category
            if any(term in description_lower for term in account_terms):
                score += 0.5
            
            # Check for partial matches
            if any(term in description_lower for term in account_terms):
                score += 0.3
                
            if score > 0:
                matches.append({
                    'account_name': account['name'],
                    'confidence': min(score, 0.8),  # Cap confidence at 0.8 for rule-based
                    'reasoning': 'Matched based on description keywords',
                    'account': account,
                    'financial_insight': 'Suggestion based on text matching rules'
                })
        
        return sorted(matches, key=lambda x: x['confidence'], reverse=True)[:3]
        
    except Exception as e:
        logger.error(f"Error in rule_based_account_matching: {str(e)}")
        return []

def calculate_similarity(transaction_description: str, comparison_description: str) -> float:
    """Calculate semantic similarity between two transaction descriptions"""
    prompt = f"""Compare these two transaction descriptions and rate their semantic similarity:
    Description 1: {transaction_description.strip()}
    Description 2: {comparison_description.strip()}
    
    Consider both textual similarity and semantic meaning.
    Return only a single float number between 0 and 1."""
    
    client = get_openai_client()
    
    @handle_rate_limit
    def make_similarity_request():
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial text analysis expert. Analyze transaction descriptions for similarity."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=50
        )
        return float(response.choices[0].message.content.strip())
    
    try:
        return make_similarity_request()
    except Exception as e:
        logger.error(f"Error calculating similarity: {str(e)}")
        return 0.0

def find_similar_transactions(transaction_description: str, transactions: list) -> list:
    """
    ERF (Explanation Recognition Feature): 
    Find transactions with similar descriptions based on:
    - 70% text similarity OR
    - 95% semantic similarity threshold
    """
    TEXT_THRESHOLD = 0.7
    SEMANTIC_THRESHOLD = 0.95

    if not transaction_description or not transactions:
        logger.warning("Empty transaction description or transactions list")
        return []
    
    logger.info(f"ERF: Finding similar transactions for description: {transaction_description}")
    
    def process_transaction(transaction):
        if not transaction or not getattr(transaction, 'description', None):
            return None
        
        similarity = calculate_similarity(transaction_description, transaction.description)
        if similarity >= TEXT_THRESHOLD or similarity >= SEMANTIC_THRESHOLD:
            return {
                'transaction': transaction,
                'similarity': similarity
            }
        return None
    
    try:
        # Process transactions in batches to handle rate limits
        similar_transactions = process_in_batches(
            transactions,
            process_transaction,
            batch_size=5
        )
        
        # Filter out None values and sort by similarity
        similar_transactions = [t for t in similar_transactions if t is not None]
        similar_transactions.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.info(f"Found {len(similar_transactions)} similar transactions")
        return similar_transactions
        
    except Exception as e:
        logger.error(f"Error in find_similar_transactions: {str(e)}")
        return []

def suggest_explanation(description: str, similar_transactions: list = None) -> dict:
    """
    ESF (Explanation Suggestion Feature): 
    Proactively generates explanation suggestions based on transaction description
    """
    logger.info("ESF: Generating explanation suggestion")
    
    # Initialize OpenAI client
    client = get_openai_client()
    
    try:
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
        
        @handle_rate_limit
        def get_explanation_suggestion():
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial transaction analyzer specializing in generating clear, professional explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=250
            )
            return response.choices[0].message.content.strip()
        
        try:
            content = get_explanation_suggestion()
            if content:
                suggestion = json.loads(content)
                return suggestion
            else:
                logger.error("Empty response from OpenAI")
                return generate_fallback_explanation(description, similar_transactions)
                
        except json.JSONDecodeError as je:
            logger.error(f"Error parsing explanation suggestion: {str(je)}")
            return generate_fallback_explanation(description, similar_transactions)
            
        except Exception as e:
            logger.error(f"Error processing explanation suggestion: {str(e)}")
            return generate_fallback_explanation(description, similar_transactions)
            
    except Exception as e:
        logger.warning(f"AI explanation generation failed, falling back to pattern matching: {str(e)}")
        return generate_fallback_explanation(description, similar_transactions)

def generate_fallback_explanation(description: str, similar_transactions: list = None) -> dict:
    """Generate explanation using fallback pattern matching approach"""
    try:
        # Fallback: Use similar transactions if available
        if similar_transactions and len(similar_transactions) > 0:
            best_match = max(similar_transactions, key=lambda x: x['similarity'])
            if best_match['similarity'] > 0.7:  # High confidence threshold
                return {
                    "suggested_explanation": best_match['transaction'].explanation or description,
                    "confidence": best_match['similarity'],
                    "factors_considered": ["Based on similar transaction pattern"]
                }
        
        # If no similar transactions, generate a basic explanation
        words = description.split()
        basic_explanation = f"Payment for {' '.join(words[:3])}..." if len(words) > 3 else description
        
        return {
            "suggested_explanation": basic_explanation,
            "confidence": 0.3,  # Low confidence for basic pattern matching
            "factors_considered": ["Generated from transaction description pattern"]
        }
        
    except Exception as fallback_error:
        logger.error(f"Fallback explanation generation failed: {str(fallback_error)}")
        return {
            "suggested_explanation": "",
            "confidence": 0.0,
            "factors_considered": [f"Error: {str(fallback_error)}"]
        }

def verify_ai_features() -> bool:
    """
    Verifies AI features functionality with direct API calls
    """
    logger.info("Starting AI features verification...")
    
    try:
        # Test ASF - Account Suggestion Feature
        test_account = predict_account(
            "Monthly Office Rent Payment",
            "Regular monthly office space rental",
            [{'name': 'Rent Expense', 'category': 'Expenses', 'link': '510'}]
        )
        logger.info("ASF test successful")
        
        # Test ERF - Explanation Recognition Feature
        similar_trans = find_similar_transactions(
            "Monthly Office Rent Payment",
            [{'description': 'Office Rent March 2024', 'id': 1}]
        )
        logger.info("ERF test successful")
        
        # Test ESF - Explanation Suggestion Feature
        explanation = suggest_explanation(
            "Monthly Office Rent Payment",
            similar_trans if similar_trans else None
        )
        logger.info("ESF test successful")
        
        return True
        
    except Exception as e:
        logger.error(f"AI features verification failed: {str(e)}")
        return False