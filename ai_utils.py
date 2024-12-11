import openai
import logging
import json
import os
from datetime import datetime
from typing import List, Dict

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

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

def analyze_historical_patterns(historical_data):
    """
    Analyze historical transaction data to identify patterns and establish baselines.
    Includes advanced pattern recognition for seasonal trends and growth analysis.
    
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
        
        # Analyze patterns for each category
        category_patterns = {}
        for category, transactions in category_data.items():
            # Basic statistics
            amounts = [t.amount for t in transactions]
            avg_amount = sum(amounts) / len(amounts) if amounts else 0
            max_amount = max(amounts) if amounts else 0
            min_amount = min(amounts) if amounts else 0
            
            # Temporal analysis
            dates = sorted([t.date for t in transactions])
            if len(dates) > 1:
                date_diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                avg_frequency = sum(date_diffs) / len(date_diffs) if date_diffs else 0
                
                # Calculate growth rate
                first_month = dates[0].strftime('%Y-%m')
                last_month = dates[-1].strftime('%Y-%m')
                if first_month in monthly_data and last_month in monthly_data:
                    first_month_avg = sum(t.amount for t in monthly_data[first_month]) / len(monthly_data[first_month])
                    last_month_avg = sum(t.amount for t in monthly_data[last_month]) / len(monthly_data[last_month])
                    months_diff = (dates[-1].year - dates[0].year) * 12 + dates[-1].month - dates[0].month
                    growth_rate = ((last_month_avg / first_month_avg) ** (1/months_diff) - 1) * 100 if months_diff > 0 and first_month_avg != 0 else 0
                else:
                    growth_rate = 0
            else:
                avg_frequency = 0
                growth_rate = 0
            
            # Seasonal pattern detection
            seasonal_patterns = []
            if len(monthly_data) >= 12:
                month_averages = {}
                for month_key, month_transactions in monthly_data.items():
                    month = datetime.strptime(month_key, '%Y-%m').month
                    if month not in month_averages:
                        month_averages[month] = []
                    month_transactions_in_category = [t for t in month_transactions if t.account and t.account.category == category]
                    if month_transactions_in_category:
                        month_averages[month].append(sum(t.amount for t in month_transactions_in_category) / len(month_transactions_in_category))
                
                for month, averages in month_averages.items():
                    if len(averages) > 1:
                        month_avg = sum(averages) / len(averages)
                        overall_avg = avg_amount
                        if overall_avg != 0:
                            seasonal_factor = (month_avg / overall_avg - 1) * 100
                            if abs(seasonal_factor) > 15:  # Significant seasonal variation threshold
                                seasonal_patterns.append({
                                    'month': datetime.strptime(str(month), '%m').strftime('%B'),
                                    'variation': seasonal_factor,
                                    'significance': 'high' if abs(seasonal_factor) > 30 else 'medium'
                                })
            
            category_patterns[category] = {
                'statistics': {
                    'average_amount': avg_amount,
                    'amount_range': {'min': min_amount, 'max': max_amount},
                    'transaction_count': len(transactions),
                    'average_frequency': avg_frequency
                },
                'trends': {
                    'growth_rate': growth_rate,
                    'seasonal_patterns': seasonal_patterns
                },
                'significance_score': min(100, (len(transactions) * abs(growth_rate) / 100) if growth_rate else len(transactions))
            }
        
        # Generate pattern summary
        pattern_summary = []
        for category, analysis in category_patterns.items():
            summary = [
                f"Category: {category}",
                f"- Average Amount: ${analysis['statistics']['average_amount']:.2f}",
                f"- Amount Range: ${analysis['statistics']['amount_range']['min']:.2f} to ${analysis['statistics']['amount_range']['max']:.2f}",
                f"- Transaction Count: {analysis['statistics']['transaction_count']}",
                f"- Average Frequency: {analysis['statistics']['average_frequency']:.1f} days",
                f"- Growth Rate: {analysis['trends']['growth_rate']:.1f}% per month"
            ]
            
            if analysis['trends']['seasonal_patterns']:
                summary.append("- Seasonal Patterns:")
                for pattern in analysis['trends']['seasonal_patterns']:
                    summary.append(f"  * {pattern['month']}: {pattern['variation']:.1f}% variation ({pattern['significance']} significance)")
            
            pattern_summary.append("\n".join(summary))
        
        return {
            'summary': "\n\n".join(pattern_summary),
            'detailed_analysis': category_patterns
        }
        
    except Exception as e:
        logger.error(f"Error analyzing historical patterns: {str(e)}")
        return {
            'summary': "Historical pattern analysis unavailable",
            'detailed_analysis': {}
        }

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
            f"- Account: {t.account.name if t.account else 'Uncategorized'}\n"
            f"- Category: {t.account.category if t.account else 'Unknown'}"
            for idx, t in enumerate(transactions)
        ])

        # Format historical data if available
        historical_context = ""
        if historical_data:
            historical_summary = analyze_historical_patterns(historical_data)
            historical_context = f"\nHistorical Context:\n{historical_summary}"

        prompt = f"""Perform comprehensive anomaly detection and pattern analysis on these transactions. Consider:

1. Amount Analysis:
   - Statistical outliers in transaction amounts
   - Unusual changes in regular payment patterns
   - Category-specific amount deviations
   - Seasonal variations and cyclical patterns
   - Year-over-year comparisons where applicable

2. Description & Explanation Analysis:
   - Natural language processing of descriptions
   - Semantic consistency between fields
   - Category alignment analysis
   - Potential duplicate transactions
   - Missing or incomplete information
   - Keyword pattern analysis

3. Temporal Pattern Analysis:
   - Transaction timing anomalies
   - Frequency pattern deviations
   - Seasonal trend analysis
   - Day-of-week patterns
   - Time-based correlations

4. Category & Account Analysis:
   - Cross-category pattern violations
   - Account usage consistency
   - Category distribution anomalies
   - Related transaction patterns
   - Historical category alignment

5. Contextual Analysis:
   - Business rule violations
   - Industry-specific patterns
   - Regulatory compliance indicators
   - Internal control considerations
   - Risk pattern identification

Transactions to analyze:
{transaction_text}
{historical_context}

Provide detailed analysis in this JSON structure:
{{
    "anomalies": [
        {{
            "transaction_index": <index>,
            "anomaly_type": "amount|description|timing|account|pattern",
            "confidence": <float between 0-1>,
            "reason": "detailed explanation",
            "severity": "high|medium|low",
            "impact_area": "financial|operational|compliance",
            "risk_level": "high|medium|low",
            "recommendation": "suggested action",
            "supporting_evidence": ["list of specific evidence points"],
            "related_transactions": [<indices of related transactions>]
        }}
    ],
    "pattern_insights": {{
        "identified_patterns": ["string"],
        "unusual_deviations": ["string"],
        "category_patterns": [
            {{
                "category": "string",
                "pattern_type": "string",
                "significance": "high|medium|low",
                "description": "string"
            }}
        ],
        "temporal_patterns": [
            {{
                "pattern_type": "string",
                "timeframe": "string",
                "description": "string",
                "confidence": <float between 0-1>
            }}
        ]
    }},
    "risk_assessment": {{
        "overall_risk_level": "high|medium|low",
        "key_risk_factors": ["string"],
        "recommended_controls": ["string"]
    }}
}}"""

        # Make API call for anomaly detection
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert financial analyst specialized in detecting transaction anomalies and patterns. Focus on providing detailed, actionable insights while maintaining high accuracy. Format your response as valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more consistent analysis
            max_tokens=1000
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
            
            # Validate required fields
            required_fields = ['monthly_forecasts', 'forecast_factors', 'confidence_metrics', 'recommendations']
            missing_fields = [field for field in required_fields if field not in forecast]
            
            if missing_fields:
                logger.warning(f"Missing required fields in forecast: {missing_fields}")
                # Initialize missing fields with empty defaults
                for field in missing_fields:
                    if field == 'monthly_forecasts':
                        forecast[field] = []
                    elif field == 'forecast_factors':
                        forecast[field] = {"key_drivers": [], "risk_factors": [], "assumptions": []}
                    elif field == 'confidence_metrics':
                        forecast[field] = {"overall_confidence": 0, "variance_range": {"min": 0, "max": 0}, "reliability_score": 0}
                    elif field == 'recommendations':
                        forecast[field] = []

            # Add metadata about the forecast
            forecast["generated_at"] = datetime.utcnow().isoformat()
            forecast["forecast_period_months"] = forecast_months
            forecast["data_points_analyzed"] = len(transactions)
            
            logger.info("Successfully generated and validated forecast")
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
        logger.error(f"Error generating expense forecast: {str(e)}")
        return {
            "error": "Failed to generate expense forecast",
            "details": str(e),
            "monthly_forecasts": [],
            "forecast_factors": {"key_drivers": [], "risk_factors": [], "assumptions": []},
            "confidence_metrics": {"overall_confidence": 0, "variance_range": {"min": 0, "max": 0}, "reliability_score": 0},
            "recommendations": []
        }