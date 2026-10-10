import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def _resolve_param_value(var_config: dict, export_params: dict):
    """从导出参数中解析模板变量对应的值。

    支持普通参数（param 直接取值）与范围参数拆分（param_part 为 start/end，
    对应执行页拆分的 {param}_start / {param}_end）。
    """
    if not export_params:
        return None
    bind_name = var_config.get('param')
    if not bind_name:
        return None
    part = var_config.get('param_part') or ''

    if part in ('start', 'end'):
        split_key = f'{bind_name}_{part}'
        split_val = export_params.get(split_key)
        if split_val not in (None, ''):
            return split_val

    raw = export_params.get(bind_name)
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        parts = [str(x).strip() for x in raw if str(x).strip()]
        if not parts:
            return None
        if part == 'start':
            return parts[0]
        if part == 'end':
            return parts[-1]
        return ','.join(parts)
    if part in ('start', 'end'):
        parts = [p.strip() for p in str(raw).split(',') if p.strip()]
        if not parts:
            return None
        return parts[0] if part == 'start' else parts[-1]
    return raw if raw != '' else None


def render_sql_template(template: str, template_config: list, params: dict = None,
                        export_params: dict = None) -> str:
    """
    渲染SQL模板，使用Jinja2语法。

    变量来源（var_config.source）：
    - auto：按 config 配置自动生成（日期范围/日期/文本/数字）
    - param：取自用户在导出/查询执行页填写的导出参数（export_params），
             通过 param 指定参数名，param_part 指定范围参数的取值部分（start/end）
    
    template_config 示例:
    [
        {
            "name": "months",
            "type": "date_range",
            "label": "月份范围",
            "config": {
                "period": "month",       # month/day/year
                "count": 12,             # 数量
                "direction": "past",     # past/future
                "format": "%Y%m",        # 日期格式
                "offset": 0              # 偏移量(0=包含当月, 1=从上月开始)
            }
        },
        {
            "name": "date_param",
            "type": "date",
            "label": "日期参数",
            "config": {
                "default": "today",      # today/now/自定义
                "format": "%Y-%m-%d"
            }
        },
        {
            "name": "custom_param",
            "type": "text",
            "label": "自定义参数",
            "config": {
                "default": ""
            }
        }
    ]
    
    模板示例:
    {% for m in months %}
    SELECT * FROM transaction_{{ m }}
    WHERE merchant_id = :value
    {% if not loop.last %} UNION ALL {% endif %}
    {% endfor %}
    """
    try:
        from jinja2 import Template, StrictUndefined
    except ImportError:
        # Jinja2未安装，回退简单替换
        return template

    # 构建模板变量上下文
    context = {}
    params = params or {}
    export_params = export_params or {}

    now = datetime.now()

    for var_config in template_config:
        var_name = var_config.get('name', '')
        var_type = var_config.get('type', 'text')
        config = var_config.get('config', {})
        source = var_config.get('source', 'auto')

        # 显式传入的模板变量值优先（兼容旧的 template_params 机制）
        if var_name in params and params[var_name] is not None:
            context[var_name] = params[var_name]
            continue

        # 变量来源为导出参数：取用户在导出/查询执行时填写的参数值
        if source == 'param':
            resolved = _resolve_param_value(var_config, export_params)
            if resolved is not None:
                context[var_name] = resolved
                continue

        if var_type == 'date_range':
            period = config.get('period', 'month')
            count = int(config.get('count', 12))
            direction = config.get('direction', 'past')
            fmt = config.get('format', '%Y%m')
            offset = int(config.get('offset', 0))

            values = []
            for i in range(count):
                if direction == 'past':
                    delta_idx = i + offset
                else:
                    delta_idx = -(i + offset)

                if period == 'month':
                    dt = now + relativedelta(months=-delta_idx)
                elif period == 'year':
                    dt = now + relativedelta(years=-delta_idx)
                elif period == 'day':
                    dt = now + timedelta(days=-delta_idx)
                else:
                    dt = now + relativedelta(months=-delta_idx)

                values.append(dt.strftime(fmt))

            context[var_name] = values

        elif var_type == 'date':
            default = config.get('default', 'today')
            fmt = config.get('format', '%Y-%m-%d')

            if default == 'today':
                dt = now
            elif default == 'now':
                dt = now
            elif default == 'yesterday':
                dt = now - timedelta(days=1)
            elif default == 'first_day_of_month':
                dt = now.replace(day=1)
            elif default == 'last_day_of_month':
                dt = now + relativedelta(months=1, day=1) - timedelta(days=1)
            else:
                try:
                    dt = datetime.strptime(default, fmt)
                except:
                    dt = now

            context[var_name] = dt.strftime(fmt)

        elif var_type == 'text':
            context[var_name] = config.get('default', '')

        elif var_type == 'number':
            context[var_name] = config.get('default', 0)

    # 添加辅助函数
    context['now'] = now
    context['today'] = now.strftime('%Y-%m-%d')
    context['current_month'] = now.strftime('%Y%m')
    context['current_year'] = now.strftime('%Y')

    try:
        tmpl = Template(template, undefined=StrictUndefined)
        result = tmpl.render(**context)
        # 清理多余空行
        lines = [line.rstrip() for line in result.split('\n')]
        cleaned = '\n'.join(line for line in lines if line.strip())
        return cleaned
    except Exception as e:
        logger.error(f'SQL模板渲染失败: {e}')
        raise ValueError(f'模板渲染失败: {str(e)}')


def get_template_preview(template: str, template_config: list, params: dict = None) -> dict:
    """预览模板渲染结果"""
    try:
        params = dict(params) if params else {}
        # 预览时，为"来源=参数"的变量注入占位示例值，
        # 避免因缺少执行页填写的参数值导致预览渲染失败。
        for var_config in template_config or []:
            if not isinstance(var_config, dict) or var_config.get('source') != 'param':
                continue
            var_name = var_config.get('name', '')
            if not var_name or var_name in params:
                continue
            bind_name = var_config.get('param') or var_name
            part = var_config.get('param_part') or ''
            suffix = f'_{part}' if part in ('start', 'end') else ''
            params[var_name] = f'<参数:{bind_name}{suffix}>'
        rendered = render_sql_template(template, template_config, params)
        return {
            'success': True,
            'rendered_sql': rendered,
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def resolve_script_template_params(template_params, script):
    """从整体 template_params 中解析出指定脚本对应的模板变量值。

    支持按脚本分组的结构：{'12': {'var': 'x'}, '脚本名': {...}}；
    也兼容所有脚本共用的扁平结构：{'var': 'x'}。
    """
    if not template_params or not isinstance(template_params, dict) or script is None:
        return None
    for key in (str(getattr(script, 'id', '')), getattr(script, 'name', None)):
        if key is None:
            continue
        val = template_params.get(key)
        if isinstance(val, dict):
            return val
    if all(not isinstance(v, dict) for v in template_params.values()):
        return template_params
    return None
