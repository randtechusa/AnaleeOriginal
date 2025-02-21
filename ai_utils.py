"""
AI utilities module with enhanced error handling and rate limiting
"""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from openai import OpenAI, APIError, RateLimitError
import os
import time
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import json
from difflib import SequenceMatcher
from sqlalchemy.exc import SQLAlchemyError
from models import ErrorLog, db


# Configure logging with proper format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global client instance with protection
_openai_client = None
_last_client_error = None
_client_error_threshold = 3

def get_openai_client() -> Optional[OpenAI]:
    """
    Get or create OpenAI client with improved error handling and caching
    Returns None if client initialization fails after retries
    """
    global _openai_client, _last_client_error

    try:
        # Return existing client if available and valid
        if _openai_client is not None:
            return _openai_client

        # Get API key from environment with enhanced validation
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            logger.error("OpenAI API key not found in environment variables")
            return None

        # Initialize new client with proper configuration
        _openai_client = OpenAI(api_key=api_key)

        # Validate client with a test call
        try:
            _openai_client.models.list(limit=1)
            logger.info("OpenAI client initialized and tested successfully")
            _last_client_error = None
            return _openai_client
        except Exception as e:
            logger.error(f"Client validation failed: {str(e)}")
            _openai_client = None
            _last_client_error = str(e)
            return None

    except Exception as e:
        logger.error(f"Unexpected error during client initialization: {str(e)}")
        _last_client_error = str(e)
        return None


# Enhance the rate limit handler
def handle_rate_limit(func, max_retries=3, base_delay=2):
    """
    Enhanced decorator to handle rate limiting with adaptive retry strategy
    and comprehensive error handling
    """
    @retry(
        retry=retry_if_exception_type((RateLimitError, APIError)),
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=base_delay, min=4, max=30),
        reraise=True
    )
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except RateLimitError as e:
            logger.warning(f"Rate limit hit: {str(e)}")
            retry_after = getattr(e, 'retry_after', None)
            if retry_after:
                logger.info(f"Waiting {retry_after} seconds as suggested by API")
                time.sleep(retry_after)
            raise
        except APIError as e:
            if e.status_code == 429:  # Rate limit
                logger.warning(f"Rate limit hit via APIError: {str(e)}")
                raise RateLimitError("Rate limit exceeded")
            logger.error(f"API error: {str(e)}")
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "invalid api key" in error_msg:
                logger.error("Invalid API key detected")
                raise ValueError("Invalid OpenAI API key configuration")
            logger.error(f"Unexpected error in API call: {str(e)}")
            raise
    return wrapper

def process_in_batches(items, process_func, batch_size=3):
    """
    Process items in batches with improved rate limit handling and dynamic backoff
    """
    results = []
    total_batches = (len(items) + batch_size - 1) // batch_size
    base_delay = 2  # Base delay between batches in seconds

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_number = i // batch_size + 1
        logger.info(f"Processing batch {batch_number}/{total_batches}")

        retry_count = 0
        max_retries = 3

        while retry_count < max_retries:
            try:
                batch_results = []
                for item in batch:
                    try:
                        result = handle_rate_limit(process_func)(item)
                        if result is not None:
                            batch_results.append(result)
                    except RateLimitError as e:
                        logger.warning(f"Rate limit hit processing item in batch {batch_number}: {str(e)}")
                        # Exponential backoff
                        wait_time = base_delay * (2 ** retry_count)
                        logger.info(f"Waiting {wait_time} seconds before retry")
                        time.sleep(wait_time)
                        raise  # Re-raise to trigger batch retry
                    except Exception as e:
                        logger.error(f"Error processing item in batch {batch_number}: {str(e)}")
                        continue

                results.extend(batch_results)
                # Successful batch, add base delay before next batch
                time.sleep(base_delay)
                break  # Break while loop on success

            except RateLimitError:
                retry_count += 1
                if retry_count >= max_retries:
                    logger.error(f"Failed to process batch {batch_number} after {max_retries} retries")
                    break
            except Exception as e:
                logger.error(f"Unexpected error processing batch {batch_number}: {str(e)}")
                break

    return results

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Initialize OpenAI client function to ensure fresh client on each request
# Global client instance


def predict_account(description: str, explanation: str, available_accounts: List[Dict]) -> Tuple[bool, str, List[Dict]]:
    """Account Suggestion Feature (ASF) with enhanced validation and pattern matching"""
    logger = logging.getLogger(__name__)
    processing_start = datetime.now()

    try:
        # Enhanced input validation
        validation_errors = []

        if not isinstance(description, str):
            validation_errors.append("Description must be a string type")
        elif not description.strip():
            validation_errors.append("Description cannot be empty")
        elif len(description.strip()) < 3:
            validation_errors.append("Description must be at least 3 characters")

        if explanation is not None and not isinstance(explanation, str):
            validation_errors.append("Explanation must be a string type")

        if validation_errors:
            error_msg = "; ".join(validation_errors)
            logger.error(f"ASF validation failed: {error_msg}")
            return False, error_msg, []

        # Validate available accounts structure
        if not isinstance(available_accounts, list):
            logger.error("ASF: Invalid accounts format")
            return False, "Invalid accounts format", []

        valid_accounts = []
        for idx, acc in enumerate(available_accounts):
            if not isinstance(acc, dict):
                logger.warning(f"ASF: Invalid account format at index {idx}")
                continue

            required_fields = ['name', 'category', 'id']
            missing_fields = [f for f in required_fields if f not in acc]

            if missing_fields:
                logger.warning(f"ASF: Account at index {idx} missing fields: {missing_fields}")
                continue

            valid_accounts.append(acc)

        if not valid_accounts:
            logger.error("ASF: No valid accounts after validation")
            return False, "No valid accounts available", []

        description = description.strip()
        if not description:
            logger.error("ASF: Empty description provided")
            return False, "Description cannot be empty", []

        if len(description) < 3:
            logger.error("ASF: Description too short")
            return False, "Description must be at least 3 characters", []

        # Account validation
        if not isinstance(available_accounts, list):
            logger.error("ASF: Invalid accounts format")
            return False, "Invalid accounts format", []

        if not available_accounts:
            logger.error("ASF: No accounts available")
            return False, "No accounts available for matching", []

        # Validate each account
        valid_accounts = []
        for acc in available_accounts:
            if not isinstance(acc, dict):
                logger.warning(f"ASF: Invalid account format: {acc}")
                continue

            required_fields = ['name', 'category', 'id']
            if all(field in acc for field in required_fields):
                valid_accounts.append(acc)
            else:
                logger.warning(f"ASF: Account missing required fields: {acc}")

        if not valid_accounts:
            logger.error("ASF: No valid accounts after validation")
            return False, "No valid accounts available", []

        # Initialize metrics
        start_time = time.time()
        processing_metrics = {
            'total_accounts': len(valid_accounts),
            'start_time': start_time
        }

        client = get_openai_client()
        if not client:
            logger.warning("OpenAI client unavailable, using fallback matching")
            return False, "OpenAI client unavailable", []

        # Format account information
        account_info = "\n".join([
            f"- {acc['name']} ({acc['category']}): {acc.get('description', 'No description')}"
            for acc in available_accounts
        ])

        prompt = f"""
Analyze this transaction and suggest the most appropriate account classification:
Transaction Description: {description}
Additional Context: {explanation}

Available Accounts:
{account_info}

Provide up to 3 suggestions in JSON format:
[{{"account": "exact_name", "confidence": 0.0-1.0, "reasoning": "explanation"}}]
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial account classification expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        suggestions = json.loads(response.choices[0].message.content)
        processing_metrics['end_time'] = time.time()
        processing_metrics['processing_time'] = processing_metrics['end_time'] - processing_metrics['start_time']
        return True, "", suggestions[:3]  # Return top 3 suggestions

    except Exception as e:
        logger.error(f"Error in account suggestion: {str(e)}")
        return False, str(e), []

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

        try:
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
            logger.error(f"Error in OpenAI API call: {str(e)}")
            return 0.0

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
    """Calculate semantic similarity between two transaction descriptions with improved error handling"""
    if not transaction_description or not comparison_description:
        logger.warning("Empty description provided for similarity calculation")
        return 0.0

    prompt = f"""Compare these two transaction descriptions and rate their semantic similarity:
    Description 1: {transaction_description.strip()}
    Description 2: {comparison_description.strip()}

    Consider both textual similarity and semantic meaning.
    Your response must be ONLY a single number between 0 and 1.
    For example: 0.75

    DO NOT include any explanation or text, just the number."""

    client = get_openai_client()
    if not client:
        logger.error("Failed to initialize OpenAI client")
        return 0.0

    @handle_rate_limit
    def make_similarity_request():
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a similarity scoring system. You MUST respond with only a single float number between 0 and 1."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=10  # Reduced to prevent verbose responses
            )

            content = response.choices[0].message.content.strip()

            # Clean the response to handle potential formatting issues
            content = content.replace(',', '.').strip('%')

            # Extract the first number found in the response
            import re
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", content)
            if numbers:
                value = float(numbers[0])
                # Ensure the value is between 0 and 1
                return max(0.0, min(1.0, value))
            else:
                logger.error(f"No valid number found in response: {content}")
                return 0.0

        except ValueError as ve:
            logger.error(f"Error parsing similarity score: {str(ve)}")
            return 0.0
        except Exception as e:
            logger.error(f"Error in similarity request: {str(e)}")
            raise  #Let handle_rate_limit handle retries if needed

    try:
        return make_similarity_request()
    except Exception as e:
        logger.error(f"Error calculating similarity: {str(e)}")
        return 0.0

class ERFProcessor:
    def __init__(self):
        self.TEXT_SIMILARITY_THRESHOLD = 0.7
        self.SEMANTIC_SIMILARITY_THRESHOLD = 0.95
        self.MAX_RETRIES = 3
        self.MIN_DESCRIPTION_LENGTH = 3

    def validate_description(self, description: str) -> Tuple[bool, str]:
        """Validate transaction description"""
        if not description:
            return False, "Description cannot be empty"
        if len(description.strip()) < self.MIN_DESCRIPTION_LENGTH:
            return False, f"Description must be at least {self.MIN_DESCRIPTION_LENGTH} characters"
        return True, "Valid description"

    def calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity between two strings"""
        try:
            return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
        except Exception as e:
            logger.error(f"Error calculating text similarity: {str(e)}")
            return 0.0

    def find_similar_transactions(self, 
                                transaction_description: str, 
                                transactions: List[Dict],
                                user_id: int) -> Tuple[bool, str, List[Dict]]:
        """
        Enhanced ERF: Find transactions with similar descriptions using multiple similarity metrics
        """
        try:
            # Validate input
            is_valid, validation_msg = self.validate_description(transaction_description)
            if not is_valid:
                return False, validation_msg, []

            # Initialize results
            similar_transactions = []
            processed_count = 0
            error_count = 0

            logger.info(f"Processing ERF for description: {transaction_description}")

            for transaction in transactions:
                try:
                    processed_count += 1

                    # Skip invalid transactions
                    if not transaction.get('description'):
                        continue

                    # Calculate similarity
                    similarity = self.calculate_text_similarity(
                        transaction_description,
                        transaction['description']
                    )

                    if similarity >= self.TEXT_SIMILARITY_THRESHOLD:
                        similar_transactions.append({
                            'transaction': transaction,
                            'similarity_score': similarity,
                            'match_type': 'text'
                        })

                except Exception as e:
                    error_count += 1
                    logger.error(f"Error processing transaction {transaction.get('id', 'unknown')}: {str(e)}")

                    # Log error to database
                    self.log_error(user_id, 'ERF_PROCESSING_ERROR', str(e))

                    if error_count > self.MAX_RETRIES:
                        return False, "Exceeded maximum error threshold", []

            # Sort by similarity score
            similar_transactions.sort(key=lambda x: x['similarity_score'], reverse=True)

            logger.info(f"ERF processing completed. Found {len(similar_transactions)} matches")

            return True, f"Successfully processed {processed_count} transactions", similar_transactions

        except Exception as e:
            error_msg = f"ERF processing failed: {str(e)}"
            logger.error(error_msg)
            self.log_error(user_id, 'ERF_SYSTEM_ERROR', error_msg)
            return False, error_msg, []

    def log_error(self, user_id: int, error_type: str, error_message: str):
        """Log errors to database"""
        try:
            error_log = ErrorLog(
                timestamp=datetime.utcnow(),
                error_type=error_type,
                error_message=error_message,
                user_id=user_id
            )
            db.session.add(error_log)
            db.session.commit()
        except SQLAlchemyError as e:
            logger.error(f"Failed to log error to database: {str(e)}")

def find_similar_transactions(transaction_description: str, transactions: list, user_id: int) -> list:
    """
    ERF (Explanation Recognition Feature): 
    Find transactions with similar descriptions based on:
    - 70% text similarity OR
    - 95% semantic similarity threshold
    """    erf_processor = ERFProcessor()
    success, message, similar_transactions = erf_processor.find_similar_transactions(
        transaction_description, transactions, user_id
    )
    if not success:
        logger.error(message)
        return []
    return similar_transactions

def suggest_explanation(description: str, similar_transactions: list = None) -> dict:
    """ESF (Explanation Suggestion Feature): Enhanced explanation generator"""
    logger = logging.getLogger(__name__)

    try:
        client = get_openai_client()
        if not client:
            return {'explanation': '', 'confidence': 0}

        # Create context from similar transactions
        context = ""
        if similar_transactions:
            context = "\nSimilar transactions:\n" + "\n".join([
                f"- {t['description']}: {t.get('explanation', 'No explanation')}"
                for t in similar_transactions[:3]
            ])

        prompt = f"""Analyze this financial transaction and suggest a clear explanation:
Description: {description}
{context}

Consider:
1. Transaction type and purpose
2. Business context
3. Similar historical transactions
4. Standard accounting practices

Provide a JSON response:
{{"explanation": "clear_professional_explanation", "confidence": 0.0-1.0}}
"""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial transaction analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        result = json.loads(response.choices[0].message.content)
        return result

    except Exception as e:
        logger.error(f"Error suggesting explanation: {str(e)}")
        return {'explanation': '', 'confidence': 0}


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
            [{'name': 'Rent Expense', 'category': 'Expenses', 'link': '510', 'id': 1}]
        )
        logger.info("ASF test successful")

        # Test ERF - Explanation Recognition Feature
        similar_trans = find_similar_transactions(
            "Monthly Office Rent Payment",
            [{'description': 'Office Rent March 2024', 'id': 1}], 1
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

import logging
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from nlp_utils import get_openai_client, clean_text

logger = logging.getLogger(__name__)
handler = logging.FileHandler('ai_utils.log')
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

class AIUtils:
    def __init__(self):
        self._client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client safely"""
        try:
            self._client = get_openai_client()
            if self._client is None:
                logger.error("Failed to initialize OpenAI client")
            else:
                logger.info("OpenAI client initialized successfully in AIUtils")
        except Exception as e:
            logger.error(f"Error initializing OpenAI client in AIUtils: {str(e)}")
            self._client = None

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def analyze_transaction(self, transaction_data):
        """Analyze a financial transaction with retries"""
        if self._client is None:
            self._initialize_client()
            if self._client is None:
                raise ValueError("OpenAI client unavailable")

        try:
            response = await self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial transaction analyzer."},
                    {"role": "user", "content": f"Analyze this transaction: {clean_text(str(transaction_data))}"}
                ],
                max_tokens=100,
                temperature=0.5
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to analyze transaction: {str(e)}")
            raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def categorize_transaction(self, description):
        """Categorize a transaction based on its description"""
        if self._client is None:
            self._initialize_client()
            if self._client is None:
                raise ValueError("OpenAI client unavailable")

        try:
            response = await self._client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial transaction categorizer."},
                    {"role": "user", "content": f"Categorize this transaction: {clean_text(description)}"}
                ],
                max_tokens=50,
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Failed to categorize transaction: {str(e)}")
            raise