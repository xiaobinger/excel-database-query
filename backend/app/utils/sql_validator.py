import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """验证结果类"""
    is_valid: bool
    message: str
    warnings: List[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SQLValidator:
    """SQL 验证器"""
    
    # 危险关键字列表
    DANGEROUS_KEYWORDS = [
        'DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 
        'INSERT', 'UPDATE', 'GRANT', 'REVOKE'
    ]
    
    # SQL 注入模式
    SQL_INJECTION_PATTERNS = [
        r"--",  # SQL 注释
        r";",   # 多语句分隔符
        #r"\bor\b",  # OR 注入
        #r"\band\b",  # AND 注入
        r"=\s*\w+\s*\(",  # 子查询注入
        r"union\s+select",  # UNION 注入
        r"exec\s*\(",  # EXEC 注入
    ]
    
    def __init__(self):
        """初始化 SQL 验证器"""
        self.table_whitelist: Optional[List[str]] = None
        self.max_result_rows: int = 10000
        self.max_query_length: int = 10000
    
    def validate(self, sql: str, check_tables: bool = True) -> ValidationResult:
        """
        验证 SQL 查询
        
        Args:
            sql: SQL 查询语句
            check_tables: 是否检查表存在性
        
        Returns:
            ValidationResult: 验证结果
        """
        warnings = []
        
        # 1. 基本检查
        if not sql or not sql.strip():
            return ValidationResult(False, "SQL 查询为空")
        
        # 2. 长度检查
        if len(sql) > self.max_query_length:
            warnings.append(f"SQL 查询过长 ({len(sql)} > {self.max_query_length} 字符)")
        
        # 3. 参数检查
        params = self._extract_parameters(sql)
        if not params:
            warnings.append("未检测到查询参数（建议使用 :value 等占位符）")
        
        # 4. 危险关键字检查
        dangerous_found = self._check_dangerous_keywords(sql)
        if dangerous_found:
            return ValidationResult(
                False,
                f"检测到危险关键字: {', '.join(dangerous_found)}",
                warnings
            )
        
        # 5. SQL 注入检查
        injection_risks = self._check_sql_injection(sql)
        if injection_risks:
            return ValidationResult(
                False,
                f"检测到潜在的 SQL 注入风险: {', '.join(injection_risks)}",
                warnings
            )
        
        # 6. 语法检查（基础）
        syntax_errors = self._check_basic_syntax(sql)
        if syntax_errors:
            return ValidationResult(
                False,
                f"SQL 语法错误: {', '.join(syntax_errors)}",
                warnings
            )
        
        # 7. 性能检查
        performance_issues = self._check_performance_issues(sql)
        if performance_issues:
            warnings.extend(performance_issues)
        
        # 8. 表存在性检查
        if check_tables and self.table_whitelist:
            tables = self._extract_tables(sql)
            invalid_tables = [t for t in tables if t not in self.table_whitelist]
            if invalid_tables:
                return ValidationResult(
                    False,
                    f"表不在白名单中: {', '.join(invalid_tables)}",
                    warnings
                )
        
        # 如果有警告但验证通过
        if warnings:
            return ValidationResult(True, "SQL 验证通过，但有警告", warnings)
        
        return ValidationResult(True, "SQL 验证通过")
    
    def _extract_parameters(self, sql: str) -> List[str]:
        """提取 SQL 参数"""
        pattern = r':\w+'
        parameters = re.findall(pattern, sql)
        return list(set(parameters))
    
    def _check_dangerous_keywords(self, sql: str) -> List[str]:
        """检查危险关键字"""
        found = []
        sql_upper = sql.upper()
        
        for keyword in self.DANGEROUS_KEYWORDS:
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, sql_upper):
                found.append(keyword)
        
        return found
    
    def _check_sql_injection(self, sql: str) -> List[str]:
        """检查 SQL 注入模式"""
        risks = []
        sql_lower = sql.lower()
        
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, sql_lower):
                risks.append(pattern)
        
        return risks
    
    def _check_basic_syntax(self, sql: str) -> List[str]:
        """基础语法检查"""
        errors = []
        
        # 检查括号匹配
        open_parens = sql.count('(')
        close_parens = sql.count(')')
        if open_parens != close_parens:
            errors.append(f"括号不匹配: 开 {open_parens}, 关 {close_parens}")
        
        # 检查引号匹配
        single_quotes = sql.count("'")
        double_quotes = sql.count('"')
        if single_quotes % 2 != 0:
            errors.append("单引号不匹配")
        if double_quotes % 2 != 0:
            errors.append("双引号不匹配")
        
        # 检查 SELECT 语句
        if 'SELECT' in sql.upper():
            if not re.search(r'SELECT\s+.+\s+FROM', sql, re.IGNORECASE):
                errors.append("SELECT 语句缺少 FROM 子句")
        
        # 检查 WHERE 子句中的参数
        if 'WHERE' in sql.upper():
            if not re.search(r':\w+', sql):
                errors.append("WHERE 子句中缺少参数占位符")
        
        return errors
    
    def _check_performance_issues(self, sql: str) -> List[str]:
        """检查性能问题"""
        issues = []
        sql_upper = sql.upper()
        
        # 检查 SELECT *
        if 'SELECT *' in sql_upper:
            issues.append("使用 SELECT * 可能影响性能（建议指定列名）")
        
        # 检查缺少 LIMIT
        if 'SELECT' in sql_upper and 'LIMIT' not in sql_upper:
            if 'TOP' not in sql_upper:
                issues.append("建议添加 LIMIT 或 TOP 子句限制结果集大小")
        
        # 检查子查询
        subquery_count = sql.count('(')
        if subquery_count > 3:
            issues.append(f"包含 {subquery_count} 个子查询，可能影响性能")
        
        # 检查 LIKE 开头的通配符
        if re.search(r'LIKE\s+[\'"]%', sql, re.IGNORECASE):
            issues.append("LIKE 以 % 开头可能无法使用索引")
        
        return issues
    
    def _extract_tables(self, sql: str) -> List[str]:
        """提取表名"""
        tables = []
        sql_upper = sql.upper()
        
        # 提取 FROM 子句中的表
        from_match = re.search(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_upper)
        if from_match:
            tables.append(from_match.group(1))
        
        # 提取 JOIN 子句中的表
        join_matches = re.findall(r'(?:INNER|LEFT|RIGHT|FULL|CROSS)\s+JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_upper)
        tables.extend(join_matches)
        
        # 提取 UPDATE/INSERT/DELETE 中的表
        update_match = re.search(r'(?:UPDATE|INSERT\s+INTO|DELETE\s+FROM)\s+([a-zA-Z_][a-zA-Z0-9_]*)', sql_upper)
        if update_match:
            tables.append(update_match.group(1))
        
        return list(set(tables))
    
    def suggest_improvements(self, sql: str) -> List[str]:
        """建议 SQL 改进"""
        suggestions = []
        sql_upper = sql.upper()
        
        # 建议使用索引列
        if 'WHERE' in sql_upper:
            if re.search(r'WHERE\s+\w+\s*=\s*:\w+', sql, re.IGNORECASE):
                suggestions.append("确保 WHERE 子句中的列有索引")
        
        # 建议使用 EXISTS 替代 IN
        if re.search(r'IN\s*\([^)]+\)', sql, re.IGNORECASE):
            suggestions.append("对于大列表，考虑使用 EXISTS 替代 IN")
        
        # 建议使用 UNION ALL 替代 UNION
        if 'UNION' in sql_upper and 'UNION ALL' not in sql_upper:
            suggestions.append("如果确定没有重复，使用 UNION ALL 替代 UNION 以提高性能")
        
        return suggestions
    
    def format_sql(self, sql: str) -> str:
        """格式化 SQL（美化）"""
        try:
            keywords = ['SELECT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 
                      'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT', 'UNION',
                      'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP']
            
            formatted_sql = sql
            for keyword in keywords:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                formatted_sql = re.sub(pattern, keyword, formatted_sql, flags=re.IGNORECASE)
            
            # 添加换行和缩进
            formatted_sql = re.sub(r'\s+FROM', '\nFROM', formatted_sql, flags=re.IGNORECASE)
            formatted_sql = re.sub(r'\s+WHERE', '\nWHERE', formatted_sql, flags=re.IGNORECASE)
            formatted_sql = re.sub(r'\s+JOIN', '\n  JOIN', formatted_sql, flags=re.IGNORECASE)
            formatted_sql = re.sub(r'\s+GROUP BY', '\nGROUP BY', formatted_sql, flags=re.IGNORECASE)
            formatted_sql = re.sub(r'\s+ORDER BY', '\nORDER BY', formatted_sql, flags=re.IGNORECASE)
            
            return formatted_sql.strip()
            
        except Exception as e:
            logger.warning(f"格式化 SQL 失败: {str(e)}")
            return sql
    
    def _find_matching_paren(self, s: str, start_idx: int) -> int:
        """
        找到匹配的右括号位置
        
        Args:
            s: 字符串
            start_idx: 起始位置（左括号位置）
        
        Returns:
            匹配的右括号位置，如果没找到返回 -1
        """
        count = 1
        for i in range(start_idx + 1, len(s)):
            if s[i] == '(':
                count += 1
            elif s[i] == ')':
                count -= 1
                if count == 0:
                    return i
        return -1
    
    def extract_column_names(self, sql: str) -> List[str]:
        """
        从 SQL 查询中提取列名，支持处理 IF、IFNULL、IS NOT NULL、CASE WHEN...THEN...END 等关键字
        
        Args:
            sql: SQL 查询语句
        
        Returns:
            列名列表
        """
        try:
            # 移除注释
            sql_clean = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
            sql_clean = re.sub(r'/\*.*?\*/', '', sql_clean, flags=re.DOTALL)
            
            # 查找 SELECT 和 FROM 之间的内容
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_clean, re.IGNORECASE | re.DOTALL)
            
            if not select_match:
                return []
            
            select_clause = select_match.group(1).strip()
            
            # 处理 DISTINCT 关键字
            select_clause = re.sub(r'DISTINCT\s+', '', select_clause, flags=re.IGNORECASE)
            
            # 分割列（需要处理嵌套括号中的逗号）
            columns = []
            current_col = ''
            paren_count = 0
            
            for char in select_clause:
                if char == '(':
                    paren_count += 1
                    current_col += char
                elif char == ')':
                    paren_count -= 1
                    current_col += char
                elif char == ',' and paren_count == 0:
                    current_col = current_col.strip()
                    if current_col:
                        columns.append(current_col)
                    current_col = ''
                else:
                    current_col += char
            
            # 添加最后一个列
            current_col = current_col.strip()
            if current_col:
                columns.append(current_col)
            
            # 提取每个列的名称
            result = []
            for col in columns:
                col = col.strip()
                
                if not col:
                    continue
                
                # 处理 AS 别名（优先处理，因为别名优先级最高）
                as_match = re.search(r'\s+AS\s+(\w+)$', col, re.IGNORECASE)
                if as_match:
                    result.append(as_match.group(1))
                    continue
                
                # 处理不带 AS 的别名（如 column_name alias_name）
                # 匹配最后一个单词，前提是前面有空格且不是关键字
                alias_match = re.search(r'\s+(\w+)$', col)
                if alias_match:
                    alias = alias_match.group(1).upper()
                    # 检查是否是 SQL 关键字
                    if alias not in ['AS', 'FROM', 'WHERE', 'AND', 'OR', 'IN', 'ON', 'JOIN', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END']:
                        result.append(alias_match.group(1))
                        continue
                
                # 处理 CASE WHEN...THEN...END 表达式
                case_match = re.search(r'CASE\s+(.+?)\s+END', col, re.IGNORECASE | re.DOTALL)
                if case_match:
                    result.append('CASE')
                    continue
                
                # 处理 IF(expr1, expr2, expr3) 函数（带别名）
                if_match = re.match(r'IF\s*\(', col, re.IGNORECASE)
                if if_match:
                    paren_end = self._find_matching_paren(col, if_match.end() - 1)
                    if paren_end != -1:
                        # 检查是否有别名
                        remaining = col[paren_end + 1:].strip()
                        as_match = re.match(r'(?:AS\s+)?(\w+)', remaining, re.IGNORECASE)
                        if as_match:
                            result.append(as_match.group(1))
                        else:
                            result.append('IF')
                    continue
                
                # 处理 IFNULL(expr1, expr2) 函数（带别名）
                ifnull_match = re.match(r'IFNULL\s*\(', col, re.IGNORECASE)
                if ifnull_match:
                    paren_end = self._find_matching_paren(col, ifnull_match.end() - 1)
                    if paren_end != -1:
                        # 检查是否有别名
                        remaining = col[paren_end + 1:].strip()
                        as_match = re.match(r'(?:AS\s+)?(\w+)', remaining, re.IGNORECASE)
                        if as_match:
                            result.append(as_match.group(1))
                        else:
                            result.append('IFNULL')
                    continue
                
                # 处理 IS NOT NULL 判断（如 column IS NOT NULL）
                is_not_null_match = re.search(r'(\w+)\s+IS\s+NOT\s+NULL', col, re.IGNORECASE)
                if is_not_null_match:
                    result.append(is_not_null_match.group(1))
                    continue
                
                # 处理 IS NULL 判断（如 column IS NULL）
                is_null_match = re.search(r'(\w+)\s+IS\s+NULL', col, re.IGNORECASE)
                if is_null_match:
                    result.append(is_null_match.group(1))
                    continue
                
                # 处理函数（如 COUNT(*), MAX(a.column), SUM(column) 等）
                func_match = re.match(r'(\w+)\s*\(', col)
                if func_match:
                    result.append(func_match.group(1))
                    continue
                
                # 处理表别名（如 a.column_name）
                table_col_match = re.search(r'(?:\w+\.|)(\w+)$', col)
                if table_col_match:
                    result.append(table_col_match.group(1))
                    continue
                
                # 处理通配符 *
                if col == '*':
                    result.append('*')
                    continue
                
                # 直接使用列名
                result.append(col)
            
            logger.info(f"从 SQL 提取到列名: {result}")
            return result
            
        except Exception as e:
            logger.warning(f"提取列名失败: {str(e)}")
            return []
