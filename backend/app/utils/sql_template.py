import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


def render_sql_template(template: str, template_config: list, params: dict = None) -> str:
    """
    渲染SQL模板，使用Jinja2语法。
    
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

    now = datetime.now()

    for var_config in template_config:
        var_name = var_config.get('name', '')
        var_type = var_config.get('type', 'text')
        config = var_config.get('config', {})

        # 用户传入的参数优先
        if var_name in params and params[var_name] is not None:
            context[var_name] = params[var_name]
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


def get_template_preview(template: str, template_config: list) -> dict:
    """预览模板渲染结果"""
    try:
        rendered = render_sql_template(template, template_config)
        return {
            'success': True,
            'rendered_sql': rendered,
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }
