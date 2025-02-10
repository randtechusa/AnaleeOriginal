"""Alert system for monitoring and detecting anomalies"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from models import Transaction, db, AlertConfiguration, AlertHistory, Account

class AlertSystem:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Configure logging with proper format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def _check_pattern_anomalies(self, config) -> List[Dict]:
        """Check for pattern-based anomalies in recent transactions"""
        try:
            recent_transactions = self._get_recent_transactions(config.user_id)
            return self._analyze_patterns(recent_transactions)
        except Exception as e:
            self.logger.error(f"Error checking pattern anomalies: {str(e)}")
            return []

    def _check_transaction_anomalies(self, config) -> List[Dict]:
        """Check for transaction amount anomalies"""
        try:
            recent_transactions = self._get_recent_transactions(config.user_id, days=30)
            return self._analyze_transactions(recent_transactions, config)
        except Exception as e:
            self.logger.error(f"Error checking transaction anomalies: {str(e)}")
            return []

    def _get_recent_transactions(self, user_id: int, days: int = 90) -> List[Transaction]:
        """Get recent transactions for analysis"""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        return Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.date >= cutoff_date
        ).order_by(Transaction.date).all()

    def _analyze_patterns(self, transactions: List[Transaction]) -> List[Dict]:
        """Analyze transactions for unusual patterns"""
        anomalies = []
        if len(transactions) >= 3:
            for i in range(2, len(transactions)):
                if self._is_unusual_pattern(transactions[i-2:i+1]):
                    anomalies.append(self._create_pattern_anomaly(transactions[i]))
        return anomalies

    def _analyze_transactions(self, transactions: List[Transaction], config) -> List[Dict]:
        """Analyze transactions for amount-based anomalies"""
        return [
            self._create_amount_anomaly(transaction, config)
            for transaction in transactions
            if abs(transaction.amount) > config.threshold_value
        ]

    def _is_unusual_pattern(self, transaction_window: List[Transaction]) -> bool:
        """Check if a transaction window contains an unusual pattern"""
        current, prev1, prev2 = [t.amount for t in transaction_window]
        return abs(current) > abs(prev1) * 3 and abs(current) > abs(prev2) * 3

    def _create_pattern_anomaly(self, transaction: Transaction) -> Dict:
        """Create a pattern-based anomaly record"""
        return {
            'type': 'pattern',
            'severity': 'medium',
            'message': 'Unusual transaction pattern detected',
            'transaction_id': transaction.id
        }

    def _create_amount_anomaly(self, transaction: Transaction, config) -> Dict:
        """Create an amount-based anomaly record"""
        severity = 'high' if abs(transaction.amount) > config.threshold_value * 1.5 else 'medium'
        return {
            'type': 'transaction',
            'severity': severity,
            'message': f'Large transaction detected: ${abs(transaction.amount):,.2f}',
            'transaction_id': transaction.id
        }
    
    def check_anomalies(self, user_id: int) -> List[Dict]:
        """
        Check for financial anomalies based on user configurations

        Args:
            user_id: ID of the user to check anomalies for

        Returns:
            List of detected anomalies
        """
        try:
            # Get active alert configurations
            configurations = AlertConfiguration.query.filter_by(
                user_id=user_id,
                is_active=True
            ).all()
            
            detected_anomalies = []
            
            for config in configurations:
                anomalies = self._process_alert_configuration(config)
                if anomalies:
                    detected_anomalies.extend(anomalies)
                    
            return detected_anomalies
            
        except Exception as e:
            self.logger.error(f"Error checking anomalies: {str(e)}")
            return []

    def _process_alert_configuration(self, config: AlertConfiguration) -> List[Dict]:
        """
        Process individual alert configuration

        Args:
            config: AlertConfiguration object to process

        Returns:
            List of anomalies detected for this configuration
        """
        try:
            if config.alert_type == 'transaction':
                return self._check_transaction_anomalies(config)
            elif config.alert_type == 'balance':
                return self._check_balance_anomalies(config)
            elif config.alert_type == 'pattern':
                return self._check_pattern_anomalies(config)
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error processing alert configuration {config.id}: {str(e)}")
            return []


    def _check_balance_anomalies(self, config: AlertConfiguration) -> List[Dict]:
        """Check for balance-based anomalies"""
        try:
            # Get account balances
            accounts = Account.query.filter_by(user_id=config.user_id).all()
            
            anomalies = []
            for account in accounts:
                balance = sum(t.amount for t in account.transactions)
                
                if config.threshold_type == 'amount' and abs(balance) > config.threshold_value:
                    anomalies.append({
                        'type': 'balance',
                        'severity': 'high' if abs(balance) > config.threshold_value * 1.5 else 'medium',
                        'message': f'Account balance threshold exceeded: {account.name}',
                        'account_id': account.id
                    })
                    
            return anomalies
            
        except Exception as e:
            self.logger.error(f"Error checking balance anomalies: {str(e)}")
            return []

    def create_alert(self, user_id: int, anomaly: Dict, config_id: int) -> Optional[AlertHistory]:
        """
        Create alert history entry for detected anomaly

        Args:
            user_id: ID of the user
            anomaly: Detected anomaly information
            config_id: ID of the alert configuration

        Returns:
            Created AlertHistory object or None if error
        """
        try:
            alert = AlertHistory(
                alert_config_id=config_id,
                user_id=user_id,
                alert_message=anomaly['message'],
                severity=anomaly['severity']
            )

            db.session.add(alert)
            db.session.commit()

            return alert

        except Exception as e:
            self.logger.error(f"Error creating alert: {str(e)}")
            db.session.rollback()
            return None

    def get_active_alerts(self, user_id: int) -> List[AlertHistory]:
        """Get list of active alerts for user"""
        try:
            return AlertHistory.query.filter(
                AlertHistory.user_id == user_id,
                AlertHistory.status != 'resolved'
            ).order_by(AlertHistory.created_at.desc()).all()
            
        except Exception as e:
            self.logger.error(f"Error getting active alerts: {str(e)}")
            return []

    def acknowledge_alert(self, alert_id: int, user_id: int) -> bool:
        """Mark alert as acknowledged"""
        try:
            alert = AlertHistory.query.filter_by(
                id=alert_id,
                user_id=user_id
            ).first()
            
            if alert:
                alert.status = 'acknowledged'
                alert.updated_at = datetime.utcnow()
                db.session.commit()
                return True
                
            return False
            
        except Exception as e:
            self.logger.error(f"Error acknowledging alert: {str(e)}")
            db.session.rollback()
            return False