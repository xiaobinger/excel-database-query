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

# 跳板机是否支持「堡垒机菜单序号跳转」的进程内缓存：key -> {'supported': bool, 'expires_at': float}
_bastion_menu_cache = {}
_bastion_menu_lock = threading.Lock()
_BASTION_MENU_CACHE_TTL = 600


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
    def _resolve_body_type(system_task: SystemTask) -> str:
        """归一化请求体类型（参考 Postman 的 Body 类型选择，兼容旧数据）"""
        raw = (getattr(system_task, 'api_body_type', None) or '').strip().lower()
        aliases = {
            'form': 'form_urlencoded',
            'urlencoded': 'form_urlencoded',
            'x-www-form-urlencoded': 'form_urlencoded',
            'formdata': 'form_data',
            'multipart': 'form_data',
            'multipart/form-data': 'form_data',
            'text': 'raw',
        }
        if raw in ('none', 'json', 'raw', 'form_urlencoded', 'form_data'):
            return raw
        if raw in aliases:
            return aliases[raw]
        return 'json' if (system_task.api_body or '').strip() else 'none'

    @staticmethod
    def _get_enabled_form_fields(system_task: SystemTask) -> List[Dict[str, str]]:
        """读取启用中的表单字段（Key/Value），过滤空 key 与未勾选行"""
        fields = []
        for item in system_task.get_api_body_params() or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get('key') or '').strip()
            if not key or item.get('enabled') is False:
                continue
            value = item.get('value')
            fields.append({'key': key, 'value': '' if value is None else str(value)})
        return fields

    @staticmethod
    def _prepare_api_request(execution: SystemTaskExecution, system_task: SystemTask,
                             params_values: Dict[str, Any]) -> Dict[str, Any]:
        """构造最终请求（占位符替换、参数归一化、Body序列化、加签），直连与SSH模式共用

        Body 类型参考 Postman：none / json / raw / form_urlencoded / form_data
        """
        from urllib.parse import urlencode

        url = system_task.api_url
        method = (system_task.api_method or 'POST').upper()
        headers = dict(system_task.get_api_headers() or {})
        timeout = system_task.api_timeout or 30
        body_type = SystemTaskService._resolve_body_type(system_task)

        request_params = dict(params_values) if params_values else {}
        body = system_task.api_body or ''
        form_fields = SystemTaskService._get_enabled_form_fields(system_task) \
            if body_type in ('form_urlencoded', 'form_data') else []
        used_param_keys = set()

        def fill_placeholders(value: Any) -> str:
            """替换 {{param}} 占位符，并记录已使用的参数"""
            text = '' if value is None else str(value)
            if not params_values or not text:
                return text
            for key, val in params_values.items():
                placeholder = f'{{{{{key}}}}}'
                if placeholder in text:
                    text = text.replace(placeholder, str(val))
                    used_param_keys.add(key)
            return text

        body = fill_placeholders(body)
        url = fill_placeholders(url)
        for field in form_fields:
            field['value'] = fill_placeholders(field.get('value'))

        # 从request_params中移除已用于URL/body替换的参数，避免重复附加
        for key in used_param_keys:
            request_params.pop(key, None)

        execution.progress = 30
        execution.add_log(f'准备请求: {method} {url}（请求体类型: {body_type}）')
        db.session.commit()
        update_execution_progress(execution.execution_id, 30, f'准备请求: {method} {url}')

        # Signing（参考 buildCurl 签名算法）
        if system_task.sign_enabled and system_task.sign_key:
            sign_name = system_task.sign_param_name or 'sign'
            if body_type in ('form_urlencoded', 'form_data'):
                # 表单字段本身就是签名参数，直接用原始值参与排序，避免被URL编码干扰
                sign_params = dict(request_params)
                sign_params.update({f['key']: f['value'] for f in form_fields})
                sign = SystemTaskService._compute_sign(
                    sign_params, '', headers,
                    system_task.sign_key, system_task.sign_method,
                    sign_param_name=sign_name
                )
            else:
                sign = SystemTaskService._compute_sign(
                    request_params, body, headers,
                    system_task.sign_key, system_task.sign_method,
                    sign_param_name=sign_name
                )
            append_type = system_task.sign_append_type or 'query'

            if append_type == 'query':
                separator = '&' if '?' in url else '?'
                url = f"{url}{separator}{sign_name}={sign}"
            elif append_type == 'body':
                if body_type in ('form_urlencoded', 'form_data'):
                    form_fields.append({'key': sign_name, 'value': sign})
                else:
                    try:
                        body_obj = json.loads(body) if body else {}
                        if isinstance(body_obj, dict):
                            body_obj[sign_name] = sign
                            body = json.dumps(body_obj, ensure_ascii=False)
                    except (json.JSONDecodeError, TypeError):
                        if body_type == 'raw' or 'application/x-www-form-urlencoded' in headers.get('Content-Type', ''):
                            body = f"{body}&{sign_name}={sign}" if body else f"{sign_name}={sign}"
                        else:
                            execution.add_log('签名附加到body失败，body不是有效的JSON', 'warning')
            elif append_type == 'header':
                headers[sign_name] = sign

            execution.add_log(f'已生成签名并附加到{append_type}')

        # 按 Body 类型序列化请求体
        request_body = None
        content_type = headers.get('Content-Type', '')
        if body_type == 'none' or method in ('GET', 'HEAD', 'OPTIONS'):
            request_body = None
        elif body_type == 'form_urlencoded':
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            request_body = urlencode([(f['key'], f['value']) for f in form_fields]) if form_fields else None
            request_params = {}
        elif body_type == 'form_data':
            # multipart 边界由发送端自动生成，需移除手写的 Content-Type
            for header_key in [k for k in headers if str(k).lower() == 'content-type']:
                headers.pop(header_key, None)
            request_body = None
            request_params = {}
        elif body_type == 'json':
            request_body = body or None
            if body:
                try:
                    request_body = json.loads(body)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif request_params and content_type.startswith('application/json'):
                # 兼容旧配置：body为空但声明了JSON Content-Type，将参数作为JSON body发送
                request_body = request_params
                request_params = {}
        else:  # raw
            request_body = body or None

        request_info = {
            'method': method,
            'url': url,
            'headers': dict(headers),
            'body_type': body_type,
            # 超长字段值（如 base64 图片）只保留摘要，避免执行结果落库过大
            'form_fields': [
                {'key': f['key'], 'value': SystemTaskService._brief_value(f['value'])}
                for f in form_fields
            ],
            'request_params': request_params,
            'request_body': request_body if not isinstance(request_body, str)
            else SystemTaskService._brief_value(request_body),
            'via': 'direct',
        }
        return {
            'method': method,
            'url': url,
            'headers': headers,
            'timeout': timeout,
            'body_type': body_type,
            'form_fields': form_fields,
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

        body_kwargs = SystemTaskService._api_body_kwargs(prepared)

        if method == 'GET':
            return requests.get(url, headers=headers, params=request_params, timeout=timeout)
        if method == 'POST':
            return requests.post(url, headers=headers, timeout=timeout, **body_kwargs)
        if method == 'PUT':
            return requests.put(url, headers=headers, timeout=timeout, **body_kwargs)
        if method == 'DELETE':
            if body_kwargs:
                return requests.delete(url, headers=headers, timeout=timeout, **body_kwargs)
            return requests.delete(url, headers=headers, params=request_params, timeout=timeout)
        raise ValueError(f'不支持的HTTP方法: {method}')

    @staticmethod
    def _api_body_kwargs(prepared: Dict[str, Any]) -> Dict[str, Any]:
        """把准备好的请求体转换为 requests 关键字参数（JSON / 表单 / multipart / 原始文本）"""
        body_type = prepared.get('body_type') or 'json'
        form_fields = prepared.get('form_fields') or []
        request_body = prepared.get('request_body')
        request_params = prepared.get('request_params') or {}

        if body_type == 'form_data':
            # requests 传 files 时为字段列表才能发送 multipart（支持重复 key）
            if not form_fields:
                return {}
            return {'files': [(f['key'], (None, f['value'])) for f in form_fields]}
        if isinstance(request_body, dict):
            return {'json': request_body}
        if request_body:
            return {'data': request_body}
        if request_params:
            return {'data': request_params}
        return {}

    @staticmethod
    def _is_http_url(url: str) -> bool:
        from urllib.parse import urlsplit
        try:
            parsed = urlsplit(url)
        except ValueError:
            return False
        return parsed.scheme in ('http', 'https') and bool(parsed.hostname)

    @staticmethod
    def _brief_value(value: Any, limit: int = 500) -> str:
        """超长值摘要（用于执行日志/结果落库，避免 base64 图片等撑爆数据库）"""
        text = '' if value is None else str(value)
        if len(text) <= limit:
            return text
        return f'{text[:100]}...共{len(text)}字符'

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
        body_type = prepared.get('body_type') or 'json'
        form_fields = prepared.get('form_fields') or []
        body_text = ''
        form_args = []

        def preview_value(value: str) -> str:
            """脱敏预览时截断超长表单值（如 base64 图片）"""
            if not mask_sensitive or len(value) <= 200:
                return value
            return f'{value[:60]}...共{len(value)}字符'

        if body_type in ('form_urlencoded', 'form_data') and method not in ('GET', 'HEAD', 'OPTIONS'):
            for field in form_fields:
                if body_type == 'form_urlencoded':
                    form_args.extend(['--data-urlencode',
                                      f"{field['key']}={preview_value(field['value'])}"])
                else:
                    form_args.extend(['-F', f"{field['key']}={preview_value(field['value'])}"])
        elif method == 'GET':
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
        if form_args:
            args.extend(form_args)
        elif body_text:
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
    def _strip_ansi(text: str) -> str:
        """去掉终端 ANSI 控制序列（参考 buildCurl GateShell 实现）"""
        if not text:
            return ''
        # OSC: ESC ] ... BEL 或 ESC ] ... ESC \
        text = re.sub(r'\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)', '', text)
        # CSI: ESC [ ... 终止符
        text = re.sub(r'\x1b\[[0-9;?]*[ -/]*[@-~]', '', text)
        # Charset designation: ESC ( X / ESC ) X
        text = re.sub(r'\x1b[()][A-Za-z0-9]', '', text)
        # Single-char escapes
        text = re.sub(r'\x1b[=>78MDEHc]', '', text)
        return text.replace('\r\n', '\n').replace('\r', '\n')

    @staticmethod
    def _read_channel(channel, timeout: float, quiet: float = 1.2, stop_when=None, min_wait: float = 0) -> str:
        """读取交互式通道输出：命中 stop_when、输出安静 quiet 秒（且已运行 min_wait 秒）或超时即返回"""
        chunks = []
        start_at = time.time()
        deadline = start_at + timeout
        last_data_at = None
        while time.time() < deadline:
            if channel.recv_ready():
                chunk = channel.recv(65536).decode('utf-8', errors='replace')
                if chunk:
                    chunks.append(chunk)
                    last_data_at = time.time()
                    if stop_when and stop_when(''.join(chunks)):
                        break
            else:
                # 输出安静一段时间（且已运行够 min_wait 秒）视为本次响应结束
                if last_data_at and time.time() - last_data_at >= quiet and time.time() - start_at >= min_wait:
                    break
                time.sleep(0.2)
        return ''.join(chunks)

    @staticmethod
    def _capture_jump_login_banner(jump_config, wait_seconds: float = 25.0) -> str:
        """以交互式 shell 登录跳板机，捕获登录欢迎信息/堡垒机主机菜单后立即断开"""
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        channel = None
        try:
            client.connect(**SystemTaskService._ssh_connect_kwargs(jump_config))
            # GateShell 需要 pty 才能进入 TUI 菜单
            channel = client.get_transport().open_session(timeout=10)
            channel.settimeout(1.0)
            channel.get_pty(term='xterm', width=200, height=50)
            channel.invoke_shell()
            raw, _ = SystemTaskService._read_channel_until(
                channel, re.compile(r'\d{3}:'), timeout=wait_seconds, idle=4.0
            )
            return raw
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
    def _parse_jump_menu(text: str) -> List[Dict[str, str]]:
        """解析堡垒机主机菜单，返回 [{'index','ip','name','raw'}]，index 为菜单序号（可能为空）

        同时支持两种格式：
        1. GateShell 全屏 TUI 格式：  001: 名称(备注)   10.0.0.1:22   ssh   root
        2. 普通逐行列表格式：  1) web-01   10.1.2.3   或   [2] db-02   10.1.2.4
        GateShell 用光标定位重绘（无换行），需对整段文本 finditer。
        """
        cleaned = SystemTaskService._strip_ansi(text)
        entries = []
        seen = set()

        # GateShell 格式：NNN: 名称(备注)   IP:port   proto   user
        # 名称中可能含数字（tomcat01），故用 IP:port 作为右锚点做非贪婪匹配
        gate_re = re.compile(
            r'(\d{3}):\s+(.*?)\s+((?:\d{1,3}\.){3}\d{1,3}):(\d+)\s+(\S+)\s+(\S+)'
        )
        for m in gate_re.finditer(cleaned):
            idx, name, ip, port, proto, user = m.groups()
            if ip in seen:
                continue
            parts = [int(p) for p in ip.split('.')]
            if any(p > 255 for p in parts) or parts[0] in (0, 127):
                continue
            seen.add(ip)
            entries.append({
                'index': idx.lstrip('0') or '0',
                'ip': ip,
                'name': name.strip()[:60],
                'raw': m.group(0).strip()[:160],
                'port': port,
                'proto': proto,
                'user': user,
            })
        if entries:
            return sorted(entries, key=lambda e: int(e['index']) if e['index'].isdigit() else 0)

        # 普通逐行列表格式
        for line in cleaned.splitlines():
            match = re.search(r'(?<![\d.])((?:\d{1,3}\.){3}\d{1,3})(?![\d.])', line)
            if not match:
                continue
            ip = match.group(1)
            parts = [int(p) for p in ip.split('.')]
            if any(p > 255 for p in parts) or parts[0] in (0, 127) or ip == '255.255.255.255':
                continue
            if ip in seen:
                continue
            seen.add(ip)
            # 序号通常出现在 IP 之前，形如 "1)" "[2]" "3." "4:" "001:"
            idx_match = re.search(
                r'[\[\(]?\s*(\d{1,3})\s*[\]\)\.、:：>\-]', line[:match.start()]
            )
            entries.append({
                'index': idx_match.group(1) if idx_match else '',
                'ip': ip,
                'name': line[match.end():].strip(' \t-|:：)>】')[:60],
                'raw': line.strip()[:160],
            })
        return entries

    @staticmethod
    def _find_menu_entry(entries, target_config):
        """在堡垒机菜单中按 IP（其次按配置名）定位目标机记录"""
        normalize = SystemTaskService._normalize_host
        target_host = normalize(getattr(target_config, 'host', ''))
        target_name = (getattr(target_config, 'name', '') or '').strip().lower()
        for entry in entries:
            if entry.get('ip') and normalize(entry['ip']) == target_host:
                return entry
        if target_name:
            for entry in entries:
                if target_name in (entry.get('name') or '').lower():
                    return entry
        return None

    @staticmethod
    def _extract_ipv4_list(text: str) -> List[str]:
        """从跳板机输出中提取 IPv4（去掉 ANSI 控制符、回环与非法地址，保持原顺序去重）"""
        ips = []
        for ip in re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', SystemTaskService._strip_ansi(text)):
            parts = [int(p) for p in ip.split('.')]
            if any(p > 255 for p in parts):
                continue
            if parts[0] == 0 or parts[0] == 127 or ip == '255.255.255.255':
                continue
            if ip not in ips:
                ips.append(ip)
        return ips

    @staticmethod
    def _normalize_host(host: str) -> str:
        """归一化主机标识：去空白、去端口、去 IPv6 方括号、转小写"""
        value = (host or '').strip().lower()
        if not value:
            return ''
        if value.startswith('['):
            value = value[1:value.find(']')] if ']' in value else value[1:]
        elif value.count(':') == 1:
            value = value.split(':', 1)[0]
        return value.rstrip('.')

    @staticmethod
    def _read_jump_host_known_hosts(jump_config) -> str:
        """兜底读取跳板机上 /etc/hosts 与 known_hosts 中记录过的主机"""
        command = (
            "cat /etc/hosts 2>/dev/null; echo '=== known_hosts ==='; "
            "cat ~/.ssh/known_hosts 2>/dev/null | cut -d' ' -f1"
        )
        try:
            out, err, _code = SystemTaskService._run_command_on_jump(jump_config, command, 15)
            return (out or '') + '\n' + (err or '')
        except Exception as exc:
            return f'<读取失败: {exc}>'

    @staticmethod
    def _bastion_cache_key(jump_config):
        return getattr(jump_config, 'id', None) or getattr(jump_config, 'host', '')

    @staticmethod
    def _bastion_menu_supported(jump_config) -> bool:
        """跳板机是否支持堡垒机菜单序号跳转；无缓存记录时先按支持处理（尝试后写回缓存）"""
        key = SystemTaskService._bastion_cache_key(jump_config)
        with _bastion_menu_lock:
            item = _bastion_menu_cache.get(key)
            if item and item.get('expires_at', 0) > time.time():
                return bool(item.get('supported'))
        return True

    @staticmethod
    def _cache_bastion_menu_support(jump_config, supported: bool):
        key = SystemTaskService._bastion_cache_key(jump_config)
        if not key:
            return
        with _bastion_menu_lock:
            _bastion_menu_cache[key] = {
                'supported': bool(supported),
                'expires_at': time.time() + _BASTION_MENU_CACHE_TTL,
            }

    @staticmethod
    def _fetch_bastion_menu(jump_config):
        """获取跳板机/堡垒机上的主机菜单，返回 (菜单项列表, 来源, 原始输出摘要)

        菜单项形如 {'index': '1', 'ip': '10.1.2.3', 'name': 'web-01', 'raw': '...'}。
        依次尝试：配置的授权清单命令 → 登录交互式 shell 抓取主机菜单 → /etc/hosts 与 known_hosts（无序号）。
        全部失败时返回空列表与来源 none，原始输出放在第三个返回值中供前端排查。
        """
        trails = []
        command = (getattr(jump_config, 'authorized_hosts_command', '') or '').strip()
        if command:
            try:
                out, err, code = SystemTaskService._run_command_on_jump(jump_config, command, 15)
                text = (out or '') + '\n' + (err or '')
                entries = SystemTaskService._parse_jump_menu(text)
                if entries:
                    if any(entry.get('index') for entry in entries):
                        SystemTaskService._cache_bastion_menu_support(jump_config, True)
                    return entries, 'command', text.strip()[:2000]
                detail = (err or out or '').strip()[:120] or f'退出码 {code}'
                trails.append(f'授权主机清单命令未返回可解析主机（{detail}）')
            except Exception as exc:
                trails.append(f'授权主机清单命令执行失败: {str(exc)[:120]}')

        banner = ''
        try:
            banner = SystemTaskService._capture_jump_login_banner(jump_config)
        except Exception as exc:
            trails.append(f'登录菜单抓取失败: {str(exc)[:120]}')
        banner_entries = SystemTaskService._parse_jump_menu(banner)
        if banner_entries:
            has_index = any(entry.get('index') for entry in banner_entries)
            # 菜单带序号才代表可用「输入序号跳转」方式登录目标机
            SystemTaskService._cache_bastion_menu_support(jump_config, has_index)
            return banner_entries, 'banner', banner.strip()[-2000:]
        SystemTaskService._cache_bastion_menu_support(jump_config, False)
        trails.append('登录欢迎信息/主机菜单中未解析到主机')

        hosts_text = SystemTaskService._read_jump_host_known_hosts(jump_config)
        hosts_ips = SystemTaskService._extract_ipv4_list(hosts_text)
        if hosts_ips:
            entries = [
                {'index': '', 'ip': ip, 'name': '', 'raw': ip}
                for ip in hosts_ips
            ]
            return entries, 'hosts', hosts_text.strip()[:2000]
        trails.append('/etc/hosts 与 known_hosts 中未解析到 IP')

        sample = '\n'.join([
            '【尝试记录】', '\n'.join(trails),
            '', '【登录菜单原始输出】', banner.strip()[-1500:] or '(空)',
            '', '【hosts/known_hosts 原始输出】', hosts_text.strip()[:800] or '(空)',
        ])
        return [], 'none', sample

    @staticmethod
    def _type_chars(channel, text: str, delay: float = 0.1):
        """逐字符输入（GateShell 菜单一次性发送会被吞，必须逐字符）"""
        for ch in text:
            channel.send(ch.encode('utf-8'))
            if delay:
                time.sleep(delay)

    @staticmethod
    def _read_channel_until(channel, until_re, timeout: float, idle: float = 4.0) -> tuple:
        """读取通道直到正则命中或超时，返回 (原始文本, match或None)

        正则在「已剥离 ANSI 且 \\r 已归一为 \\n」的文本上匹配。
        参考 buildCurl GateShellSession._pump。
        """
        raw = ''
        deadline = time.time() + timeout
        last = time.time()
        while time.time() < deadline:
            if time.time() - last > idle:
                break
            if channel.recv_ready():
                chunk = channel.recv(65536).decode('utf-8', errors='replace')
                if chunk:
                    raw += chunk
                    last = time.time()
                    m = until_re.search(SystemTaskService._strip_ansi(raw))
                    if m:
                        return raw, m
            else:
                time.sleep(0.05)
        m = until_re.search(SystemTaskService._strip_ansi(raw))
        return raw, m

    @staticmethod
    def _run_command_via_bastion_menu(jump_config, target_config, command: str, timeout: int):
        """堡垒机模式（参考 buildCurl GateShellSession）：
        登录 → 解析菜单 → /{ip} 搜索进入目标机 → 哨兵包裹执行命令
        """
        import paramiko

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        channel = None
        try:
            try:
                client.connect(**SystemTaskService._ssh_connect_kwargs(jump_config))
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError(f'堡垒机[{jump_config.name}]连接失败: {str(exc)}') from exc

            # GateShell 需要 pty 才能进入 TUI 菜单
            channel = client.get_transport().open_session(timeout=10)
            channel.settimeout(1.0)
            channel.get_pty(term='xterm', width=200, height=50)
            channel.invoke_shell()

            # 等待菜单渲染完成（GateShell 全屏 TUI，用 idle 判定渲染结束）
            raw = SystemTaskService._read_channel(channel, 25, quiet=4.0, min_wait=3.0)
            menu_text = SystemTaskService._strip_ansi(raw)
            entries = SystemTaskService._parse_jump_menu(menu_text)
            if not entries:
                SystemTaskService._cache_bastion_menu_support(jump_config, False)
                raise ValueError('堡垒机登录后未解析到主机菜单')

            entry = SystemTaskService._find_menu_entry(entries, target_config)
            if not entry:
                raise ValueError(
                    f'堡垒机授权菜单中未找到目标机 {target_config.host}（菜单共 {len(entries)} 台）'
                )

            # 用 /{ip} 搜索 + 回车进入目标机（GateShell 菜单交互方式）
            target_ip = entry['ip']
            SystemTaskService._type_chars(channel, f'/{target_ip}', delay=0.1)
            time.sleep(1.2)
            channel.send(b'\r')  # 执行搜索
            SystemTaskService._read_channel_until(
                channel, re.compile(r'.'), timeout=10, idle=2.5
            )
            channel.send(b'\r')  # 回车进入选中行

            # 用哨兵回显确认目标机 shell 已可交互（比匹配提示符更可靠）
            ready = f'__BASTION_READY_{uuid.uuid4().hex[:8]}__'
            time.sleep(1.0)
            SystemTaskService._type_chars(channel, f'echo {ready}', delay=0.02)
            channel.send(b'\r')
            raw_ready, m_ready = SystemTaskService._read_channel_until(
                channel, re.compile(r'(?m)^' + re.escape(ready) + r'[ \t]*$'),
                timeout=40, idle=5.0
            )
            if not m_ready:
                text = SystemTaskService._strip_ansi(raw_ready).strip()
                low = text.lower()
                hint = ''
                if 'permission' in low or 'denied' in low or 'not authorized' in low:
                    hint = '（堡垒机拒绝了该连接）'
                elif 'not found' in low or 'no such' in low:
                    hint = '（菜单中未找到该机器）'
                raise ValueError(
                    f'进入目标机 {target_ip} 失败{hint}，请确认该机器在堡垒机授权列表内。'
                )

            # 排空欢迎语/提示符/哨兵回显，避免污染业务命令输出
            SystemTaskService._read_channel(channel, 1.5, quiet=0.4)

            # 执行命令：双哨兵 + 退出码（stderr 合并进 stdout）
            token = uuid.uuid4().hex[:10]
            start_mark = f'__BS_S_{token}__'
            end_mark = f'__BS_E_{token}__'
            wrapped = (
                f'echo {start_mark}; {command} 2>&1; '
                f'__ec=$?; echo; echo {end_mark}$__ec'
            )
            start_pat = re.compile(r'(?m)^' + re.escape(start_mark) + r'[ \t]*$')
            end_pat = re.compile(r'(?m)^' + re.escape(end_mark) + r'(\d+)[ \t]*$')

            SystemTaskService._type_chars(channel, wrapped, delay=0)
            channel.send(b'\r')

            exec_deadline = time.time() + timeout + 10
            raw = ''

            def _match(pattern):
                return pattern.search(SystemTaskService._strip_ansi(raw))

            # 阶段一：等 START 独占成行
            while time.time() < exec_deadline and not _match(start_pat):
                chunk, _ = SystemTaskService._read_channel_until(
                    channel, start_pat, timeout=5.0, idle=5.0
                )
                if chunk:
                    raw += chunk
            if not _match(start_pat):
                raise ValueError('堡垒机目标机未开始执行命令（超时）')

            # 阶段二：流式读取到 END 行
            match = None
            while time.time() < exec_deadline:
                match = _match(end_pat)
                if match:
                    break
                chunk, _ = SystemTaskService._read_channel_until(
                    channel, end_pat, timeout=3.0, idle=3.0
                )
                if chunk:
                    raw += chunk

            if not match:
                raise ValueError('堡垒机目标机执行超时（未收到结束标记）')

            exit_code = int(match.group(1))
            # 提取 START 与 END 之间的正文
            text = SystemTaskService._strip_ansi(raw)
            m_start = start_pat.search(text)
            body_start = m_start.end() if m_start else 0
            m_end = end_pat.search(text)
            body_end = m_end.start() if m_end else len(text)
            body = text[body_start:body_end].strip('\n')
            # 去掉尾部残留的 shell 提示符
            body = re.sub(r'\[[^\]\n]*\][#$][ \t]*$', '', body.rstrip()).rstrip()

            SystemTaskService._cache_bastion_menu_support(jump_config, True)
            return body, '', exit_code
        finally:
            if channel is not None:
                try:
                    channel.send('exit\n')
                except Exception:
                    pass
                try:
                    channel.close()
                except Exception:
                    pass
            try:
                client.close()
            except Exception:
                pass

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
        """依次尝试：堡垒机菜单序号跳转 → 跳板机免密 ssh → 目标机凭据 + 端口转发"""
        errors = []

        if SystemTaskService._bastion_menu_supported(jump_config):
            try:
                return SystemTaskService._run_command_via_bastion_menu(
                    jump_config, target_config, command, timeout
                )
            except Exception as exc:
                detail = str(exc)[:200]
                errors.append(f'堡垒机菜单跳转失败: {detail}')
                logger.info(
                    "堡垒机菜单跳转失败(%s -> %s): %s",
                    jump_config.name, target_config.host, detail
                )

        jump_command = SystemTaskService._build_jump_side_ssh_command(target_config, command)
        try:
            out, err, exit_code = SystemTaskService._run_command_on_jump(
                jump_config, jump_command, timeout
            )
            # ssh 自身失败（认证/网络）固定返回 255，其余退出码来自目标机上的命令
            if exit_code != 255:
                return out, err, exit_code
            detail = (err or out or '').strip()[:200] or '无输出'
            errors.append(f'跳板机免密登录目标机返回 255: {detail}')
        except Exception as exc:
            errors.append(f'跳板机免密登录目标机失败: {str(exc)[:200]}')

        try:
            return SystemTaskService._run_ssh_command_via_tunnel(
                jump_config, target_config, command, timeout
            )
        except Exception as exc:
            errors.append(f'目标机凭据+端口转发失败: {str(exc)[:200]}')
            raise ValueError(
                '无法通过跳板机[{}]登录目标机[{}]：{}'.format(
                    jump_config.name, target_config.name, '；'.join(errors)
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
                      sign_key: str, sign_method: str, sign_param_name: str = 'sign') -> str:
        """计算签名（参考 buildCurl 项目的 Java 风格签名算法）

        规则：过滤空值/sign参数 → 键名不区分大小写排序 → 拼接 k1=v1&k2=v2& → 追加 key={secret}
        → MD5/SHA256 → 全大写十六进制。
        """
        # 汇总参与签名的参数（query + body 字段）
        all_params = dict(params) if params else {}

        # body 中的参数也并入签名（参考 buildCurl: JSON/Form/Raw 都并入）
        if body:
            body_text = body.strip()
            content_type = (headers or {}).get('Content-Type', '')
            if 'application/json' in content_type or body_text.startswith('{'):
                try:
                    obj = json.loads(body_text)
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, bool):
                                all_params[str(k)] = 'true' if v else 'false'
                            elif isinstance(v, (dict, list)):
                                all_params[str(k)] = json.dumps(v, separators=(',', ':'), ensure_ascii=False)
                            elif v is not None:
                                all_params[str(k)] = v
                except (json.JSONDecodeError, TypeError):
                    pass
            elif 'application/x-www-form-urlencoded' in content_type or '&' in body_text:
                for pair in body_text.split('&'):
                    pair = pair.strip()
                    if '=' in pair:
                        k, v = pair.split('=', 1)
                        all_params[k.strip()] = v.strip()

        # 过滤空值与 sign 参数本身，键名不区分大小写排序
        filtered = {
            k: v for k, v in all_params.items()
            if v is not None and str(v) != '' and str(k) != sign_param_name
        }
        sorted_items = sorted(filtered.items(), key=lambda x: x[0].upper())
        sign_str = '&'.join(f'{k}={v}' for k, v in sorted_items) + '&'
        sign_str += f'key={sign_key}'

        method = (sign_method or 'md5').lower()
        if method in ('sha256', 'sha256_upper'):
            return hashlib.sha256(sign_str.encode('utf-8')).hexdigest().upper()
        elif method == 'hmac_sha256':
            return hmac.new(sign_key.encode('utf-8'), sign_str.encode('utf-8'), hashlib.sha256).hexdigest().upper()
        elif method == 'sha1':
            return hashlib.sha1(sign_str.encode('utf-8')).hexdigest().upper()
        else:
            # md5 / md5_upper / 默认
            return hashlib.md5(sign_str.encode('utf-8')).hexdigest().upper()

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

        # Signing（参考 buildCurl 签名算法）
        if system_task.sign_enabled and system_task.sign_key:
            sign_name = system_task.sign_param_name or 'sign'
            sign = SystemTaskService._compute_sign(
                request_params, body, headers,
                system_task.sign_key, system_task.sign_method,
                sign_param_name=sign_name
            )
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
