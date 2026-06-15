import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import text

from app import db
from app.models.script import Script
from app.models.database import DatabaseConnection
from app.utils.db_connector import DatabaseConnector
from app.utils.sql_validator import SQLValidator
from app.utils.error_sanitizer import sanitize_error_for_user

logger = logging.getLogger(__name__)


class LookupService:

    @staticmethod
    def execute_lookup(script_id: int, params_values: Dict[str, Any] = None, user_id: int = None) -> Dict[str, Any]:
        """
        执行 lookup 类型的查询，返回查询结果。

        Args:
            script_id: 脚本ID
            params_values: 参数值字典，key 为参数名，value 为参数值
            user_id: 用户ID

        Returns:
            dict: {
                success: bool,
                results: list[dict],  # 每行为一个字典 {列名: 值}
                columns: list[str],   # 列名列表
                row_count: int,
                error_message: str | None
            }
        """
        if params_values is None:
            params_values = {}

        logger.info(f'LookupService.execute_lookup: script_id={script_id}, params_values={params_values}')

        try:
            # 1. 查找脚本
            script = Script.query.get(script_id)
            if not script:
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': f'脚本不存在: {script_id}'
                }

            # 2. 验证脚本类型
            if script.type != 'lookup':
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': '脚本配置错误，请联系管理员'
                }

            # 3. 验证 SQL 为 SELECT 语句（不允许 DML）
            sql = script.sql_text
            validator = SQLValidator()
            validation = validator.validate(sql, check_tables=False, allow_dml=False)
            if not validation.is_valid:
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': 'SQL配置验证失败，请联系管理员'
                }

            # 4. 智能参数映射：确保传入的参数名和SQL中的参数名一致
            script_params = script.get_params_config() or []
            all_sql_params = set(LookupService._extract_bind_params(sql))
            # 也加入 {{param}} 占位符
            all_sql_params.update(re.findall(r'\{\{(\w+)\}\}', sql))

            if params_values and all_sql_params:
                # 构建映射表：各种可能的键名 -> SQL中的参数名
                # 优先级：SQL参数名精确匹配 > 脚本参数配置name映射 > 模糊匹配
                param_to_sql = {}  # 各种可能的键名 -> SQL参数名

                # 1. SQL参数名本身（精确匹配）
                for sql_p in all_sql_params:
                    param_to_sql[sql_p] = sql_p
                    param_to_sql[sql_p.lower()] = sql_p
                    param_to_sql[sql_p.lower().replace('_', '').replace('-', '')] = sql_p

                # 2. 脚本参数配置的name和label映射到SQL参数名
                for p in script_params:
                    p_name = p['name']
                    p_label = (p.get('label') or '').strip()
                    # 如果脚本参数name直接在SQL参数中，映射到自身
                    if p_name in all_sql_params:
                        target = p_name
                    else:
                        # 脚本参数name不在SQL参数中，尝试模糊匹配到SQL参数
                        p_name_lower = p_name.lower().replace('_', '').replace('-', '')
                        target = None
                        for sql_p in all_sql_params:
                            sql_lower = sql_p.lower().replace('_', '').replace('-', '')
                            if p_name_lower == sql_lower or p_name_lower in sql_lower or sql_lower in p_name_lower:
                                target = sql_p
                                break
                        if not target:
                            target = p_name  # 无法映射到SQL参数，保持原样

                    # name的各种变体
                    param_to_sql[p_name] = target
                    param_to_sql[p_name.lower()] = target
                    p_name_normalized = p_name.lower().replace('_', '').replace('-', '')
                    param_to_sql[p_name_normalized] = target
                    # label的各种变体
                    if p_label:
                        param_to_sql[p_label] = target
                        param_to_sql[p_label.lower()] = target
                        p_label_normalized = p_label.lower().replace('_', '').replace('-', '')
                        param_to_sql[p_label_normalized] = target

                # 执行映射
                mapped = {}
                for key, val in params_values.items():
                    if key in all_sql_params:
                        # 键名直接匹配SQL参数，不需要映射
                        mapped[key] = val
                    elif key in param_to_sql:
                        # 通过映射表找到SQL参数名
                        mapped[param_to_sql[key]] = val
                    else:
                        # 尝试小写和去分隔符变体
                        key_lower = key.lower()
                        key_normalized = key_lower.replace('_', '').replace('-', '')
                        if key_lower in param_to_sql:
                            mapped[param_to_sql[key_lower]] = val
                        elif key_normalized in param_to_sql:
                            mapped[param_to_sql[key_normalized]] = val
                        else:
                            # 模糊匹配：尝试和SQL参数名做模糊匹配
                            matched = False
                            for sql_param in all_sql_params:
                                sql_lower = sql_param.lower().replace('_', '').replace('-', '')
                                if key_normalized == sql_lower or key_normalized in sql_lower or sql_lower in key_normalized:
                                    mapped[sql_param] = val
                                    matched = True
                                    break
                            if not matched:
                                mapped[key] = val
                params_values = mapped
                logger.info(f'Lookup参数映射: 映射后={params_values}, SQL参数={all_sql_params}')

            # 5. 替换 {{param}} 占位符
            sql = LookupService._replace_placeholders(sql, params_values)

            # 6. 提取 SQLAlchemy bind 参数 (%(name)s 格式) 并构建 filtered_params
            bind_params = LookupService._extract_bind_params(sql)
            logger.info(f'Lookup SQL bind参数: {bind_params}, 传入参数: {list(params_values.keys())}')
            filtered_params = {}
            missing_bind_params = []
            for param_name in bind_params:
                if param_name in params_values:
                    filtered_params[param_name] = params_values[param_name]
                else:
                    missing_bind_params.append(param_name)

            if missing_bind_params:
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': f'缺少查询参数：{", ".join(missing_bind_params)}'
                }

            # 6. 获取超时时间
            timeout = script.timeout or 30

            # 7. 获取关联的数据库连接
            db_ids = script.get_database_ids()
            if not db_ids:
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': '脚本未配置数据库连接'
                }

            # 8. 在所有关联数据库上执行查询，合并结果
            all_rows = []
            columns = []
            last_error = None

            for conn_id in db_ids:
                conn_model = DatabaseConnection.query.get(conn_id)
                if not conn_model:
                    logger.warning(f'数据库连接不存在: {conn_id}')
                    continue

                try:
                    from app.utils.connection_pool import ConnectionPoolManager
                    pool = ConnectionPoolManager.get_instance()
                    connector = pool.get_connector(conn_id)
                    if not connector:
                        logger.warning(f'数据库连接失败: {conn_model.name}')
                        continue

                    with connector.get_connection() as conn:
                        result = conn.execute(text(sql), filtered_params)

                        # 获取列名
                        if result.cursor and result.cursor.description:
                            columns = [desc[0] for desc in result.cursor.description]

                        # 获取所有行
                        rows = result.fetchall()

                        for row in rows:
                            row_dict = {}
                            for i, col in enumerate(columns):
                                value = row[i]
                                # 处理不可序列化的类型
                                if hasattr(value, 'isoformat'):
                                    value = value.isoformat()
                                elif isinstance(value, (bytes, bytearray)):
                                    value = value.hex()
                                row_dict[col] = value
                            all_rows.append(row_dict)

                except Exception as e:
                    last_error = str(e)
                    logger.error(f'Lookup 查询执行失败 [数据库: {conn_model.name}]: {last_error}')

            # 如果没有任何结果且有错误，返回错误
            if not all_rows and last_error:
                sanitized = sanitize_error_for_user(last_error, False)
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': sanitized['error_message']
                }

            # 如果没有从 cursor 获取到列名，尝试从 SQL 提取
            if not columns and all_rows:
                columns = list(all_rows[0].keys())
            elif not columns:
                columns = SQLValidator().extract_column_names(sql)

            return {
                'success': True,
                'results': all_rows,
                'columns': columns,
                'row_count': len(all_rows),
                'error_message': None
            }

        except Exception as e:
            logger.error(f'Lookup 执行异常: {str(e)}', exc_info=True)
            sanitized = sanitize_error_for_user(str(e), False)
            return {
                'success': False,
                'results': [],
                'columns': [],
                'row_count': 0,
                'error_message': sanitized['error_message']
            }

    @staticmethod
    def _replace_placeholders(sql: str, params_values: Dict[str, Any]) -> str:
        """
        替换 SQL 中的 {{param}} 占位符为参数值。

        Args:
            sql: SQL 语句
            params_values: 参数值字典

        Returns:
            替换后的 SQL 语句
        """
        def replacer(match):
            param_name = match.group(1)
            value = params_values.get(param_name)
            if value is None:
                return match.group(0)
            if isinstance(value, str):
                escaped = value.replace("'", "''")
                return f"'{escaped}'"
            elif isinstance(value, bool):
                return '1' if value else '0'
            elif isinstance(value, (int, float)):
                return str(value)
            else:
                escaped = str(value).replace("'", "''")
                return f"'{escaped}'"

        return re.sub(r'\{\{(\w+)\}\}', replacer, sql)

    @staticmethod
    def _extract_bind_params(sql: str) -> List[str]:
        """
        提取 SQL 中的 SQLAlchemy bind 参数名。
        支持 %(name)s 和 :name 两种格式。
        """
        params = re.findall(r'%\((\w+)\)s', sql)
        # 匹配 :name 格式，但排除 :: （PostgreSQL类型转换）和数字(:1 :2)
        colon_params = re.findall(r'(?<!:):(\w+)', sql)
        # 过滤掉 SQL 关键字
        sql_keywords = {'select', 'from', 'where', 'and', 'or', 'not', 'in', 'is', 'null',
                        'as', 'on', 'join', 'left', 'right', 'inner', 'outer', 'group', 'by',
                        'order', 'having', 'limit', 'offset', 'union', 'all', 'distinct',
                        'insert', 'update', 'delete', 'set', 'values', 'into', 'like',
                        'between', 'exists', 'case', 'when', 'then', 'else', 'end', 'asc', 'desc'}
        for p in colon_params:
            if p.lower() not in sql_keywords and p not in params:
                params.append(p)
        return params
