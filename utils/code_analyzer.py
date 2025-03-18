"""
Code Analyzer Module

Provides comprehensive static code analysis to detect bugs, inefficiencies, and issues.
"""

import os
import re
import ast
import logging
import glob
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class CodeAnalysisResult:
    """Class to store code analysis results"""
    def __init__(self):
        self.issues = []
        self.files_analyzed = 0
        self.total_issues = 0
        self.start_time = datetime.utcnow()
        self.end_time = None
        self.duration = 0.0
    
    def add_issue(self, file_path: str, line_number: int, issue_type: str, description: str, 
                  severity: str, recommendation: str = None):
        """Add a detected issue to the results"""
        if recommendation is None:
            recommendation = "Review and fix the issue."
            
        # Normalize severity
        if severity not in ['critical', 'high', 'medium', 'low']:
            severity = 'medium'
            
        self.issues.append({
            'file_path': file_path,
            'line_number': line_number,
            'issue_type': issue_type,
            'description': description,
            'severity': severity,
            'recommendation': recommendation
        })
        self.total_issues += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the analysis results"""
        # Calculate analysis duration
        if self.end_time is None:
            self.end_time = datetime.utcnow()
        
        self.duration = (self.end_time - self.start_time).total_seconds()
        
        # Count issues by severity
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        for issue in self.issues:
            severity = issue['severity']
            if severity in severity_counts:
                severity_counts[severity] += 1
        
        return {
            'total_files': self.files_analyzed,
            'total_issues': self.total_issues,
            'duration': self.duration,
            'critical_count': severity_counts['critical'],
            'high_count': severity_counts['high'],
            'medium_count': severity_counts['medium'],
            'low_count': severity_counts['low'],
            'issues': self.issues
        }


class CodeAnalyzer:
    """Analyzes Python code for bugs, inefficiencies, and issues"""
    
    def __init__(self):
        self.result = CodeAnalysisResult()
        self.skip_dirs = [
            'venv',
            '.git',
            '.github',
            '__pycache__',
            'node_modules',
            '.pytest_cache',
            '.vscode',
            'migrations'
        ]
        self.skip_files = [
            'setup.py',
            'conftest.py'
        ]
    
    def analyze_project(self, root_dir: str = '.') -> CodeAnalysisResult:
        """Analyze all Python files in a project"""
        logger.info(f"Starting code analysis on directory: {root_dir}")
        
        # Find all Python files
        python_files = []
        for root, dirs, files in os.walk(root_dir):
            # Skip directories in skip_dirs
            dirs[:] = [d for d in dirs if d not in self.skip_dirs]
            
            for file in files:
                if file.endswith('.py') and file not in self.skip_files:
                    full_path = os.path.join(root, file)
                    python_files.append(full_path)
        
        # Analyze each file
        for file_path in python_files:
            try:
                self._analyze_file(file_path)
                self.result.files_analyzed += 1
                logger.debug(f"Analyzed file: {file_path}")
            except Exception as e:
                logger.error(f"Error analyzing file {file_path}: {str(e)}")
        
        self.result.end_time = datetime.utcnow()
        logger.info(f"Code analysis completed. Found {self.result.total_issues} issues in {self.result.files_analyzed} files.")
        
        return self.result
    
    def _analyze_file(self, file_path: str):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Check for syntax errors
            self._check_syntax(file_path, content)
            
            # Check for common bugs
            self._check_common_bugs(file_path, content, lines)
            
            # Check for inefficiencies
            self._check_inefficiencies(file_path, content, lines)
            
            # Check for security issues
            self._check_security_issues(file_path, content, lines)
            
        except UnicodeDecodeError:
            logger.warning(f"Skipping file due to encoding issues: {file_path}")
    
    def _check_syntax(self, file_path: str, content: str):
        """Check for syntax errors in Python code"""
        try:
            ast.parse(content)
        except SyntaxError as e:
            self.result.add_issue(
                file_path=file_path,
                line_number=e.lineno or 1,
                issue_type="Syntax Error",
                description=f"Syntax error: {str(e)}",
                severity="critical",
                recommendation="Fix the syntax error to ensure the code can run."
            )
    
    def _check_common_bugs(self, file_path: str, content: str, lines: List[str]):
        """Check for common bugs in the code"""
        # Check for bare exceptions
        self._find_bare_exceptions(file_path, content, lines)
        
        # Check for mutable default arguments
        self._find_mutable_defaults(file_path, content)
        
        # Check for variable shadowing
        self._find_variable_shadowing(file_path, content)
        
        # Check for hardcoded credentials
        self._find_hardcoded_credentials(file_path, content, lines)
    
    def _find_bare_exceptions(self, file_path: str, content: str, lines: List[str]):
        """Find bare exceptions (except:) which can hide errors"""
        for i, line in enumerate(lines):
            if re.search(r'^\s*except\s*:', line):
                self.result.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type="Bare Exception",
                    description="Bare 'except:' clause found. This catches all exceptions including KeyboardInterrupt and SystemExit.",
                    severity="medium",
                    recommendation="Use specific exception types (e.g., 'except ValueError:') or at least 'except Exception:' to avoid catching system exits."
                )
    
    def _find_mutable_defaults(self, file_path: str, content: str):
        """Find functions with mutable default arguments"""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for arg in node.args.defaults:
                        if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                            self.result.add_issue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="Mutable Default Argument",
                                description=f"Function '{node.name}' uses a mutable default argument, which can cause unexpected behavior.",
                                severity="medium",
                                recommendation="Use None as the default and initialize the mutable object inside the function."
                            )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _find_undefined_list_comp_variables(self, file_path: str, content: str):
        """Find potentially undefined variables in list comprehensions"""
        # This is a complex analysis that would need a proper variable scope tracking
        # Simplified implementation for demonstration
        pass
    
    def _find_variable_shadowing(self, file_path: str, content: str):
        """Find variables that shadow Python builtins"""
        builtin_names = dir(__builtins__)
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    if node.id in builtin_names:
                        self.result.add_issue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="Builtin Shadowing",
                            description=f"Variable '{node.id}' shadows a Python builtin, which can lead to unexpected behavior.",
                            severity="low",
                            recommendation=f"Rename the variable to avoid shadowing the builtin '{node.id}'."
                        )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _find_hardcoded_credentials(self, file_path: str, content: str, lines: List[str]):
        """Find potentially hardcoded credentials"""
        credential_patterns = [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'secret\s*=\s*[\'"][^\'"]+[\'"]',
            r'token\s*=\s*[\'"][^\'"]+[\'"]'
        ]
        
        for i, line in enumerate(lines):
            for pattern in credential_patterns:
                if re.search(pattern, line, re.IGNORECASE) and 'os.environ' not in line and 'get(' not in line:
                    self.result.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type="Hardcoded Credential",
                        description="Potential hardcoded credential found.",
                        severity="high",
                        recommendation="Use environment variables or a secure configuration system instead of hardcoding credentials."
                    )
    
    def _check_inefficiencies(self, file_path: str, content: str, lines: List[str]):
        """Check for code inefficiencies"""
        # Check for inefficient database queries
        self._find_inefficient_queries(file_path, content, lines)
        
        # Check for complex functions
        self._find_complex_functions(file_path, content)
    
    def _find_inefficient_queries(self, file_path: str, content: str, lines: List[str]):
        """Find inefficient database queries"""
        # Example: Look for queries in loops (simplified)
        query_in_loop = False
        in_loop = False
        loop_start_line = 0
        
        for i, line in enumerate(lines):
            # Detect loop start
            if re.search(r'^\s*(for|while)\s', line):
                in_loop = True
                loop_start_line = i + 1
            
            # Detect loop end (simplified)
            elif in_loop and re.match(r'^[a-zA-Z]', line) and not line.startswith(' '):
                in_loop = False
                query_in_loop = False
            
            # Detect query inside loop
            if in_loop and ('query' in line.lower() or '.filter(' in line or '.execute(' in line):
                query_in_loop = True
                self.result.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type="Query in Loop",
                    description="Database query found inside a loop, which can be inefficient.",
                    severity="medium",
                    recommendation="Consider fetching all needed data in a single query before the loop."
                )
    
    def _find_complex_functions(self, file_path: str, content: str):
        """Find overly complex functions"""
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Count statements as a simple complexity metric
                    statement_count = 0
                    for child in ast.walk(node):
                        if isinstance(child, (ast.Assign, ast.AugAssign, ast.Return, ast.Raise,
                                             ast.Assert, ast.If, ast.For, ast.While, ast.Try)):
                            statement_count += 1
                    
                    # Check for complex functions
                    if statement_count > 50:  # Arbitrary threshold
                        self.result.add_issue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="Complex Function",
                            description=f"Function '{node.name}' is overly complex with {statement_count} statements.",
                            severity="medium",
                            recommendation="Consider breaking this function into smaller, more focused functions."
                        )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _check_security_issues(self, file_path: str, content: str, lines: List[str]):
        """Check for security issues in the code"""
        # Check for SQL injection vulnerabilities
        self._find_sql_injection(file_path, content, lines)
        
        # Check for XSS vulnerabilities
        self._find_xss_vulnerabilities(file_path, content, lines)
    
    def _find_sql_injection(self, file_path: str, content: str, lines: List[str]):
        """Find potential SQL injection vulnerabilities"""
        for i, line in enumerate(lines):
            # Look for string formatting or concatenation in SQL queries
            if ('execute(' in line or 'executemany(' in line) and ('%' in line or '+' in line or 'format(' in line):
                if 'parameterized' not in line and '?' not in line and '%s' not in line:
                    self.result.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type="SQL Injection Risk",
                        description="Potential SQL injection vulnerability found.",
                        severity="critical",
                        recommendation="Use parameterized queries or ORM methods instead of string formatting/concatenation."
                    )
    
    def _find_xss_vulnerabilities(self, file_path: str, content: str, lines: List[str]):
        """Find potential XSS vulnerabilities"""
        # Look for direct use of request data in templates
        for i, line in enumerate(lines):
            if 'render_template' in line:
                for j in range(max(0, i-5), min(len(lines), i+5)):
                    if 'request.' in lines[j] and 'escape' not in lines[j]:
                        self.result.add_issue(
                            file_path=file_path,
                            line_number=j + 1,
                            issue_type="XSS Vulnerability",
                            description="Potential XSS vulnerability: request data may be rendered without escaping.",
                            severity="high",
                            recommendation="Use appropriate escaping functions or Jinja2's automatic escaping."
                        )
                        break