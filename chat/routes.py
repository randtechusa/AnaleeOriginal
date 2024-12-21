"""
Financial AI Assistant Chat Routes
This module handles all chat-related functionality including message processing,
context management, and financial insights generation.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models import db, Transaction, Account
from ai_insights import FinancialInsightsGenerator
from nlp_utils import get_openai_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create blueprint
chat = Blueprint('chat', __name__)

@chat.route('/chat')
@login_required
def chat_interface():
    """Render the chat interface."""
    try:
        # Get unanalyzed transactions count
        unanalyzed_count = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            or_(
                Transaction.account_id.is_(None),
                Transaction.explanation.is_(None)
            )
        ).count()

        logger.info(f"Found {unanalyzed_count} unanalyzed transactions for user {current_user.id}")
        return render_template('financial_chat.html', unanalyzed_count=unanalyzed_count)
    except Exception as e:
        logger.error(f"Error loading chat interface: {str(e)}")
        return render_template('financial_chat.html', error="Error loading transaction data")

@chat.route('/chat/send', methods=['POST'])
@login_required
def send_message():
    """Process incoming chat messages and generate responses with financial context."""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()

        if not message:
            return jsonify({
                'success': False,
                'error': 'Empty message'
            })

        # Get OpenAI client
        client = get_openai_client()
        if not client:
            logger.error("Failed to initialize OpenAI client")
            return jsonify({
                'success': False,
                'error': 'AI service temporarily unavailable'
            })

        # Get user's financial context
        context = get_financial_context(current_user.id)

        # Generate AI response with context
        try:
            response = generate_ai_response(client, message, context)
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            response = "I apologize, but I'm having trouble analyzing your request right now. Please try again in a moment."

        return jsonify({
            'success': True,
            'response': response,
            'context_update': context
        })

    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        })

@chat.route('/chat/history')
@login_required
def get_chat_history():
    """Retrieve chat history for the current user."""
    try:
        # For now, return empty history as we haven't implemented persistence
        return jsonify({
            'success': True,
            'history': []
        })
    except Exception as e:
        logger.error(f"Error retrieving chat history: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error retrieving chat history'
        })

@chat.route('/chat/context')
@login_required
def get_context():
    """Get current financial context for the chat."""
    try:
        context = get_financial_context(current_user.id)
        unanalyzed_count = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            or_(
                Transaction.account_id.is_(None),
                Transaction.explanation.is_(None)
            )
        ).count()

        context['unanalyzed_count'] = unanalyzed_count

        return jsonify({
            'success': True,
            'context': context
        })
    except Exception as e:
        logger.error(f"Error retrieving financial context: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error retrieving financial context'
        })

def get_financial_context(user_id: int) -> Dict:
    """
    Get current financial context including recent transactions,
    monthly summary, and key metrics.
    """
    try:
        # Get current month's transactions
        start_date = datetime.now().replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)

        transactions = Transaction.query.filter(
            Transaction.user_id == user_id,
            Transaction.date.between(start_date, end_date)
        ).order_by(desc(Transaction.date)).all()

        # Calculate monthly totals
        income = sum(t.amount for t in transactions if t.amount > 0)
        expenses = abs(sum(t.amount for t in transactions if t.amount < 0))
        balance = income - expenses

        # Get recent transactions
        recent = Transaction.query.filter_by(user_id=user_id)\
            .order_by(desc(Transaction.date))\
            .limit(5)\
            .all()

        recent_transactions = [{
            'date': tx.date.strftime('%Y-%m-%d'),
            'description': tx.description,
            'amount': float(tx.amount),
            'category': tx.account.category if tx.account else 'Uncategorized',
            'analyzed': bool(tx.account_id and tx.explanation)
        } for tx in recent]

        return {
            'income': float(income),
            'expenses': float(expenses),
            'balance': float(balance),
            'recent_transactions': recent_transactions,
            'total_transactions': len(transactions)
        }

    except Exception as e:
        logger.error(f"Error getting financial context: {str(e)}")
        return {
            'income': 0,
            'expenses': 0,
            'balance': 0,
            'recent_transactions': [],
            'total_transactions': 0
        }

def generate_ai_response(client, message: str, context: Dict) -> str:
    """Generate AI response with financial context."""
    try:
        # Create prompt with context
        prompt = f"""As a financial AI assistant, help the user with their query. Here's the current context:

Monthly Summary:
- Income: ${context['income']:,.2f}
- Expenses: ${context['expenses']:,.2f}
- Balance: ${context['balance']:,.2f}
- Unanalyzed Transactions: {context.get('unanalyzed_count', 0)}

Recent Transactions:
{format_transactions_for_prompt(context['recent_transactions'])}

User Query: {message}

Provide a helpful, concise response focusing on their financial situation."""

        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful financial assistant focused on providing clear, actionable advice based on the user's financial data."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Error generating AI response: {str(e)}")
        return "I apologize, but I'm having trouble generating a response right now. Please try again in a moment."

def format_transactions_for_prompt(transactions: List[Dict]) -> str:
    """Format recent transactions for the AI prompt."""
    return "\n".join([
        f"- {tx['date']}: {tx['description']} (${tx['amount']:,.2f}) {'[Unanalyzed]' if not tx.get('analyzed') else ''}"
        for tx in transactions
    ])

def update_context_if_needed(message: str, response: str) -> Optional[Dict]:
    """Update financial context if the conversation requires it."""
    # For now, always return None as we're not implementing
    # context updates in this version
    return None