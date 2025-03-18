"""
Code analyzer module for detecting bugs, inefficiencies, and potential issues in application code
"""
import os
import re
import ast
import logging
import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeAnalysisResult:
    """Class to store code analysis results"""
    def __init__(self):
        self.issues = []
        self.stats = {
            'files_analyzed': 0,
            'lines_analyzed': 0,
            'issues_found': 0,
            'critical_issues': 0,
            'high_issues': 0,
            'medium_issues': 0,
            'low_issues': 0
        }
    
    def add_issue(self, file_path: str, line_number: int, issue_type: str, description: str, 
                  severity: str, recommendation: str = None):
        """Add a detected issue to the results"""
        self.issues.append({
            'file_path': file_path,
            'line_number': line_number,
            'issue_type': issue_type,
            'description': description,
            'severity': severity.lower(),  # normalize severity
            'recommendation': recommendation
        })
        
        self.stats['issues_found'] += 1
        severity_key = f"{severity.lower()}_issues"
        if severity_key in self.stats:
            self.stats[severity_key] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the analysis results"""
        return {
            'stats': self.stats,
            'top_issues': self.issues[:10] if len(self.issues) > 10 else self.issues
        }

class CodeAnalyzer:
    """Analyzes Python code for bugs, inefficiencies, and issues"""
    
    def __init__(self):
        self.results = CodeAnalysisResult()
    
    def analyze_project(self, root_dir: str = '.') -> CodeAnalysisResult:
        """Analyze all Python files in a project"""
        logger.info(f"Starting code analysis of project in {root_dir}")
        
        # Reset results
        self.results = CodeAnalysisResult()
        
        # Find all Python files
        python_files = []
        for dirpath, _, filenames in os.walk(root_dir):
            # Skip virtual environments, cache directories, and migrations
            if any(part.startswith('.') or part in ('venv', 'env', '__pycache__', 'migrations', '.cache', 'node_modules') 
                   for part in dirpath.split(os.sep)):
                continue
            
            for filename in filenames:
                if filename.endswith('.py'):
                    python_files.append(os.path.join(dirpath, filename))
        
        logger.info(f"Found {len(python_files)} Python files to analyze")
        
        # Analyze each file
        for file_path in python_files:
            self._analyze_file(file_path)
        
        logger.info(f"Code analysis complete. Found {self.results.stats['issues_found']} issues.")
        return self.results
    
    def _analyze_file(self, file_path: str):
        """Analyze a single Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            lines = content.split('\n')
            self.results.stats['files_analyzed'] += 1
            self.results.stats['lines_analyzed'] += len(lines)
            
            # Run various analysis checks
            self._check_syntax(file_path, content)
            self._check_common_bugs(file_path, content, lines)
            self._check_inefficiencies(file_path, content, lines)
            self._check_security_issues(file_path, content, lines)
            self._check_database_queries(file_path, content, lines)
            self._check_resource_leaks(file_path, content, lines)
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            # Count this as a critical issue
            self.results.add_issue(
                file_path=file_path,
                line_number=1,
                issue_type="analysis_error",
                description=f"Could not analyze file: {str(e)}",
                severity="critical",
                recommendation="Fix the syntax or other issues in this file to allow proper analysis."
            )
    
    def _check_syntax(self, file_path: str, content: str):
        """Check for syntax errors in Python code"""
        try:
            ast.parse(content)
        except SyntaxError as e:
            self.results.add_issue(
                file_path=file_path,
                line_number=e.lineno,
                issue_type="syntax_error",
                description=f"Syntax error: {e.msg}",
                severity="critical",
                recommendation="Fix the syntax error to ensure the code can be executed."
            )
    
    def _check_common_bugs(self, file_path: str, content: str, lines: List[str]):
        """Check for common bugs in the code"""
        # Check for bare exceptions
        self._find_bare_exceptions(file_path, content, lines)
        
        # Check for mutable default arguments
        self._find_mutable_defaults(file_path, content)
        
        # Check for undefined variables in list comprehensions
        self._find_undefined_list_comp_variables(file_path, content)
        
        # Check for variable shadowing
        self._find_variable_shadowing(file_path, content)
        
        # Check for hardcoded credentials
        self._find_hardcoded_credentials(file_path, content, lines)
    
    def _find_bare_exceptions(self, file_path: str, content: str, lines: List[str]):
        """Find bare exceptions (except:) which can hide errors"""
        bare_except_pattern = re.compile(r'\s*except\s*:')
        
        for i, line in enumerate(lines):
            if bare_except_pattern.match(line):
                self.results.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type="bare_except",
                    description="Bare except clause can hide errors and make debugging difficult",
                    severity="medium",
                    recommendation="Specify the exception types you want to catch (e.g., 'except ValueError:')."
                )
    
    def _find_mutable_defaults(self, file_path: str, content: str):
        """Find functions with mutable default arguments"""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    for arg in node.args.defaults:
                        if isinstance(arg, (ast.List, ast.Dict, ast.Set)):
                            self.results.add_issue(
                                file_path=file_path,
                                line_number=node.lineno,
                                issue_type="mutable_default",
                                description=f"Function '{node.name}' uses a mutable default argument",
                                severity="medium",
                                recommendation="Use None as default and create mutable objects inside the function."
                            )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _find_undefined_list_comp_variables(self, file_path: str, content: str):
        """Find potentially undefined variables in list comprehensions"""
        # This is a simplified implementation - a full analysis would require proper scope tracking
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ListComp):
                    # This is a simplified check - in reality, you'd need to check 
                    # if the variables in node.elt exist in the scopes created by node.generators
                    pass
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _find_variable_shadowing(self, file_path: str, content: str):
        """Find variables that shadow Python builtins"""
        builtin_names = dir(__builtins__)
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in builtin_names:
                    self.results.add_issue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type="builtin_shadowing",
                        description=f"Variable '{node.id}' shadows a Python builtin",
                        severity="low",
                        recommendation=f"Rename the variable to avoid shadowing the '{node.id}' builtin."
                    )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _find_hardcoded_credentials(self, file_path: str, content: str, lines: List[str]):
        """Find potentially hardcoded credentials"""
        suspicious_patterns = [
            (r'password\s*=\s*[\'"][^\'"]+[\'"]', "hardcoded password"),
            (r'api_key\s*=\s*[\'"][^\'"]+[\'"]', "hardcoded API key"),
            (r'secret\s*=\s*[\'"][^\'"]+[\'"]', "hardcoded secret"),
            (r'token\s*=\s*[\'"][^\'"]+[\'"]', "hardcoded token")
        ]
        
        for i, line in enumerate(lines):
            for pattern, issue_type in suspicious_patterns:
                if re.search(pattern, line, re.IGNORECASE) and 'os.environ' not in line and 'env' not in line:
                    self.results.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type="hardcoded_credentials",
                        description=f"Possible {issue_type} detected",
                        severity="high",
                        recommendation="Use environment variables or a configuration file for sensitive information."
                    )
    
    def _check_inefficiencies(self, file_path: str, content: str, lines: List[str]):
        """Check for code inefficiencies"""
        # Check for duplicate code
        # (Simplified - a full implementation would use more sophisticated algorithms)
        
        # Check for inefficient database queries
        self._find_inefficient_queries(file_path, content, lines)
        
        # Check for excessive complexity
        self._find_complex_functions(file_path, content)
    
    def _find_inefficient_queries(self, file_path: str, content: str, lines: List[str]):
        """Find inefficient database queries"""
        # Look for queries in loops
        in_for_loop = False
        query_patterns = [r'\.query\.', r'\.execute\(', r'session\.']
        
        for i, line in enumerate(lines):
            if re.search(r'\s*for\s+\w+\s+in\s+', line):
                in_for_loop = True
            elif line.strip().startswith(('def ', 'class ', 'if ', 'else:', 'elif ')):
                in_for_loop = False
            
            if in_for_loop:
                for pattern in query_patterns:
                    if re.search(pattern, line):
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="query_in_loop",
                            description="Database query inside a loop may cause performance issues",
                            severity="high",
                            recommendation="Consider using a bulk query or join instead of querying inside a loop."
                        )
        
        # Look for N+1 query patterns (simplified)
        for i, line in enumerate(lines):
            if '.query.all()' in line and i < len(lines) - 3:
                for j in range(i + 1, min(i + 4, len(lines))):
                    if 'for' in lines[j] and '.query.' in lines[j+1:j+3]:
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="n_plus_one",
                            description="Potential N+1 query pattern detected",
                            severity="medium",
                            recommendation="Use eager loading with joined or subquery options to avoid N+1 queries."
                        )
                        break
    
    def _find_complex_functions(self, file_path: str, content: str):
        """Find overly complex functions"""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Simple complexity metric: count branches
                    branches = 0
                    for subnode in ast.walk(node):
                        if isinstance(subnode, (ast.If, ast.For, ast.While, ast.Try)):
                            branches += 1
                    
                    if branches > 10:  # Arbitrary threshold
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="complex_function",
                            description=f"Function '{node.name}' appears to be too complex ({branches} branches)",
                            severity="medium",
                            recommendation="Consider breaking this function into smaller, more focused functions."
                        )
        except SyntaxError:
            # Already reported in _check_syntax
            pass
    
    def _check_security_issues(self, file_path: str, content: str, lines: List[str]):
        """Check for security issues in the code"""
        self._find_sql_injection(file_path, content, lines)
        self._find_xss_vulnerabilities(file_path, content, lines)
        self._find_insecure_direct_object_references(file_path, content, lines)
    
    def _find_sql_injection(self, file_path: str, content: str, lines: List[str]):
        """Find potential SQL injection vulnerabilities"""
        sql_patterns = [
            r'execute\([\'"].*?\%s.*?[\'"]',
            r'execute\([\'"].*?\{.*?\}.*?[\'"]\.format',
            r'execute\([\'"].*?\+.*?[\'"]',
            r'text\([\'"].*?\%s.*?[\'"]',
            r'text\([\'"].*?\{.*?\}.*?[\'"]\.format',
            r'text\([\'"].*?\+.*?[\'"]',
        ]
        
        for i, line in enumerate(lines):
            for pattern in sql_patterns:
                if re.search(pattern, line):
                    if 'parameterized' not in line.lower() and 'bind' not in line.lower():
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="sql_injection",
                            description="Potential SQL injection vulnerability detected",
                            severity="critical",
                            recommendation="Use parameterized queries or SQLAlchemy ORM to prevent SQL injection."
                        )
    
    def _find_xss_vulnerabilities(self, file_path: str, content: str, lines: List[str]):
        """Find potential XSS vulnerabilities"""
        # Simplified check - look for direct request data being rendered
        xss_patterns = [
            (r'render_template\(.*?request\.(args|form|json|data|values|get_json\(\))', "Flask template rendering request data directly"),
            (r'jsonify\(.*?request\.(args|form|json|data|values|get_json\(\))', "Returning unfiltered request data as JSON"),
            (r'\.html\(.*?request\.', "jQuery setting HTML from request data")
        ]
        
        for i, line in enumerate(lines):
            for pattern, desc in xss_patterns:
                if re.search(pattern, line) and 'escape' not in line and 'safe_string' not in line:
                    self.results.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type="xss_vulnerability",
                        description=f"Potential XSS vulnerability: {desc}",
                        severity="high",
                        recommendation="Sanitize user input before rendering in HTML or validate input properly."
                    )
    
    def _find_insecure_direct_object_references(self, file_path: str, content: str, lines: List[str]):
        """Find potential insecure direct object references"""
        idor_patterns = [
            r'get\(\s*request\.(args|form|json)\s*\[\s*[\'"]id[\'"]\s*\]\s*\)',
            r'get_or_404\(\s*request\.(args|form|json)\s*\[\s*[\'"]id[\'"]\s*\]\s*\)',
            r'query\.get\(\s*request\.(args|form|json)\s*\[\s*[\'"]id[\'"]\s*\]\s*\)'
        ]
        
        for i, line in enumerate(lines):
            for pattern in idor_patterns:
                if re.search(pattern, line) and 'current_user' not in content[max(0, content.find(line)-200):content.find(line)+len(line)+200]:
                    self.results.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type="idor",
                        description="Potential insecure direct object reference vulnerability",
                        severity="high",
                        recommendation="Verify that the user has permission to access the specified object."
                    )
    
    def _check_database_queries(self, file_path: str, content: str, lines: List[str]):
        """Check for database query issues"""
        # Look for unfinished transactions
        self._find_unclosed_transactions(file_path, content, lines)
        
        # Look for missing indexes
        self._find_missing_indexes(file_path, content, lines)
    
    def _find_unclosed_transactions(self, file_path: str, content: str, lines: List[str]):
        """Find potentially unclosed database transactions"""
        commit_patterns = [
            (r'db\.session\.begin\(\)', r'db\.session\.commit\(\)'),
            (r'session\.begin\(\)', r'session\.commit\(\)'),
            (r'connection\.begin\(\)', r'connection\.commit\(\)')
        ]
        
        for begin_pattern, commit_pattern in commit_patterns:
            begins = []
            commits = []
            
            for i, line in enumerate(lines):
                if re.search(begin_pattern, line):
                    begins.append(i)
                if re.search(commit_pattern, line):
                    commits.append(i)
            
            if len(begins) > len(commits):
                for i in begins:
                    found = False
                    for j in commits:
                        if j > i:
                            found = True
                            break
                    
                    if not found:
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="unclosed_transaction",
                            description="Database transaction may not be properly committed or rolled back",
                            severity="high",
                            recommendation="Ensure all database transactions are properly committed or rolled back, preferably using a context manager or try/finally block."
                        )
    
    def _find_missing_indexes(self, file_path: str, content: str, lines: List[str]):
        """Find database queries that might benefit from indexes"""
        # This is a simplified placeholder - real implementation would require more sophisticated analysis
        # of database schema and query patterns
        query_patterns = [
            r'\.filter_by\((\w+)=',
            r'\.filter\(\w+\.(\w+)\s*==',
            r'\.where\(\w+\.(\w+)\s*=='
        ]
        
        for i, line in enumerate(lines):
            for pattern in query_patterns:
                matches = re.finditer(pattern, line)
                for match in matches:
                    column = match.group(1)
                    if column not in ('id',) and 'index=True' not in content:
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="potential_missing_index",
                            description=f"Query on column '{column}' might benefit from an index",
                            severity="low",
                            recommendation=f"Consider adding an index on the '{column}' column if this query is used frequently."
                        )
                        
    def _check_resource_leaks(self, file_path: str, content: str, lines: List[str]):
        """Check for potential resource leaks"""
        # Look for opened files that might not be closed
        self._find_unclosed_files(file_path, content, lines)
        
        # Look for other resource leaks
        self._find_other_resource_leaks(file_path, content, lines)
    
    def _find_unclosed_files(self, file_path: str, content: str, lines: List[str]):
        """Find potentially unclosed file handles"""
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and hasattr(node, 'func') and isinstance(node.func, ast.Name) and node.func.id == 'open':
                    # Check if this open call is inside a with statement
                    is_in_with = False
                    parent = node
                    while hasattr(parent, 'parent') and parent.parent is not None:
                        parent = parent.parent
                        if isinstance(parent, ast.With):
                            is_in_with = True
                            break
                    
                    if not is_in_with and not self._has_close_call(node, tree):
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type="unclosed_file",
                            description="File opened without being closed",
                            severity="medium",
                            recommendation="Use a 'with' statement to ensure the file is properly closed."
                        )
        except (SyntaxError, AttributeError, TypeError):
            # Skip if we can't parse the AST
            pass
    
    def _has_close_call(self, open_node, tree):
        """Helper method to find if there's a .close() call for an open() call"""
        # This is a simplified implementation - a full implementation would track variables and assignments
        return False  # Simplified always return False
    
    def _find_other_resource_leaks(self, file_path: str, content: str, lines: List[str]):
        """Find other potential resource leaks (connections, locks, etc.)"""
        resource_patterns = [
            (r'connect\(', r'close\(\)', "database connection"),
            (r'lock\(', r'unlock\(\)', "lock"),
            (r'acquire\(', r'release\(\)', "semaphore/lock")
        ]
        
        for acquire_pattern, release_pattern, resource_type in resource_patterns:
            acquires = []
            releases = []
            
            for i, line in enumerate(lines):
                if re.search(acquire_pattern, line) and 'with' not in line:
                    acquires.append(i)
                if re.search(release_pattern, line):
                    releases.append(i)
            
            if len(acquires) > len(releases):
                for i in acquires:
                    found = False
                    for j in releases:
                        if j > i:
                            found = True
                            break
                    
                    if not found:
                        self.results.add_issue(
                            file_path=file_path,
                            line_number=i + 1,
                            issue_type="resource_leak",
                            description=f"Potential {resource_type} resource leak",
                            severity="medium",
                            recommendation=f"Ensure all {resource_type}s are properly released, preferably using a context manager or try/finally block."
                        )

def analyze_code(root_dir: str = '.') -> Dict[str, Any]:
    """Run full code analysis and return results"""
    analyzer = CodeAnalyzer()
    results = analyzer.analyze_project(root_dir)
    return results.get_summary()