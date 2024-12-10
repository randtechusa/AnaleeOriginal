import pandas as pd

def inspect_excel(filename):
    print(f"\nInspecting {filename}:")
    try:
        df = pd.read_excel(filename)
        print("Columns:", df.columns.tolist())
        print("\nFirst few rows:")
        print(df.head())
    except Exception as e:
        print(f"Error reading {filename}: {str(e)}")

# Inspect both Excel files
inspect_excel("Chart of Accounts.xlsx")
inspect_excel("Analee Sample (1).xlsx")
