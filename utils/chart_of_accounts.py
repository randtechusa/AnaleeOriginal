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
        logger.info(f"Attempting to read Chart of Accounts from: {file_path}")
        
        try:
            # Try reading with openpyxl first as it's more reliable for structure
            workbook = openpyxl.load_workbook(file_path, data_only=True)
            worksheet = workbook.active
            
            # Get headers and validate required columns
            headers = []
            required_columns = {'Link', 'Name', 'Category', 'Sub Category', 'Account Code'}
            for cell in worksheet[1]:
                header = cell.value.strip() if cell.value else ''
                headers.append(header)
            
            # Validate all required columns are present
            missing_columns = required_columns - set(headers)
            if missing_columns:
                logger.error(f"Missing required columns in Excel file: {missing_columns}")
                raise ValueError(f"Excel file missing required columns: {missing_columns}")
            
            # Convert worksheet to list of dicts with careful type handling
            raw_data = []
            for row in worksheet.iter_rows(min_row=2):
                row_data = {}
                for idx, cell in enumerate(headers):
                    # Handle different cell types appropriately
                    value = row[idx].value
                    if value is not None:
                        if isinstance(value, (int, float)):
                            value = str(value)
                        row_data[cell] = str(value).strip()
                    else:
                        row_data[cell] = ''
                raw_data.append(row_data)
                
            logger.info(f"Successfully read {len(raw_data)} rows from Excel file")
            
        except Exception as openpyxl_error:
            logger.warning(f"Failed to read with openpyxl: {str(openpyxl_error)}. Trying pandas as fallback.")
            try:
                df = pd.read_excel(file_path)
                # Ensure all required columns exist
                missing_columns = required_columns - set(df.columns)
                if missing_columns:
                    raise ValueError(f"Excel file missing required columns: {missing_columns}")
                    
                # Convert DataFrame to list of dicts with proper string handling
                raw_data = []
                for _, row in df.iterrows():
                    row_dict = {}
                    for col in df.columns:
                        value = row[col]
                        if pd.notna(value):  # Check if value is not NaN
                            if isinstance(value, (int, float)):
                                value = str(value)
                            row_dict[col] = str(value).strip()
                        else:
                            row_dict[col] = ''
                    raw_data.append(row_dict)
                    
                logger.info(f"Successfully read {len(raw_data)} rows using pandas")
            except Exception as pandas_error:
                logger.error(f"Failed to read Excel file with both methods: {str(pandas_error)}")
                raise

        # Process the data
        accounts = []
        bank_accounts_found = False
        
        for row in raw_data:
            try:
                # Clean and validate the data with detailed logging
                account = {
                    'link': str(row.get('Link', '')).strip(),
                    'name': str(row.get('Name', '')).strip(),
                    'category': str(row.get('Category', '')).strip(),
                    'sub_category': str(row.get('Sub Category', '')).strip(),
                    'account_code': str(row.get('Account Code', '')).strip()
                }
                
                # Skip empty rows
                if not any(account.values()):
                    logger.debug("Skipping empty row")
                    continue
                
                # Log raw data for debugging
                logger.debug(f"Processing row: {row}")
                
                # Validate required fields
                if not account['link'] or not account['name']:
                    logger.warning(f"Skipping row with missing required fields: Link={account['link']}, Name={account['name']}")
                    continue
                
                # Special handling for bank accounts (ca.810)
                if account['link'].lower().startswith('ca.810'):
                    bank_accounts_found = True
                    account['category'] = 'Assets'
                    account['sub_category'] = 'Bank Accounts'
                    logger.info(f"Found bank account: {account['link']} - {account['name']}")
                else:
                    # Set default category if missing based on link pattern
                    if not account['category']:
                        first_char = account['link'][0] if account['link'] else ''
                        category_map = {
                            '1': 'Assets',
                            '2': 'Liabilities',
                            '3': 'Equity',
                            '4': 'Income',
                            '5': 'Expenses'
                        }
                        if first_char in category_map:
                            account['category'] = category_map[first_char]
                            logger.info(f"Assigned default category {account['category']} for account {account['link']}")
                
                # Ensure sub_category is never None
                if not account['sub_category']:
                    account['sub_category'] = 'Other'
                
                # Validate the final account structure
                required_fields = ['link', 'name', 'category']
                if all(account.get(field) for field in required_fields):
                    accounts.append(account)
                    logger.info(f"Successfully processed account: {account['link']} - {account['name']} ({account['category']})")
                else:
                    logger.warning(f"Skipping invalid account: {account}")
                
            except Exception as row_error:
                logger.error(f"Error processing row {row}: {str(row_error)}")
                continue
        
        if not bank_accounts_found:
            logger.warning("No bank accounts (ca.810.xxx) found in the Chart of Accounts")

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
