"""
System Auditor Module

Provides comprehensive system auditing capabilities for security,
performance, and data integrity.
"""

import logging
import os
import psutil
import json
import datetime
import platform
import re
import sys
import sqlite3
import hashlib
from pathlib import Path

from models import db, ErrorLog, Transaction, UploadedFile, User, Account
from sqlalchemy import text, inspect
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

class SystemAuditor:
    """
    System Auditor that performs comprehensive checks on the application
    to ensure security, performance, and data integrity.
    """
    
    def __init__(self):
        """Initialize system auditor with configuration"""
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.security_checks = {
            'password_policy': self._check_password_policy,
            'file_permissions': self._check_file_permissions,
            'database_security': self._check_database_security,
            'sensitive_data_exposure': self._check_sensitive_data_exposure,
            'input_validation': self._check_input_validation,
            'csrf_protection': self._check_csrf_protection
        }
        
        self.performance_checks = {
            'database_performance': self._check_database_performance,
            'memory_usage': self._check_memory_usage,
            'query_performance': self._check_query_performance,
            'application_responsiveness': self._check_application_responsiveness,
            'cache_efficiency': self._check_cache_efficiency
        }
        
        self.integrity_checks = {
            'database_consistency': self._check_database_consistency,
            'orphaned_records': self._check_orphaned_records,
            'data_validation': self._check_data_validation,
            'backup_integrity': self._check_backup_integrity,
            'file_integrity': self._check_file_integrity
        }
        
    def check_security(self):
        """
        Run all security checks
        
        Returns:
            Dictionary with security check results
        """
        logger.info("Running security audit checks")
        results = {}
        
        for check_name, check_func in self.security_checks.items():
            try:
                logger.debug(f"Running security check: {check_name}")
                results[check_name] = check_func()
            except Exception as e:
                logger.error(f"Error in security check {check_name}: {e}")
                results[check_name] = {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Error running security check: {check_name}",
                    'recommendation': "Investigate the error and fix the underlying issue",
                    'details': {
                        'error': str(e),
                        'check': check_name
                    }
                }
                
        return results
    
    def check_performance(self):
        """
        Run all performance checks
        
        Returns:
            Dictionary with performance check results
        """
        logger.info("Running performance audit checks")
        results = {}
        
        for check_name, check_func in self.performance_checks.items():
            try:
                logger.debug(f"Running performance check: {check_name}")
                results[check_name] = check_func()
            except Exception as e:
                logger.error(f"Error in performance check {check_name}: {e}")
                results[check_name] = {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Error running performance check: {check_name}",
                    'recommendation': "Investigate the error and fix the underlying issue",
                    'details': {
                        'error': str(e),
                        'check': check_name
                    }
                }
                
        return results
    
    def check_data_integrity(self):
        """
        Run all data integrity checks
        
        Returns:
            Dictionary with data integrity check results
        """
        logger.info("Running data integrity audit checks")
        results = {}
        
        for check_name, check_func in self.integrity_checks.items():
            try:
                logger.debug(f"Running integrity check: {check_name}")
                results[check_name] = check_func()
            except Exception as e:
                logger.error(f"Error in integrity check {check_name}: {e}")
                results[check_name] = {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Error running integrity check: {check_name}",
                    'recommendation': "Investigate the error and fix the underlying issue",
                    'details': {
                        'error': str(e),
                        'check': check_name
                    }
                }
                
        return results
    
    # Security Checks
    
    def _check_password_policy(self):
        """
        Check that password policy is enforced
        
        Returns:
            Check results dictionary
        """
        # Check if there's a password policy definition in the code
        found_password_validation = False
        policy_strength = 'weak'
        
        # Look in auth module files
        auth_dir = os.path.join(self.root_dir, 'auth')
        if os.path.exists(auth_dir):
            for file_name in os.listdir(auth_dir):
                if file_name.endswith('.py'):
                    file_path = os.path.join(auth_dir, file_name)
                    with open(file_path, 'r') as f:
                        content = f.read()
                        # Look for password validation code
                        if re.search(r'validate_password|password_strength|check_password_strength', content):
                            found_password_validation = True
                            # Check strength requirements
                            if re.search(r'(?=.*\d)(?=.*[a-z])(?=.*[A-Z])(?=.*[!@#$%^&*(),.?":{}|<>]).{8,}', content):
                                policy_strength = 'strong'
                            elif re.search(r'(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).{8,}', content):
                                policy_strength = 'medium'
                            break
        
        # Also check models.py for password hashing
        models_path = os.path.join(self.root_dir, 'models.py')
        uses_secure_hashing = False
        if os.path.exists(models_path):
            with open(models_path, 'r') as f:
                content = f.read()
                # Check if using secure password hashing
                if 'generate_password_hash' in content and 'check_password_hash' in content:
                    uses_secure_hashing = True
        
        if found_password_validation and uses_secure_hashing and policy_strength != 'weak':
            return {
                'passed': True,
                'severity': 'info',
                'description': f"Password policy is enforced with {policy_strength} requirements",
                'details': {
                    'policy_strength': policy_strength,
                    'secure_hashing': uses_secure_hashing
                }
            }
        else:
            severity = 'high' if not uses_secure_hashing else 'medium'
            description = []
            recommendation = []
            
            if not found_password_validation:
                description.append("No password validation logic found")
                recommendation.append("Implement password strength validation in the auth module")
            if not uses_secure_hashing:
                description.append("Secure password hashing not implemented")
                recommendation.append("Use werkzeug.security.generate_password_hash for password storage")
            if policy_strength == 'weak':
                description.append("Password policy is too weak")
                recommendation.append("Require minimum 8 characters with numbers, uppercase, lowercase, and special characters")
            
            return {
                'passed': False,
                'severity': severity,
                'description': "; ".join(description),
                'recommendation': "; ".join(recommendation),
                'details': {
                    'policy_strength': policy_strength,
                    'secure_hashing': uses_secure_hashing,
                    'validation_found': found_password_validation
                }
            }
    
    def _check_file_permissions(self):
        """
        Check file permissions for sensitive files
        
        Returns:
            Check results dictionary
        """
        # Get list of sensitive files
        sensitive_files = []
        
        # Config files
        config_files = [
            os.path.join(self.root_dir, 'config.py'),
            os.path.join(self.root_dir, 'config_dev.py'),
            os.path.join(self.root_dir, '.env')
        ]
        sensitive_files.extend([f for f in config_files if os.path.exists(f)])
        
        # Instance directory (SQLite, etc)
        instance_dir = os.path.join(self.root_dir, 'instance')
        if os.path.exists(instance_dir):
            for file_name in os.listdir(instance_dir):
                if file_name.endswith('.db') or file_name.endswith('.sqlite'):
                    sensitive_files.append(os.path.join(instance_dir, file_name))
        
        # Check permissions
        issues = []
        
        for file_path in sensitive_files:
            try:
                stats = os.stat(file_path)
                mode = stats.st_mode
                
                # On Unix-like systems, check if file is world-readable or world-writable
                if platform.system() != 'Windows':
                    if mode & 0o004:  # World-readable
                        issues.append({
                            'file': os.path.basename(file_path),
                            'issue': 'World-readable',
                            'mode': oct(mode)[-3:]
                        })
                    if mode & 0o002:  # World-writable
                        issues.append({
                            'file': os.path.basename(file_path),
                            'issue': 'World-writable',
                            'mode': oct(mode)[-3:]
                        })
            except Exception as e:
                logger.error(f"Error checking permissions for {file_path}: {e}")
        
        if not issues:
            return {
                'passed': True,
                'severity': 'info',
                'description': f"All sensitive files have appropriate permissions",
                'details': {
                    'files_checked': len(sensitive_files),
                    'sensitive_files': [os.path.basename(f) for f in sensitive_files]
                }
            }
        else:
            return {
                'passed': False,
                'severity': 'high',
                'description': f"Found {len(issues)} permission issues with sensitive files",
                'recommendation': "Update file permissions to restrict access to sensitive files",
                'details': {
                    'issues': issues,
                    'files_checked': len(sensitive_files)
                }
            }
    
    def _check_database_security(self):
        """
        Check database security configuration
        
        Returns:
            Check results dictionary
        """
        # Check connection string for hardcoded credentials
        config_path = os.path.join(self.root_dir, 'config.py')
        hardcoded_credentials = False
        using_environment_vars = False
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                # Check for hardcoded credentials in connection strings
                if re.search(r'postgresql://[^:]+:[^@]+@', content) or re.search(r'mysql://[^:]+:[^@]+@', content):
                    hardcoded_credentials = True
                # Check for environment variable usage
                if re.search(r'os\.environ\.get\([\'"]DATABASE_URL[\'"]', content):
                    using_environment_vars = True
        
        # Check SQLAlchemy security settings
        using_pooling = False
        using_ssl = False
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                # Check for connection pooling
                if 'pool_size' in content and 'max_overflow' in content:
                    using_pooling = True
                # Check for SSL usage
                if 'connect_args' in content and 'sslmode' in content:
                    using_ssl = True
        
        issues = []
        if hardcoded_credentials:
            issues.append("Hardcoded database credentials found")
        if not using_environment_vars:
            issues.append("Not using environment variables for database configuration")
        if not using_pooling:
            issues.append("Connection pooling not configured")
        if not using_ssl:
            issues.append("SSL not configured for database connections")
        
        if not issues:
            return {
                'passed': True,
                'severity': 'info',
                'description': "Database security configuration is good",
                'details': {
                    'using_environment_vars': using_environment_vars,
                    'using_pooling': using_pooling,
                    'using_ssl': using_ssl
                }
            }
        else:
            return {
                'passed': False,
                'severity': 'medium',
                'description': "; ".join(issues),
                'recommendation': "Update database configuration to use environment variables, connection pooling, and SSL",
                'details': {
                    'issues': issues,
                    'hardcoded_credentials': hardcoded_credentials,
                    'using_environment_vars': using_environment_vars,
                    'using_pooling': using_pooling,
                    'using_ssl': using_ssl
                }
            }
    
    def _check_sensitive_data_exposure(self):
        """
        Check for sensitive data exposure in logs and code
        
        Returns:
            Check results dictionary
        """
        # Check log files for sensitive data
        log_dir = os.path.join(self.root_dir)
        log_issues = []
        
        log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
        sensitive_patterns = [
            r'password\s*=\s*[\'"][^\'"]+[\'"]',
            r'api_key\s*=\s*[\'"][^\'"]+[\'"]',
            r'secret\s*=\s*[\'"][^\'"]+[\'"]',
            r'token\s*=\s*[\'"][^\'"]+[\'"]',
            r'credit_card\s*=\s*[\'"][^\'"]+[\'"]',
            r'Authorization: Bearer\s+[^\'"\s]+'
        ]
        
        for log_file in log_files:
            log_path = os.path.join(log_dir, log_file)
            try:
                with open(log_path, 'r') as f:
                    line_num = 0
                    for line in f:
                        line_num += 1
                        for pattern in sensitive_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                log_issues.append({
                                    'file': log_file,
                                    'line': line_num,
                                    'pattern': pattern
                                })
            except Exception as e:
                logger.error(f"Error checking log file {log_file}: {e}")
        
        # Check code for print statements with sensitive data
        code_issues = []
        
        for root, dirs, files in os.walk(self.root_dir):
            for file_name in files:
                if file_name.endswith('.py'):
                    file_path = os.path.join(root, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            line_num = 0
                            for line in f:
                                line_num += 1
                                if 'print(' in line:
                                    for pattern in sensitive_patterns:
                                        if re.search(pattern, line, re.IGNORECASE):
                                            code_issues.append({
                                                'file': os.path.relpath(file_path, self.root_dir),
                                                'line': line_num,
                                                'pattern': pattern
                                            })
                    except Exception as e:
                        logger.error(f"Error checking code file {file_path}: {e}")
        
        total_issues = len(log_issues) + len(code_issues)
        
        if total_issues == 0:
            return {
                'passed': True,
                'severity': 'info',
                'description': "No sensitive data exposure found in logs or code",
                'details': {
                    'log_files_checked': len(log_files),
                    'patterns_checked': len(sensitive_patterns)
                }
            }
        else:
            return {
                'passed': False,
                'severity': 'critical' if len(log_issues) > 0 else 'high',
                'description': f"Found {total_issues} instances of sensitive data exposure",
                'recommendation': "Remove sensitive data from logs and avoid printing sensitive data",
                'details': {
                    'log_issues': log_issues[:10],  # Limit to first 10 issues
                    'code_issues': code_issues[:10],  # Limit to first 10 issues
                    'total_log_issues': len(log_issues),
                    'total_code_issues': len(code_issues)
                }
            }
    
    def _check_input_validation(self):
        """
        Check for input validation in forms and API endpoints
        
        Returns:
            Check results dictionary
        """
        # Check form validation in forms module
        forms_dir = os.path.join(self.root_dir, 'forms')
        routes_dir = os.path.join(self.root_dir, 'routes')
        
        form_validation_issues = []
        route_validation_issues = []
        
        validators_used = set()
        
        # Check form validation
        if os.path.exists(forms_dir):
            for file_name in os.listdir(forms_dir):
                if file_name.endswith('.py'):
                    file_path = os.path.join(forms_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            
                            # Check for validator imports
                            for validator in ['DataRequired', 'Email', 'Length', 'EqualTo', 'Regexp', 'NumberRange']:
                                if validator in content:
                                    validators_used.add(validator)
                            
                            # Check if validators are actually used
                            form_classes = re.findall(r'class\s+(\w+)\(\w+\):', content)
                            for form_class in form_classes:
                                if not re.search(r'validators\s*=\s*\[', content):
                                    form_validation_issues.append({
                                        'file': file_name,
                                        'form': form_class,
                                        'issue': 'No validators found'
                                    })
                    except Exception as e:
                        logger.error(f"Error checking form file {file_path}: {e}")
        
        # Check route validation
        if os.path.exists(routes_dir):
            for file_name in os.listdir(routes_dir):
                if file_name.endswith('.py'):
                    file_path = os.path.join(routes_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            
                            # Find route functions with request.form or request.json
                            route_methods = re.findall(r'@(\w+)\.route\([\'"][^\'"]+[\'"](,\s*methods=\[[^\]]+\])?\)\s*\n\s*def\s+(\w+)', content)
                            
                            for bp_name, methods, func_name in route_methods:
                                # Check for POST/PUT/DELETE methods without validation
                                if 'POST' in methods or 'PUT' in methods or 'DELETE' in methods:
                                    # Look for validation
                                    func_body = re.search(r'def\s+' + func_name + r'\([^)]*\):\s*(.*?)(?=\n\s*@|\n\s*def|\Z)', content, re.DOTALL)
                                    if func_body:
                                        func_text = func_body.group(1)
                                        # Look for common validation patterns
                                        if 'request.form' in func_text or 'request.json' in func_text:
                                            if not any(pattern in func_text for pattern in ['validate_on_submit', '.validate(', 'validators.', 'if not form.', 'if form.errors']):
                                                route_validation_issues.append({
                                                    'file': file_name,
                                                    'route': func_name,
                                                    'blueprint': bp_name,
                                                    'methods': methods,
                                                    'issue': 'No input validation found'
                                                })
                    except Exception as e:
                        logger.error(f"Error checking route file {file_path}: {e}")
        
        total_issues = len(form_validation_issues) + len(route_validation_issues)
        
        if total_issues == 0 and len(validators_used) >= 3:
            return {
                'passed': True,
                'severity': 'info',
                'description': "Input validation is properly implemented",
                'details': {
                    'validators_used': list(validators_used)
                }
            }
        else:
            return {
                'passed': False,
                'severity': 'high',
                'description': f"Found {total_issues} input validation issues",
                'recommendation': "Implement proper input validation using WTForms validators or manual validation",
                'details': {
                    'form_issues': form_validation_issues,
                    'route_issues': route_validation_issues,
                    'validators_used': list(validators_used)
                }
            }
    
    def _check_csrf_protection(self):
        """
        Check for CSRF protection in forms and routes
        
        Returns:
            Check results dictionary
        """
        # Check for WTF_CSRF_ENABLED in config
        config_path = os.path.join(self.root_dir, 'config.py')
        csrf_enabled = False
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                if 'WTF_CSRF_ENABLED' in content and 'False' not in content[content.find('WTF_CSRF_ENABLED'):content.find('WTF_CSRF_ENABLED')+50]:
                    csrf_enabled = True
        
        # Check for csrf_token in templates
        templates_dir = os.path.join(self.root_dir, 'templates')
        csrf_in_templates = False
        unprotected_forms = []
        
        if os.path.exists(templates_dir):
            for root, dirs, files in os.walk(templates_dir):
                for file_name in files:
                    if file_name.endswith('.html'):
                        file_path = os.path.join(root, file_name)
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read()
                                # Check if the file contains any forms
                                form_tags = re.findall(r'<form[^>]*>', content)
                                if form_tags:
                                    # Check if csrf_token is used
                                    if 'csrf_token' in content:
                                        csrf_in_templates = True
                                    else:
                                        # Check if it's a form that submits data (has POST method)
                                        for form_tag in form_tags:
                                            if 'method="post"' in form_tag.lower() or "method='post'" in form_tag.lower():
                                                rel_path = os.path.relpath(file_path, templates_dir)
                                                unprotected_forms.append({
                                                    'template': rel_path,
                                                    'form': form_tag[:50] + '...' if len(form_tag) > 50 else form_tag
                                                })
                        except Exception as e:
                            logger.error(f"Error checking template file {file_path}: {e}")
        
        # Check for CSRF exemptions in routes
        routes_dir = os.path.join(self.root_dir, 'routes')
        app_py_path = os.path.join(self.root_dir, 'app.py')
        csrf_exemptions = []
        
        if os.path.exists(routes_dir):
            for file_name in os.listdir(routes_dir):
                if file_name.endswith('.py'):
                    file_path = os.path.join(routes_dir, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            exemptions = re.findall(r'@csrf\.exempt', content)
                            if exemptions:
                                csrf_exemptions.append({
                                    'file': file_name,
                                    'exemptions': len(exemptions)
                                })
                    except Exception as e:
                        logger.error(f"Error checking route file {file_path}: {e}")
        
        if os.path.exists(app_py_path):
            try:
                with open(app_py_path, 'r') as f:
                    content = f.read()
                    exemptions = re.findall(r'@csrf\.exempt', content)
                    if exemptions:
                        csrf_exemptions.append({
                            'file': 'app.py',
                            'exemptions': len(exemptions)
                        })
            except Exception as e:
                logger.error(f"Error checking app.py: {e}")
        
        if csrf_enabled and csrf_in_templates and not unprotected_forms and not csrf_exemptions:
            return {
                'passed': True,
                'severity': 'info',
                'description': "CSRF protection is properly implemented",
                'details': {
                    'csrf_enabled': csrf_enabled,
                    'csrf_in_templates': csrf_in_templates
                }
            }
        else:
            issues = []
            if not csrf_enabled:
                issues.append("CSRF protection is not enabled in config")
            if not csrf_in_templates:
                issues.append("No CSRF tokens found in templates")
            if unprotected_forms:
                issues.append(f"Found {len(unprotected_forms)} unprotected forms")
            if csrf_exemptions:
                issues.append(f"Found {sum(e['exemptions'] for e in csrf_exemptions)} CSRF exemptions")
            
            return {
                'passed': False,
                'severity': 'high',
                'description': "; ".join(issues),
                'recommendation': "Enable CSRF protection and add csrf_token to all forms",
                'details': {
                    'csrf_enabled': csrf_enabled,
                    'csrf_in_templates': csrf_in_templates,
                    'unprotected_forms': unprotected_forms,
                    'csrf_exemptions': csrf_exemptions
                }
            }
    
    # Performance Checks
    
    def _check_database_performance(self):
        """
        Check database performance metrics
        
        Returns:
            Check results dictionary
        """
        # Check query count
        try:
            query_count = db.session.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")).scalar()
            
            # Get table counts
            table_counts = {}
            inspector = inspect(db.engine)
            for table_name in inspector.get_table_names():
                count = db.session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
                table_counts[table_name] = count
            
            # Get largest tables
            large_tables = [name for name, count in table_counts.items() if count > 10000]
            
            # Check index usage (simplified for SQLite)
            index_info = []
            for table_name in inspector.get_table_names():
                indices = inspector.get_indexes(table_name)
                index_info.append({
                    'table': table_name,
                    'index_count': len(indices),
                    'indices': [idx['name'] for idx in indices]
                })
            
            # Find tables without indices
            tables_without_indices = [info['table'] for info in index_info if info['index_count'] == 0]
            
            # Identify potential performance issues
            issues = []
            
            if large_tables:
                issues.append(f"Large tables found: {', '.join(large_tables)}")
            
            if tables_without_indices:
                large_tables_without_indices = [t for t in tables_without_indices if t in large_tables]
                if large_tables_without_indices:
                    issues.append(f"Large tables without indices: {', '.join(large_tables_without_indices)}")
            
            if not issues:
                return {
                    'passed': True,
                    'severity': 'info',
                    'description': "Database performance metrics look good",
                    'details': {
                        'table_count': len(table_counts),
                        'total_records': sum(table_counts.values()),
                        'largest_tables': sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    }
                }
            else:
                return {
                    'passed': False,
                    'severity': 'medium',
                    'description': "; ".join(issues),
                    'recommendation': "Consider adding indices to large tables and optimizing queries",
                    'details': {
                        'table_count': len(table_counts),
                        'total_records': sum(table_counts.values()),
                        'largest_tables': sorted(table_counts.items(), key=lambda x: x[1], reverse=True)[:5],
                        'tables_without_indices': tables_without_indices,
                        'index_info': index_info
                    }
                }
        except Exception as e:
            logger.error(f"Error checking database performance: {e}")
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Error checking database performance: {str(e)}",
                'recommendation': "Investigate database connection and query issues",
                'details': {
                    'error': str(e)
                }
            }
    
    def _check_memory_usage(self):
        """
        Check memory usage of the application
        
        Returns:
            Check results dictionary
        """
        try:
            # Get memory usage
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_usage_mb = memory_info.rss / 1024 / 1024  # Convert to MB
            
            # Get system memory info
            system_memory = psutil.virtual_memory()
            system_memory_total_mb = system_memory.total / 1024 / 1024  # Convert to MB
            system_memory_used_mb = system_memory.used / 1024 / 1024  # Convert to MB
            system_memory_percent = system_memory.percent
            
            # Calculate app's percentage of system memory
            app_percentage = (memory_usage_mb / system_memory_total_mb) * 100
            
            # Determine if memory usage is excessive
            if app_percentage > 30:
                return {
                    'passed': False,
                    'severity': 'high',
                    'description': f"Application using {app_percentage:.2f}% of system memory ({memory_usage_mb:.2f} MB)",
                    'recommendation': "Investigate memory leaks and optimize memory usage",
                    'details': {
                        'app_memory_mb': memory_usage_mb,
                        'app_percentage': app_percentage,
                        'system_memory_total_mb': system_memory_total_mb,
                        'system_memory_used_mb': system_memory_used_mb,
                        'system_memory_percent': system_memory_percent
                    }
                }
            elif app_percentage > 15:
                return {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Application using {app_percentage:.2f}% of system memory ({memory_usage_mb:.2f} MB)",
                    'recommendation': "Monitor memory usage and optimize if it continues to increase",
                    'details': {
                        'app_memory_mb': memory_usage_mb,
                        'app_percentage': app_percentage,
                        'system_memory_total_mb': system_memory_total_mb,
                        'system_memory_used_mb': system_memory_used_mb,
                        'system_memory_percent': system_memory_percent
                    }
                }
            else:
                return {
                    'passed': True,
                    'severity': 'info',
                    'description': f"Application memory usage is acceptable ({memory_usage_mb:.2f} MB, {app_percentage:.2f}%)",
                    'details': {
                        'app_memory_mb': memory_usage_mb,
                        'app_percentage': app_percentage,
                        'system_memory_total_mb': system_memory_total_mb,
                        'system_memory_used_mb': system_memory_used_mb,
                        'system_memory_percent': system_memory_percent
                    }
                }
        except Exception as e:
            logger.error(f"Error checking memory usage: {e}")
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Error checking memory usage: {str(e)}",
                'recommendation': "Investigate memory monitoring issues",
                'details': {
                    'error': str(e)
                }
            }
    
    def _check_query_performance(self):
        """
        Check for inefficient database queries
        
        Returns:
            Check results dictionary
        """
        # Check Python files for potential N+1 query issues and inefficient queries
        query_issues = []
        
        for root, dirs, files in os.walk(self.root_dir):
            for file_name in files:
                if file_name.endswith('.py'):
                    file_path = os.path.join(root, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                # Check for potential N+1 queries (loop with query inside)
                                if 'for' in line and 'in' in line:
                                    # Check next few lines for query
                                    for j in range(1, min(5, len(lines) - i)):
                                        next_line = lines[i + j]
                                        if any(query_pattern in next_line for query_pattern in ['.query.', '.filter(', '.filter_by(', '.get(']):
                                            query_issues.append({
                                                'file': os.path.relpath(file_path, self.root_dir),
                                                'line': i + 1,
                                                'issue': 'Potential N+1 query issue',
                                                'code': line + '\n' + next_line
                                            })
                                            break
                                
                                # Check for inefficient queries
                                if '.all()' in line and not any(join_pattern in line for join_pattern in ['.join(', '.outerjoin(']):
                                    context = '\n'.join(lines[max(0, i-2):min(len(lines), i+3)])
                                    if any(relationship_pattern in context for relationship_pattern in ['relationship', 'backref']):
                                        query_issues.append({
                                            'file': os.path.relpath(file_path, self.root_dir),
                                            'line': i + 1,
                                            'issue': 'Query without explicit join for relationship',
                                            'code': context
                                        })
                    except Exception as e:
                        logger.error(f"Error checking file {file_path}: {e}")
        
        if not query_issues:
            return {
                'passed': True,
                'severity': 'info',
                'description': "No obvious query performance issues found",
                'details': {}
            }
        else:
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Found {len(query_issues)} potential query performance issues",
                'recommendation': "Review and optimize database queries to avoid N+1 issues and use joins appropriately",
                'details': {
                    'issues': query_issues[:10]  # Limit to first 10 issues to avoid too much data
                }
            }
    
    def _check_application_responsiveness(self):
        """
        Check application responsiveness
        
        Returns:
            Check results dictionary
        """
        # Check error logs for timeout issues
        timeout_issues = []
        
        log_files = [f for f in os.listdir(self.root_dir) if f.endswith('.log')]
        timeout_patterns = [
            r'timeout',
            r'timed out',
            r'connection timeout',
            r'request timed out',
            r'504 Gateway Timeout',
            r'ConnectionTimeoutError'
        ]
        
        for log_file in log_files:
            log_path = os.path.join(self.root_dir, log_file)
            try:
                with open(log_path, 'r') as f:
                    line_num = 0
                    for line in f:
                        line_num += 1
                        for pattern in timeout_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                timeout_issues.append({
                                    'file': log_file,
                                    'line': line_num,
                                    'message': line.strip()
                                })
            except Exception as e:
                logger.error(f"Error checking log file {log_file}: {e}")
        
        # Check ErrorLog table for timeout errors
        db_timeout_errors = []
        try:
            errors = ErrorLog.query.filter(ErrorLog.error_message.like('%timeout%')).all()
            for error in errors:
                db_timeout_errors.append({
                    'id': error.id,
                    'timestamp': error.timestamp.isoformat() if error.timestamp else None,
                    'endpoint': error.endpoint,
                    'message': error.error_message
                })
        except Exception as e:
            logger.error(f"Error querying ErrorLog table: {e}")
        
        total_issues = len(timeout_issues) + len(db_timeout_errors)
        
        if total_issues == 0:
            return {
                'passed': True,
                'severity': 'info',
                'description': "No application responsiveness issues found",
                'details': {}
            }
        else:
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Found {total_issues} timeout/responsiveness issues",
                'recommendation': "Optimize slow operations and implement proper timeout handling",
                'details': {
                    'log_issues': timeout_issues[:5],  # Limit to first 5 issues
                    'db_errors': db_timeout_errors[:5]  # Limit to first 5 errors
                }
            }
    
    def _check_cache_efficiency(self):
        """
        Check for proper cache implementation
        
        Returns:
            Check results dictionary
        """
        # Check for cache implementation
        cache_modules = ['flask_caching', 'cachetools', 'pylibmc', 'redis']
        cache_found = False
        cache_type = None
        
        # Check imports in Python files
        for root, dirs, files in os.walk(self.root_dir):
            if cache_found:
                break
                
            for file_name in files:
                if file_name.endswith('.py'):
                    file_path = os.path.join(root, file_name)
                    try:
                        with open(file_path, 'r') as f:
                            content = f.read()
                            for module in cache_modules:
                                if f"import {module}" in content or f"from {module}" in content:
                                    cache_found = True
                                    cache_type = module
                                    break
                            
                            # Also check for manual caching
                            if not cache_found and ('cache = {}' in content or 'cache = dict()' in content):
                                cache_found = True
                                cache_type = 'manual'
                            
                            if cache_found:
                                break
                    except Exception as e:
                        logger.error(f"Error checking file {file_path}: {e}")
        
        # Check for cache configuration in config
        config_path = os.path.join(self.root_dir, 'config.py')
        cache_config_found = False
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                if 'CACHE_TYPE' in content:
                    cache_config_found = True
        
        # Check for cache usage in code
        if cache_found:
            cache_usage_patterns = [
                r'@cache\.',
                r'cache\.set',
                r'cache\.get',
                r'cache\.delete',
                r'cache\[',
                r'cache\['
            ]
            
            cache_usage_count = 0
            
            for root, dirs, files in os.walk(self.root_dir):
                for file_name in files:
                    if file_name.endswith('.py'):
                        file_path = os.path.join(root, file_name)
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read()
                                for pattern in cache_usage_patterns:
                                    cache_usage_count += len(re.findall(pattern, content))
                        except Exception as e:
                            logger.error(f"Error checking file {file_path}: {e}")
        
            if cache_usage_count > 0:
                return {
                    'passed': True,
                    'severity': 'info',
                    'description': f"Cache implementation found ({cache_type}) with {cache_usage_count} usages",
                    'details': {
                        'cache_type': cache_type,
                        'cache_config_found': cache_config_found,
                        'cache_usage_count': cache_usage_count
                    }
                }
            else:
                return {
                    'passed': False,
                    'severity': 'low',
                    'description': f"Cache implementation found ({cache_type}) but not used effectively",
                    'recommendation': "Implement caching for expensive operations and frequently accessed data",
                    'details': {
                        'cache_type': cache_type,
                        'cache_config_found': cache_config_found,
                        'cache_usage_count': cache_usage_count
                    }
                }
        else:
            return {
                'passed': False,
                'severity': 'medium',
                'description': "No cache implementation found",
                'recommendation': "Implement caching (e.g., Flask-Caching) for expensive operations and frequent queries",
                'details': {
                    'cache_modules_checked': cache_modules
                }
            }
    
    # Data Integrity Checks
    
    def _check_database_consistency(self):
        """
        Check database consistency
        
        Returns:
            Check results dictionary
        """
        # Check for SQLite database integrity
        integrity_issues = []
        
        # Find SQLite database files
        db_files = []
        for root, dirs, files in os.walk(os.path.join(self.root_dir, 'instance')):
            for file_name in files:
                if file_name.endswith('.db') or file_name.endswith('.sqlite'):
                    db_files.append(os.path.join(root, file_name))
        
        # Check integrity of each database
        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("PRAGMA integrity_check")
                result = cursor.fetchone()
                if result[0] != 'ok':
                    integrity_issues.append({
                        'file': os.path.basename(db_file),
                        'error': result[0]
                    })
                conn.close()
            except Exception as e:
                logger.error(f"Error checking database integrity for {db_file}: {e}")
                integrity_issues.append({
                    'file': os.path.basename(db_file),
                    'error': str(e)
                })
        
        # Check for inconsistent data
        data_inconsistencies = []
        
        try:
            # Check if transactions reference valid accounts
            invalid_transactions = Transaction.query.filter(
                Transaction.account_id.isnot(None)
            ).outerjoin(
                Account, Transaction.account_id == Account.id
            ).filter(
                Account.id.is_(None)
            ).count()
            
            if invalid_transactions > 0:
                data_inconsistencies.append({
                    'issue': 'Transactions referencing non-existent accounts',
                    'count': invalid_transactions
                })
            
            # Check if uploaded files reference valid users
            invalid_files = UploadedFile.query.outerjoin(
                User, UploadedFile.user_id == User.id
            ).filter(
                User.id.is_(None)
            ).count()
            
            if invalid_files > 0:
                data_inconsistencies.append({
                    'issue': 'Uploaded files referencing non-existent users',
                    'count': invalid_files
                })
            
        except Exception as e:
            logger.error(f"Error checking data consistency: {e}")
            data_inconsistencies.append({
                'issue': 'Error checking data consistency',
                'error': str(e)
            })
        
        total_issues = len(integrity_issues) + len(data_inconsistencies)
        
        if total_issues == 0:
            return {
                'passed': True,
                'severity': 'info',
                'description': "Database integrity and consistency checks passed",
                'details': {
                    'databases_checked': [os.path.basename(db) for db in db_files]
                }
            }
        else:
            return {
                'passed': False,
                'severity': 'critical',
                'description': f"Found {total_issues} database integrity/consistency issues",
                'recommendation': "Repair database integrity issues and fix inconsistent data",
                'details': {
                    'integrity_issues': integrity_issues,
                    'data_inconsistencies': data_inconsistencies,
                    'databases_checked': [os.path.basename(db) for db in db_files]
                }
            }
    
    def _check_orphaned_records(self):
        """
        Check for orphaned records in the database
        
        Returns:
            Check results dictionary
        """
        orphaned_records = []
        
        try:
            # Get table relationships
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            for table_name in tables:
                foreign_keys = inspector.get_foreign_keys(table_name)
                for fk in foreign_keys:
                    referred_table = fk.get('referred_table')
                    referred_columns = fk.get('referred_columns', [])
                    constrained_columns = fk.get('constrained_columns', [])
                    
                    if referred_table and referred_columns and constrained_columns:
                        # Check for orphaned records
                        query = f"""
                        SELECT COUNT(*) FROM {table_name} t
                        LEFT JOIN {referred_table} r ON t.{constrained_columns[0]} = r.{referred_columns[0]}
                        WHERE t.{constrained_columns[0]} IS NOT NULL AND r.{referred_columns[0]} IS NULL
                        """
                        
                        try:
                            count = db.session.execute(text(query)).scalar()
                            if count > 0:
                                orphaned_records.append({
                                    'table': table_name,
                                    'foreign_key': constrained_columns[0],
                                    'referenced_table': referred_table,
                                    'referenced_column': referred_columns[0],
                                    'count': count
                                })
                        except Exception as e:
                            logger.error(f"Error checking orphaned records for {table_name}: {e}")
            
            if not orphaned_records:
                return {
                    'passed': True,
                    'severity': 'info',
                    'description': "No orphaned records found in database",
                    'details': {
                        'tables_checked': len(tables)
                    }
                }
            else:
                return {
                    'passed': False,
                    'severity': 'high',
                    'description': f"Found {len(orphaned_records)} tables with orphaned records",
                    'recommendation': "Clean up orphaned records and ensure referential integrity",
                    'details': {
                        'orphaned_records': orphaned_records,
                        'tables_checked': len(tables)
                    }
                }
        except Exception as e:
            logger.error(f"Error checking orphaned records: {e}")
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Error checking orphaned records: {str(e)}",
                'recommendation': "Investigate database error and rerun check",
                'details': {
                    'error': str(e)
                }
            }
    
    def _check_data_validation(self):
        """
        Check for proper data validation in models
        
        Returns:
            Check results dictionary
        """
        models_path = os.path.join(self.root_dir, 'models.py')
        validation_issues = []
        
        if os.path.exists(models_path):
            try:
                with open(models_path, 'r') as f:
                    content = f.read()
                    
                    # Look for model classes
                    model_classes = re.findall(r'class\s+(\w+)\(db\.Model\):', content)
                    
                    for model_class in model_classes:
                        # Skip certain models
                        if model_class in ('User', 'Base'):
                            continue
                            
                        # Find the class body
                        class_match = re.search(r'class\s+' + model_class + r'\(db\.Model\):.*?(?=class|\Z)', content, re.DOTALL)
                        if class_match:
                            class_body = class_match.group(0)
                            
                            # Check for potential validation issues
                            
                            # Look for nullable string columns without length limit
                            unlimited_strings = re.findall(r'(\w+)\s*=\s*db\.Column\(db\.String\(\s*\),', class_body)
                            if unlimited_strings:
                                validation_issues.append({
                                    'model': model_class,
                                    'issue': 'String columns without length limit',
                                    'columns': unlimited_strings
                                })
                            
                            # Look for required fields without nullable=False
                            required_fields = re.findall(r'(\w+)\s*=\s*db\.Column\(.*[^\w]required\s*=\s*True[^\w].*\)', class_body)
                            nullable_fields = re.findall(r'(\w+)\s*=\s*db\.Column\(.*[^\w]nullable\s*=\s*False[^\w].*\)', class_body)
                            
                            # Fields that are required but not marked as nullable=False
                            missing_nullable = [field for field in required_fields if field not in nullable_fields]
                            if missing_nullable:
                                validation_issues.append({
                                    'model': model_class,
                                    'issue': 'Required fields without nullable=False',
                                    'columns': missing_nullable
                                })
                            
                            # Check for lack of validation/check methods
                            if not re.search(r'def\s+validate', class_body) and not re.search(r'def\s+check', class_body):
                                validation_issues.append({
                                    'model': model_class,
                                    'issue': 'No validation methods found in model',
                                    'columns': []
                                })
            except Exception as e:
                logger.error(f"Error checking data validation: {e}")
                return {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Error checking data validation: {str(e)}",
                    'recommendation': "Investigate file parsing error and rerun check",
                    'details': {
                        'error': str(e)
                    }
                }
        
        if not validation_issues:
            return {
                'passed': True,
                'severity': 'info',
                'description': "No obvious data validation issues found in models",
                'details': {}
            }
        else:
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Found {len(validation_issues)} potential data validation issues",
                'recommendation': "Add proper validation to models with nullable constraints and validation methods",
                'details': {
                    'validation_issues': validation_issues
                }
            }
    
    def _check_backup_integrity(self):
        """
        Check backup integrity
        
        Returns:
            Check results dictionary
        """
        backup_dir = os.path.join(self.root_dir, 'backups')
        if not os.path.exists(backup_dir):
            return {
                'passed': False,
                'severity': 'high',
                'description': "Backup directory not found",
                'recommendation': "Set up a proper backup system with scheduled backups",
                'details': {
                    'backup_dir': backup_dir
                }
            }
        
        # Check backup files
        backup_files = []
        for file_name in os.listdir(backup_dir):
            if file_name.endswith('.db') or file_name.endswith('.sql'):
                file_path = os.path.join(backup_dir, file_name)
                backup_files.append({
                    'name': file_name,
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'modified': datetime.datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                })
        
        if not backup_files:
            return {
                'passed': False,
                'severity': 'high',
                'description': "No backup files found in backup directory",
                'recommendation': "Set up a proper backup system with scheduled backups",
                'details': {
                    'backup_dir': backup_dir
                }
            }
        
        # Check for recent backups
        now = datetime.datetime.now()
        recent_backups = []
        for backup in backup_files:
            modified = datetime.datetime.fromisoformat(backup['modified'])
            days_old = (now - modified).days
            backup['days_old'] = days_old
            if days_old <= 7:  # Consider backups within last week as recent
                recent_backups.append(backup)
        
        if not recent_backups:
            return {
                'passed': False,
                'severity': 'high',
                'description': "No recent backups found (within last 7 days)",
                'recommendation': "Set up regular scheduled backups (daily or weekly)",
                'details': {
                    'backup_count': len(backup_files),
                    'newest_backup_days': min([b['days_old'] for b in backup_files]) if backup_files else None,
                    'recent_backups': recent_backups
                }
            }
        
        # Check for very small backups (potential corruption)
        problematic_backups = []
        for backup in backup_files:
            # Flag suspiciously small backups
            if backup['size'] < 1024:  # Smaller than 1 KB
                problematic_backups.append({
                    'name': backup['name'],
                    'size': backup['size'],
                    'issue': 'Suspiciously small size'
                })
        
        if problematic_backups:
            return {
                'passed': False,
                'severity': 'high',
                'description': f"Found {len(problematic_backups)} potentially corrupted backup files",
                'recommendation': "Check and replace corrupted backups, and establish backup verification",
                'details': {
                    'problematic_backups': problematic_backups,
                    'backup_count': len(backup_files),
                    'recent_backups': len(recent_backups)
                }
            }
        
        return {
            'passed': True,
            'severity': 'info',
            'description': f"Backup system is working properly with {len(recent_backups)} recent backups",
            'details': {
                'backup_count': len(backup_files),
                'recent_backups': len(recent_backups),
                'backup_files': [b['name'] for b in recent_backups]
            }
        }
    
    def _check_file_integrity(self):
        """
        Check file integrity for uploaded files
        
        Returns:
            Check results dictionary
        """
        uploads_dir = os.path.join(self.root_dir, 'uploads')
        if not os.path.exists(uploads_dir):
            return {
                'passed': True,
                'severity': 'info',
                'description': "Uploads directory not found or not used",
                'details': {}
            }
        
        integrity_issues = []
        
        try:
            # Get files from database
            uploaded_files = UploadedFile.query.all()
            db_files = set()
            
            for file in uploaded_files:
                if file.file_path:
                    db_files.add(file.file_path)
            
            # Check if files exist on disk
            missing_files = []
            for file_path in db_files:
                if not os.path.exists(file_path):
                    missing_files.append(file_path)
            
            if missing_files:
                integrity_issues.append({
                    'issue': 'Files in database but missing from disk',
                    'count': len(missing_files),
                    'files': missing_files[:5]  # Limit to first 5
                })
            
            # Check for orphaned files on disk
            disk_files = []
            for root, dirs, files in os.walk(uploads_dir):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    disk_files.append(file_path)
            
            orphaned_files = [f for f in disk_files if f not in db_files]
            
            if orphaned_files:
                integrity_issues.append({
                    'issue': 'Files on disk but not in database',
                    'count': len(orphaned_files),
                    'files': orphaned_files[:5]  # Limit to first 5
                })
            
            if not integrity_issues:
                return {
                    'passed': True,
                    'severity': 'info',
                    'description': "File integrity checks passed",
                    'details': {
                        'files_in_db': len(db_files),
                        'files_on_disk': len(disk_files)
                    }
                }
            else:
                return {
                    'passed': False,
                    'severity': 'medium',
                    'description': f"Found {sum(issue['count'] for issue in integrity_issues)} file integrity issues",
                    'recommendation': "Reconcile missing files and clean up orphaned files",
                    'details': {
                        'integrity_issues': integrity_issues,
                        'files_in_db': len(db_files),
                        'files_on_disk': len(disk_files)
                    }
                }
        except Exception as e:
            logger.error(f"Error checking file integrity: {e}")
            return {
                'passed': False,
                'severity': 'medium',
                'description': f"Error checking file integrity: {str(e)}",
                'recommendation': "Investigate file integrity error and rerun check",
                'details': {
                    'error': str(e)
                }
            }