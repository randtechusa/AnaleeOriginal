import logging
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy import func
from collections import defaultdict

logger = logging.getLogger(__name__)

class FinancialRiskAnalyzer:
    """AI-powered financial risk analyzer"""
    
    def __init__(self):
        self.risk_thresholds = {
            'liquidity_ratio': {'low': 2.0, 'medium': 1.5, 'high': 1.0},
            'debt_ratio': {'low': 0.4, 'medium': 0.6, 'high': 0.8},
            'profit_margin': {'low': 0.15, 'medium': 0.10, 'high': 0.05},
            'cash_flow_coverage': {'low': 1.5, 'medium': 1.2, 'high': 1.0}
        }
    
    def assess_financial_risk(self, transactions: List[Any], accounts: List[Any]) -> Dict:
        """Perform comprehensive financial risk assessment"""
        try:
            # Calculate key financial indicators
            indicators = self._calculate_financial_indicators(transactions, accounts)
            
            # Determine risk levels for each indicator
            risk_levels = self._determine_risk_levels(indicators)
            
            # Calculate overall risk score (0-100, higher means more risk)
            risk_score = self._calculate_risk_score(risk_levels)
            
            # Generate risk level category
            risk_level = self._categorize_risk_level(risk_score)
            
            # Generate findings and recommendations
            findings = self._generate_findings(indicators, risk_levels)
            recommendations = self._generate_recommendations(risk_levels)
            
            return {
                'risk_score': risk_score,
                'risk_level': risk_level,
                'findings': findings,
                'recommendations': recommendations,
                'indicators': self._format_indicators(indicators, risk_levels)
            }
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {str(e)}")
            raise
    
    def _calculate_financial_indicators(self, transactions: List[Any], accounts: List[Any]) -> Dict:
        """Calculate key financial indicators from transaction and account data"""
        try:
            # Get account balances by category
            balances = defaultdict(float)
            for account in accounts:
                balances[account.category] += sum(t.amount for t in account.transactions)
            
            # Calculate liquidity ratio (current assets / current liabilities)
            current_assets = balances.get('Current Assets', 0)
            current_liabilities = balances.get('Current Liabilities', 0)
            liquidity_ratio = current_assets / current_liabilities if current_liabilities else float('inf')
            
            # Calculate debt ratio (total liabilities / total assets)
            total_assets = sum(bal for cat, bal in balances.items() if 'Assets' in cat)
            total_liabilities = sum(bal for cat, bal in balances.items() if 'Liabilities' in cat)
            debt_ratio = total_liabilities / total_assets if total_assets else 0
            
            # Calculate profit margin
            revenue = sum(t.amount for t in transactions if t.amount > 0)
            expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
            profit_margin = (revenue - expenses) / revenue if revenue else 0
            
            # Calculate cash flow coverage
            operating_cash_flow = sum(t.amount for t in transactions 
                                   if t.date >= datetime.now() - timedelta(days=30))
            debt_obligations = balances.get('Current Liabilities', 0) / 12  # Monthly debt obligations
            cash_flow_coverage = operating_cash_flow / debt_obligations if debt_obligations else float('inf')
            
            return {
                'liquidity_ratio': liquidity_ratio,
                'debt_ratio': debt_ratio,
                'profit_margin': profit_margin,
                'cash_flow_coverage': cash_flow_coverage
            }
            
        except Exception as e:
            logger.error(f"Error calculating financial indicators: {str(e)}")
            raise
    
    def _determine_risk_levels(self, indicators: Dict) -> Dict:
        """Determine risk levels for each indicator"""
        risk_levels = {}
        
        for indicator, value in indicators.items():
            thresholds = self.risk_thresholds.get(indicator, {})
            
            if value >= thresholds.get('low', float('inf')):
                risk_levels[indicator] = 'low'
            elif value >= thresholds.get('medium', float('inf')):
                risk_levels[indicator] = 'medium'
            else:
                risk_levels[indicator] = 'high'
        
        return risk_levels
    
    def _calculate_risk_score(self, risk_levels: Dict) -> float:
        """Calculate overall risk score (0-100)"""
        risk_weights = {
            'low': 0.2,
            'medium': 0.5,
            'high': 1.0
        }
        
        total_weight = len(risk_levels)
        weighted_sum = sum(risk_weights[level] for level in risk_levels.values())
        
        return (weighted_sum / total_weight) * 100
    
    def _categorize_risk_level(self, risk_score: float) -> str:
        """Categorize overall risk level based on risk score"""
        if risk_score <= 30:
            return 'low'
        elif risk_score <= 70:
            return 'medium'
        else:
            return 'high'
    
    def _generate_findings(self, indicators: Dict, risk_levels: Dict) -> str:
        """Generate detailed findings based on indicators and risk levels"""
        findings = []
        
        if indicators['liquidity_ratio'] < self.risk_thresholds['liquidity_ratio']['medium']:
            findings.append("Liquidity ratio indicates potential short-term payment challenges.")
        
        if indicators['debt_ratio'] > self.risk_thresholds['debt_ratio']['medium']:
            findings.append("High debt ratio suggests increased financial leverage risk.")
        
        if indicators['profit_margin'] < self.risk_thresholds['profit_margin']['medium']:
            findings.append("Lower profit margins may impact long-term sustainability.")
        
        if indicators['cash_flow_coverage'] < self.risk_thresholds['cash_flow_coverage']['medium']:
            findings.append("Cash flow coverage indicates potential debt service challenges.")
        
        return " ".join(findings) if findings else "No significant risk factors identified."
    
    def _generate_recommendations(self, risk_levels: Dict) -> str:
        """Generate recommendations based on risk levels"""
        recommendations = []
        
        if risk_levels.get('liquidity_ratio') in ['medium', 'high']:
            recommendations.append("Consider improving working capital management.")
        
        if risk_levels.get('debt_ratio') in ['medium', 'high']:
            recommendations.append("Review debt structure and consider debt reduction strategies.")
        
        if risk_levels.get('profit_margin') in ['medium', 'high']:
            recommendations.append("Focus on cost optimization and revenue enhancement.")
        
        if risk_levels.get('cash_flow_coverage') in ['medium', 'high']:
            recommendations.append("Implement stronger cash flow management practices.")
        
        return " ".join(recommendations) if recommendations else "Maintain current financial management practices."
    
    def _format_indicators(self, indicators: Dict, risk_levels: Dict) -> List[Dict]:
        """Format indicators for storage and display"""
        formatted = []
        
        for name, value in indicators.items():
            threshold = self.risk_thresholds[name]['medium']
            is_breach = risk_levels[name] in ['medium', 'high']
            
            formatted.append({
                'name': name,
                'value': value,
                'threshold': threshold,
                'is_breach': is_breach
            })
        
        return formatted
