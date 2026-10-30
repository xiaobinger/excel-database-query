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
from app.utils.sql_template import (
    has_jinja_syntax, render_jinja_structure, render_jinja_with_params,
    render_sql_template, resolve_script_template_params
)
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

        说明：
            SQL 支持两种书写模式，按内容自动判别：
            - Jinja2 模板模式（含 {% %} / {# #} 控制语法）：完整 Jinja2 语义，
              {% if %} 可选条件、{% set %} 变量、过滤器、辅助变量 now/today 等；
              {{ param }} 输出经单引号转义的原始值，不自动加引号（引号由 SQL 作者手写）。
            - 传统模式：{{param}} 占位符由引擎替换（字符串自动加引号并转义），
              或使用 :param / %(param)s SQLAlchemy bind 参数。
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

            # 3. SQL 来源判定：
            #    动态模板脚本（is_template=True 且配置了 sql_template）优先取 sql_template，
            #    与查询/导出脚本（ExportService._prepare_script_sql）保持一致；
            #    否则沿用 sql_text（兼容 Jinja 语法 / {{param}} / :param 三种写法）
            is_dynamic_template = bool(script.is_template and script.sql_template)
            sql = (script.sql_template if is_dynamic_template else script.sql_text) or ''
            validator = SQLValidator()
            is_jinja = has_jinja_syntax(sql)
            logger.info(f'Lookup SQL来源: script_id={script_id}, '
                        f'{"动态模板(sql_template)" if is_dynamic_template else "普通SQL(sql_text)"}')

            # 3.5 检测未替换的预览占位符（如 <参数:id_card>）：
            #     脚本 SQL 中混入了模板预览用的占位文本（多因从预览结果复制保存），
            #     直接执行会永远查不出数据——快速失败并给出明确原因
            placeholder_leak = re.findall(r'<参数:[^>]*>', sql)
            if placeholder_leak:
                logger.error(f'Lookup SQL包含未替换占位符: script_id={script_id}, {placeholder_leak}')
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': ('SQL 配置错误：包含未替换的占位符 ' + ', '.join(placeholder_leak) +
                                      '（疑似从模板预览复制），请在脚本中改用真实参数引用（{{ param }} 或 :param）')
                }

            # 4. 智能参数映射：确保传入的参数名和SQL中的参数名一致
            #    （映射先于渲染：Jinja 渲染需要用映射后的参数名作为模板 context）
            script_params = script.get_params_config() or []
            all_sql_params = set(LookupService._extract_bind_params(sql))
            # 也加入 {{param}} 占位符（容忍空格与过滤器，如 {{ id_card | trim }}）
            all_sql_params.update(re.findall(r'\{\{\s*(\w+)', sql))
            # 动态模板：模板变量名（来源=参数）同样是可接收的参数名
            if is_dynamic_template:
                for var_cfg in (script.get_template_config() or []):
                    if isinstance(var_cfg, dict) and var_cfg.get('name'):
                        all_sql_params.add(var_cfg['name'])

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

            # 5. 校验与渲染（按书写模式分流）
            if is_dynamic_template:
                # 动态模板模式：复用查询/导出的模板渲染入口，
                # "来源=参数"的模板变量直接取本次执行传入的参数值，
                # 未传值时由模板内的 {% if %} / default 自行处理
                try:
                    sql = render_sql_template(
                        script.sql_template,
                        script.get_template_config() or [],
                        resolve_script_template_params(None, script),
                        export_params=dict(params_values or {})
                    )
                except Exception as e:
                    logger.error(f'Lookup 动态模板渲染失败: script_id={script_id}, error={e}')
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL模板渲染失败，请联系管理员'
                    }
                # 渲染后的 SQL 参数值已内联为字面量（如 m.code = 'xxx'），
                # 不再含占位符，故用 allow_inline_params=True 跳过占位符检查
                validation = validator.validate(sql, check_tables=False, allow_dml=False,
                                                allow_inline_params=True)
                if not validation.is_valid:
                    logger.error(f'Lookup 模板SQL校验失败: script_id={script_id}, message={validation.message}')
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL配置验证失败，请联系管理员'
                    }
            elif is_jinja:
                # Jinja2 模板模式：
                # 1) 先用占位值结构渲染并校验——校验的是模板结构，
                #    避免参数值中的 ; -- union select 等字符触发注入模式误报
                # 2) 再用真实参数值渲染执行；{{ param }} 输出经单引号转义的
                #    原始值，不自动加引号（需要引号时由 SQL 作者手写）
                try:
                    structure_sql = render_jinja_structure(sql)
                except Exception as e:
                    logger.error(f'Lookup Jinja模板解析失败: script_id={script_id}, error={e}')
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL配置验证失败，请联系管理员'
                    }
                validation = validator.validate(structure_sql, check_tables=False,
                                                allow_dml=False, allow_inline_params=True)
                if not validation.is_valid:
                    logger.error(f'Lookup Jinja SQL校验失败: script_id={script_id}, message={validation.message}')
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL配置验证失败，请联系管理员'
                    }
                try:
                    sql = render_jinja_with_params(sql, params_values)
                except Exception as e:
                    logger.error(f'Lookup Jinja渲染失败: script_id={script_id}, error={e}')
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL配置验证失败，请联系管理员'
                    }
            else:
                # 传统模式：直接校验原始 SQL，再替换 {{param}} 占位符（自动加引号）
                validation = validator.validate(sql, check_tables=False, allow_dml=False)
                if not validation.is_valid:
                    return {
                        'success': False,
                        'results': [],
                        'columns': [],
                        'row_count': 0,
                        'error_message': 'SQL配置验证失败，请联系管理员'
                    }
                sql = LookupService._replace_placeholders(sql, params_values)

            # 6. 打印最终渲染出的执行 SQL（动态 SQL 排查用）：
            #    确认参数是否正确内联、引号是否缺失（如 m.code = {{ param }}
            #    未手写引号时，VARCHAR 列会被 MySQL 隐式转数字比较导致匹配不到数据）
            sql_log = sql if len(sql) <= 4000 else sql[:4000] + f'...(共{len(sql)}字符，已截断)'
            logger.info(f'Lookup 最终执行SQL: {sql_log}')

            # 7. 提取 SQLAlchemy bind 参数 (%(name)s 格式) 并构建 filtered_params
            bind_params = LookupService._extract_bind_params(sql)
            # bind 为空属正常：Jinja / {{param}} 模式下参数已内联进 SQL 文本，
            # 只有 :param / %(param)s 写法才会留下 bind 参数
            logger.info(f'Lookup SQL bind参数: {bind_params}（为空=参数已内联，属正常）, 传入参数: {list(params_values.keys())}')
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

            # 8. 获取超时时间
            timeout = script.timeout or 30

            # 9. 获取关联的数据库连接
            db_ids = script.get_database_ids()
            if not db_ids:
                return {
                    'success': False,
                    'results': [],
                    'columns': [],
                    'row_count': 0,
                    'error_message': '脚本未配置数据库连接'
                }

            # 10. 在所有关联数据库上执行查询，合并结果
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
                    connector = pool.get_connector_with_health_check(conn_id)
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
                        logger.info(f'Lookup 查询执行完成 [数据库: {conn_model.name}]: {len(rows)} 行')

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

            logger.info(f'Lookup 执行汇总: script_id={script_id}, 共 {len(all_rows)} 行')
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
        替换 SQL 中的 {{param}} 占位符为参数值（传统模式）。
        未提供的参数按空字符串 '' 处理，以支持
        ('{{param}}' = '' OR col = '{{param}}') 这类可选过滤条件写法
        （前端/AI 链路只传非空参数）。

        注意：字符串值会自动包单引号并转义，因此 SQL 模板里 {{param}}
        不要手动包引号（'{{param}}' 会渲染成 ''value'' 双引号字面量）。

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
                return "''"
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

        return re.sub(r'\{\{\s*(\w+)\s*\}\}', replacer, sql)

    @staticmethod
    def _extract_bind_params(sql: str) -> List[str]:
        """
        提取 SQL 中的 SQLAlchemy bind 参数名。
        支持 %(name)s 和 :name 两种格式。
        先剔除单引号字符串字面量，避免内联值中的冒号
        （如时间 '12:30'、URL 'http://...'）被误识别为 bind 参数。
        """
        # 剔除单引号字符串字面量（'' 为转义引号），仅保留结构部分用于参数提取
        sql_masked = re.sub(r"'(?:[^']|'')*'", "''", sql)
        params = re.findall(r'%\((\w+)\)s', sql_masked)
        # 匹配 :name 格式，但排除 :: （PostgreSQL类型转换）和数字(:1 :2)
        colon_params = re.findall(r'(?<!:):(\w+)', sql_masked)
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
