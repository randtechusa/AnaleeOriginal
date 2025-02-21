
import asyncio
from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from icountant import ICountant

async def demo_icountant():
    # Sample available accounts
    available_accounts = [
        {'name': 'Sales Revenue', 'category': 'Revenue', 'id': 1},
        {'name': 'Office Supplies', 'category': 'Expense', 'id': 2},
        {'name': 'Consulting Income', 'category': 'Revenue', 'id': 3},
        {'name': 'Utilities', 'category': 'Expense', 'id': 4},
        {'name': 'Rent', 'category': 'Expense', 'id': 5}
    ]

    # Initialize iCountant
    agent = ICountant(available_accounts)

    # Test cases including edge cases and invalid data
    test_transactions = [
        # Valid transactions
        {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'amount': Decimal('1500.00'),
            'description': 'Client payment received - ABC Corp'
        },
        {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'amount': Decimal('-250.75'),
            'description': 'Office supplies purchase'
        },
        # Invalid transactions for testing error handling
        {
            'date': 'invalid-date',
            'amount': 'not-a-number',
            'description': ''
        },
        {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'amount': Decimal('0.00'),
            'description': 'Zero amount transaction'
        },
        # Missing required fields
        {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'description': 'Missing amount'
        }
    ]

    # Process each test transaction
    for transaction in test_transactions:
        print("\n" + "="*50)
        print(f"Testing transaction: {transaction}")
        
        # Process transaction
        success, message, insights = agent.process_transaction(transaction)
        print(f"Success: {success}")
        print(f"Message: {message}")
        if success:
            print("Insights:", insights)

if __name__ == "__main__":
    asyncio.run(demo_icountant())
