import hashlib
import hmac
import json
import logging
import os
import re
import subprocess
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
_execution_threads = {}  # execution_id -> thread reference
_execution_cancel_events = {}  # execution_id -> threading.Event


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
    def execute_async(execution_id: str, system_task_id: int, params_values: Dict[str, Any], database_id: int = None):
        cancel_event = threading.Event()
        _execution_cancel_events[execution_id] = cancel_event
        thread = threading.Thread(
            target=SystemTaskService._execute_background,
            args=(execution_id, system_task_id, params_values, database_id, cancel_event),
            daemon=True
        )
        _execution_threads[execution_id] = thread
        thread.start()

    @staticmethod
    def _execute_background(execution_id: str, system_task_id: int, params_values: Dict[str, Any], database_id: int = None, cancel_event: threading.Event = None):
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

                # 检查是否已被取消
                if cancel_event and cancel_event.is_set():
                    raise RuntimeError('任务已被手动终止')

                if system_task.task_type == 'sql':
                    SystemTaskService._execute_sql(execution, system_task, params_values, database_id, cancel_event)
                elif system_task.task_type == 'api':
                    SystemTaskService._execute_api(execution, system_task, params_values)
                elif system_task.task_type == 'script':
                    SystemTaskService._execute_script(execution, system_task, params_values)
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
    def _resolve_param_source(execution: SystemTaskExecution, system_task: SystemTask,
                              params_values: Dict[str, Any]) -> Dict[str, Any]:
        if not system_task.param_source_enabled or not system_task.param_source_script_id:
            return params_values

        execution.add_log('开始执行参数来源脚本，获取动态参数')
        db.session.commit()

        source_script = Script.query.get(system_task.param_source_script_id)
        if not source_script:
            raise ValueError('参数来源脚本不存在')

        sql_text = source_script.sql_text
        if not sql_text:
            raise ValueError('参数来源脚本SQL为空')

        if params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in sql_text:
                    sql_text = sql_text.replace(placeholder, str(val))

        filter_params = {}
        if params_values:
            for k, v in params_values.items():
                if v is not None and v != '' and v != []:
                    filter_params[k] = v

        source_db_id = system_task.param_source_db_id
        if not source_db_id:
            db_ids = source_script.get_database_ids()
            source_db_id = db_ids[0] if db_ids else None

        if not source_db_id:
            raise ValueError('参数来源脚本未配置数据库')

        conn_model = DatabaseConnection.query.get(source_db_id)
        if not conn_model:
            raise ValueError(f'参数来源数据库不存在(ID:{source_db_id})')

        from app.utils.connection_pool import ConnectionPoolManager
        pool = ConnectionPoolManager.get_instance()
        connector = pool.get_connector_with_health_check(source_db_id)
        if not connector:
            raise ValueError(f'参数来源数据库连接失败: {conn_model.name}')

        statements = SystemTaskService._split_sql_statements(sql_text)
        if not statements:
            raise ValueError('参数来源脚本无可执行SQL')

        last_query_result = None
        with connector.get_connection() as conn:
            for stmt in statements:
                if not stmt.strip():
                    continue
                result = conn.execute(text(stmt), filter_params) if filter_params else conn.execute(text(stmt))
                if SystemTaskService._is_query_statement(stmt):
                    column_headers = list(result.keys()) if hasattr(result, 'keys') else []
                    rows = result.fetchall()
                    if rows and column_headers:
                        row_dict = {}
                        for i, header in enumerate(column_headers):
                            if i < len(rows[0]):
                                row_dict[header] = rows[0][i]
                        last_query_result = row_dict
                else:
                    conn.commit()

        if not last_query_result:
            raise ValueError('参数来源脚本未返回查询结果')

        param_mapping = system_task.get_param_source_param_mapping()
        if param_mapping:
            merged = dict(params_values) if params_values else {}
            mapped_count = 0
            for m in param_mapping:
                source_field = m.get('source_field', '')
                target_param = m.get('target_param', '')
                if not source_field or not target_param:
                    continue
                if source_field in last_query_result:
                    val = last_query_result[source_field]
                    merged[target_param] = str(val) if val is not None else ''
                    mapped_count += 1
            execution.add_log(f'参数来源脚本执行成功，映射了 {mapped_count} 个参数')
            db.session.commit()
            return merged
        else:
            merged = dict(params_values) if params_values else {}
            merged.update({k: str(v) if v is not None else '' for k, v in last_query_result.items()})
            execution.add_log('参数来源脚本执行成功（无映射配置，自动合并所有字段）')
            db.session.commit()
            return merged

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
                     params_values: Dict[str, Any], database_id: int = None, cancel_event: threading.Event = None):
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
        # 并识别列表参数：将列表/逗号分隔字符串值保留为 list，供后续展开 IN 子句
        filtered_params = {}
        list_params = {}  # key -> list[str]  纯标量参数存 filtered_params，列表存 list_params
        if params_values:
            for k, v in params_values.items():
                if v is None or v == '':
                    continue
                # 列表值（前端 list 类型参数可能直接传 list，或 text/textarea 传逗号分隔字符串）
                if isinstance(v, list):
                    list_params[k] = [str(item).strip() for item in v if str(item).strip()]
                elif isinstance(v, str) and re.search(r'[,，]\s*', v):
                    parts = [p.strip() for p in re.split(r'[,，]', v) if p.strip()]
                    if len(parts) >= 2:
                        list_params[k] = parts
                    else:
                        filtered_params[k] = v
                else:
                    filtered_params[k] = v

        # Split into multiple statements
        statements = SystemTaskService._split_sql_statements(sql_text)
        if not statements:
            raise ValueError('没有可执行的SQL语句')

        # 展开列表参数：将 IN (:param) 中的列表值展开为 IN (:param_0, :param_1, ...)
        if list_params:
            expanded = []
            for stmt in statements:
                for key, values in list_params.items():
                    # 匹配 IN (:key) 模式（不区分大小写，允许空格）
                    pattern = rf'\bIN\s*\(\s*:{key}\s*\)'
                    if re.search(pattern, stmt, re.IGNORECASE):
                        placeholders = ', '.join(f':{key}_{i}' for i in range(len(values)))
                        stmt = re.sub(pattern, f'IN ({placeholders})', stmt, flags=re.IGNORECASE)
                        for i, val in enumerate(values):
                            filtered_params[f'{key}_{i}'] = val
                        execution.add_log(f'列表参数 [{key}] 展开为 {len(values)} 个值')
                    else:
                        # IN 子句以外的地方也可能用了 :key（极少见），直接展平为第一个值作为兜底
                        if f':{key}' in stmt and not re.search(rf':{key}_\d+', stmt):
                            filtered_params[key] = values[0]
                expanded.append(stmt)
            statements = expanded

        execution.progress = 20
        execution.add_log(f'SQL准备完成，共 {len(statements)} 条语句')
        db.session.commit()
        update_execution_progress(execution_id, 20, f'SQL准备完成，共 {len(statements)} 条语句')

        db_ids = system_task.get_database_ids()
        if not db_ids:
            db_ids = script.get_database_ids()
        if not db_ids:
            raise ValueError('没有配置数据库连接')

        # 如果指定了数据库ID，只使用指定的那一个
        if database_id:
            database_id = int(database_id)
            if database_id in db_ids:
                db_ids = [database_id]
            else:
                raise ValueError(f'指定的数据库连接(ID:{database_id})不在任务关联的数据库列表中')

        all_results = []
        total_dbs = len(db_ids)

        for idx, conn_id in enumerate(db_ids):
            # 检查是否已被取消
            if cancel_event and cancel_event.is_set():
                raise RuntimeError('任务已被手动终止')

            conn_model = DatabaseConnection.query.get(conn_id)
            if not conn_model:
                execution.add_log(f'数据库连接不存在: {conn_id}', 'warning')
                continue

            try:
                from app.utils.connection_pool import ConnectionPoolManager
                pool = ConnectionPoolManager.get_instance()
                connector = pool.get_connector_with_health_check(conn_id)
                if not connector:
                    execution.add_log(f'数据库连接失败: {conn_model.name}', 'warning')
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
                            # DML语句需要显式提交事务
                            conn.commit()
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

                # 连接由连接池管理，不再手动关闭
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

        params_values = SystemTaskService._resolve_param_source(execution, system_task, params_values)
        execution.progress = 15
        db.session.commit()
        update_execution_progress(execution_id, 15, '参数已就绪，准备API请求')

        prepared = SystemTaskService._prepare_api_request(execution, system_task, params_values)

        # 配置了SSH跳板机时，由跳板机执行curl（用于访问本机无法直达的目标地址）
        if system_task.ssh_config_id:
            return SystemTaskService._execute_api_via_ssh(execution, system_task, prepared)

        # SSRF protection: validate URL before making request
        from app.utils.url_validator import validate_url
        is_valid, reason = validate_url(prepared['url'])
        if not is_valid:
            raise ValueError(f'SSRF protection: {reason}')

        execution.progress = 50
        db.session.commit()
        update_execution_progress(execution_id, 50, '发送API请求')

        try:
            resp = SystemTaskService._send_api_request_via_requests(prepared)
        except requests.exceptions.Timeout:
            raise ValueError(f'API请求超时({prepared["timeout"]}秒)')
        except requests.exceptions.RequestException as e:
            raise ValueError(f'API请求失败: {str(e)}')

        execution.progress = 80
        execution.add_log(f'API响应状态码: {resp.status_code}')
        db.session.commit()
        update_execution_progress(execution_id, 80, f'API响应状态码: {resp.status_code}')

        try:
            resp_data = resp.json()
            resp_text = json.dumps(resp_data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            resp_data = resp.text
            resp_text = resp.text

        SystemTaskService._finalize_api_response(
            execution, system_task, prepared, resp.status_code,
            dict(resp.headers), resp_data, resp_text,
        )

    @staticmethod
    def _prepare_api_request(execution: SystemTaskExecution, system_task: SystemTask,
                             params_values: Dict[str, Any]) -> Dict[str, Any]:
        """构造最终请求（占位符替换、参数归一化、加签），直连与SSH模式共用"""
        url = system_task.api_url
        method = (system_task.api_method or 'POST').upper()
        headers = dict(system_task.get_api_headers() or {})
        timeout = system_task.api_timeout or 30

        request_params = dict(params_values) if params_values else {}
        body = system_task.api_body or ''
        used_param_keys = set()

        # Replace placeholders in body {{param}}
        if body and params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in body:
                    body = body.replace(placeholder, str(val))
                    used_param_keys.add(key)

        # Replace placeholders in url
        if params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in url:
                    url = url.replace(placeholder, str(val))
                    used_param_keys.add(key)

        # 从request_params中移除已用于URL/body替换的参数，避免重复附加
        for key in used_param_keys:
            request_params.pop(key, None)

        execution.progress = 30
        execution.add_log(f'准备请求: {method} {url}')
        db.session.commit()
        update_execution_progress(execution.execution_id, 30, f'准备请求: {method} {url}')

        # Signing
        if system_task.sign_enabled and system_task.sign_key:
            sign = SystemTaskService._compute_sign(
                request_params, body, headers,
                system_task.sign_key, system_task.sign_method
            )
            sign_name = system_task.sign_param_name or 'sign'
            append_type = system_task.sign_append_type or 'query'

            if append_type == 'query':
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}{sign_name}={sign}"
            elif append_type == 'body':
                try:
                    body_obj = json.loads(body) if body else {}
                    if isinstance(body_obj, dict):
                        body_obj[sign_name] = sign
                        body = json.dumps(body_obj, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    if 'application/x-www-form-urlencoded' in headers.get('Content-Type', ''):
                        body = f"{body}&{sign_name}={sign}" if body else f"{sign_name}={sign}"
                    else:
                        execution.add_log('签名附加到body失败，body不是有效的JSON', 'warning')
            elif append_type == 'header':
                headers[sign_name] = sign

            execution.add_log(f'已生成签名并附加到{append_type}')

        # Parse body for JSON content-type
        request_body = body
        content_type = headers.get('Content-Type', '')
        if content_type.startswith('application/json') and body:
            try:
                request_body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                pass

        # 如果body为空但有params，且是JSON请求，将params作为JSON body发送
        if not body and request_params and content_type.startswith('application/json'):
            request_body = request_params
            request_params = {}

        request_info = {
            'method': method,
            'url': url,
            'headers': dict(headers),
            'request_params': request_params,
            'request_body': request_body,
            'via': 'direct',
        }
        return {
            'method': method,
            'url': url,
            'headers': headers,
            'timeout': timeout,
            'request_params': request_params,
            'request_body': request_body,
            'request_info': request_info,
        }

    @staticmethod
    def _send_api_request_via_requests(prepared: Dict[str, Any]):
        """本机直连发送HTTP请求"""
        url = prepared['url']
        method = prepared['method']
        headers = prepared['headers']
        timeout = prepared['timeout']
        request_params = prepared['request_params']
        request_body = prepared['request_body']

        if method == 'GET':
            return requests.get(url, headers=headers, params=request_params, timeout=timeout)
        if method == 'POST':
            if isinstance(request_body, dict):
                return requests.post(url, headers=headers, json=request_body, timeout=timeout)
            if request_body:
                return requests.post(url, headers=headers, data=request_body, timeout=timeout)
            if request_params:
                return requests.post(url, headers=headers, data=request_params, timeout=timeout)
            return requests.post(url, headers=headers, timeout=timeout)
        if method == 'PUT':
            if isinstance(request_body, dict):
                return requests.put(url, headers=headers, json=request_body, timeout=timeout)
            if request_body:
                return requests.put(url, headers=headers, data=request_body, timeout=timeout)
            if request_params:
                return requests.put(url, headers=headers, data=request_params, timeout=timeout)
            return requests.put(url, headers=headers, timeout=timeout)
        if method == 'DELETE':
            if isinstance(request_body, dict):
                return requests.delete(url, headers=headers, json=request_body, timeout=timeout)
            if request_body:
                return requests.delete(url, headers=headers, data=request_body, timeout=timeout)
            return requests.delete(url, headers=headers, params=request_params, timeout=timeout)
        raise ValueError(f'不支持的HTTP方法: {method}')

    @staticmethod
    def _is_http_url(url: str) -> bool:
        from urllib.parse import urlsplit
        try:
            parsed = urlsplit(url)
        except ValueError:
            return False
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname)

    @staticmethod
    def _has_header(headers: Dict[str, str], name: str) -> bool:
        return any(str(key).lower() == name.lower() for key in headers)

    @staticmethod
    def _append_query_params(url: str, params: Dict[str, Any]) -> str:
        if not params:
            return url
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
        try:
            parts = urlsplit(url)
        except ValueError as exc:
            raise ValueError(f'API地址不合法: {exc}') from exc
        query = parse_qsl(parts.query, keep_blank_values=True)
        for key, value in params.items():
            if isinstance(value, (list, tuple)):
                for item in value:
                    query.append((str(key), '' if item is None else str(item)))
            else:
                query.append((str(key), '' if value is None else str(value)))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @staticmethod
    def _curl_body_text(request_body: Any) -> str:
        if request_body is None:
            return ''
        if isinstance(request_body, (dict, list)):
            return json.dumps(request_body, ensure_ascii=False)
        return str(request_body)

    @staticmethod
    def _build_curl_arguments(prepared: Dict[str, Any], mask_sensitive: bool = False):
        """把已构造好的HTTP请求转换为curl参数，返回(command, args)"""
        import shlex
        from urllib.parse import urlencode

        method = prepared['method']
        headers = dict(prepared['headers'])
        if mask_sensitive:
            for key in list(headers.keys()):
                lower = str(key).lower()
                if any(token in lower for token in ('authorization', 'cookie', 'token', 'secret', 'key', 'sign', 'password')):
                    headers[key] = '***'

        url = prepared['url']
        timeout = int(prepared['timeout'] or 30)
        request_params = dict(prepared['request_params'] or {})
        request_body = prepared['request_body']
        body_text = ''

        if method == 'GET':
            url = SystemTaskService._append_query_params(url, request_params)
            request_params = {}
        elif method == 'DELETE':
            if request_body:
                body_text = SystemTaskService._curl_body_text(request_body)
                if isinstance(request_body, (dict, list)) and not SystemTaskService._has_header(headers, 'Content-Type'):
                    headers['Content-Type'] = 'application/json'
            else:
                url = SystemTaskService._append_query_params(url, request_params)
                request_params = {}
        else:
            if isinstance(request_body, (dict, list)):
                body_text = SystemTaskService._curl_body_text(request_body)
                if not SystemTaskService._has_header(headers, 'Content-Type'):
                    headers['Content-Type'] = 'application/json'
            elif request_body:
                body_text = str(request_body)
            elif request_params:
                body_text = urlencode(request_params, doseq=True)
                if not SystemTaskService._has_header(headers, 'Content-Type'):
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'

        args = [
            'curl', '-sS', '-L',
            '--max-time', str(timeout),
            '--connect-timeout', str(min(10, max(1, timeout))),
            '-X', method,
        ]
        for key, value in headers.items():
            args.extend(['-H', f'{key}: {value}'])
        if body_text:
            args.extend(['--data-binary', body_text])
        args.extend(['-w', '\n__CURL_META__:%{http_code}:%{content_type}:%{time_total}'])
        args.append(url)

        command = ' '.join(shlex.quote(str(arg)) for arg in args)
        return command, args

    @staticmethod
    def _parse_curl_output(output: str):
        """解析 curl -w 标记，返回(status_code, content_type, elapsed, body)"""
        marker = '__CURL_META__'
        index = (output or '').rfind(marker)
        if index < 0:
            raise ValueError('无法解析curl响应：缺少状态标记')

        body = output[:index]
        if body.endswith('\n'):
            body = body[:-1]
        if body.endswith('\r'):
            body = body[:-1]

        meta = output[index + len(marker):].strip().lstrip(':')
        parts = meta.split(':', 2)
        status_code = int(parts[0]) if parts and parts[0].isdigit() else 0
        content_type = parts[1] if len(parts) > 1 else ''
        elapsed = parts[2] if len(parts) > 2 else ''
        return status_code, content_type, elapsed, body

    @staticmethod
    def _ssh_connect_kwargs(ssh_config) -> Dict[str, Any]:
        password = ssh_config.get_password()
        if not password and not ssh_config.pkey_path:
            raise ValueError(f'SSH配置[{ssh_config.name}]未配置密码或私钥')
        kwargs = {
            'hostname': ssh_config.host,
            'port': int(ssh_config.port or 22),
            'username': ssh_config.username,
            'timeout': 10,
            'banner_timeout': 15,
            'auth_timeout': 15,
            'allow_agent': False,
            'look_for_keys': False,
        }
        if password:
            kwargs['password'] = password
        if ssh_config.pkey_path:
            kwargs['key_filename'] = ssh_config.pkey_path
        return kwargs

    @staticmethod
    def _run_command_on_jump(jump_config, remote_command: str, timeout: int):
        """在跳板机本机执行命令，返回 (标准输出, 标准错误, 退出码)"""
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(**SystemTaskService._ssh_connect_kwargs(jump_config))
            stdin, stdout, stderr = client.exec_command(remote_command, timeout=timeout)
            out = stdout.read().decode('utf-8', errors='replace')
            err = stderr.read().decode('utf-8', errors='replace')
            return out, err, stdout.channel.recv_exit_status()
        finally:
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    def _build_jump_side_ssh_command(target_config, command: str) -> str:
        """构造在跳板机上执行的 ssh 命令，依赖跳板机到目标机的免密登录"""
        import shlex

        options = [
            'ssh',
            '-o', 'BatchMode=yes',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'ConnectTimeout=10',
            '-p', str(int(target_config.port or 22)),
            '{}@{}'.format(target_config.username, target_config.host),
        ]
        return ' '.join(shlex.quote(part) for part in options) + ' ' + shlex.quote(command)

    @staticmethod
    def _capture_jump_login_banner(jump_config, wait_seconds: float = 8.0) -> str:
        """以交互式 shell 登录跳板机，捕获登录欢迎信息/堡垒机主机菜单后立即断开"""
        import paramiko
        import time as _time

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        channel = None
        chunks = []
        try:
            client.connect(**SystemTaskService._ssh_connect_kwargs(jump_config))
            channel = client.invoke_shell(width=200, height=60)
            channel.settimeout(1.0)
            deadline = _time.time() + wait_seconds
            last_data_at = None
            while _time.time() < deadline:
                if channel.recv_ready():
                    chunk = channel.recv(65536).decode('utf-8', errors='replace')
                    if chunk:
                        chunks.append(chunk)
                        last_data_at = _time.time()
                else:
                    # 输出安静 1.5 秒视为菜单已打印完毕
                    if last_data_at and _time.time() - last_data_at >= 1.5:
                        break
                    _time.sleep(0.2)
            return ''.join(chunks)
        finally:
            if channel is not None:
                try:
                    channel.close()
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass

    @staticmethod
    def _extract_ipv4_list(text: str) -> List[str]:
        """从跳板机输出中提取 IPv4（去掉 ANSI 控制符、回环与非法地址，保持原顺序去重）"""
        cleaned = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', text or '')
        ips = []
        for ip in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', cleaned):
            parts = [int(p) for p in ip.split('.')]
            if any(p > 255 for p in parts):
                continue
            if parts[0] == 0 or parts[0] == 127 or ip == '255.255.255.255':
                continue
            if ip not in ips:
                ips.append(ip)
        return ips

    @staticmethod
    def _fetch_authorized_target_ips(jump_config):
        """获取跳板机/堡垒机上的授权目标机 IP 列表，返回 (IP列表, 来源, 原始输出摘要)"""
        command = (getattr(jump_config, 'authorized_hosts_command', '') or '').strip()
        if command:
            out, err, code = SystemTaskService._run_command_on_jump(jump_config, command, 15)
            text = (out or '') + '\n' + (err or '')
            ips = SystemTaskService._extract_ipv4_list(text)
            if code == 0 and ips:
                return ips, 'command', text.strip()[:2000]
            detail = (err or out or '').strip()[:200] or f'退出码 {code}'
            raise ValueError(f'跳板机授权清单命令执行失败: {detail}')

        banner = SystemTaskService._capture_jump_login_banner(jump_config)
        return SystemTaskService._extract_ipv4_list(banner), 'banner', banner.strip()[-2000:]

    @staticmethod
    def _run_ssh_command_via_tunnel(jump_config, target_config, command: str, timeout: int):
        """通过跳板机建立到目标机的SSH通道，并在目标机执行命令"""
        import paramiko

        jump_client = paramiko.SSHClient()
        target_client = paramiko.SSHClient()
        channel = None
        target_host = target_config.host
        target_port = int(target_config.port or 22)

        try:
            jump_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                jump_client.connect(**SystemTaskService._ssh_connect_kwargs(jump_config))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f'SSH跳板机[{jump_config.name}]连接失败: {str(exc)}') from exc

            transport = jump_client.get_transport()
            if not transport or not transport.is_active():
                raise ValueError(f'SSH跳板机[{jump_config.name}]连接未就绪')

            try:
                channel = transport.open_channel(
                    'direct-tcpip',
                    (target_host, target_port),
                    ('127.0.0.1', 0),
                    timeout=10,
                )
            except Exception as exc:
                raise ValueError(f'跳板机无法连接目标机 {target_host}:{target_port}: {str(exc)}') from exc
            if channel is None:
                raise ValueError(f'跳板机无法连接目标机 {target_host}:{target_port}')

            target_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            target_kwargs = SystemTaskService._ssh_connect_kwargs(target_config)
            target_kwargs['sock'] = channel
            try:
                target_client.connect(**target_kwargs)
            except Exception as exc:
                raise ValueError(f'跳板机登录目标机[{target_config.name}]失败: {str(exc)}') from exc

            try:
                stdin, stdout, stderr = target_client.exec_command(command, timeout=timeout)
                out = stdout.read().decode('utf-8', errors='replace')
                err = stderr.read().decode('utf-8', errors='replace')
                exit_code = stdout.channel.recv_exit_status()
                return out, err, exit_code
            except Exception as exc:
                raise ValueError(f'目标机执行curl失败: {str(exc)}') from exc
        finally:
            for client in (target_client, jump_client):
                try:
                    client.close()
                except Exception:
                    pass
            if channel is not None:
                try:
                    channel.close()
                except Exception:
                    pass

    @staticmethod
    def _run_ssh_command_via_jump(jump_config, target_config, command: str, timeout: int):
        """优先在跳板机上经免密 ssh 登录目标机执行命令，失败时回退到「目标机凭据 + 端口转发」"""
        jump_command = SystemTaskService._build_jump_side_ssh_command(target_config, command)
        jump_error = None
        try:
            out, err, exit_code = SystemTaskService._run_command_on_jump(
                jump_config, jump_command, timeout
            )
            # ssh 自身失败（认证/网络）固定返回 255，其余退出码来自目标机上的命令
            if exit_code != 255:
                return out, err, exit_code
            jump_error = (err or out or '').strip() or 'ssh 返回 255'
        except Exception as exc:
            jump_error = str(exc)

        try:
            return SystemTaskService._run_ssh_command_via_tunnel(
                jump_config, target_config, command, timeout
            )
        except Exception as exc:
            raise ValueError(
                '跳板机免密登录目标机[{}]失败({})，回退到目标机凭据方式也失败: {}'.format(
                    target_config.name, jump_error, exc
                )
            ) from exc


    @staticmethod
    def _execute_api_via_ssh(execution: SystemTaskExecution, system_task: SystemTask,
                            prepared: Dict[str, Any]):
        """通过SSH跳板机登录目标机执行curl，并将响应按原有API任务逻辑落库"""
        from app.models.ssh_config import SshConfig

        jump_config = SshConfig.query.get(system_task.ssh_config_id)
        if not jump_config or not jump_config.is_active:
            raise ValueError('SSH跳板机不存在或已停用')
        if not system_task.target_ssh_config_id:
            raise ValueError('未配置目标机器SSH配置')
        target_config = SshConfig.query.get(system_task.target_ssh_config_id)
        if not target_config or not target_config.is_active:
            raise ValueError('目标机器SSH配置不存在或已停用')
        if not SystemTaskService._is_http_url(prepared['url']):
            raise ValueError('API地址必须是 http/https 协议')

        execution_id = execution.execution_id
        execution.progress = 50
        target_label = f'{target_config.username}@{target_config.host}:{target_config.port or 22}'
        execution.add_log(
            f'通过SSH跳板机[{jump_config.name}]登录目标机[{target_label}]执行 '
            f'{prepared["method"]} {prepared["url"]}'
        )
        db.session.commit()
        update_execution_progress(execution_id, 50, f'通过跳板机登录目标机[{target_config.host}]发送请求')

        command, _ = SystemTaskService._build_curl_arguments(prepared, mask_sensitive=False)
        preview, _ = SystemTaskService._build_curl_arguments(prepared, mask_sensitive=True)
        execution.add_log(f'curl命令(敏感头已脱敏): {preview[:4000]}')
        db.session.commit()

        timeout = int(prepared['timeout'] or 30)
        out, err, exit_code = SystemTaskService._run_ssh_command_via_jump(
            jump_config, target_config, command, timeout + 15
        )
        if exit_code != 0:
            detail = (err or out).strip()[:1000]
            raise ValueError(f'目标机curl执行失败(exit={exit_code})：{detail or "无输出"}')

        status_code, content_type, elapsed, body_text = SystemTaskService._parse_curl_output(out)
        prepared['request_info'].update({
            'via': 'ssh',
            'ssh_config_id': jump_config.id,
            'ssh_config_name': jump_config.name,
            'target_ssh_config_id': target_config.id,
            'target_ssh_config_name': target_config.name,
            'target_host': target_config.host,
            'curl_preview': preview[:4000],
        })

        execution.progress = 80
        execution.add_log(f'目标机响应状态码: {status_code}')
        db.session.commit()
        update_execution_progress(execution_id, 80, f'目标机响应状态码: {status_code}')

        resp_headers = {'Content-Type': content_type} if content_type else {}
        try:
            resp_data = json.loads(body_text)
            resp_text = json.dumps(resp_data, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            resp_data = body_text
            resp_text = body_text

        SystemTaskService._finalize_api_response(
            execution, system_task, prepared, status_code,
            resp_headers, resp_data, resp_text, elapsed=elapsed,
        )

    @staticmethod
    def _finalize_api_response(execution: SystemTaskExecution, system_task: SystemTask,
                               prepared: Dict[str, Any], status_code: int,
                               resp_headers: Dict[str, str], resp_data: Any, resp_text: str,
                               elapsed: str = None):
        """API响应统一处理：字段映射、结果落库、状态判定"""
        request_info = prepared['request_info']
        is_success = 200 <= status_code < 300

        resp_data_mapped = resp_data
        mapping_info = ''
        response_mapping = system_task.get_response_mapping()
        if response_mapping and isinstance(resp_data, dict):
            resp_data_mapped, mapping_info, is_business_success = SystemTaskService._apply_response_mapping(resp_data, response_mapping)
            if is_business_success is True:
                is_success = True
            elif is_business_success is False:
                is_success = False
                execution.error_message = mapping_info

        result_data = {
            'status_code': status_code,
            'request': request_info,
            'response': resp_data_mapped if isinstance(resp_data_mapped, (dict, list)) else resp_text,
            'response_raw': resp_data if isinstance(resp_data, (dict, list)) else resp_text,
            'mapping_applied': bool(mapping_info),
            'mapping_info': mapping_info,
            'response_headers': resp_headers,
            'success': is_success,
        }
        if elapsed:
            result_data['elapsed'] = elapsed

        execution.set_result_data(result_data)
        execution.progress = 100
        execution.status = 'completed' if is_success else 'failed'
        execution.completed_at = datetime.utcnow()
        if not is_success and not execution.error_message:
            execution.error_message = f'API返回非成功状态码: {status_code}'
        execution.add_log(f'API请求完成，状态码: {status_code}')
        db.session.commit()
        update_execution_progress(execution.execution_id, 100, 'API请求完成')


    @staticmethod
    def _execute_script(execution: SystemTaskExecution, system_task: SystemTask,
                        params_values: Dict[str, Any]):
        """执行本地脚本类型的系统任务"""
        execution_id = execution.execution_id
        execution.progress = 10
        execution.add_log('执行本地脚本类型系统任务')
        db.session.commit()
        update_execution_progress(execution_id, 10, '执行本地脚本类型系统任务')

        if not system_task.script_path:
            raise ValueError('本地脚本路径未配置')

        params_values = SystemTaskService._resolve_param_source(execution, system_task, params_values)
        execution.progress = 15
        db.session.commit()
        update_execution_progress(execution_id, 15, '参数已就绪，准备执行脚本')

        script_path = system_task.script_path
        script_type = system_task.script_type or 'python'
        timeout = system_task.script_timeout or 60

        # 验证脚本文件存在
        if not os.path.isfile(script_path):
            raise ValueError(f'脚本文件不存在: {script_path}')

        # 构建命令
        if script_type == 'python':
            cmd = ['python', script_path]
        elif script_type in ('shell', 'bash', 'sh'):
            cmd = ['bash', script_path]
        elif script_type == 'bat':
            cmd = ['cmd', '/c', script_path]
        elif script_type == 'powershell':
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path]
        else:
            # 自定义解释器
            cmd = [script_type, script_path]

        # 将参数作为命令行参数追加
        if params_values:
            for key, val in params_values.items():
                if val is not None and val != '':
                    cmd.append(f'--{key}')
                    cmd.append(str(val))

        execution.progress = 20
        execution.add_log(f'准备执行: {" ".join(cmd)}')
        db.session.commit()
        update_execution_progress(execution_id, 20, f'准备执行脚本')

        # 构建环境变量
        env = os.environ.copy()
        script_env = system_task.get_script_env()
        if script_env:
            for k, v in script_env.items():
                env[str(k)] = str(v)
            # 同时将参数值设为环境变量（SCRIPT_PARAM_前缀）
            if params_values:
                for k, v in params_values.items():
                    env[f'SCRIPT_PARAM_{k.upper()}'] = str(v) if v is not None else ''

        execution.progress = 30
        db.session.commit()
        update_execution_progress(execution_id, 30, '脚本执行中')

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=os.path.dirname(script_path) or None,
            )

            execution.progress = 80
            stdout = result.stdout or ''
            stderr = result.stderr or ''
            returncode = result.returncode

            execution.add_log(f'脚本执行完成，返回码: {returncode}')
            if stdout:
                # 截取前2000字符避免过大
                log_stdout = stdout[:2000] + '...' if len(stdout) > 2000 else stdout
                execution.add_log(f'标准输出: {log_stdout}')
            if stderr:
                log_stderr = stderr[:2000] + '...' if len(stderr) > 2000 else stderr
                execution.add_log(f'标准错误: {log_stderr}', 'warning')

            is_success = returncode == 0

            # 尝试解析stdout为JSON
            stdout_data = stdout.strip()
            parsed_output = None
            if stdout_data:
                try:
                    parsed_output = json.loads(stdout_data)
                except (json.JSONDecodeError, ValueError):
                    parsed_output = stdout_data

            execution.set_result_data({
                'returncode': returncode,
                'stdout': parsed_output if parsed_output is not None else stdout,
                'stderr': stderr,
                'success': is_success,
            })

            execution.progress = 100
            execution.status = 'completed' if is_success else 'failed'
            execution.completed_at = datetime.utcnow()
            if not is_success:
                execution.error_message = f'脚本执行失败，返回码: {returncode}' + (f'\n{stderr[:500]}' if stderr else '')
            execution.add_log(f'脚本任务执行完成，返回码: {returncode}')
            db.session.commit()
            update_execution_progress(execution_id, 100, '脚本任务执行完成')

        except subprocess.TimeoutExpired:
            raise ValueError(f'脚本执行超时({timeout}秒)')
        except FileNotFoundError as e:
            raise ValueError(f'脚本解释器未找到: {str(e)}')
        except Exception as e:
            raise ValueError(f'脚本执行失败: {str(e)}')

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
    def _apply_response_mapping(resp_data: dict, response_mapping: list) -> tuple:
        """应用响应字段映射，将原始值替换为可读文本，同时保留原始值。
        返回 (mapped_data, mapping_info_str, is_business_success)
        """
        import copy
        mapped = copy.deepcopy(resp_data)
        info_parts = []
        is_business_success = None
        business_error_message = ''

        for m in response_mapping:
            field = m.get('field', '')
            label = m.get('label', field)
            mapping = m.get('mapping', {})
            if not field:
                continue

            value = SystemTaskService._get_nested_value(resp_data, field)
            if value is None:
                continue

            value_str = str(value)

            if m.get('is_status'):
                success_value = str(m.get('success_value', ''))
                if value_str == success_value:
                    is_business_success = True
                else:
                    is_business_success = False
                    error_field = m.get('error_field', '')
                    if error_field:
                        error_value = SystemTaskService._get_nested_value(resp_data, error_field)
                        if error_value is not None:
                            business_error_message = str(error_value)

            if value_str in mapping:
                readable = mapping[value_str]
                SystemTaskService._set_nested_value(mapped, field, f'{value_str}({readable})')
                info_parts.append(f'{label}({field}): {value_str} → {readable}')

        mapping_info = '; '.join(info_parts) if info_parts else ''
        if is_business_success is False and business_error_message:
            mapping_info = f'{mapping_info}; 错误原因: {business_error_message}' if mapping_info else f'错误原因: {business_error_message}'
        return mapped, mapping_info, is_business_success

    @staticmethod
    def _get_nested_value(data: dict, field_path: str):
        """获取嵌套字段值，支持 data.status 格式"""
        keys = field_path.split('.')
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return None
            else:
                return None
        return current

    @staticmethod
    def _set_nested_value(data: dict, field_path: str, value):
        """设置嵌套字段值，支持 data.status 格式"""
        keys = field_path.split('.')
        current = data
        for key in keys[:-1]:
            if isinstance(current, dict):
                current = current.setdefault(key, {})
            elif isinstance(current, list) and key.isdigit():
                idx = int(key)
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    return
            else:
                return
        last_key = keys[-1]
        if isinstance(current, dict):
            current[last_key] = value
        elif isinstance(current, list) and last_key.isdigit():
            idx = int(last_key)
            if 0 <= idx < len(current):
                current[idx] = value

    @staticmethod
    def execute_api_sync(system_task: SystemTask, params_values: Dict[str, Any], user_id: int = None) -> Dict[str, Any]:
        """同步执行API类型系统任务，直接返回执行结果（用于AI自动执行场景）

        会创建SystemTaskExecution记录，使执行结果进入执行历史。
        """
        if not system_task.api_url:
            return {'error': 'API地址未配置', 'success': False}

        # 创建执行记录
        execution_id = str(uuid.uuid4())
        execution = SystemTaskExecution(
            execution_id=execution_id,
            system_task_id=system_task.id,
            status='running',
            task_type='api',
            created_by=user_id,
            started_at=datetime.utcnow(),
        )
        execution.set_params_values(params_values)
        execution.add_log(f'开始执行API系统任务: {system_task.name}')
        db.session.add(execution)
        db.session.commit()

        # 解析参数来源脚本
        params_values = SystemTaskService._resolve_param_source(execution, system_task, params_values)

        url = system_task.api_url
        method = (system_task.api_method or 'POST').upper()
        headers = system_task.get_api_headers()
        timeout = system_task.api_timeout or 30

        # Prepare params and body
        request_params = dict(params_values) if params_values else {}
        body = system_task.api_body or ''

        # 已用于URL/body占位符替换的参数名集合（这些参数不应再作为query/form重复附加）
        used_param_keys = set()

        # Replace placeholders in body {{param}}
        if body and params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in body:
                    body = body.replace(placeholder, str(val))
                    used_param_keys.add(key)

        # Replace placeholders in url
        if params_values:
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in url:
                    url = url.replace(placeholder, str(val))
                    used_param_keys.add(key)

        # 从request_params中移除已用于URL/body替换的参数，避免重复附加
        for key in used_param_keys:
            request_params.pop(key, None)

        # Signing
        if system_task.sign_enabled and system_task.sign_key:
            sign = SystemTaskService._compute_sign(
                request_params, body, headers,
                system_task.sign_key, system_task.sign_method
            )
            sign_name = system_task.sign_param_name or 'sign'
            append_type = system_task.sign_append_type or 'query'

            if append_type == 'query':
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}{sign_name}={sign}"
            elif append_type == 'body':
                try:
                    body_obj = json.loads(body) if body else {}
                    if isinstance(body_obj, dict):
                        body_obj[sign_name] = sign
                        body = json.dumps(body_obj, ensure_ascii=False)
                except (json.JSONDecodeError, TypeError):
                    if 'application/x-www-form-urlencoded' in headers.get('Content-Type', ''):
                        body = f"{body}&{sign_name}={sign}" if body else f"{sign_name}={sign}"
            elif append_type == 'header':
                headers[sign_name] = sign

        # Parse body for JSON content-type
        request_body = body
        if headers.get('Content-Type', '').startswith('application/json') and body:
            try:
                request_body = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                pass

        # 如果body为空但有params，且是JSON请求，将params作为JSON body发送
        if not body and request_params and headers.get('Content-Type', '').startswith('application/json'):
            request_body = request_params
            request_params = {}  # 避免参数重复

        # 记录实际请求信息（占位符替换与加签后的最终请求），完整返回给调用方（含AI）
        request_info = {
            'method': method,
            'url': url,
            'headers': dict(headers),
            'request_params': request_params,
            'request_body': request_body,
        }

        # Make request
        try:
            if method == 'GET':
                resp = requests.get(url, headers=headers, params=request_params, timeout=timeout)
            elif method == 'POST':
                if isinstance(request_body, dict):
                    resp = requests.post(url, headers=headers, json=request_body, timeout=timeout)
                elif request_body:
                    resp = requests.post(url, headers=headers, data=request_body, timeout=timeout)
                elif request_params:
                    # body为空且有params，作为form data发送
                    resp = requests.post(url, headers=headers, data=request_params, timeout=timeout)
                else:
                    resp = requests.post(url, headers=headers, timeout=timeout)
            elif method == 'PUT':
                if isinstance(request_body, dict):
                    resp = requests.put(url, headers=headers, json=request_body, timeout=timeout)
                elif request_body:
                    resp = requests.put(url, headers=headers, data=request_body, timeout=timeout)
                elif request_params:
                    # body为空且有params，作为form data发送
                    resp = requests.put(url, headers=headers, data=request_params, timeout=timeout)
                else:
                    resp = requests.put(url, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                # DELETE通常用query params，但若有body则用body
                if isinstance(request_body, dict):
                    resp = requests.delete(url, headers=headers, json=request_body, timeout=timeout)
                elif request_body:
                    resp = requests.delete(url, headers=headers, data=request_body, timeout=timeout)
                else:
                    resp = requests.delete(url, headers=headers, params=request_params, timeout=timeout)
            else:
                return {'error': f'不支持的HTTP方法: {method}', 'success': False}

            # Try to parse response as JSON
            try:
                resp_data = resp.json()
                resp_text = json.dumps(resp_data, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                resp_data = resp.text
                resp_text = resp.text

            is_success = 200 <= resp.status_code < 300

            # 应用响应字段映射
            resp_data_mapped = resp_data
            mapping_info = ''
            mapping_summary = ''
            response_mapping = system_task.get_response_mapping()
            if response_mapping and isinstance(resp_data, dict):
                resp_data_mapped, mapping_info, is_business_success = SystemTaskService._apply_response_mapping(resp_data, response_mapping)
                mapping_summary = SystemTaskService._build_mapping_summary(resp_data, response_mapping)
                if is_business_success is True:
                    is_success = True
                elif is_business_success is False:
                    is_success = False

            # 更新执行记录
            execution.status = 'completed' if is_success else 'failed'
            execution.progress = 100
            execution.completed_at = datetime.utcnow()
            if not is_success and mapping_info:
                execution.error_message = mapping_info
            execution.set_result_data({
                'status_code': resp.status_code,
                'request': request_info,
                'response': resp_data_mapped if isinstance(resp_data_mapped, (dict, list)) else resp_text,
                'response_raw': resp_data if isinstance(resp_data, (dict, list)) else resp_text,
                'mapping_applied': bool(mapping_info),
                'mapping_summary': mapping_summary,
            })
            execution.add_log(f'API请求完成，状态码: {resp.status_code}', 'info' if is_success else 'error')
            db.session.commit()

            return {
                'status_code': resp.status_code,
                'request': request_info,
                'response': resp_data_mapped if isinstance(resp_data_mapped, (dict, list)) else resp_text,
                'response_raw': resp_data if isinstance(resp_data, (dict, list)) else resp_text,
                'mapping_applied': bool(mapping_info),
                'mapping_info': mapping_info,
                'mapping_summary': mapping_summary,
                'success': is_success,
                'auto_executed': True,
                'execution_id': execution_id,
            }

        except requests.exceptions.Timeout as e:
            execution.status = 'failed'
            execution.error_message = f'API请求超时({timeout}秒)'
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'API请求超时({timeout}秒)', 'error')
            db.session.commit()
            return {'error': f'API请求超时({timeout}秒)', 'success': False}
        except requests.exceptions.RequestException as e:
            execution.status = 'failed'
            execution.error_message = f'API请求失败: {str(e)}'
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'API请求失败: {str(e)}', 'error')
            db.session.commit()
            return {'error': f'API请求失败: {str(e)}', 'success': False}

    @staticmethod
    def execute_script_sync(system_task: SystemTask, params_values: Dict[str, Any], user_id: int = None) -> Dict[str, Any]:
        """同步执行本地脚本类型系统任务，直接返回执行结果（用于AI自动执行场景）

        会创建SystemTaskExecution记录，使执行结果进入执行历史。
        """
        if not system_task.script_path:
            return {'error': '本地脚本路径未配置', 'success': False}

        # 创建执行记录
        execution_id = str(uuid.uuid4())
        execution = SystemTaskExecution(
            execution_id=execution_id,
            system_task_id=system_task.id,
            status='running',
            task_type='script',
            created_by=user_id,
            started_at=datetime.utcnow(),
        )
        execution.set_params_values(params_values)
        execution.add_log(f'开始执行本地脚本任务: {system_task.name}')
        db.session.add(execution)
        db.session.commit()

        # 解析参数来源脚本
        params_values = SystemTaskService._resolve_param_source(execution, system_task, params_values)

        script_path = system_task.script_path
        script_type = system_task.script_type or 'python'
        timeout = system_task.script_timeout or 60

        if not os.path.isfile(script_path):
            return {'error': f'脚本文件不存在: {script_path}', 'success': False}

        # 构建命令
        if script_type == 'python':
            cmd = ['python', script_path]
        elif script_type in ('shell', 'bash', 'sh'):
            cmd = ['bash', script_path]
        elif script_type == 'bat':
            cmd = ['cmd', '/c', script_path]
        elif script_type == 'powershell':
            cmd = ['powershell', '-ExecutionPolicy', 'Bypass', '-File', script_path]
        else:
            cmd = [script_type, script_path]

        # 将参数作为命令行参数追加
        if params_values:
            for key, val in params_values.items():
                if val is not None and val != '':
                    cmd.append(f'--{key}')
                    cmd.append(str(val))

        # 构建环境变量
        env = os.environ.copy()
        script_env = system_task.get_script_env()
        if script_env:
            for k, v in script_env.items():
                env[str(k)] = str(v)
        if params_values:
            for k, v in params_values.items():
                env[f'SCRIPT_PARAM_{k.upper()}'] = str(v) if v is not None else ''

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=os.path.dirname(script_path) or None,
            )

            stdout = result.stdout or ''
            stderr = result.stderr or ''
            returncode = result.returncode
            is_success = returncode == 0

            # 尝试解析stdout为JSON
            stdout_data = stdout.strip()
            parsed_output = None
            if stdout_data:
                try:
                    parsed_output = json.loads(stdout_data)
                except (json.JSONDecodeError, ValueError):
                    parsed_output = stdout_data

            # 更新执行记录
            execution.status = 'completed' if is_success else 'failed'
            execution.progress = 100
            execution.completed_at = datetime.utcnow()
            execution.set_result_data({
                'returncode': returncode,
                'stdout': parsed_output if parsed_output is not None else stdout,
                'stderr': stderr,
            })
            execution.add_log(f'脚本执行完成，返回码: {returncode}', 'info' if is_success else 'error')
            db.session.commit()

            return {
                'returncode': returncode,
                'stdout': parsed_output if parsed_output is not None else stdout,
                'stderr': stderr,
                'success': is_success,
                'auto_executed': True,
                'execution_id': execution_id,
            }

        except subprocess.TimeoutExpired:
            execution.status = 'failed'
            execution.error_message = f'脚本执行超时({timeout}秒)'
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'脚本执行超时({timeout}秒)', 'error')
            db.session.commit()
            return {'error': f'脚本执行超时({timeout}秒)', 'success': False}
        except FileNotFoundError as e:
            execution.status = 'failed'
            execution.error_message = f'脚本解释器未找到: {str(e)}'
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'脚本解释器未找到: {str(e)}', 'error')
            db.session.commit()
            return {'error': f'脚本解释器未找到: {str(e)}', 'success': False}
        except Exception as e:
            execution.status = 'failed'
            execution.error_message = f'脚本执行失败: {str(e)}'
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'脚本执行失败: {str(e)}', 'error')
            db.session.commit()
            return {'error': f'脚本执行失败: {str(e)}', 'success': False}

    @staticmethod
    def _build_mapping_summary(resp_data: dict, response_mapping: list) -> str:
        """根据响应字段映射构建可读的结果摘要，供AI直接反馈给用户"""
        parts = []
        for m in response_mapping:
            field = m.get('field', '')
            if not field:
                continue
            label = m.get('label', field)
            mapping = m.get('mapping', {})
            value = SystemTaskService._get_nested_value(resp_data, field)
            if value is None:
                continue
            value_str = str(value)
            if m.get('is_status'):
                success_value = str(m.get('success_value', ''))
                status_text = '成功' if value_str == success_value else '失败'
                parts.append(f'{label}: {value_str}（{status_text}）')
                if value_str != success_value:
                    error_field = m.get('error_field', '')
                    if error_field:
                        error_value = SystemTaskService._get_nested_value(resp_data, error_field)
                        if error_value is not None:
                            parts.append(f'失败原因: {error_value}')
            elif value_str in mapping:
                readable = mapping[value_str]
                parts.append(f'{label}: {readable}')
            else:
                parts.append(f'{label}: {value_str}')
        return '；'.join(parts) if parts else ''

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
        if execution.status not in ('pending', 'running'):
            return False

        # 设置取消标志（通知子线程在下一个检查点退出）
        cancel_event = _execution_cancel_events.get(execution_id)
        if cancel_event:
            cancel_event.set()

        # 尝试异步终止线程（注入 SystemExit）
        thread = _execution_threads.get(execution_id)
        if thread and thread.is_alive():
            try:
                import ctypes
                tid = ctypes.c_long(thread.ident)
                ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(SystemExit))
            except Exception as e:
                logger.warning(f'终止系统任务线程失败: {e}')

        # 更新执行记录状态（带异常保护，避免 commit 失败导致 500）
        try:
            execution.status = 'manual_cancelled'
            execution.completed_at = datetime.utcnow()
            execution.add_log('任务已被手动终止', 'warning')
            db.session.commit()
        except Exception as e:
            logger.error(f'更新任务取消状态失败 (commit): {e}', exc_info=True)
            db.session.rollback()
            # rollback 后重新加载对象并再次尝试设置状态
            try:
                db.session.expire_all()
                execution = SystemTaskExecution.query.filter_by(execution_id=execution_id).first()
                if execution:
                    execution.status = 'manual_cancelled'
                    execution.completed_at = datetime.utcnow()
                    execution.add_log('任务已被手动终止', 'warning')
                    db.session.commit()
            except Exception as e2:
                logger.error(f'重试更新任务取消状态仍失败: {e2}', exc_info=True)
                db.session.rollback()
                raise

        try:
            update_execution_progress(execution_id, 100, '任务已被手动终止', 'warning')
        except Exception as e:
            logger.warning(f'更新取消进度失败: {e}')

        # 清理线程引用
        _execution_threads.pop(execution_id, None)
        _execution_cancel_events.pop(execution_id, None)
        return True
