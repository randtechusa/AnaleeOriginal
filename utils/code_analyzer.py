"""
Code Analyzer Module

Provides comprehensive static code analysis to detect bugs, inefficiencies, and issues.
"""

import os
import re
import ast
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

@dataclass
class CodeIssue:
    """Class to represent a code issue"""
    file_path: str
    line_number: int
    issue_type: str
    description: str
    severity: str
    recommendation: Optional[str] = None
    
    def __str__(self):
        return f"{self.severity.upper()}: {self.issue_type} at {os.path.basename(self.file_path)}:{self.line_number} - {self.description}"

@dataclass
class CodeAnalysisResult:
    """Class to store code analysis results"""
    issues: List[CodeIssue] = field(default_factory=list)
    
    def add_issue(self, file_path: str, line_number: int, issue_type: str, description: str, 
                  severity: str, recommendation: str = None):
        """Add a detected issue to the results"""
        self.issues.append(
            CodeIssue(
                file_path=file_path,
                line_number=line_number,
                issue_type=issue_type,
                description=description,
                severity=severity,
                recommendation=recommendation
            )
        )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the analysis results"""
        severity_counts = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0,
            'info': 0
        }
        
        issue_types = {}
        
        for issue in self.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            
            issue_types[issue.issue_type] = issue_types.get(issue.issue_type, 0) + 1
        
        return {
            'total_issues': len(self.issues),
            'severity_counts': severity_counts,
            'issue_types': issue_types,
            'files_with_issues': len(set(issue.file_path for issue in self.issues))
        }

class CodeAnalyzer:
    """Analyzes Python code for bugs, inefficiencies, and issues"""
    
    def __init__(self):
        """Initialize code analyzer"""
        self.skipped_dirs = {'.git', '__pycache__', 'venv', 'env', '.env', 'node_modules', 'migrations', 'static', 'templates'}
        self.severity_levels = {'critical', 'high', 'medium', 'low', 'info'}
        
    def analyze_project(self, root_dir: str = '.') -> CodeAnalysisResult:
        """Analyze all Python files in a project"""
        logger.info(f"Starting code analysis for project at {root_dir}")
        
        result = CodeAnalysisResult()
        
        for root, dirs, files in os.walk(root_dir):
            # Skip certain directories
            dirs[:] = [d for d in dirs if d not in self.skipped_dirs]
            
            for file_name in files:
                if file_name.endswith('.py'):
                    file_path = os.path.join(root, file_name)
                    logger.debug(f"Analyzing file: {file_path}")
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            self._analyze_file(file_path, content, result)
                    except Exception as e:
                        logger.error(f"Error analyzing file {file_path}: {e}")
                        result.add_issue(
                            file_path=file_path,
                            line_number=0,
                            issue_type='analyzer_error',
                            description=f"Failed to analyze file: {str(e)}",
                            severity='medium'
                        )
        
        logger.info(f"Code analysis completed. Found {len(result.issues)} issues.")
        return result
    
    def _analyze_file(self, file_path: str, content: str, result: CodeAnalysisResult) -> None:
        """Analyze a single Python file"""
        lines = content.split('\n')
        
        # Check for syntax errors
        self._check_syntax(file_path, content, result)
        
        # Parse the AST for more detailed analysis
        try:
            tree = ast.parse(content, filename=file_path)
            
            # Check for various code issues
            self._check_common_bugs(file_path, tree, lines, result)
            
        except SyntaxError:
            # Already reported in _check_syntax
            pass
        except Exception as e:
            logger.error(f"Error in AST analysis for {file_path}: {e}")
            result.add_issue(
                file_path=file_path,
                line_number=0,
                issue_type='ast_error',
                description=f"Failed to parse AST: {str(e)}",
                severity='medium'
            )
        
        # Line-by-line checks (not requiring AST)
        self._find_bare_exceptions(file_path, lines, result)
        self._find_hardcoded_credentials(file_path, lines, result)
        self._find_debug_code(file_path, lines, result)
        self._find_commented_out_code(file_path, lines, result)
        self._find_todo_comments(file_path, lines, result)
    
    def _check_syntax(self, file_path: str, content: str, result: CodeAnalysisResult) -> None:
        """Check for syntax errors in Python code"""
        try:
            ast.parse(content, filename=file_path)
        except SyntaxError as e:
            result.add_issue(
                file_path=file_path,
                line_number=e.lineno,
                issue_type='syntax_error',
                description=f"Syntax error: {e.msg}",
                severity='critical',
                recommendation="Fix the syntax error to ensure the code can run properly"
            )
    
    def _check_common_bugs(self, file_path: str, tree: ast.AST, lines: List[str], result: CodeAnalysisResult) -> None:
        """Check for common bugs in the code"""
        # Various bug checkers using AST
        self._find_mutable_defaults(file_path, tree, result)
        self._find_variable_shadowing(file_path, tree, result)
        self._find_unused_imports(file_path, tree, result)
        self._find_redundant_code(file_path, tree, result)
        self._find_complex_code(file_path, tree, lines, result)
    
    def _find_bare_exceptions(self, file_path: str, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find bare exceptions (except:) which can hide errors"""
        for i, line in enumerate(lines):
            line = line.strip()
            if line.startswith('except:') or line == 'except :':
                result.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type='bare_except',
                    description="Bare 'except:' clause found which can hide errors",
                    severity='high',
                    recommendation="Specify the exception types to catch"
                )
    
    def _find_mutable_defaults(self, file_path: str, tree: ast.AST, result: CodeAnalysisResult) -> None:
        """Find functions with mutable default arguments"""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for default in node.args.defaults:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        result.add_issue(
                            file_path=file_path,
                            line_number=node.lineno,
                            issue_type='mutable_default',
                            description=f"Function '{node.name}' uses mutable default argument",
                            severity='medium',
                            recommendation="Use None as default and initialize the mutable value inside the function"
                        )
    
    def _find_variable_shadowing(self, file_path: str, tree: ast.AST, result: CodeAnalysisResult) -> None:
        """Find variables that shadow Python builtins"""
        builtin_names = dir(__builtins__)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if node.id in builtin_names:
                    result.add_issue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type='shadowed_builtin',
                        description=f"Variable '{node.id}' shadows a Python builtin",
                        severity='medium',
                        recommendation=f"Rename the variable to avoid shadowing the builtin '{node.id}'"
                    )
    
    def _find_hardcoded_credentials(self, file_path: str, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find potentially hardcoded credentials"""
        sensitive_patterns = [
            (r'password\s*=\s*[\'"][^\'"]{8,}[\'"]', 'password'),
            (r'api_key\s*=\s*[\'"][^\'"]{8,}[\'"]', 'API key'),
            (r'secret\s*=\s*[\'"][^\'"]{8,}[\'"]', 'secret'),
            (r'token\s*=\s*[\'"][^\'"]{8,}[\'"]', 'token'),
            (r'auth\s*=\s*[\'"][^\'"]{8,}[\'"]', 'authentication credential')
        ]
        
        for i, line in enumerate(lines):
            for pattern, credential_type in sensitive_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Skip if this looks like it's reading from environment or config
                    if 'os.environ' in line or 'config' in line.lower() or 'get(' in line:
                        continue
                        
                    result.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type='hardcoded_credentials',
                        description=f"Possible hardcoded {credential_type} found",
                        severity='critical',
                        recommendation="Use environment variables or a secure secret manager"
                    )
    
    def _find_unused_imports(self, file_path: str, tree: ast.AST, result: CodeAnalysisResult) -> None:
        """Find unused imports in the code"""
        imported_names = set()
        used_names = set()
        
        # First pass: collect imported names
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    imported_names.add(name.asname if name.asname else name.name)
            elif isinstance(node, ast.ImportFrom):
                for name in node.names:
                    if name.name != '*':  # Can't track * imports
                        imported_names.add(name.asname if name.asname else name.name)
        
        # Second pass: collect used names
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load):
                if isinstance(node.value, ast.Name):
                    used_names.add(node.value.id)
        
        # Find unused imports
        for name in imported_names:
            if name not in used_names and not name.startswith('_'):  # Skip private imports
                result.add_issue(
                    file_path=file_path,
                    line_number=0,  # Can't get line number easily
                    issue_type='unused_import',
                    description=f"Unused import: '{name}'",
                    severity='low',
                    recommendation="Remove unused imports to improve maintainability"
                )
    
    def _find_redundant_code(self, file_path: str, tree: ast.AST, result: CodeAnalysisResult) -> None:
        """Find redundant code patterns"""
        # Check for unnecessary pass statements
        for node in ast.walk(tree):
            if isinstance(node, ast.Pass):
                parent = node.parent if hasattr(node, 'parent') else None
                if parent and len(parent.body) > 1:
                    result.add_issue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type='unnecessary_pass',
                        description="Unnecessary 'pass' statement",
                        severity='low',
                        recommendation="Remove unnecessary 'pass' statements"
                    )
    
    def _find_complex_code(self, file_path: str, tree: ast.AST, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find complex code that might be hard to maintain"""
        # Check for very long functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                function_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if function_lines > 50:
                    result.add_issue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type='long_function',
                        description=f"Function '{node.name}' is very long ({function_lines} lines)",
                        severity='medium',
                        recommendation="Consider breaking the function into smaller, more manageable functions"
                    )
                
                # Check for excessive nesting
                max_nesting = self._get_max_nesting(node)
                if max_nesting > 4:
                    result.add_issue(
                        file_path=file_path,
                        line_number=node.lineno,
                        issue_type='excessive_nesting',
                        description=f"Function '{node.name}' has excessive nesting (depth {max_nesting})",
                        severity='medium',
                        recommendation="Reduce nesting by extracting code into helper functions"
                    )
        
        # Check for long lines
        for i, line in enumerate(lines):
            if len(line) > 100:
                result.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type='long_line',
                    description=f"Line is too long ({len(line)} characters)",
                    severity='low',
                    recommendation="Break long lines to improve readability (max 100 characters per line)"
                )
    
    def _get_max_nesting(self, node: ast.AST, current_depth: int = 0) -> int:
        """Calculate the maximum nesting depth in a node"""
        if not hasattr(node, 'body'):
            return current_depth
        
        max_depth = current_depth
        for child in node.body:
            if isinstance(child, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
                child_depth = self._get_max_nesting(child, current_depth + 1)
                max_depth = max(max_depth, child_depth)
        
        return max_depth
    
    def _find_debug_code(self, file_path: str, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find debug code that should be removed in production"""
        debug_patterns = [
            r'^\s*print\(',
            r'^\s*debugger',
            r'^\s*console\.log\(',
            r'^\s*# DEBUG',
            r'pdb\.set_trace\(\)'
        ]
        
        for i, line in enumerate(lines):
            for pattern in debug_patterns:
                if re.search(pattern, line):
                    result.add_issue(
                        file_path=file_path,
                        line_number=i + 1,
                        issue_type='debug_code',
                        description="Debug code found that should be removed in production",
                        severity='medium',
                        recommendation="Remove debug statements or move them to proper logging"
                    )
    
    def _find_commented_out_code(self, file_path: str, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find commented out code that should be removed or documented"""
        code_patterns = [
            r'^\s*#\s*\w+\(',
            r'^\s*#\s*if\s+',
            r'^\s*#\s*for\s+',
            r'^\s*#\s*def\s+',
            r'^\s*#\s*class\s+',
            r'^\s*#\s*import\s+',
            r'^\s*#\s*from\s+'
        ]
        
        comment_blocks = []
        current_block = []
        
        # First collect comment blocks
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                current_block.append((i, line))
            elif current_block:
                if len(current_block) >= 2:  # Only consider blocks of 2+ comments
                    comment_blocks.append(current_block)
                current_block = []
        
        # Check the last block
        if current_block and len(current_block) >= 2:
            comment_blocks.append(current_block)
        
        # Check each block for code patterns
        for block in comment_blocks:
            code_lines = 0
            for i, line in block:
                for pattern in code_patterns:
                    if re.search(pattern, line):
                        code_lines += 1
                        break
            
            # If more than 50% of comments look like code, flag it
            if code_lines > len(block) / 2:
                result.add_issue(
                    file_path=file_path,
                    line_number=block[0][0] + 1,
                    issue_type='commented_code',
                    description=f"Block of {len(block)} commented-out code lines found",
                    severity='low',
                    recommendation="Remove commented-out code or document why it's kept"
                )
    
    def _find_todo_comments(self, file_path: str, lines: List[str], result: CodeAnalysisResult) -> None:
        """Find TODO comments that might indicate unfinished work"""
        todo_pattern = r'^\s*#\s*TODO'
        
        for i, line in enumerate(lines):
            if re.search(todo_pattern, line, re.IGNORECASE):
                result.add_issue(
                    file_path=file_path,
                    line_number=i + 1,
                    issue_type='todo_comment',
                    description="TODO comment found",
                    severity='info',
                    recommendation="Address TODO items before considering code complete"
                )