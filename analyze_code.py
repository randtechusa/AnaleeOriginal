"""
Script to analyze code for bugs and issues
"""
import os
import sys
from utils.code_analyzer import CodeAnalyzer, CodeAnalysisResult

def main():
    """Run a comprehensive code analysis"""
    try:
        analyzer = CodeAnalyzer()
        print(f"Starting code analysis... This might take a few moments.")
        
        # Exclude directories that aren't part of our application
        excludes = ['.cache', 'backups', 'instance', 'venv', '__pycache__', '.pytest_cache', 'migrations']
        
        # Only analyze these file patterns
        patterns = ['*.py']
        
        # Focus on main application files
        key_files = [
            'app.py',
            'config.py',
            'create_admin.py',
            'run_migrations.py',
            'restore_icountant.py',
            'utils/db_health.py',
            'models.py',
            'extensions.py'
        ]
        
        # First analyze key files
        results = []
        print("Analyzing key application files...")
        for file in key_files:
            if os.path.exists(file):
                with open(file, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
                    file_result = CodeAnalysisResult()
                    analyzer._analyze_file(file, content, file_result)
                    results.append(file_result)
        
        # Merge results
        final_result = CodeAnalysisResult()
        for result in results:
            final_result.issues.extend(result.issues)
        
        # Print summary
        print("\n=== Analysis Summary ===")
        summary = final_result.get_summary()
        print(f"Total issues found: {summary['total_issues']}")
        print(f"Critical: {summary['by_severity']['critical']}")
        print(f"High: {summary['by_severity']['high']}")
        print(f"Medium: {summary['by_severity']['medium']}")
        print(f"Low: {summary['by_severity']['low']}")
        
        # Print critical and high issues
        if summary['by_severity']['critical'] > 0 or summary['by_severity']['high'] > 0:
            print("\n=== Critical and High Priority Issues ===")
            for issue in final_result.issues:
                if issue.severity in ['critical', 'high']:
                    print(f"{issue}")
                    if issue.recommendation:
                        print(f"  Recommendation: {issue.recommendation}")
                    print()
        
        return 0
    except Exception as e:
        print(f"Error running code analysis: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())