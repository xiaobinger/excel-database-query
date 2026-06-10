import hashlib
import hmac
import json
import logging
import re
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy import text

from app import db
from app.models.database import DatabaseConnection
from app.models.script import Script
from app.models.system_task import SystemTask, SystemTaskExecution
from app.utils.db_connector import DatabaseConnector
from app.utils.helpers import beijing_isoformat
from app.utils.sql_validator import SQLValidator

logger = logging.getLogger(__name__)

_execution_progress = {}
_execution_lock = threading.Lock()


def update_execution_progress(execution_id: str, progress: int, log_message: str = None, level: str = 'info'):
    with _execution_lock:
        _execution_progress[execution_id] = {
            'progress': progress,
            'log_message': log_message,
            'level': level,
            'timestamp': beijing_isoformat(datetime.utcnow())
        }


def get_execution_progress(execution_id: str) -> dict:
    with _execution_lock:
        return _execution_progress.get(execution_id, {'progress': 0})


class SystemTaskService:

    @staticmethod
    def create_execution(system_task_id: int, params_values: Dict[str, Any],
                         created_by: int = None) -> SystemTaskExecution:
        execution_id = str(uuid.uuid4())
        execution = SystemTaskExecution(
            execution_id=execution_id,
            system_task_id=system_task_id,
            status='pending',
            params_values=json.dumps(params_values, ensure_ascii=False) if params_values else None,
            created_by=created_by,
        )
        db.session.add(execution)
        db.session.commit()
        return execution

    @staticmethod
    def execute_async(execution_id: str, system_task_id: int, params_values: Dict[str, Any]):
        thread = threading.Thread(
            target=SystemTaskService._execute_background,
            args=(execution_id, system_task_id, params_values),
            daemon=True
        )
        thread.start()

    @staticmethod
    def _execute_background(execution_id: str, system_task_id: int, params_values: Dict[str, Any]):
        try:
            from app import create_app
            app = create_app()
        except Exception:
            from flask import current_app
            app = current_app._get_current_object()

        with app.app_context():
            execution = SystemTaskExecution.query.filter_by(execution_id=execution_id).first()
            if not execution:
                return

            system_task = SystemTask.query.get(system_task_id)
            if not system_task:
                execution.status = 'failed'
                execution.error_message = '系统任务不存在'
                execution.completed_at = datetime.utcnow()
                db.session.commit()
                return

            execution.task_type = system_task.task_type
            db.session.commit()

            try:
                execution.status = 'running'
                execution.started_at = datetime.utcnow()
                execution.progress = 5
                execution.add_log('开始执行系统任务')
                db.session.commit()
                update_execution_progress(execution_id, 5, '开始执行系统任务')

                if system_task.task_type == 'sql':
                    SystemTaskService._execute_sql(execution, system_task, params_values)
                elif system_task.task_type == 'api':
                    SystemTaskService._execute_api(execution, system_task, params_values)
                else:
                    raise ValueError(f'不支持的任务类型: {system_task.task_type}')

            except Exception as e:
                logger.error(f"系统任务执行失败: {str(e)}", exc_info=True)
                execution.status = 'failed'
                execution.completed_at = datetime.utcnow()
                execution.error_message = str(e)
                execution.progress = 100
                execution.add_log(f'执行失败: {str(e)}', 'error')
                db.session.commit()
                update_execution_progress(execution_id, 100, f'执行失败: {str(e)}', 'error')

    @staticmethod
    def _split_sql_statements(sql: str) -> List[str]:
        """Split SQL into individual statements, respecting string literals."""
        # Remove single-line comments
        sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        # Remove multi-line comments
        sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)

        statements = []
        current = []
        in_string = False
        string_char = None
        prev_char = None

        for char in sql:
            if not in_string:
                if char in ("'", '"', '`'):
                    in_string = True
                    string_char = char
                elif char == ';':
                    stmt = ''.join(current).strip()
                    if stmt:
                        statements.append(stmt)
                    current = []
                    continue
            else:
                if char == string_char and prev_char != '\\':
                    in_string = False
                    string_char = None
            current.append(char)
            prev_char = char

        stmt = ''.join(current).strip()
        if stmt:
            statements.append(stmt)

        return statements

    @staticmethod
    def _is_query_statement(sql: str) -> bool:
        first_word = sql.strip().split()[0].upper()
        return first_word in ('SELECT', 'SHOW', 'DESCRIBE', 'DESC', 'EXPLAIN')

    @staticmethod
    def _execute_sql(execution: SystemTaskExecution, system_task: SystemTask,
                     params_values: Dict[str, Any]):
        execution_id = execution.execution_id
        execution.progress = 10
        execution.add_log('执行SQL类型系统任务')
        db.session.commit()
        update_execution_progress(execution_id, 10, '执行SQL类型系统任务')

        script = Script.query.get(system_task.script_id) if system_task.script_id else None
        if not script:
            raise ValueError('关联的SQL脚本不存在')

        sql_text = script.sql_text
        if not sql_text:
            raise ValueError('SQL脚本内容为空')

        # Validate SQL (allow DML for system tasks)
        validator = SQLValidator()
        validation = validator.validate(sql_text, allow_dml=True)
        if not validation.is_valid:
            raise ValueError(f'SQL验证失败: {validation.message}')

        # Replace placeholders {{param}} in SQL
        if params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in sql_text:
                    val_str = str(val)
                    sql_text = sql_text.replace(placeholder, val_str)

        # 过滤空值参数（SQLAlchemy bind parameter不允许None值）
        filtered_params = {}
        if params_values:
            for k, v in params_values.items():
                if v is not None and v != '' and v != []:
                    filtered_params[k] = v

        # Split into multiple statements
        statements = SystemTaskService._split_sql_statements(sql_text)
        if not statements:
            raise ValueError('没有可执行的SQL语句')

        execution.progress = 20
        execution.add_log(f'SQL准备完成，共 {len(statements)} 条语句')
        db.session.commit()
        update_execution_progress(execution_id, 20, f'SQL准备完成，共 {len(statements)} 条语句')

        db_ids = system_task.get_database_ids()
        if not db_ids:
            db_ids = script.get_database_ids()
        if not db_ids:
            raise ValueError('没有配置数据库连接')

        all_results = []
        total_dbs = len(db_ids)

        for idx, conn_id in enumerate(db_ids):
            conn_model = DatabaseConnection.query.get(conn_id)
            if not conn_model:
                execution.add_log(f'数据库连接不存在: {conn_id}', 'warning')
                continue

            try:
                connector = DatabaseConnector(conn_model.to_config_dict())
                if not connector.test_connection():
                    execution.add_log(f'数据库连接测试失败: {conn_model.name}', 'warning')
                    continue

                execution.add_log(f'连接到数据库: {conn_model.name}')

                db_results = []
                total_affected = 0

                with connector.get_connection() as conn:
                    for stmt_idx, stmt in enumerate(statements):
                        if not stmt.strip():
                            continue

                        is_query = SystemTaskService._is_query_statement(stmt)
                        # 如果有bind parameter，将其作为参数传入
                        result = conn.execute(text(stmt), filtered_params) if filtered_params else conn.execute(text(stmt))

                        if is_query:
                            rows_data = []
                            column_headers = list(result.keys()) if hasattr(result, 'keys') else []
                            rows = result.fetchall()
                            for row in rows:
                                row_dict = {}
                                if column_headers and len(column_headers) == len(row):
                                    for i, header in enumerate(column_headers):
                                        row_dict[header] = row[i]
                                elif column_headers and len(row) > 0:
                                    for i in range(min(len(column_headers), len(row))):
                                        row_dict[column_headers[i]] = row[i]
                                    for i in range(len(column_headers), len(row)):
                                        row_dict[f'extra_col_{i}'] = row[i]
                                else:
                                    for i, val in enumerate(row):
                                        row_dict[f'col_{i}'] = val
                                rows_data.append(row_dict)

                            db_results.append({
                                'statement_index': stmt_idx,
                                'statement': stmt[:200],
                                'type': 'query',
                                'rows': rows_data,
                                'columns': column_headers,
                                'row_count': len(rows_data),
                            })
                            execution.add_log(f'语句 {stmt_idx + 1}: 查询完成，返回 {len(rows_data)} 行')
                        else:
                            rowcount = result.rowcount if hasattr(result, 'rowcount') else 0
                            total_affected += rowcount
                            db_results.append({
                                'statement_index': stmt_idx,
                                'statement': stmt[:200],
                                'type': 'command',
                                'rowcount': rowcount,
                            })
                            execution.add_log(f'语句 {stmt_idx + 1}: 执行完成，影响 {rowcount} 行')

                all_results.append({
                    'db_name': conn_model.name,
                    'db_id': conn_id,
                    'statements': db_results,
                    'total_affected': total_affected,
                    'success': True,
                })
                execution.add_log(f'数据库 {conn_model.name} 执行完成，{len(statements)} 条语句')

                connector.close()
            except Exception as e:
                all_results.append({
                    'db_name': conn_model.name if conn_model else str(conn_id),
                    'db_id': conn_id,
                    'statements': [],
                    'total_affected': 0,
                    'success': False,
                    'error': str(e),
                })
                execution.add_log(f'数据库 {conn_model.name if conn_model else conn_id} 执行失败: {str(e)}', 'error')

            progress = 20 + int(60 * (idx + 1) / total_dbs)
            execution.progress = min(progress, 80)
            db.session.commit()
            update_execution_progress(execution_id, execution.progress, f'数据库执行进度')

        total_affected = sum(r.get('total_affected', 0) for r in all_results)
        success_count = sum(1 for r in all_results if r.get('success'))
        failure_count = len(all_results) - success_count

        execution.set_result_data({
            'results': all_results,
            'total_affected': total_affected,
            'success_count': success_count,
            'failure_count': failure_count,
        })

        execution.progress = 100
        execution.status = 'completed' if failure_count == 0 else 'failed' if success_count == 0 else 'completed'
        execution.completed_at = datetime.utcnow()
        execution.add_log(f'SQL任务执行完成，成功数据库 {success_count} 个，失败 {failure_count} 个')
        db.session.commit()
        update_execution_progress(execution_id, 100, 'SQL任务执行完成')

    @staticmethod
    def _execute_api(execution: SystemTaskExecution, system_task: SystemTask,
                     params_values: Dict[str, Any]):
        execution_id = execution.execution_id
        execution.progress = 10
        execution.add_log('执行API类型系统任务')
        db.session.commit()
        update_execution_progress(execution_id, 10, '执行API类型系统任务')

        if not system_task.api_url:
            raise ValueError('API地址未配置')

        url = system_task.api_url
        method = (system_task.api_method or 'POST').upper()
        headers = system_task.get_api_headers()
        timeout = system_task.api_timeout or 30

        # Prepare params and body
        request_params = dict(params_values) if params_values else {}
        body = system_task.api_body or ''

        # Replace placeholders in body {{param}}
        if body and params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in body:
                    body = body.replace(placeholder, str(val))

        # Replace placeholders in url
        if params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in url:
                    url = url.replace(placeholder, str(val))

        execution.progress = 30
        execution.add_log(f'准备请求: {method} {url}')
        db.session.commit()
        update_execution_progress(execution_id, 30, f'准备请求: {method} {url}')

        # Signing
        if system_task.sign_enabled and system_task.sign_key:
            sign = SystemTaskService._compute_sign(
                request_params, body, headers,
                system_task.sign_key, system_task.sign_method
            )
            sign_name = system_task.sign_param_name or 'sign'
            append_type = system_task.sign_append_type or 'query'

            if append_type == 'query':
                # Add sign to URL query string
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}{sign_name}={sign}"
            elif append_type == 'body':
                # Try to add to JSON body
                try:
                    body_obj = json.loads(body) if body else {}
                    if isinstance(body_obj, dict):
                        body_obj[sign_name] = sign
                        body = json.dumps(body_obj, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    # If body is not JSON, append as form param
                    if 'application/x-www-form-urlencoded' in headers.get('Content-Type', ''):
                        body = f"{body}&{sign_name}={sign}" if body else f"{sign_name}={sign}"
                    else:
                        execution.add_log('签名附加到body失败，body不是有效的JSON', 'warning')
            elif append_type == 'header':
                headers[sign_name] = sign

            execution.add_log(f'已生成签名并附加到{append_type}')

        execution.progress = 50
        db.session.commit()
        update_execution_progress(execution_id, 50, '发送API请求')

        # Parse body for JSON content-type
        request_body = body
        if headers.get('Content-Type', '').startswith('application/json') and body:
            try:
                request_body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                pass

        # Make request
        try:
            if method == 'GET':
                # For GET, pass request_params as query params
                resp = requests.get(url, headers=headers, params=request_params, timeout=timeout)
            elif method == 'POST':
                if isinstance(request_body, dict):
                    resp = requests.post(url, headers=headers, json=request_body, timeout=timeout)
                else:
                    resp = requests.post(url, headers=headers, data=request_body, timeout=timeout)
            elif method == 'PUT':
                if isinstance(request_body, dict):
                    resp = requests.put(url, headers=headers, json=request_body, timeout=timeout)
                else:
                    resp = requests.put(url, headers=headers, data=request_body, timeout=timeout)
            elif method == 'DELETE':
                resp = requests.delete(url, headers=headers, params=request_params, timeout=timeout)
            else:
                raise ValueError(f'不支持的HTTP方法: {method}')

            execution.progress = 80
            execution.add_log(f'API响应状态码: {resp.status_code}')
            db.session.commit()
            update_execution_progress(execution_id, 80, f'API响应状态码: {resp.status_code}')

            # Try to parse response as JSON
            try:
                resp_data = resp.json()
                resp_text = json.dumps(resp_data, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                resp_data = resp.text
                resp_text = resp.text

            is_success = 200 <= resp.status_code < 300

            execution.set_result_data({
                'status_code': resp.status_code,
                'response': resp_data if isinstance(resp_data, (dict, list)) else resp_text,
                'response_headers': dict(resp.headers),
                'success': is_success,
            })

            execution.progress = 100
            execution.status = 'completed' if is_success else 'failed'
            execution.completed_at = datetime.utcnow()
            if not is_success:
                execution.error_message = f'API返回非成功状态码: {resp.status_code}'
            execution.add_log(f'API请求完成，状态码: {resp.status_code}')
            db.session.commit()
            update_execution_progress(execution_id, 100, f'API请求完成')

        except requests.exceptions.Timeout:
            raise ValueError(f'API请求超时({timeout}秒)')
        except requests.exceptions.RequestException as e:
            raise ValueError(f'API请求失败: {str(e)}')

    @staticmethod
    def _compute_sign(params: Dict[str, Any], body: str, headers: Dict[str, str],
                      sign_key: str, sign_method: str) -> str:
        """Compute signature based on method."""
        # Build sign string from sorted params
        sign_parts = []
        if params:
            for k in sorted(params.keys()):
                sign_parts.append(f"{k}={params[k]}")

        sign_str = '&'.join(sign_parts)

        # Include body in sign if present and method supports it
        if body and sign_method not in ('md5_param_only', 'sha256_param_only'):
            sign_str = f"{sign_str}&body={body}" if sign_str else f"body={body}"

        # Append key
        sign_str = f"{sign_str}{sign_key}"

        method = (sign_method or 'md5').lower()

        if method == 'md5':
            return hashlib.md5(sign_str.encode('utf-8')).hexdigest()
        elif method == 'sha256':
            return hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
        elif method == 'hmac_sha256':
            return hmac.new(sign_key.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha256).hexdigest()
        elif method == 'md5_upper':
            return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()
        elif method == 'sha1':
            return hashlib.sha1(sign_str.encode('utf-8')).hexdigest()
        else:
            # Default to md5
            return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

    @staticmethod
    def get_execution_status(execution_id: str) -> Optional[Dict[str, Any]]:
        execution = SystemTaskExecution.query.filter_by(execution_id=execution_id).first()
        if not execution:
            return None
        result = execution.to_dict()
        progress_info = get_execution_progress(execution_id)
        if progress_info.get('progress', 0) > result.get('progress', 0):
            result['progress'] = progress_info['progress']

        system_task = SystemTask.query.get(execution.system_task_id) if execution.system_task_id else None
        result['system_task_name'] = system_task.name if system_task else '未知'
        result['system_task_type'] = system_task.task_type if system_task else ''
        return result

    @staticmethod
    def cancel_execution(execution_id: str) -> bool:
        execution = SystemTaskExecution.query.filter_by(execution_id=execution_id).first()
        if not execution:
            return False
        if execution.status in ('pending', 'running'):
            execution.status = 'cancelled'
            execution.completed_at = datetime.utcnow()
            execution.add_log('任务已取消', 'warning')
            db.session.commit()
            update_execution_progress(execution_id, 100, '任务已取消', 'warning')
            return True
        return False
