"""
Excel reader service for bank statements
Handles CNBS Business Bank Statement format
"""
import logging
from typing import Dict, List, Optional
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

class BankStatementExcelReader:
    """Handles reading and validation of bank statement Excel files"""
    
    def __init__(self):
        self.required_columns = ['Date', 'Description', 'Amount']
        self.errors = []
        
    def read_excel(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Read bank statement Excel file
        Returns DataFrame if successful, None if failed
        """
        try:
            # Read Excel file
            df = pd.read_excel(file_path, engine='openpyxl')
            
            # Log the columns found
            logger.info(f"Found columns: {df.columns.tolist()}")
            
            # Check for required columns
            missing_columns = [col for col in self.required_columns if col not in df.columns]
            if missing_columns:
                error_msg = f"Missing required columns: {', '.join(missing_columns)}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return None
                
            # Convert date column to datetime
            try:
                df['Date'] = pd.to_datetime(df['Date'])
            except Exception as e:
                error_msg = f"Error converting dates: {str(e)}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return None
                
            # Convert amount to float
            try:
                df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce')
            except Exception as e:
                error_msg = f"Error converting amounts: {str(e)}"
                logger.error(error_msg)
                self.errors.append(error_msg)
                return None
                
            return df
            
        except Exception as e:
            error_msg = f"Error reading Excel file: {str(e)}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return None
            
    def get_errors(self) -> List[str]:
        """Return list of errors encountered during reading"""
        return self.errors

    def validate_data(self, df: pd.DataFrame) -> bool:
        """
        Validate the data in the DataFrame
        Returns True if valid, False otherwise
        """
        try:
            # Check for empty dataframe
            if df.empty:
                self.errors.append("No data found in file")
                return False
                
            # Check for null values
            null_counts = df[self.required_columns].isnull().sum()
            if null_counts.any():
                for col, count in null_counts.items():
                    if count > 0:
                        self.errors.append(f"Found {count} empty values in {col}")
                return False
                
            # Validate date range
            date_range = df['Date'].agg(['min', 'max'])
            if (date_range['max'] - date_range['min']).days > 366:
                self.errors.append("Statement period exceeds 1 year")
                return False
                
            return True
            
        except Exception as e:
            self.errors.append(f"Error validating data: {str(e)}")
            return False
