"""运营数据看板服务

移植自 data_dashboard 项目的查询引擎，适配本项目：
- 数据源复用 DatabaseConnection（连接池 + SSH 隧道 + 健康检查）
- SQL 模板 {{参数}} 占位符渲染 + 维度参数（日/月/年）
- 多数据源合并（concat / 按键聚合）
- 查询结果内存 TTL 缓存
- 只读 SQL 校验
"""
import hashlib
import json
import re
import threading
import time
import calendar
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

import pandas as pd
from sqlalchemy import text

from app import db
from app.models.dashboard import DashboardScript, DashboardQuickQuery
from app.models.database import DatabaseConnection
from app.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

PARAM_PATTERN = re.compile(r'\{\{(\w+)\}\}')

BUILTIN_PARAMS = {
    'dimension', 'date_format', 'date', 'start_date', 'end_date',
    'year', 'month', 'day', 'start_year', 'end_year',
}

DIMENSIONS = ['day', 'month', 'year']
DIMENSION_DATE_FORMATS = {'day': '%Y-%m-%d', 'month': '%Y-%m', 'year': '%Y'}
CHART_TYPES = ['line', 'bar', 'area', 'pie', 'scatter', 'table', 'radar', 'gauge', 'funnel', 'mix']

DANGEROUS_KEYWORDS = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE', 'GRANT', 'REVOKE']

DEFAULT_DASHBOARD_CONFIG = {
    'cache_enabled': True,
    'cache_ttl': 600,
    'max_rows': 10000,
    'default_dimension': 'day',
    'max_chart_count': 4,
    'animation_enabled': True,
}

DASHBOARD_CONFIG_KEY = 'dashboard_config'

# ── 配置 ──────────────────────────────────────────────


def get_dashboard_config() -> dict:
    cfg = dict(DEFAULT_DASHBOARD_CONFIG)
    row = SystemConfig.query.filter_by(config_key=DASHBOARD_CONFIG_KEY).first()
    if row and row.config_value:
        try:
            saved = json.loads(row.config_value)
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in DEFAULT_DASHBOARD_CONFIG})
        except (json.JSONDecodeError, TypeError):
            pass
    return cfg


def save_dashboard_config(patch: dict) -> dict:
    cfg = get_dashboard_config()
    cfg.update({k: v for k, v in patch.items() if k in DEFAULT_DASHBOARD_CONFIG})
    row = SystemConfig.query.filter_by(config_key=DASHBOARD_CONFIG_KEY).first()
    if not row:
        row = SystemConfig(config_key=DASHBOARD_CONFIG_KEY, description='运营数据看板配置')
        db.session.add(row)
    row.config_value = json.dumps(cfg, ensure_ascii=False)
    db.session.commit()
    _cache.clear()
    return cfg


# ── 查询缓存（内存 TTL） ──────────────────────────────


class _TTLCache:
    def __init__(self):
        self._store: Dict[str, tuple] = {}
        self._lock = threading.Lock()

    def get(self, key: str, ttl: int) -> Optional[dict]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: dict, ttl: int):
        with self._lock:
            if len(self._store) > 500:
                now = time.time()
                self._store = {k: v for k, v in self._store.items() if v[1] > now}
            self._store[key] = (value, time.time() + max(1, ttl))

    def clear(self):
        with self._lock:
            self._store.clear()


_cache = _TTLCache()


def build_cache_key(params: dict) -> str:
    parts = []
    for k in sorted(params.keys()):
        v = params[k]
        if isinstance(v, (list, dict)):
            v = json.dumps(v, sort_keys=True, ensure_ascii=False)
        else:
            v = str(v) if v is not None else ''
        parts.append(f'{k}={v}')
    return hashlib.md5('&'.join(parts).encode('utf-8')).hexdigest()


# ── SQL 渲染与校验 ────────────────────────────────────


def render_sql(sql: str, params: Dict[str, Any]) -> str:
    string_params = {'dimension', 'date_format', 'date', 'start_date', 'end_date'}

    def replacer(match):
        key = match.group(1)
        if key in params:
            value = params[key]
            if isinstance(value, str):
                escaped = value.replace("'", "''")
                if key in string_params:
                    return f"'{escaped}'"
                return escaped
            return str(value)
        return match.group(0)

    return PARAM_PATTERN.sub(replacer, sql)


def validate_readonly_sql(sql: str):
    """看板 SQL 只读校验：仅允许 SELECT/WITH 单语句，禁止 DML/DDL 关键字"""
    cleaned = sql.strip().rstrip(';').strip()
    if not cleaned:
        return 'SQL 为空'
    head = cleaned.split(None, 1)[0].upper() if cleaned.split(None, 1) else ''
    if head not in ('SELECT', 'WITH'):
        return '看板仅支持 SELECT / WITH 开头的只读查询'
    if ';' in cleaned:
        return '不允许执行多条语句'
    upper = cleaned.upper()
    for kw in DANGEROUS_KEYWORDS:
        if re.search(r'\b' + kw + r'\b', upper):
            return f'检测到禁止的关键字: {kw}'
    return ''


def parse_params(sql: str) -> dict:
    all_params = PARAM_PATTERN.findall(sql or '')
    builtin = sorted(set(p for p in all_params if p in BUILTIN_PARAMS))
    custom = sorted(set(p for p in all_params if p not in BUILTIN_PARAMS))
    return {'builtin': builtin, 'custom': custom}


def parse_columns(sql: str) -> List[str]:
    """解析 SELECT 列名（支持括号嵌套、CASE WHEN、别名）"""
    if not sql or not sql.strip():
        return []

    sql_clean = sql.strip().rstrip(';').strip()
    if sql_clean.lower().startswith('select'):
        sql_clean = sql_clean[len('select'):]

    from_pos = None
    depth = 0
    in_case = 0
    i = 0
    while i < len(sql_clean):
        ch = sql_clean[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and in_case == 0:
            upper = sql_clean[i:i + 4].upper()
            if upper == 'CASE':
                in_case += 1
                i += 4
                continue
            if upper == 'FROM':
                prev = sql_clean[i - 1] if i > 0 else ' '
                if prev in (' ', '\t', '\n', '\r'):
                    from_pos = i
                    break
        if depth == 0 and in_case > 0:
            upper_rest = sql_clean[i:i + 3].upper()
            if upper_rest == 'END' and (i + 3 >= len(sql_clean) or not sql_clean[i + 3].isalnum()):
                in_case -= 1
                i += 3
                continue
        i += 1

    if from_pos is None:
        return []

    select_part = sql_clean[:from_pos].strip()

    columns = []
    depth = 0
    in_case = 0
    current = []
    i = 0
    while i < len(select_part):
        ch = select_part[i]
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0 and in_case == 0:
            columns.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
        if depth == 0:
            upper = select_part[i:i + 4].upper()
            if upper == 'CASE':
                in_case += 1
            upper_end = select_part[i:i + 3].upper()
            if upper_end == 'END' and (i + 3 >= len(select_part) or not select_part[i + 3].isalnum()):
                in_case -= 1
        i += 1
    if current:
        columns.append(''.join(current).strip())

    result = []
    alias_pattern = re.compile(r'\bAS\s+([\w\u4e00-\u9fff]+)\s*$', re.IGNORECASE)
    no_as_pattern = re.compile(r'([\w\u4e00-\u9fff]+)\s*$', re.IGNORECASE)
    for col in columns:
        m = alias_pattern.search(col)
        if m:
            result.append(m.group(1))
        else:
            m2 = no_as_pattern.search(col)
            if m2 and m2.group(1).upper() not in (
                    'FROM', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'LIMIT', 'AND', 'OR', 'ON', 'AS', 'BY', 'DESC', 'ASC'):
                result.append(m2.group(1))
    return result


# ── 维度参数 ──────────────────────────────────────────


def build_dimension_params(dimension: str, date: Optional[str] = None,
                           start_year: Optional[int] = None,
                           end_year: Optional[int] = None) -> Dict[str, Any]:
    now = datetime.now()
    if date:
        try:
            now = datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            pass

    fmt = DIMENSION_DATE_FORMATS.get(dimension, '%Y-%m-%d')
    y, m = now.year, now.month

    if dimension == 'day':
        start_date = datetime(y, m, 1)
        end_date = datetime(y, m, calendar.monthrange(y, m)[1])
    elif dimension == 'month':
        start_date = datetime(y, 1, 1)
        end_date = datetime(y, 12, 31)
    else:
        sy = start_year if start_year is not None else y
        ey = end_year if end_year is not None else (start_year if start_year is not None else y)
        start_date = datetime(sy, 1, 1)
        end_date = datetime(ey, 12, 31)

    params = {
        'dimension': dimension,
        'date_format': fmt,
        'date': now.strftime(fmt),
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'year': y,
        'month': m,
        'day': now.day,
    }
    if start_year is not None:
        params['start_year'] = start_year
    if end_year is not None:
        params['end_year'] = end_year
    return params


# ── 查询执行 ──────────────────────────────────────────


def _get_connector_by_name(conn_name: str):
    conn = DatabaseConnection.query.filter_by(name=conn_name, is_active=True).first()
    if not conn:
        raise ValueError(f"数据源 '{conn_name}' 不存在或已停用，请在数据库管理中检查")
    from app.services.database_service import DatabaseService
    connector = DatabaseService.get_connector(conn.id)
    if not connector:
        raise ValueError(f"数据源 '{conn_name}' 连接器创建失败")
    return connector


def execute_query_df(conn_name: str, sql: str, params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
    """在指定数据源上执行渲染后的 SQL，返回 DataFrame"""
    connector = _get_connector_by_name(conn_name)
    rendered = render_sql(sql, params or {})

    error = validate_readonly_sql(rendered)
    if error:
        raise ValueError(f'SQL 校验失败: {error}')

    try:
        with connector.get_connection() as connection:
            df = pd.read_sql(text(rendered), connection)
        return df
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"数据源 '{conn_name}' 查询执行失败: {e}")


def merge_from_sources(conn_names: List[str], sql: str, params: Optional[Dict[str, Any]] = None,
                       merge_mode: str = 'concat', merge_key: Optional[str] = None,
                       hide_fields: Optional[List[str]] = None) -> pd.DataFrame:
    """多数据源合并查询：separate=逐源拼接(_source列)，aggregate=按键聚合求和"""
    frames = []
    errors = []
    for conn_name in conn_names:
        try:
            df = execute_query_df(conn_name, sql, params)
            if df is not None and not df.empty:
                df['_source'] = conn_name
                frames.append(df)
        except Exception as e:
            logger.warning(f"看板合并查询跳过 '{conn_name}': {e}")
            errors.append(f'{conn_name}: {e}')

    if not frames:
        if errors:
            raise RuntimeError(f'所有数据源查询均失败：{errors[0]}')
        return pd.DataFrame()

    if merge_mode == 'sum':
        for f in frames:
            if '_source' in f.columns:
                f.drop(columns=['_source'], inplace=True)
        combined = pd.concat(frames, ignore_index=True)
        numeric_cols = combined.select_dtypes(include='number').columns.tolist()
        if merge_key and merge_key in combined.columns:
            group_cols = [merge_key]
        else:
            group_cols = [c for c in combined.columns if c not in numeric_cols]
        if group_cols and numeric_cols:
            return combined.groupby(group_cols, as_index=False).agg({c: 'sum' for c in numeric_cols})
        return combined
    return pd.concat(frames, ignore_index=True)


def _serialize_value(val):
    if val is None:
        return None
    if hasattr(val, 'item'):
        try:
            val = val.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, (int, float, str, bool)):
        return val
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    if pd.isna(val):
        return None
    return str(val)


def dataframe_to_result(df: pd.DataFrame, title: str, chart_type: str,
                        hide_fields: Optional[List[str]] = None) -> dict:
    if df is None or df.empty:
        return {'title': title, 'chart_type': chart_type, 'columns': [], 'rows': [], 'row_count': 0}

    columns = [str(c) for c in df.columns.tolist()]
    if hide_fields:
        keep = [c for c in columns if c not in hide_fields]
        df = df[keep]
        columns = keep

    rows = [[_serialize_value(v) for v in row] for row in df.itertuples(index=False, name=None)]
    return {
        'title': title,
        'chart_type': chart_type,
        'columns': columns,
        'rows': rows,
        'row_count': len(rows),
    }


def execute_dashboard_query(data: dict) -> dict:
    """看板查询入口（含缓存、维度参数、钻取、多源合并）"""
    sql = (data.get('sql') or '').strip()
    conn_name = data.get('conn_name', '')
    merge_names = data.get('merge_conn_names', []) or []
    dimension = data.get('dimension', 'day')
    date = data.get('date', '')
    custom_params = data.get('custom_params', {}) or {}
    chart_type = data.get('chart_type', 'line')
    merge_mode = data.get('merge_mode', 'separate')
    hide_fields = data.get('hide_fields', []) or []
    merge_key = data.get('merge_key', '')
    force_refresh = bool(data.get('force_refresh', False))

    if not sql:
        raise ValueError('请输入SQL')
    if not conn_name and not merge_names:
        raise ValueError('请选择数据源')

    cfg = get_dashboard_config()

    cache_params = {
        'sql': sql, 'conn_name': conn_name,
        'merge_conn_names': sorted(merge_names) if merge_names else [],
        'dimension': dimension, 'date': date,
        'custom_params': custom_params,
        'drill_start_date': data.get('drill_start_date', ''),
        'drill_end_date': data.get('drill_end_date', ''),
        'start_year': data.get('start_year'), 'end_year': data.get('end_year'),
        'merge_mode': merge_mode, 'merge_key': merge_key,
        'hide_fields': sorted(hide_fields) if hide_fields else [],
    }
    cache_key = build_cache_key(cache_params)

    if not force_refresh and cfg.get('cache_enabled'):
        cached = _cache.get(cache_key, int(cfg.get('cache_ttl', 600)))
        if cached is not None:
            cached['from_cache'] = True
            return cached

    start_year = data.get('start_year')
    end_year = data.get('end_year')
    dim_params = build_dimension_params(
        dimension, date,
        start_year=int(start_year) if start_year else None,
        end_year=int(end_year) if end_year else None,
    )
    drill_start_date = data.get('drill_start_date')
    drill_end_date = data.get('drill_end_date')
    if drill_start_date:
        dim_params['start_date'] = drill_start_date
    if drill_end_date:
        dim_params['end_date'] = drill_end_date
    all_params = {**dim_params, **custom_params}

    if merge_names:
        effective_mode = 'concat' if merge_mode == 'separate' else 'sum'
        df = merge_from_sources(
            conn_names=merge_names, sql=sql, params=all_params,
            merge_mode=effective_mode, merge_key=merge_key or None,
            hide_fields=hide_fields,
        )
        title = f'合并数据 ({len(merge_names)}个源)'
    else:
        df = execute_query_df(conn_name, sql, all_params)
        title = conn_name

    if cfg.get('max_rows') and len(df) > int(cfg.get('max_rows')):
        df = df.head(int(cfg.get('max_rows')))

    result = dataframe_to_result(df, title, chart_type, hide_fields)
    if cfg.get('cache_enabled'):
        _cache.set(cache_key, result, int(cfg.get('cache_ttl', 600)))
    return result


def clear_dashboard_cache() -> int:
    count = len(_cache._store)
    _cache.clear()
    return count


# ── 种子脚本（从 data_dashboard 适配） ─────────────────


def seed_default_scripts():
    """首次启动时导入示例看板脚本（连接名留空，需自行关联数据源）"""
    if DashboardScript.query.count() > 0:
        return
    seeds = [
        {
            'name': '商户进件情况',
            'sql_text': (
                "SELECT CASE WHEN m.channel_type='HKRT' THEN '海科融通' WHEN m.channel_type='LEPASS' THEN '乐刷' "
                "WHEN m.channel_type='DYIN' THEN '电银' WHEN m.channel_type='HELIPAY' THEN '合利宝' "
                "WHEN m.channel_type='ZF' THEN '中付' END 通道,"
                "DATE_FORMAT(m.create_time,{{date_format}}) 日期,"
                "count(1) 总进件商户,"
                "SUM(CASE WHEN m.apply_status=2 THEN 1 ELSE 0 END) 进件成功商户数,"
                "SUM(IF(m.activate_time IS NOT NULL,1,0)) 激活商户数 "
                "FROM posp_business.merchant m "
                "WHERE m.create_time BETWEEN CONCAT({{start_date}},' 00:00:00') AND CONCAT({{end_date}},' 23:59:59') "
                "GROUP BY DATE_FORMAT(m.create_time,{{date_format}})"
            ),
            'chart_type': 'line',
            'conn_name': '',
            'merge_conn_names': [],
            'description': '示例脚本：按维度统计商户进件与激活情况，需关联业务库后使用',
        },
        {
            'name': '商户交易统计',
            'sql_text': (
                "SELECT CASE WHEN t.channel_code='hkrt' THEN '融聚商户通' WHEN t.channel_code='zft_plus' THEN '支付通PLUS' "
                "WHEN t.channel_code='dyin' THEN '电银' WHEN t.channel_code='helipay' THEN '合利宝' "
                "WHEN t.channel_code='zf' THEN '中付' WHEN t.channel_code='lepass' THEN '乐刷' END 通道,"
                "DATE_FORMAT(t.trade_time,{{date_format}}) 日期,"
                "count(1) 总交易流水笔数,"
                "sum(t.trade_amount)/100 总交易流水金额,"
                "sum(IF(t.flow_activity_amount IS NULL,0,t.flow_activity_amount))/100 总流量卡金额,"
                "sum(ifnull(t.trade_t0_fee,0)+ifnull(t.trade_fee_amount,0))/100 总手续费金额 "
                "FROM posp_business.trade_order t "
                "WHERE t.trade_time BETWEEN CONCAT({{start_date}},' 00:00:00') AND CONCAT({{end_date}},' 23:59:59') "
                "AND t.trade_status=1 "
                "GROUP BY DATE_FORMAT(t.trade_time,{{date_format}}),t.channel_code "
                "ORDER BY t.channel_code,DATE_FORMAT(t.trade_time,{{date_format}})"
            ),
            'chart_type': 'line',
            'conn_name': '',
            'merge_conn_names': [],
            'description': '示例脚本：按维度统计交易流水与手续费，需关联业务库后使用',
        },
    ]
    for seed in seeds:
        script = DashboardScript(
            name=seed['name'],
            sql_text=seed['sql_text'],
            chart_type=seed['chart_type'],
            conn_name=seed['conn_name'],
            description=seed['description'],
        )
        script.set_merge_conn_names(seed['merge_conn_names'])
        db.session.add(script)
    try:
        db.session.commit()
        logger.info('已导入 %d 个看板示例脚本', len(seeds))
    except Exception as e:
        db.session.rollback()
        logger.warning(f'看板示例脚本导入失败: {e}')
