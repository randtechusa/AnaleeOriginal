import os
import openai
import logging
import json
from typing import List, Dict, Union, Any
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

def analyze_cross_field_patterns(transactions):
    """
    Analyze patterns across Description and Explanation fields to detect correlations and anomalies.
    
    Args:
        transactions: List of transaction objects with Description and Explanation fields
    
    Returns:
        Dictionary containing cross-field analysis results
    """
    logger.info("Starting cross-field pattern analysis")
    
    try:
        if not transactions:
            logger.warning("No transactions provided for cross-field analysis")
            return {
                "warning": "No transactions available for analysis",
                "field_correlations": [],
                "pattern_confidence": 0.0,
                "identified_relationships": [],
                "anomaly_indicators": []
            }
            
        # Validate transaction data structure
        valid_transactions = []
        for t in transactions:
            try:
                if (hasattr(t, 'description') and hasattr(t, 'amount') and 
                    hasattr(t, 'date') and hasattr(t, 'explanation')):
                    valid_transactions.append(t)
                else:
                    logger.warning(f"Invalid transaction structure: {vars(t) if hasattr(t, '__dict__') else str(t)}")
            except Exception as e:
                logger.warning(f"Error validating transaction: {str(e)}")
                continue
                
        if not valid_transactions:
            return {
                "warning": "No valid transactions found for analysis",
                "field_correlations": [],
                "pattern_confidence": 0.0,
                "identified_relationships": [],
                "anomaly_indicators": []
            }
            
        logger.info(f"Found {len(valid_transactions)} valid transactions for analysis")
        transactions = valid_transactions
        
        patterns = {
            "field_correlations": [],
            "pattern_confidence": 0.0,
            "identified_relationships": [],
            "anomaly_indicators": []
        }
        
        logger.info(f"Analyzing {len(transactions)} transactions for patterns")
        
        # Group transactions by common patterns in descriptions
        description_patterns = {}
        explanation_patterns = {}
        
        for transaction in transactions:
            # Analyze description patterns
            desc_key = transaction.description.lower()
            if desc_key not in description_patterns:
                description_patterns[desc_key] = []
            description_patterns[desc_key].append(transaction)
            
            # Analyze explanation patterns if available
            if transaction.explanation:
                exp_key = transaction.explanation.lower()
                if exp_key not in explanation_patterns:
                    explanation_patterns[exp_key] = []
                explanation_patterns[exp_key].append(transaction)
        
        # Identify correlations between descriptions and explanations
        for desc_key, desc_transactions in description_patterns.items():
            related_explanations = set()
            for trans in desc_transactions:
                if trans.explanation:
                    related_explanations.add(trans.explanation.lower())
            
            if len(related_explanations) > 0:
                correlation = {
                    "description_pattern": desc_key,
                    "related_explanations": list(related_explanations),
                    "frequency": len(desc_transactions),
                    "confidence": len(related_explanations) / len(desc_transactions)
                }
                patterns["field_correlations"].append(correlation)
        
        # Calculate overall pattern confidence
        if patterns["field_correlations"]:
            patterns["pattern_confidence"] = sum(c["confidence"] for c in patterns["field_correlations"]) / len(patterns["field_correlations"])
        
        # Identify relationship patterns
        for correlation in patterns["field_correlations"]:
            if correlation["confidence"] > 0.7:  # High confidence threshold
                relationship = {
                    "pattern": correlation["description_pattern"],
                    "associated_explanations": correlation["related_explanations"],
                    "strength": correlation["confidence"],
                    "frequency": correlation["frequency"]
                }
                patterns["identified_relationships"].append(relationship)
        
        # Detect potential anomalies in relationships
        for correlation in patterns["field_correlations"]:
            if correlation["confidence"] < 0.3:  # Low confidence threshold
                anomaly = {
                    "pattern": correlation["description_pattern"],
                    "inconsistency_level": 1 - correlation["confidence"],
                    "frequency": correlation["frequency"],
                    "recommendation": "Review transactions with inconsistent description-explanation patterns"
                }
                patterns["anomaly_indicators"].append(anomaly)
                
        return patterns
            
    except Exception as e:
        logger.error(f"Error in cross-field pattern analysis: {str(e)}")
        return {
            "error": str(e),
            "field_correlations": [],
            "pattern_confidence": 0.0,
            "identified_relationships": [],
            "anomaly_indicators": []
        }

def analyze_temporal_patterns(transactions, time_window_days=30):
    """
    Analyze temporal patterns in transaction data to identify trends and cyclical behavior.
    Uses advanced pattern recognition to detect recurring transactions and seasonal variations.
    
    Args:
        transactions: List of transaction objects
        time_window_days: Number of days to consider for each analysis window
    
    Returns:
        Dictionary containing detailed temporal pattern analysis results
    """
    temporal_patterns = {
        "cycles": [],
        "trends": [],
        "seasonal_patterns": [],
        "confidence_metrics": {
            "cycle_confidence": 0.0,
            "trend_confidence": 0.0,
            "seasonality_confidence": 0.0
        }
    }
    
    try:
        # Sort transactions by date
        sorted_transactions = sorted(transactions, key=lambda x: x.date)
        
        # Group transactions by time windows
        time_windows = {}
        current_window = None
        
        for transaction in sorted_transactions:
            window_start = transaction.date.replace(hour=0, minute=0, second=0, microsecond=0)
            if current_window is None or (window_start - current_window).days >= time_window_days:
                current_window = window_start
                if current_window not in time_windows:
                    time_windows[current_window] = []
            time_windows[current_window].append(transaction)
        
        # Analyze patterns within each time window
        for window_start, window_transactions in time_windows.items():
            window_end = window_start + timedelta(days=time_window_days)
            
            # Calculate window metrics
            total_amount = sum(t.amount for t in window_transactions)
            avg_amount = total_amount / len(window_transactions) if window_transactions else 0
            transaction_count = len(window_transactions)
            
            # Identify cyclical patterns
            if transaction_count > 0:
                cycle = {
                    "period": f"{window_start.strftime('%Y-%m-%d')} to {window_end.strftime('%Y-%m-%d')}",
                    "transaction_count": transaction_count,
                    "average_amount": avg_amount,
                    "total_amount": total_amount,
                    "confidence": min(transaction_count / 10, 1.0)  # Confidence based on sample size
                }
                temporal_patterns["cycles"].append(cycle)
            
            # Analyze trends
            if len(temporal_patterns["cycles"]) > 1:
                prev_cycle = temporal_patterns["cycles"][-2]
                current_cycle = temporal_patterns["cycles"][-1]
                
                trend = {
                    "period": current_cycle["period"],
                    "change_in_frequency": current_cycle["transaction_count"] - prev_cycle["transaction_count"],
                    "change_in_amount": current_cycle["total_amount"] - prev_cycle["total_amount"],
                    "confidence": min(current_cycle["confidence"], prev_cycle["confidence"])
                }
                temporal_patterns["trends"].append(trend)
        
        # Calculate overall confidence metrics
        if temporal_patterns["cycles"]:
            temporal_patterns["confidence_metrics"]["cycle_confidence"] = sum(c["confidence"] for c in temporal_patterns["cycles"]) / len(temporal_patterns["cycles"])
        
        if temporal_patterns["trends"]:
            temporal_patterns["confidence_metrics"]["trend_confidence"] = sum(t["confidence"] for t in temporal_patterns["trends"]) / len(temporal_patterns["trends"])
        
        # Identify seasonal patterns
        if len(temporal_patterns["cycles"]) >= 4:  # Need at least 4 cycles for seasonal analysis
            seasonal_patterns = []
            cycle_amounts = [cycle["total_amount"] for cycle in temporal_patterns["cycles"]]
            
            # Simple seasonal pattern detection
            for i in range(len(cycle_amounts) - 3):
                if abs(cycle_amounts[i] - cycle_amounts[i + 3]) / max(abs(cycle_amounts[i]), 1) < 0.2:  # 20% threshold
                    pattern = {
                        "start_period": temporal_patterns["cycles"][i]["period"],
                        "end_period": temporal_patterns["cycles"][i + 3]["period"],
                        "pattern_type": "quarterly",
                        "confidence": 0.8
                    }
                    seasonal_patterns.append(pattern)
            
            temporal_patterns["seasonal_patterns"] = seasonal_patterns
            if seasonal_patterns:
                temporal_patterns["confidence_metrics"]["seasonality_confidence"] = sum(p["confidence"] for p in seasonal_patterns) / len(seasonal_patterns)
        
        return temporal_patterns
            
    except Exception as e:
        logger.error(f"Error in temporal pattern analysis: {str(e)}")
        return {
            "error": str(e),
            "cycles": [],
            "trends": [],
            "seasonal_patterns": [],
            "confidence_metrics": {
                "cycle_confidence": 0.0,
                "trend_confidence": 0.0,
                "seasonality_confidence": 0.0
            }
        }

def detect_transaction_anomalies(transactions, historical_data=None, sensitivity_threshold=0.7):
    """
    Detect anomalies in transactions using AI analysis of Description and Explanation fields.
    """
    try:
        if not transactions:
            logger.warning("No transactions provided for anomaly detection")
            return {
                "warning": "No transactions available for analysis",
                "anomalies": [],
                "pattern_insights": {}
            }

        # Validate transaction data and handle missing attributes gracefully
        valid_transactions = []
        for t in transactions:
            try:
                if (hasattr(t, 'amount') and 
                    hasattr(t, 'description') and 
                    hasattr(t, 'date')):
                    valid_transactions.append(t)
            except Exception as e:
                logger.warning(f"Invalid transaction data: {str(e)}")
                continue

        if not valid_transactions:
            return {
                "warning": "No valid transactions for analysis",
                "anomalies": [],
                "pattern_insights": {}
            }

        # Process a smaller batch for initial analysis
        analysis_batch = valid_transactions[:10]  # Reduced from 20 to 10 for faster processing
        
        # Initialize OpenAI client with proper error handling
        try:
            client = openai.OpenAI(
                api_key=os.environ.get('OPENAI_API_KEY'),
                timeout=10.0  # Reduced timeout for faster response
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            return {
                "error": "Unable to initialize analysis",
                "anomalies": [],
                "pattern_insights": {}
            }

        # Prepare transaction data for analysis
        transaction_summary = "\n".join([
            f"Transaction {idx + 1}:\n"
            f"Amount: ${t.amount}\n"
            f"Description: {t.description}\n"
            f"Date: {t.date.strftime('%Y-%m-%d')}"
            for idx, t in enumerate(analysis_batch)
        ])

        # Simplified prompt for faster processing
        prompt = f"""Analyze these transactions for anomalies. Keep analysis brief and focused:

Transactions:
{transaction_summary}

Threshold: {sensitivity_threshold}

Provide analysis in this JSON format:
{{
    "anomalies": [
        {{
            "transaction_index": number,
            "severity": "low|medium|high",
            "reason": "brief explanation",
            "confidence": 0.0-1.0
        }}
    ],
    "pattern_insights": {{
        "identified_patterns": ["pattern1", "pattern2"],
        "unusual_deviations": ["deviation1", "deviation2"]
    }}
}}"""

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a financial analyst. Provide brief, focused analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=300,  # Reduced for faster response
                timeout=10  # Shorter timeout
            )
            
            analysis = json.loads(response.choices[0].message.content)
            
            # Add basic validation for the analysis
            if not isinstance(analysis, dict):
                raise ValueError("Invalid analysis format")
                
            return analysis
            
        except Exception as e:
            logger.error(f"Error in transaction analysis: {str(e)}")
            return {
                "error": f"Analysis error: {str(e)}",
                "anomalies": [],
                "pattern_insights": {}
            }
            
    except Exception as e:
        logger.error(f"Error in anomaly detection: {str(e)}")
        return {
            "error": str(e),
            "anomalies": [],
            "pattern_insights": {}
        }

def analyze_historical_patterns(historical_data):
    """
    Analyze historical transaction data to identify patterns and establish baselines.
    
    Args:
        historical_data: List of historical transactions
        
    Returns:
        Dictionary containing detailed pattern analysis
    """
    try:
        # Group transactions by category and month
        category_data = {}
        monthly_data = {}
        
        for transaction in historical_data:
            # Category grouping
            category = transaction.account.category if transaction.account else 'Uncategorized'
            if category not in category_data:
                category_data[category] = []
            category_data[category].append(transaction)
            
            # Monthly grouping
            month_key = transaction.date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = []
            monthly_data[month_key].append(transaction)
        
        # Calculate statistics and patterns for each category
        category_patterns = {}
        for category, transactions in category_data.items():
            amounts = [t.amount for t in transactions]
            category_patterns[category] = {
                'average_amount': sum(amounts) / len(amounts) if amounts else 0,
                'transaction_count': len(transactions),
                'total_amount': sum(amounts),
                'min_amount': min(amounts) if amounts else 0,
                'max_amount': max(amounts) if amounts else 0
            }
        
        # Generate summary
        summary = []
        for category, stats in category_patterns.items():
            summary.append(
                f"Category: {category}\n"
                f"- Transaction Count: {stats['transaction_count']}\n"
                f"- Average Amount: ${stats['average_amount']:.2f}\n"
                f"- Total Amount: ${stats['total_amount']:.2f}\n"
                f"- Amount Range: ${stats['min_amount']:.2f} to ${stats['max_amount']:.2f}"
            )
        
        return {
            'summary': "\n\n".join(summary),
            'category_patterns': category_patterns,
            'monthly_data': monthly_data
        }
        
    except Exception as e:
        logger.error(f"Error analyzing historical patterns: {str(e)}")
        return {
            'summary': "Error analyzing historical patterns",
            'category_patterns': {},
            'monthly_data': {}
        }

def predict_account(description: str, explanation: str, available_accounts: List[Dict]) -> List[Dict]:
    """Predict the most likely account classifications for a transaction."""
    try:
        # Cache key for suggestions
        cache_key = f"{description}:{explanation}"
        
        # Format account information (limited to top 10 most relevant)
        account_info = "\n".join([
            f"- {acc['name']} (Category: {acc['category']}, Code: {acc['link']})"
            for acc in available_accounts[:10]
        ])
        
        prompt = f"""Analyze this transaction and suggest account classification:

Transaction:
- Description: {description}
- Explanation: {explanation}

Available Accounts:
{account_info}

Provide up to 2 suggestions in JSON format."""

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial accounting expert."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200,
            timeout=10
        )
        
        suggestions = json.loads(response.choices[0].message.content)
        
        # Match suggestions with available accounts
        valid_suggestions = []
        for suggestion in suggestions[:2]:  # Limit to top 2 suggestions
            matching_accounts = [acc for acc in available_accounts 
                               if acc['name'].lower() == suggestion['account_name'].lower()]
            if matching_accounts:
                valid_suggestions.append({
                    **suggestion,
                    'account': matching_accounts[0]
                })
        
        return valid_suggestions
        
    except Exception as e:
        logger.error(f"Error in account prediction: {str(e)}")
        return []

def generate_financial_advice(transactions, accounts):
    """Generate comprehensive financial advice based on transaction patterns."""
    try:
        transaction_summary = "\n".join([
            f"- Amount: ${t['amount']}, Description: {t['description']}, "
            f"Account: {t['account_name'] if 'account_name' in t else 'Uncategorized'}"
            for t in transactions[:10]
        ])
        
        account_summary = "\n".join([
            f"- {acc['name']}: ${acc.get('balance', 0):.2f} ({acc['category']})"
            for acc in accounts
        ])
        
        prompt = f"""Analyze these financial transactions and account balances to provide insights:

Transaction History:
{transaction_summary}

Account Balances:
{account_summary}

Instructions:
1. Analyze patterns and trends
2. Evaluate financial health
3. Provide actionable recommendations
4. Consider risk factors

Format response as JSON with structure:
{{
    "key_insights": [
        {{
            "category": "string",
            "finding": "string",
            "impact_level": "high|medium|low"
        }}
    ],
    "recommendations": [
        {{
            "action": "string",
            "priority": "high|medium|low",
            "timeline": "short|medium|long"
        }}
    ]
}}"""

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert financial advisor."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return json.loads(response.choices[0].message.content)
            
    except Exception as e:
        logger.error(f"Error generating financial advice: {str(e)}")
        return {
            "error": "Failed to generate financial advice",
            "details": str(e)
        }

def forecast_expenses(transactions, forecast_months=12):
    """Generate expense forecasts based on historical patterns."""
    try:
        transaction_summary = "\n".join([
            f"- Amount: ${t['amount']}, Description: {t['description']}, "
            f"Date: {t.get('date', 'N/A')}"
            for t in transactions[:50]
        ])
        
        prompt = f"""Analyze these transactions to generate expense forecasts:

Transaction History:
{transaction_summary}

Instructions:
1. Analyze historical patterns
2. Generate {forecast_months}-month forecast
3. Include confidence metrics
4. Consider seasonal factors

Format response as JSON with structure:
{{
    "monthly_forecasts": [
        {{
            "month": "YYYY-MM",
            "amount": float,
            "confidence": float
        }}
    ],
    "confidence_metrics": {{
        "overall_confidence": float,
        "reliability_score": float
    }}
}}"""

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert financial analyst."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1000
        )
        
        forecast = json.loads(response.choices[0].message.content)
        forecast["generated_at"] = datetime.utcnow().isoformat()
        return forecast
            
    except Exception as e:
        logger.error(f"Error generating forecast: {str(e)}")
        return {
            "error": "Failed to generate forecast",
            "details": str(e)
        }