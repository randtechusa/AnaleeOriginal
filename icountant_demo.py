from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from icountant import ICountant

def demo_icountant():
    # Sample available accounts
    available_accounts = [
        {'name': 'Sales Revenue', 'category': 'Revenue', 'id': 1},
        {'name': 'Office Supplies', 'category': 'Expense', 'id': 2},
        {'name': 'Consulting Income', 'category': 'Revenue', 'id': 3},
        {'name': 'Utilities', 'category': 'Expense', 'id': 4},
        {'name': 'Rent', 'category': 'Expense', 'id': 5}
    ]

    # Sample transactions to process
    sample_transactions = [
        {
            'date': datetime.now(),
            'amount': Decimal('1500.00'),
            'description': 'Client payment received - ABC Corp'
        },
        {
            'date': datetime.now(),
            'amount': Decimal('-250.75'),
            'description': 'Office supplies purchase'
        },
        # Add an invalid transaction to test error handling
        {
            'date': datetime.now(),
            'amount': 'invalid',
            'description': 'Invalid transaction'
        }
    ]

    # Initialize iCountant
    agent = ICountant(available_accounts)

    # Process each transaction
    for transaction in sample_transactions:
        print("\n" + "="*50)  # Visual separator

        # Get guidance message and transaction info
        message, transaction_info = await agent.process_transaction(transaction)
        print("ICountant says:", message)

        if transaction_info:  # Only proceed if transaction was valid
            # In a real application, this would be user input
            # For demo, we'll simulate user selecting the first applicable account
            selected_index = 0 if 'Revenue' in available_accounts[0]['category'] else 1

            # Complete the transaction
            success, result_message, completed_transaction = agent.complete_transaction(selected_index)
            print("\nResult:", result_message)

            if success:
                print("\nCompleted transaction:", completed_transaction)
        else:
            print("\nSkipping invalid transaction")

if __name__ == "__main__":
    demo_icountant()