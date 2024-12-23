"""
Bank statement validation module
Handles specific validation rules for bank statements
"""
import logging
import pandas as pd
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict

logger = logging.getLogger(__name__)

class BankStatementValidator:
    """Validates and processes bank statement uploads"""

    REQUIRED_COLUMNS = ['Date', 'Description', 'Amount']

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.processed_rows = 0
        self.total_rows = 0

    def validate_and_process(self, file, account_id: int, user_id: int) -> bool:
        """
        Validate and process the uploaded bank statement
        Returns True if successful, False otherwise
        """
        try:
            # Read file
            if file.filename.endswith('.xlsx'):
                df = pd.read_excel(file, engine='openpyxl')
            else:
                try:
                    df = pd.read_csv(file, encoding='utf-8')
                except UnicodeDecodeError:
                    file.seek(0)
                    df = pd.read_csv(file, encoding='latin1')

            # Validate structure
            if not self._validate_structure(df):
                return False

            # Process rows
            self.total_rows = len(df)
            success = self._process_rows(df, account_id, user_id)

            return success

        except Exception as e:
            logger.error(f"Error processing bank statement: {str(e)}")
            self.errors.append(f"Error processing file: {str(e)}")
            return False

    def _validate_structure(self, df: pd.DataFrame) -> bool:
        """Validate the basic structure of the uploaded file"""
        try:
            if df.empty:
                self.errors.append("The uploaded file is empty")
                return False

            # Check for required columns
            missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
            if missing_columns:
                self.errors.append(f"Missing required columns: {', '.join(missing_columns)}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating file structure: {str(e)}")
            self.errors.append(f"Error validating file structure: {str(e)}")
            return False

    def _process_rows(self, df: pd.DataFrame, account_id: int, user_id: int) -> bool:
        """Process each row of the bank statement"""
        try:
            for idx, row in df.iterrows():
                self.processed_rows += 1
                
                # Validate row data
                if not self._validate_row(row, idx + 2):  # Add 2 for header row and 0-based index
                    continue

            return len(self.errors) == 0

        except Exception as e:
            logger.error(f"Error processing rows: {str(e)}")
            self.errors.append(f"Error processing rows: {str(e)}")
            return False

    def _validate_row(self, row: pd.Series, row_num: int) -> bool:
        """Validate a single row of data"""
        try:
            # Date validation
            if pd.isna(row['Date']):
                self.errors.append(f"Row {row_num}: Missing date")
                return False

            try:
                date_value = pd.to_datetime(row['Date'])
                if date_value > datetime.now():
                    self.errors.append(f"Row {row_num}: Date cannot be in the future")
                    return False
            except Exception as e:
                self.errors.append(f"Row {row_num}: Invalid date format: {str(e)}")
                return False

            # Amount validation
            if pd.isna(row['Amount']):
                self.errors.append(f"Row {row_num}: Missing amount")
                return False

            try:
                amount = Decimal(str(row['Amount']))
                if amount == 0:
                    self.warnings.append(f"Row {row_num}: Zero amount transaction")
            except (InvalidOperation, ValueError) as e:
                self.errors.append(f"Row {row_num}: Invalid amount format: {str(e)}")
                return False

            # Description validation
            if pd.isna(row['Description']) or str(row['Description']).strip() == '':
                self.errors.append(f"Row {row_num}: Missing description")
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating row {row_num}: {str(e)}")
            self.errors.append(f"Error validating row {row_num}: {str(e)}")
            return False

    def get_error_messages(self) -> List[str]:
        """Get list of error messages"""
        return self.errors

    def get_warning_messages(self) -> List[str]:
        """Get list of warning messages"""
        return self.warnings

    def get_progress(self) -> Dict:
        """Get processing progress information"""
        return {
            'processed_rows': self.processed_rows,
            'total_rows': self.total_rows,
            'success': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings
        }
