"""系统任务批量执行服务

流程：解析上传的参数文件 → 按字段映射逐行执行系统任务 → 汇总结果写入 Excel 供下载
"""
import os
import re
import json
import uuid
import threading
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from flask import current_app

from app import db
from app.models.system_task import SystemTask, SystemTaskBatch, SystemTaskExecution
from app.models.script import Script
from app.services.system_task_service import SystemTaskService
from app.utils.excel_writer import ExcelWriter

logger = logging.getLogger(__name__)

STATUS_COLUMN = '执行状态'
ERROR_COLUMN = '错误信息'

# SSH 远程 API 批量执行：单次 SSH 连接最多打包的 curl 条数与总字符数
# 目标机通过跳板机交互式终端下发命令，单行过长可能被终端行缓冲截断，因此同时按字符数分批
SSH_CURL_CHUNK_MAX_COMMANDS = 10
SSH_CURL_CHUNK_MAX_CHARS = 2000


class SystemTaskBatchService:
    """系统任务批量执行服务"""

    # ------------------------------------------------------------------
    # 参数文件读取
    # ------------------------------------------------------------------
    @staticmethod
    def read_table(file_path: str, sheet_name: str = None,
                   limit: Optional[int] = None) -> Tuple[List[str], List[Dict[str, str]]]:
        """读取参数文件（xlsx/xls/csv），返回 (列名列表, 行数据列表)"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.csv':
            df = None
            last_error = None
            for encoding in ('utf-8-sig', 'utf-8', 'gbk', 'gb18030'):
                try:
                    df = pd.read_csv(file_path, dtype=str, encoding=encoding, nrows=limit)
                    break
                except UnicodeDecodeError as exc:
                    last_error = exc
            if df is None:
                raise ValueError(f'CSV文件编码无法识别: {last_error}')
        else:
            df = pd.read_excel(file_path, dtype=str, sheet_name=sheet_name or 0, nrows=limit)

        df = df.fillna('')
        columns = [str(col).strip() for col in df.columns]
        rows: List[Dict[str, str]] = []
        for _, series in df.iterrows():
            row: Dict[str, str] = {}
            for key, value in series.items():
                row[str(key).strip()] = '' if value is None else str(value).strip()
            rows.append(row)
        return columns, rows

    # ------------------------------------------------------------------
    # 批量执行
    # ------------------------------------------------------------------
    @staticmethod
    def create_batch(system_task: SystemTask, file_path: str, file_name: str,
                     param_mapping: Dict[str, str], params_defaults: Dict[str, Any],
                     database_id: int = None, sheet_name: str = None,
                     created_by: int = None) -> SystemTaskBatch:
        batch = SystemTaskBatch(
            batch_id=str(uuid.uuid4()),
            system_task_id=system_task.id,
            status='pending',
            progress=0,
            input_file=file_path,
            input_file_name=file_name,
            sheet_name=sheet_name,
            database_id=database_id,
            created_by=created_by,
        )
        batch.set_param_mapping(param_mapping)
        batch.set_params_defaults(params_defaults)
        db.session.add(batch)
        db.session.commit()
        return batch

    @staticmethod
    def execute_async(app, batch_id: str):
        thread = threading.Thread(
            target=SystemTaskBatchService._execute_batch,
            args=(app, batch_id),
            daemon=True,
        )
        thread.start()

    @staticmethod
    def get_param_configs(system_task: SystemTask) -> List[Dict[str, Any]]:
        """获取任务参数定义（SQL 任务取关联脚本的参数配置）"""
        if system_task.task_type == 'sql':
            script = Script.query.get(system_task.script_id) if system_task.script_id else None
            return script.get_params_config() if script else []
        return system_task.get_params_config() or []

    @staticmethod
    def _execute_batch(app, batch_id: str):
        with app.app_context():
            batch = SystemTaskBatch.query.filter_by(batch_id=batch_id).first()
            if not batch:
                logger.warning(f'批量执行记录不存在: {batch_id}')
                return

            try:
                system_task = SystemTask.query.get(batch.system_task_id)
                if not system_task:
                    raise ValueError('系统任务不存在')

                batch.status = 'running'
                batch.started_at = datetime.utcnow()
                batch.progress = 3
                batch.add_log('开始批量执行')
                db.session.commit()

                mapping = batch.get_param_mapping()
                defaults = batch.get_params_defaults()
                columns, rows = SystemTaskBatchService.read_table(
                    batch.input_file, sheet_name=batch.sheet_name
                )

                missing = [col for col in mapping.values() if col not in columns]
                if missing:
                    raise ValueError(f'字段映射的文件列不存在: {", ".join(missing)}')

                rows = [row for row in rows if any(str(row.get(col, '') or '').strip() for col in columns)]
                total = len(rows)
                batch.total_rows = total
                batch.processed_rows = 0
                batch.success_count = 0
                batch.failure_count = 0
                batch.progress = 5
                batch.add_log(f'参数文件解析完成，共 {total} 行有效数据')
                db.session.commit()

                if total == 0:
                    batch.progress = 100
                    batch.status = 'completed'
                    batch.completed_at = datetime.utcnow()
                    batch.error_message = '参数文件中没有有效数据行'
                    batch.add_log('参数文件中没有有效数据行，未生成结果文件', 'warning')
                    db.session.commit()
                    return

                param_configs = SystemTaskBatchService.get_param_configs(system_task)
                input_columns = list(columns)
                status_column = STATUS_COLUMN if STATUS_COLUMN not in input_columns else f'{STATUS_COLUMN}(系统)'
                error_column = ERROR_COLUMN if ERROR_COLUMN not in input_columns else f'{ERROR_COLUMN}(系统)'
                result_columns: List[str] = []
                output_rows: List[Dict[str, Any]] = []
                success_count = 0
                failure_count = 0

                # 远程 API 任务（配置了跳板机）走「分批打包 curl → 目标机批量执行」模式，
                # 避免每行都建立一次 SSH 连接；其余任务保持本地逐行执行
                ssh_api_mode = system_task.task_type == 'api' and bool(system_task.ssh_config_id)
                if ssh_api_mode:
                    jump_config, target_config = SystemTaskBatchService._load_ssh_configs(system_task)
                    batch.add_log(
                        f'检测到远程API任务，将分批打包curl后经跳板机[{jump_config.name}]'
                        f'在目标机[{target_config.host}]批量执行'
                    )
                    db.session.commit()
                    result_iter = SystemTaskBatchService._iter_api_ssh_results(
                        batch, system_task, rows, param_configs, mapping, defaults,
                        batch.created_by, jump_config, target_config
                    )
                else:
                    result_iter = SystemTaskBatchService._iter_local_results(
                        system_task, rows, param_configs, mapping, defaults,
                        batch.database_id, batch.created_by
                    )

                for index, (row, success, result_data, error) in enumerate(result_iter, 1):
                    flat_rows = SystemTaskBatchService._flatten_result(
                        system_task.task_type, result_data
                    )
                    if not flat_rows:
                        flat_rows = [{}]

                    for flat in flat_rows:
                        renamed: Dict[str, Any] = {}
                        for key, value in flat.items():
                            target_key = key
                            if target_key in input_columns or target_key in (status_column, error_column):
                                target_key = f'结果.{key}'
                            renamed[target_key] = SystemTaskBatchService._to_cell_value(value)
                            if target_key not in result_columns:
                                result_columns.append(target_key)

                        output = {}
                        for col in input_columns:
                            output[col] = SystemTaskBatchService._to_cell_value(row.get(col, ''))
                        output.update(renamed)
                        output[status_column] = '成功' if success else '失败'
                        output[error_column] = error or ''
                        output_rows.append(output)

                    if success:
                        success_count += 1
                    else:
                        failure_count += 1

                    batch.processed_rows = index
                    batch.success_count = success_count
                    batch.failure_count = failure_count
                    batch.progress = min(95, 5 + int(index * 90 / total))
                    if index == 1 or index % 10 == 0 or index == total:
                        batch.add_log(f'已处理 {index}/{total} 行，成功 {success_count}，失败 {failure_count}')
                    db.session.commit()

                    if not success:
                        logger.warning(
                            f'批量执行第 {index} 行失败: task={system_task.id}, error={error}'
                        )

                # 写入汇总结果
                if output_rows:
                    output_path = SystemTaskBatchService._write_output(
                        batch, system_task, input_columns, result_columns,
                        status_column, error_column, output_rows
                    )
                    batch.output_file = output_path
                    batch.status = 'completed'
                    batch.add_log(f'结果文件已生成: {os.path.basename(output_path)}')
                else:
                    batch.status = 'failed'
                    batch.error_message = '所有行均未返回可写入的结果'
                    batch.add_log('所有行均未返回可写入的结果，未生成结果文件', 'warning')

                batch.progress = 100
                batch.completed_at = datetime.utcnow()
                batch.add_log(f'批量执行完成，成功 {success_count} 行，失败 {failure_count} 行')
                db.session.commit()

            except Exception as exc:
                logger.exception(f'批量执行失败: batch_id={batch_id}')
                db.session.rollback()
                try:
                    batch = SystemTaskBatch.query.filter_by(batch_id=batch_id).first()
                    if batch:
                        batch.status = 'failed'
                        batch.progress = 100
                        batch.error_message = str(exc)
                        batch.completed_at = datetime.utcnow()
                        batch.add_log(f'批量执行失败: {exc}', 'error')
                        db.session.commit()
                except Exception:
                    db.session.rollback()
                    logger.exception('更新批量执行失败状态时出错')
            finally:
                db.session.remove()

    # ------------------------------------------------------------------
    # 逐行结果迭代器（本地执行 / 远程分批 curl）
    # ------------------------------------------------------------------
    @staticmethod
    def _iter_local_results(system_task: SystemTask, rows: List[Dict[str, str]],
                            param_configs: List[Dict[str, Any]], mapping: Dict[str, str],
                            defaults: Dict[str, Any], database_id: int = None,
                            created_by: int = None):
        """本地逐行执行，逐条产出 (原始行, 是否成功, 结果数据, 错误信息)"""
        for row in rows:
            params_values = SystemTaskBatchService._build_params(
                param_configs, mapping, defaults, row
            )
            success, result_data, error = SystemTaskBatchService._execute_single(
                system_task, params_values, database_id, created_by
            )
            yield row, success, result_data, error

    @staticmethod
    def _load_ssh_configs(system_task: SystemTask):
        """加载并校验跳板机 / 目标机配置"""
        from app.models.ssh_config import SshConfig

        jump_config = SshConfig.query.get(system_task.ssh_config_id)
        if not jump_config or not jump_config.is_active:
            raise ValueError('SSH跳板机不存在或已停用')
        if not system_task.target_ssh_config_id:
            raise ValueError('未配置目标机器SSH配置')
        target_config = SshConfig.query.get(system_task.target_ssh_config_id)
        if not target_config or not target_config.is_active:
            raise ValueError('目标机器SSH配置不存在或已停用')
        return jump_config, target_config

    @staticmethod
    def _iter_api_ssh_results(batch: SystemTaskBatch, system_task: SystemTask,
                              rows: List[Dict[str, str]], param_configs: List[Dict[str, Any]],
                              mapping: Dict[str, str], defaults: Dict[str, Any],
                              created_by: int, jump_config, target_config):
        """远程 API 批量执行：先为每行构造 curl 命令，再分批在目标机一次性执行"""
        chunk: List[Dict[str, Any]] = []
        chunk_chars = 0
        chunk_no = 0

        for row in rows:
            params_values = SystemTaskBatchService._build_params(
                param_configs, mapping, defaults, row
            )
            item, error = SystemTaskBatchService._prepare_api_stage(
                system_task, params_values, created_by, jump_config, target_config
            )
            if item is None:
                yield row, False, {}, error
                continue
            item['row'] = row

            # 达到条数或字符数上限时先下发当前批次，避免单行过长被终端截断
            if chunk and (
                len(chunk) >= SSH_CURL_CHUNK_MAX_COMMANDS
                or chunk_chars + len(item['command']) > SSH_CURL_CHUNK_MAX_CHARS
            ):
                chunk_no += 1
                yield from SystemTaskBatchService._run_ssh_curl_chunk(
                    batch, system_task, jump_config, target_config, chunk, chunk_no
                )
                chunk = []
                chunk_chars = 0

            chunk.append(item)
            chunk_chars += len(item['command'])

        if chunk:
            chunk_no += 1
            yield from SystemTaskBatchService._run_ssh_curl_chunk(
                batch, system_task, jump_config, target_config, chunk, chunk_no
            )

    @staticmethod
    def _prepare_api_stage(system_task: SystemTask, params_values: Dict[str, Any],
                           created_by: int, jump_config, target_config):
        """准备单行请求：解析参数、构造请求、生成 curl 命令（不执行）"""
        execution = SystemTaskService.create_execution(system_task.id, params_values, created_by)
        execution.task_type = 'api'
        db.session.commit()
        execution_db_id = execution.id

        try:
            resolved = SystemTaskService._resolve_runtime_params(execution, system_task, params_values)
            prepared = SystemTaskService._prepare_api_request(execution, system_task, resolved)
            if not SystemTaskService._is_http_url(prepared['url']):
                raise ValueError('API地址必须是 http/https 协议')

            command, _ = SystemTaskService._build_curl_arguments(prepared, mask_sensitive=False)
            preview, _ = SystemTaskService._build_curl_arguments(prepared, mask_sensitive=True)
            prepared['request_info'].update({
                'via': 'ssh-batch',
                'ssh_config_id': jump_config.id,
                'ssh_config_name': jump_config.name,
                'target_ssh_config_id': target_config.id,
                'target_ssh_config_name': target_config.name,
                'target_host': target_config.host,
                'target_port': target_config.port or 22,
                'curl_preview': preview[:4000],
            })

            execution.progress = 40
            execution.add_log(f'curl命令已打包(敏感头已脱敏): {preview[:2000]}')
            execution.add_log('等待批量下发到目标机执行')
            db.session.commit()
            return {
                'execution_db_id': execution_db_id,
                'execution_id': execution.execution_id,
                'prepared': prepared,
                'command': command,
                'timeout': int(prepared['timeout'] or 30),
            }, ''
        except Exception as exc:
            error = str(exc)
            db.session.rollback()
            SystemTaskBatchService._mark_execution_failed(execution_db_id, error)
            return None, error

    @staticmethod
    def _run_ssh_curl_chunk(batch: SystemTaskBatch, system_task: SystemTask,
                            jump_config, target_config, chunk: List[Dict[str, Any]],
                            chunk_no: int):
        """一次 SSH 连接内批量执行多条 curl，并按标记解析每条响应"""
        token = uuid.uuid4().hex[:10]
        parts = []
        timeout_total = 15
        for position, item in enumerate(chunk):
            item['start_mark'] = f'__BT_S_{token}_{position}__'
            item['end_mark'] = f'__BT_E_{token}_{position}__'
            parts.append(
                f"echo {item['start_mark']}; {item['command']} 2>&1; __bt_ec=$?; "
                f"echo; echo {item['end_mark']}$__bt_ec"
            )
            timeout_total += item['timeout'] + 5

        batch.add_log(f'第 {chunk_no} 批：已打包 {len(chunk)} 条curl，开始下发目标机批量执行')
        db.session.commit()

        try:
            out, err, exit_code = SystemTaskService._run_ssh_command_via_jump(
                jump_config, target_config, '; '.join(parts), min(timeout_total, 3600)
            )
        except Exception as exc:
            message = f'批量下发目标机失败: {str(exc)[:300]}'
            batch.add_log(f'第 {chunk_no} 批：{message}', 'error')
            db.session.commit()
            for item in chunk:
                SystemTaskBatchService._mark_execution_failed(item['execution_db_id'], message)
                yield item['row'], False, {}, message
            return

        out = out or ''
        batch.add_log(f'第 {chunk_no} 批：目标机执行完成，返回 {len(out)} 字节')
        db.session.commit()

        for item in chunk:
            pattern = re.compile(
                r'(?ms)^' + re.escape(item['start_mark']) + r'[ \t]*\r?\n'
                r'(.*?)\r?\n' + re.escape(item['end_mark']) + r'(\d+)[ \t]*$'
            )
            match = pattern.search(out)
            if not match:
                message = f'第 {chunk_no} 批未收到该行响应（目标机可能中断输出）'
                if err:
                    message += f'：{str(err).strip()[:500]}'
                SystemTaskBatchService._mark_execution_failed(item['execution_db_id'], message)
                yield item['row'], False, {}, message
                continue

            section = match.group(1)
            row_exit = int(match.group(2))
            if row_exit != 0:
                detail = (section or err or '').strip()[:1000] or '无输出'
                if 'not supported or disabled in libcurl' in detail:
                    detail += (
                        '（提示：请检查API地址是否含前导空格或换行；若地址正常，'
                        '在目标机执行 curl -V 确认 Protocols 是否包含 https）'
                    )
                message = f'目标机curl执行失败(exit={row_exit})：{detail}'
                SystemTaskBatchService._mark_execution_failed(item['execution_db_id'], message)
                yield item['row'], False, {}, message
                continue

            try:
                status_code, content_type, elapsed, body_text = (
                    SystemTaskService._parse_curl_output(section)
                )
            except Exception as exc:
                message = f'解析目标机响应失败: {exc}'
                SystemTaskBatchService._mark_execution_failed(item['execution_db_id'], message)
                yield item['row'], False, {}, message
                continue

            success, result_data, error = SystemTaskBatchService._finalize_ssh_curl_row(
                system_task, item, status_code, content_type, elapsed, body_text
            )
            yield item['row'], success, result_data, error

    @staticmethod
    def _finalize_ssh_curl_row(system_task: SystemTask, item: Dict[str, Any],
                               status_code: int, content_type: str, elapsed: str,
                               body_text: str):
        """将目标机单条 curl 响应按既有 API 任务逻辑落库"""
        execution_db_id = item['execution_db_id']
        try:
            execution = db.session.get(SystemTaskExecution, execution_db_id)
            if not execution:
                raise ValueError('执行记录不存在')

            execution.progress = 80
            execution.add_log(f'目标机响应状态码: {status_code}')
            db.session.commit()

            resp_headers = {'Content-Type': content_type} if content_type else {}
            try:
                resp_data = json.loads(body_text)
                resp_text = json.dumps(resp_data, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                resp_data = body_text
                resp_text = body_text

            SystemTaskService._finalize_api_response(
                execution, system_task, item['prepared'], status_code,
                resp_headers, resp_data, resp_text, elapsed=elapsed,
            )

            execution = db.session.get(SystemTaskExecution, execution_db_id)
            status = execution.status if execution else 'failed'
            result_data = execution.get_result_data() if execution else {}
            error = execution.error_message if execution and execution.error_message else ''
            return status == 'completed', result_data or {}, error
        except Exception as exc:
            db.session.rollback()
            message = f'处理目标机响应失败: {exc}'
            SystemTaskBatchService._mark_execution_failed(execution_db_id, message)
            return False, {}, message

    @staticmethod
    def _mark_execution_failed(execution_db_id: int, error: str):
        """将执行记录标记为失败（不影响批次继续处理其他行）"""
        try:
            execution = db.session.get(SystemTaskExecution, execution_db_id)
            if not execution:
                return
            execution.status = 'failed'
            execution.progress = 100
            execution.error_message = error
            execution.completed_at = datetime.utcnow()
            execution.add_log(f'执行失败: {error}', 'error')
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.exception('标记执行记录失败状态时出错')

    @staticmethod
    def _build_params(param_configs: List[Dict[str, Any]], mapping: Dict[str, str],
                      defaults: Dict[str, Any], row: Dict[str, str]) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        for config in param_configs:
            name = config.get('name')
            if not name:
                continue
            if name in mapping:
                value = row.get(mapping[name], '')
            elif name in defaults:
                value = defaults[name]
            else:
                value = config.get('default', '')
            params[name] = SystemTaskBatchService._normalize_param_value(value, config.get('type'))
        return params

    @staticmethod
    def _normalize_param_value(value: Any, param_type: str = None) -> Any:
        if value is None:
            return ''
        if isinstance(value, (list, tuple)):
            return list(value)
        text = str(value)
        if param_type == 'list':
            parts = re.split(r'[,，;；\n\r]+', text)
            return [part.strip() for part in parts if part.strip()]
        return text

    @staticmethod
    def _execute_single(system_task: SystemTask, params_values: Dict[str, Any],
                        database_id: int = None, created_by: int = None):
        """同步执行一次系统任务，返回 (是否成功, 结果数据, 错误信息)"""
        execution = SystemTaskService.create_execution(system_task.id, params_values, created_by)
        execution.task_type = system_task.task_type
        db.session.commit()
        execution_db_id = execution.id

        error = ''
        try:
            if system_task.task_type == 'sql':
                SystemTaskService._execute_sql(execution, system_task, params_values, database_id)
            elif system_task.task_type == 'api':
                SystemTaskService._execute_api(execution, system_task, params_values)
            elif system_task.task_type == 'script':
                SystemTaskService._execute_script(execution, system_task, params_values)
            else:
                raise ValueError(f'不支持的系统任务类型: {system_task.task_type}')
        except Exception as exc:
            logger.exception(f'系统任务单次执行失败: task={system_task.id}')
            error = str(exc)
            db.session.rollback()
            try:
                execution = db.session.get(SystemTaskExecution, execution_db_id)
                if execution:
                    execution.status = 'failed'
                    execution.progress = 100
                    execution.error_message = error
                    execution.completed_at = datetime.utcnow()
                    db.session.commit()
            except Exception:
                db.session.rollback()

        try:
            execution = db.session.get(SystemTaskExecution, execution_db_id)
            execution_status = execution.status if execution else 'failed'
            result_data = execution.get_result_data() if execution else {}
            if not error and execution and execution.error_message:
                error = execution.error_message
            return execution_status == 'completed', result_data or {}, error
        except Exception:
            db.session.rollback()
            return False, {}, error or '读取执行结果失败'

    # ------------------------------------------------------------------
    # 结果展开
    # ------------------------------------------------------------------
    @staticmethod
    def _flatten_result(task_type: str, result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not result_data:
            return []
        try:
            if task_type == 'sql':
                return SystemTaskBatchService._flatten_sql_result(result_data)
            if task_type == 'api':
                return SystemTaskBatchService._flatten_api_result(result_data)
            if task_type == 'script':
                return SystemTaskBatchService._flatten_script_result(result_data)
        except Exception:
            logger.exception('展开执行结果失败')
        return []

    @staticmethod
    def _flatten_sql_result(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        queries = []
        errors = []
        for db_result in result_data.get('results') or []:
            if not isinstance(db_result, dict):
                continue
            db_name = db_result.get('db_name') or ''
            if db_result.get('error'):
                errors.append(f'{db_name}: {db_result["error"]}')
            for statement in db_result.get('statements') or []:
                if str(statement.get('type', '')).lower() == 'query':
                    queries.append((db_name, statement))

        if not queries:
            if errors:
                return [{'说明': '; '.join(errors)}]
            return [{'说明': f'影响行数: {result_data.get("total_affected", 0)}'}]

        single = len(queries) == 1
        rows: List[Dict[str, Any]] = []
        for query_index, (db_name, statement) in enumerate(queries, 1):
            columns = statement.get('columns') or []
            prefix = '' if single else f'{db_name}.语句{query_index}.'
            for item in statement.get('rows') or []:
                if isinstance(item, dict):
                    rows.append({f'{prefix}{key}': value for key, value in item.items()})
                elif isinstance(item, (list, tuple)):
                    row = {}
                    for cell_index, value in enumerate(item):
                        column = columns[cell_index] if cell_index < len(columns) else f'列{cell_index + 1}'
                        row[f'{prefix}{column}'] = value
                    rows.append(row)

        if errors and not rows:
            return [{'说明': '; '.join(errors)}]
        return rows

    @staticmethod
    def _flatten_api_result(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        response = result_data.get('response')
        status_code = result_data.get('status_code')
        rows: List[Dict[str, Any]] = []

        if isinstance(response, list):
            if response and all(isinstance(item, dict) for item in response):
                for item in response:
                    row: Dict[str, Any] = {}
                    SystemTaskBatchService._flatten_value('', item, row)
                    rows.append(row)
            else:
                rows.append({'响应': json.dumps(response, ensure_ascii=False)})
        elif isinstance(response, dict):
            row = {}
            SystemTaskBatchService._flatten_value('', response, row)
            rows.append(row)
        else:
            rows.append({'响应': '' if response is None else str(response)})

        if status_code is not None:
            for row in rows:
                row['状态码'] = status_code
        return rows

    @staticmethod
    def _flatten_value(prefix: str, value: Any, output: Dict[str, Any], depth: int = 0):
        if isinstance(value, dict):
            if depth >= 3:
                output[prefix or '响应'] = json.dumps(value, ensure_ascii=False)
                return
            for key, item in value.items():
                child_prefix = f'{prefix}.{key}' if prefix else str(key)
                SystemTaskBatchService._flatten_value(child_prefix, item, output, depth + 1)
        elif isinstance(value, list):
            output[prefix or '响应'] = json.dumps(value, ensure_ascii=False)
        else:
            output[prefix or '响应'] = value

    @staticmethod
    def _flatten_script_result(result_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        stdout = result_data.get('stdout')
        stderr = result_data.get('stderr') or ''
        returncode = result_data.get('returncode')

        rows: List[Dict[str, Any]] = []
        if isinstance(stdout, list):
            if stdout and all(isinstance(item, dict) for item in stdout):
                for item in stdout:
                    row: Dict[str, Any] = {}
                    SystemTaskBatchService._flatten_value('', item, row)
                    rows.append(row)
            elif stdout:
                rows.append({'标准输出': json.dumps(stdout, ensure_ascii=False)})
        elif isinstance(stdout, dict):
            row = {}
            SystemTaskBatchService._flatten_value('', stdout, row)
            rows.append(row)
        elif stdout:
            rows.append({'标准输出': str(stdout)})

        if not rows:
            rows.append({})
        for row in rows:
            if returncode is not None:
                row['返回码'] = returncode
            if stderr:
                row['标准错误'] = stderr
        return rows

    # ------------------------------------------------------------------
    # 结果文件
    # ------------------------------------------------------------------
    @staticmethod
    def _write_output(batch: SystemTaskBatch, system_task: SystemTask,
                      input_columns: List[str], result_columns: List[str],
                      status_column: str, error_column: str,
                      output_rows: List[Dict[str, Any]]) -> str:
        output_folder = current_app.config.get('OUTPUT_FOLDER') or current_app.config.get('UPLOAD_FOLDER')
        os.makedirs(output_folder, exist_ok=True)
        file_name = (
            f'system_task_batch_{system_task.id}_'
            f'{datetime.now().strftime("%Y%m%d_%H%M%S")}_{batch.batch_id[:8]}.xlsx'
        )
        output_path = os.path.join(output_folder, file_name)

        headers = input_columns + result_columns + [status_column, error_column]
        data = [[row.get(header, '') for header in headers] for row in output_rows]

        writer = ExcelWriter(output_path)
        writer.create_new()
        writer.create_sheet('批量执行结果')
        writer.write_headers(headers)
        writer.write_data(data)
        if not writer.save():
            raise ValueError('结果文件保存失败')
        return output_path

    @staticmethod
    def _to_cell_value(value: Any) -> Any:
        if value is None:
            return ''
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, datetime):
            return value.strftime('%Y-%m-%d %H:%M:%S')
        if isinstance(value, (dict, list, tuple)):
            return json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='ignore')
        return str(value)