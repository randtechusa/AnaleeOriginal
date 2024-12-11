import openai
import logging
import json
import os
import statistics
from datetime import datetime, timedelta
from typing import List, Dict, Union, Any

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
    patterns = {
        "field_correlations": [],
        "pattern_confidence": 0.0,
        "identified_relationships": [],
        "anomaly_indicators": []
    }
    
    try:
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
                
    except Exception as e:
        logger.error(f"Error in cross-field pattern analysis: {str(e)}")
        patterns["error"] = str(e)
    
    return patterns

def analyze_temporal_patterns(transactions, time_window_days=30):
    """
    Analyze temporal patterns in transaction data to identify trends and cyclical behavior.
    
    Args:
        transactions: List of transaction objects
        time_window_days: Number of days to consider for each analysis window
    
    Returns:
        Dictionary containing temporal pattern analysis results
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
                
    except Exception as e:
        logger.error(f"Error in temporal pattern analysis: {str(e)}")
        temporal_patterns["error"] = str(e)
    
    return temporal_patterns

def detect_transaction_anomalies(transactions, historical_data=None, sensitivity_threshold=0.7):
    """
    Detect anomalies in transactions using AI analysis of Description and Explanation fields.
    
    Args:
        transactions: List of current transactions to analyze
        historical_data: Optional historical transaction data for baseline comparison
        sensitivity_threshold: Threshold for anomaly detection sensitivity (0.0 to 1.0)
        
    Returns:
        Dictionary containing detected anomalies and analysis results
    """
    try:
        # Set timeout for API calls
        client = openai.OpenAI(timeout=30.0)
        
        # Analyze only essential patterns first
        field_patterns = analyze_cross_field_patterns(transactions[:50])  # Limit initial analysis
        temporal_analysis = analyze_temporal_patterns(transactions[:50])
        
        # Format transaction data with limits
        transaction_text = "\n".join([
            f"Transaction {idx + 1}:\n"
            f"- Amount: ${t.amount}\n"
            f"- Description: {t.description}\n"
            f"- Explanation: {t.explanation or 'No explanation provided'}\n"
            f"- Date: {t.date.strftime('%Y-%m-%d')}\n"
            f"- Account: {t.account.name if t.account else 'Uncategorized'}\n"
            f"- Category: {t.account.category if t.account else 'Unknown'}"
            for idx, t in enumerate(transactions[:50])  # Limit to recent transactions
        ])

        # Format historical data if available (with limits)
        historical_context = ""
        if historical_data:
            historical_summary = analyze_historical_patterns(historical_data[:100])  # Limit historical data
            historical_context = f"\nHistorical Context:\n{historical_summary['summary']}"

        prompt = f"""Analyze transaction patterns and detect anomalies (brief analysis):

Key Patterns:
{json.dumps(field_patterns, indent=2)}

Recent Transactions:
{transaction_text}
{historical_context}

Instructions:
1. Focus on most significant patterns
2. Use sensitivity threshold of {sensitivity_threshold}
3. Provide key anomalies and risks
4. Keep analysis concise

Provide analysis in JSON format."""

        # Make API call with timeout
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a financial analyst. Provide brief, focused analysis."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=500,  # Reduced token limit
                timeout=20  # Shorter timeout
            )
            
            # Parse and enhance the analysis
            analysis = json.loads(response.choices[0].message.content)
            
        except Exception as api_error:
            logger.error(f"API call error: {str(api_error)}")
            return {
                "error": "Failed to analyze transactions",
                "details": str(api_error)
            }
        
        # Add pattern-specific insights
        if field_patterns.get("identified_relationships"):
            analysis["pattern_insights"] = analysis.get("pattern_insights", {})
            analysis["pattern_insights"]["field_relationships"] = field_patterns["identified_relationships"]
        
        if temporal_analysis.get("seasonal_patterns"):
            if "pattern_insights" not in analysis:
                analysis["pattern_insights"] = {}
            analysis["pattern_insights"]["temporal_patterns"] = temporal_analysis["seasonal_patterns"]

        return analysis

    except Exception as e:
        logger.error(f"Error detecting transaction anomalies: {str(e)}")
        return {
            "error": "Failed to analyze transactions for anomalies",
            "details": str(e)
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
        account_info = "\n".join([
            f"- {acc['name']} (Category: {acc['category']}, Code: {acc['link']})"
            for acc in available_accounts
        ])
        
        prompt = f"""Analyze this financial transaction and provide comprehensive account classification:

Transaction Details:
- Description: {description}
- Additional Context/Explanation: {explanation}

Available Chart of Accounts:
{account_info}

Instructions:
1. Analyze both transaction description and explanation
2. Consider account categories and accounting principles
3. Evaluate patterns and implications
4. Provide confidence scores and reasoning

Format response as JSON list with structure:
[
    {{
        "account_name": "suggested account name",
        "confidence": 0.95,
        "reasoning": "detailed explanation including principles"
    }}
]

Provide up to 3 suggestions, ranked by confidence."""

        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a financial accounting assistant helping to classify transactions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        suggestions = []
        
        if content.startswith('[') and content.endswith(']'):
            suggestions = json.loads(content)
            
        valid_suggestions = []
        for suggestion in suggestions:
            matching_accounts = [acc for acc in available_accounts 
                              if acc['name'].lower() == suggestion['account_name'].lower()]
            if matching_accounts:
                valid_suggestions.append({
                    **suggestion,
                    'account': matching_accounts[0]
                })
        
        return valid_suggestions[:3]
        
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