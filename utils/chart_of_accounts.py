import logging
import openpyxl
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

def load_default_chart_of_accounts() -> List[Dict]:
    """Load the default Chart of Accounts from Excel file"""
    try:
        file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Chart of Accounts.xlsx')
        workbook = openpyxl.load_workbook(file_path, read_only=True)
        worksheet = workbook.active
        
        accounts = []
        # Skip header row
        for row in list(worksheet.rows)[1:]:
            try:
                account = {
                    'link': str(row[0].value).strip() if row[0].value else '',
                    'name': str(row[1].value).strip() if row[1].value else '',
                    'category': str(row[2].value).strip() if row[2].value else '',
                    'sub_category': str(row[3].value).strip() if row[3].value else '',
                    'account_code': str(row[4].value).strip() if row[4].value else ''
                }
                
                # Only add if required fields are present
                if account['link'] and account['name'] and account['category']:
                    accounts.append(account)
            except Exception as row_error:
                logger.error(f"Error processing row: {str(row_error)}")
                continue
                
        return accounts
        
    except Exception as e:
        logger.error(f"Error loading Chart of Accounts: {str(e)}")
        return []
