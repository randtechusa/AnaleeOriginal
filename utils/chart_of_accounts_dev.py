import logging
import openpyxl
from typing import List, Dict, Optional, Tuple
import os
import pandas as pd

logger = logging.getLogger(__name__)

class ChartOfAccountsLoader:
    """Enhanced Chart of Accounts loader with improved error handling and validation"""
    
    def __init__(self):
        self.required_columns = {'Link', 'Name', 'Category', 'Sub Category', 'Account Code'}
        self.file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Chart of Accounts.xlsx')
        
    def validate_headers(self, headers: List[str]) -> Tuple[bool, Optional[str]]:
        """Validate that all required columns are present"""
        headers_set = set(headers)
        missing = self.required_columns - headers_set
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"
        return True, None
        
    def process_row(self, row: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Process a single row of data with enhanced validation"""
        try:
            account = {
                'link': str(row.get('Link', '')).strip(),
                'name': str(row.get('Name', '')).strip(),
                'category': str(row.get('Category', '')).strip(),
                'sub_category': str(row.get('Sub Category', '')).strip(),
                'account_code': str(row.get('Account Code', '')).strip()
            }
            
            # Skip empty rows
            if not any(account.values()):
                return None
                
            # Validate required fields
            if not account['link'] or not account['name']:
                logger.warning(f"Invalid row: missing link or name - {account}")
                return None
            
            # Special handling for bank accounts (ca.810)
            if account['link'].lower().startswith('ca.810'):
                account['category'] = 'Assets'
                account['sub_category'] = 'Bank Accounts'
                logger.info(f"Processed bank account: {account['link']} - {account['name']}")
            
            return account
            
        except Exception as e:
            logger.error(f"Error processing row: {e}")
            return None
            
    def load_accounts(self) -> List[Dict[str, str]]:
        """Load and process the Chart of Accounts"""
        try:
            logger.info(f"Loading Chart of Accounts from: {self.file_path}")
            
            # Try openpyxl first
            try:
                workbook = openpyxl.load_workbook(self.file_path, data_only=True)
                sheet = workbook.active
                
                # Get headers
                headers = [str(cell.value).strip() if cell.value else '' for cell in sheet[1]]
                valid, error = self.validate_headers(headers)
                if not valid:
                    raise ValueError(error)
                
                # Process rows
                raw_data = []
                for row in sheet.iter_rows(min_row=2):
                    row_data = {}
                    for idx, header in enumerate(headers):
                        value = row[idx].value
                        if value is not None:
                            row_data[header] = str(value).strip()
                    raw_data.append(row_data)
                    
            except Exception as e:
                logger.warning(f"Openpyxl read failed: {e}, trying pandas")
                
                # Fallback to pandas
                df = pd.read_excel(self.file_path)
                headers = list(df.columns)
                valid, error = self.validate_headers(headers)
                if not valid:
                    raise ValueError(error)
                
                raw_data = df.fillna('').astype(str).apply(lambda x: x.str.strip()).to_dict('records')
            
            # Process all rows
            accounts = []
            bank_accounts = []
            
            for row in raw_data:
                account = self.process_row(row)
                if account:
                    accounts.append(account)
                    if account['link'].lower().startswith('ca.810'):
                        bank_accounts.append(account)
            
            # Log results
            logger.info(f"Successfully loaded {len(accounts)} accounts")
            logger.info(f"Found {len(bank_accounts)} bank accounts")
            
            return accounts
            
        except Exception as e:
            logger.error(f"Failed to load Chart of Accounts: {e}")
            logger.exception("Full traceback:")
            return []

def load_default_chart_of_accounts() -> List[Dict]:
    """Wrapper function to maintain compatibility with existing code"""
    loader = ChartOfAccountsLoader()
    return loader.load_accounts()
