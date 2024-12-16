import logging
import openpyxl
from typing import List, Dict
import os
import pandas as pd

logger = logging.getLogger(__name__)

def load_default_chart_of_accounts() -> List[Dict]:
    """Load the default Chart of Accounts from Excel file"""
    try:
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Chart of Accounts.xlsx')
        
        # Try reading with pandas first
        try:
            df = pd.read_excel(file_path)
            # Convert DataFrame to list of dicts for processing
            raw_data = df.to_dict('records')
            logger.info(f"Successfully read Excel file using pandas with {len(raw_data)} rows")
        except Exception as pandas_error:
            logger.warning(f"Failed to read with pandas: {str(pandas_error)}. Falling back to openpyxl.")
            # Fallback to openpyxl
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            worksheet = workbook.active
            
            # Get headers
            headers = [cell.value.strip() if cell.value else '' for cell in worksheet[1]]
            
            # Convert worksheet to list of dicts
            raw_data = []
            for row in worksheet.iter_rows(min_row=2):
                row_data = {}
                for idx, cell in enumerate(row):
                    if idx < len(headers):
                        row_data[headers[idx]] = cell.value
                raw_data.append(row_data)

        # Process the data
        accounts = []
        for row in raw_data:
            try:
                # Clean and validate the data
                account = {
                    'link': str(row.get('Link', '')).strip(),
                    'name': str(row.get('Name', '')).strip(),
                    'category': str(row.get('Category', '')).strip(),
                    'sub_category': str(row.get('Sub Category', '')).strip(),
                    'account_code': str(row.get('Account Code', '')).strip()
                }

                # Skip empty rows
                if not any(account.values()):
                    continue

                # Validate required fields
                if not all([account['link'], account['name']]):
                    logger.warning(f"Skipping row with missing required fields: {account}")
                    continue

                # Special handling for bank accounts (ca.810)
                if account['link'].startswith('ca.810'):
                    account['category'] = 'Assets'
                    account['sub_category'] = 'Bank Accounts'
                    logger.info(f"Found bank account: {account['link']} - {account['name']}")
                
                # Set default category if missing
                if not account['category']:
                    if account['link'].startswith('1'):
                        account['category'] = 'Assets'
                    elif account['link'].startswith('2'):
                        account['category'] = 'Liabilities'
                    elif account['link'].startswith('3'):
                        account['category'] = 'Equity'
                    elif account['link'].startswith('4'):
                        account['category'] = 'Income'
                    elif account['link'].startswith('5'):
                        account['category'] = 'Expenses'

                accounts.append(account)
                logger.info(f"Processed account: {account['link']} - {account['name']}")

            except Exception as row_error:
                logger.error(f"Error processing row: {str(row_error)}")
                continue

        # Validate the final account list
        bank_accounts = [acc for acc in accounts if acc['link'].startswith('ca.810')]
        logger.info(f"Total accounts loaded: {len(accounts)}")
        logger.info(f"Bank accounts found: {len(bank_accounts)}")
        
        if not bank_accounts:
            logger.warning("No bank accounts (ca.810.xxx) found in Chart of Accounts")
        else:
            logger.info("Bank accounts found:")
            for bank_acc in bank_accounts:
                logger.info(f"  - {bank_acc['link']}: {bank_acc['name']}")

        return accounts

    except Exception as e:
        logger.error(f"Error loading Chart of Accounts: {str(e)}")
        logger.exception("Full error traceback:")
        return []
