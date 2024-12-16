import logging
import openpyxl
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

def load_default_chart_of_accounts() -> List[Dict]:
    """Load the default Chart of Accounts from Excel file"""
    try:
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Chart of Accounts.xlsx')
        workbook = openpyxl.load_workbook(file_path, data_only=True)
        worksheet = workbook.active

        # Get header row to identify columns
        header_row = []
        for cell in worksheet[1]:
            value = cell.value.strip() if cell.value else ''
            header_row.append(value)

        required_columns = ['Link', 'Name', 'Category', 'Sub Category', 'Account Code']
        for col in required_columns:
            if col not in header_row:
                logger.error(f"Required column '{col}' not found in Excel file")
                raise ValueError(f"Missing required column: {col}")

        column_indices = {
            'link': header_row.index('Link'),
            'name': header_row.index('Name'),
            'category': header_row.index('Category'),
            'sub_category': header_row.index('Sub Category'),
            'account_code': header_row.index('Account Code')
        }

        accounts = []
        for row_idx in range(2, worksheet.max_row + 1):
            try:
                row = worksheet[row_idx]
                account = {
                    'link': str(row[column_indices['link']].value).strip() if row[column_indices['link']].value else '',
                    'name': str(row[column_indices['name']].value).strip() if row[column_indices['name']].value else '',
                    'category': str(row[column_indices['category']].value).strip() if row[column_indices['category']].value else '',
                    'sub_category': str(row[column_indices['sub_category']].value).strip() if row[column_indices['sub_category']].value else '',
                    'account_code': str(row[column_indices['account_code']].value).strip() if row[column_indices['account_code']].value else ''
                }
                
                # Skip empty rows
                if not any(account.values()):
                    continue

                # Enhanced validation
                if all(account[field] for field in ['link', 'name', 'category']):
                    # Special handling for bank accounts
                    if account['link'].startswith('ca.810'):
                        account['category'] = 'Assets'
                        account['sub_category'] = 'Bank Accounts'
                        logger.info(f"Found bank account: {account['link']} - {account['name']}")
                    
                    logger.info(f"Processing account: {account['link']} - {account['name']}")
                    accounts.append(account)
                else:
                    logger.warning(f"Skipping incomplete account record: {account}")
                    
            except Exception as row_error:
                logger.error(f"Error processing row {row_idx}: {str(row_error)}")
                continue

        logger.info(f"Successfully loaded {len(accounts)} accounts from Chart of Accounts")
        if not any(acc['link'].startswith('ca.810') for acc in accounts):
            logger.warning("No bank accounts (ca.810.xxx) found in Chart of Accounts")
            
        return accounts

    except Exception as e:
        logger.error(f"Error loading Chart of Accounts: {str(e)}")
        return []
