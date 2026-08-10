"""代理商分润计算与导出服务

根据两个SQL脚本查询数据：
  脚本1: 查询代理关系及代理相关成本费率
  脚本2: 查询交易订单

计算逻辑：
  1. 根据订单的 一级代理商、交易类型、卡类型、终端类型、产品ID 找到整个代理层级的成本
  2. 总分润池 = 交易金额 * (交易费率 - 一级代理商费率成本) + 一级代理商T0成本
  3. 逐级分钱: 每个上级分得 = 交易金额 * (下级费率成本 - 上级费率成本) + (下级T0成本 - 上级T0成本)
  4. 累计分润若超出总分润池，则不再往下分，后续均为0
  5. 特殊规则: 交易金额 > 1000 时，费率成本取刷卡贷记卡相关值
"""

import json
import logging
import os
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app import db
from app.models.database import DatabaseConnection
from app.models.query_task import QueryTask
from app.utils.helpers import beijing_isoformat

logger = logging.getLogger(__name__)

_task_progress = {}
_task_lock = threading.Lock()
_task_threads = {}
_task_cancel_events = {}

# ── SQL 脚本 ──────────────────────────────────────────────

SQL_AGENT_RATE_CONFIG = """
SELECT
    ac.agent_no       AS 代理商编号,
    a.agent_name      AS 代理商名称,
    a.rank            AS 代理商等级,
    a.login_phone     AS 代理手机号码,
    a.parent_agent_no AS 上级代理商编号,
    p.agent_name      AS 所属上级,
    r.agent_name      AS 所属一级,
    ac.device_type    AS 终端类型,
    ac.rate_type      AS 费率类型,
    ac.product_id     AS 产品ID,
    ac.rate_info      AS 成本内容
FROM pro_isp_db.tbl_agent_rate_config ac
LEFT JOIN pro_isp_db.tbl_agent a  ON ac.agent_no = a.agent_no
LEFT JOIN pro_isp_db.tbl_agent p  ON a.parent_agent_no = p.agent_no
LEFT JOIN pro_isp_db.tbl_agent r  ON a.root_agent_no = r.agent_no
WHERE ac.product_type = 1
  AND ac.rate_type != 1
  AND ac.`status` = 0
  AND ac.product_id IS NOT NULL
  AND r.agent_no = :org_no
"""

SQL_TRADE_ORDERS = """
SELECT
    o.trade_time                           AS 交易时间,
    o.org_no                               AS 一级代理商编号,
    o.trade_amount / 100                   AS 交易金额,
    o.trade_rate / 100                     AS 交易费率,
    o.trade_fee_amount / 100               AS 交易手续费,
    IFNULL(o.trade_t0_fee, 0) / 100        AS 交易T0服务费,
    o.channel_rate                         AS 服务商费率成本,
    IFNULL(o.channel_t0_fee, 0) / 100      AS 服务商T0成本,
    o.org_rate                             AS 一级代理费率成本,
    IFNULL(o.org_t0_fee, 0) / 100          AS 一级代理T0成本,
    CASE
        WHEN o.trade_type = 1 THEN '刷卡'
        WHEN o.trade_type = 2 THEN '银二'
        WHEN o.trade_type = 3 THEN '手机PAY'
        WHEN o.trade_type = 4 THEN '支付宝'
        WHEN o.trade_type = 5 THEN '微信'
    END                                    AS 交易类型,
    IF(o.card_type = 1, '借记卡', '贷记卡')  AS 卡类型,
    opm.old_product_id                     AS 产品ID,
    d.device_type                          AS 终端类型
FROM posp_business.trade_order o
LEFT JOIN posp_business.org_migrate_mapping om   ON o.org_no = om.new_org_code
LEFT JOIN posp_business.device d                  ON o.device_sn = d.device_sn
LEFT JOIN posp_business.org_product_migrate_mapping opm ON d.product_code = opm.new_product_id
WHERE om.old_org_code = :org_no
  AND o.trade_status = 1
  AND o.trade_time BETWEEN :start_time AND :end_time
"""

# ── 费率键映射 ────────────────────────────────────────────

# 交易类型/卡类型 → (费率成本键, T0成本键)
# 手机PAY (NFC支付) 按刷卡处理，区分借贷记卡
RATE_KEY_MAP = {
    ('微信', None):     ('wxPayRate',      'tsWxPay'),
    ('支付宝', None):   ('aliPayRate',     'tsAliPay'),
    ('银二', None):     ('unionPayRate',   'tsUnionPay'),
    ('刷卡', '借记卡'): ('debitPayRate',   'tsDebitCardPay'),
    ('刷卡', '贷记卡'): ('creditPayRate',  'tsCreditCardPay'),
    ('手机PAY', '借记卡'): ('debitPayRate', 'tsDebitCardPay'),
    ('手机PAY', '贷记卡'): ('creditPayRate', 'tsCreditCardPay'),
}

# 交易金额 > 1000 时强制使用刷卡贷记卡费率
HIGH_AMOUNT_RATE_KEYS = ('creditPayRate', 'tsCreditCardPay')

# 导出表头
EXPORT_HEADERS = [
    '代理商编号', '代理商名称', '分润金额', '月份',
    '代理商电话', '代理商等级', '所属一级代理商名称',
    '上级代理商', '上级关系'
]

# ── 进度管理 ──────────────────────────────────────────────

def _update_progress(task_id: str, progress: int, log_message: str = None, level: str = 'info'):
    with _task_lock:
        _task_progress[task_id] = {
            'progress': progress,
            'log_message': log_message,
            'level': level,
            'timestamp': beijing_isoformat(datetime.utcnow()),
        }


def _get_progress(task_id: str) -> dict:
    with _task_lock:
        return _task_progress.get(task_id, {'progress': 0})


# ── 数据解析工具 ──────────────────────────────────────────

def _parse_rate_info(rate_info_str) -> dict:
    """解析成本内容 JSON 字符串，返回费率字典"""
    if not rate_info_str:
        return {}
    if isinstance(rate_info_str, dict):
        return rate_info_str
    try:
        return json.loads(rate_info_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"解析 rate_info 失败: {rate_info_str}")
        return {}


def _to_float(value, default=0.0) -> float:
    """安全转换为 float"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _get_rate_keys(trade_type: str, card_type: str, trade_amount: float) -> Tuple[str, str]:
    """根据交易类型、卡类型、交易金额确定费率键

    特殊规则: 交易金额 > 1000 时，取刷卡贷记卡相关值
    """
    if trade_amount is not None and trade_amount > 1000:
        return HIGH_AMOUNT_RATE_KEYS

    # 刷卡和手机PAY 需要区分借贷记卡
    if trade_type in ('刷卡', '手机PAY'):
        key = (trade_type, card_type)
    else:
        key = (trade_type, None)
    return RATE_KEY_MAP.get(key, HIGH_AMOUNT_RATE_KEYS)


def _extract_rate(rate_info_dict: dict, rate_key: str) -> float:
    """从费率字典中提取指定键的值"""
    if not rate_info_dict:
        return 0.0
    return _to_float(rate_info_dict.get(rate_key))


# ── 代理层级构建 ──────────────────────────────────────────

class AgentNode:
    """代理层级树节点"""
    __slots__ = ('agent_no', 'agent_name', 'rank', 'login_phone',
                 'parent_agent_no', 'parent_name', 'root_name',
                 'rate_cost_info', 't0_cost_info', 'children')

    def __init__(self, agent_no, agent_name, rank, login_phone,
                 parent_agent_no, parent_name, root_name):
        self.agent_no = agent_no
        self.agent_name = agent_name or ''
        self.rank = rank
        self.login_phone = login_phone or ''
        self.parent_agent_no = parent_agent_no
        self.parent_name = parent_name or ''
        self.root_name = root_name or ''
        self.rate_cost_info = {}   # 费率成本 JSON (rate_type=0)
        self.t0_cost_info = {}     # T0成本 JSON (rate_type=2)
        self.children: List['AgentNode'] = []


def _build_agent_configs(rows: List[dict], org_no: str) -> Dict[Tuple, Dict[str, AgentNode]]:
    """构建代理配置字典

    返回: {(device_type, product_id): {agent_no: AgentNode}}
    """
    configs: Dict[Tuple, Dict[str, AgentNode]] = defaultdict(dict)

    for row in rows:
        agent_no = str(row.get('代理商编号', '')).strip()
        if not agent_no:
            continue

        device_type = str(row.get('终端类型', '')).strip()
        product_id = str(row.get('产品ID', '')).strip()
        rate_type = row.get('费率类型')
        rate_info_str = row.get('成本内容', '')

        key = (device_type, product_id)
        node = configs[key].get(agent_no)

        if node is None:
            node = AgentNode(
                agent_no=agent_no,
                agent_name=row.get('代理商名称', ''),
                rank=row.get('代理商等级'),
                login_phone=row.get('代理手机号码', ''),
                parent_agent_no=str(row.get('上级代理商编号', '')).strip() if row.get('上级代理商编号') else None,
                parent_name=row.get('所属上级', ''),
                root_name=row.get('所属一级', ''),
            )
            configs[key][agent_no] = node

        # 合并费率/T0成本信息
        parsed = _parse_rate_info(rate_info_str)
        if rate_type == 0:  # 代理费率成本
            node.rate_cost_info = parsed
        elif rate_type == 2:  # 代理T0成本
            node.t0_cost_info = parsed

    return dict(configs)


def _build_hierarchy(agents: Dict[str, AgentNode], org_no: str) -> Optional[AgentNode]:
    """构建代理层级树，返回根节点（一级代理商）

    注意: 每次调用前会清空所有节点的 children，避免重复构建导致子节点累积。
    """
    if not agents:
        return None

    # 清空已有 children（避免重复构建导致累积）
    for node in agents.values():
        node.children = []

    # 构建父子映射
    children_map: Dict[str, List[AgentNode]] = defaultdict(list)
    root = None

    for agent_no, node in agents.items():
        if agent_no == org_no or (node.rank is not None and _to_float(node.rank) == 1):
            root = node
        if node.parent_agent_no and node.parent_agent_no in agents and node.parent_agent_no != agent_no:
            children_map[node.parent_agent_no].append(node)

    # 如果没有通过 org_no 找到根，尝试找 rank 最小的
    if root is None:
        ranked = sorted(agents.values(), key=lambda n: _to_float(n.rank, 999))
        if ranked:
            root = ranked[0]

    if root is None:
        return None

    # 递归构建子节点（BFS 防止循环引用）
    visited = {root.agent_no}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        for child in children_map.get(current.agent_no, []):
            if child.agent_no not in visited:
                visited.add(child.agent_no)
                current.children.append(child)
                queue.append(child)

    return root


def _get_ancestor_chain(node: AgentNode, agents: Dict[str, AgentNode]) -> List[str]:
    """获取节点的所有上级名称链（从根到直接上级）"""
    chain = []
    current = node
    visited = set()

    while current and current.parent_agent_no and current.parent_agent_no in agents and current.parent_agent_no not in visited:
        visited.add(current.parent_agent_no)
        parent = agents[current.parent_agent_no]
        chain.append(parent.agent_name or parent.agent_no)
        current = parent

    chain.reverse()
    return chain


# ── 分润计算 ──────────────────────────────────────────────

def _calculate_order_shares(
    order: dict,
    root: AgentNode,
    agents: Dict[str, AgentNode],
    org_no: str
) -> Dict[str, float]:
    """计算单笔订单各代理的分润金额

    返回: {agent_no: share_amount}
    """
    trade_amount = _to_float(order.get('交易金额'))
    trade_rate = _to_float(order.get('交易费率'))
    org_rate = _to_float(order.get('一级代理费率成本'))
    org_t0 = _to_float(order.get('一级代理T0成本'))
    trade_type = order.get('交易类型', '')
    card_type = order.get('卡类型', '')
    trade_time = order.get('交易时间')

    rate_key, t0_key = _get_rate_keys(trade_type, card_type, trade_amount)

    # 总分润池
    total_pool = trade_amount * (trade_rate - org_rate) + org_t0

    if total_pool <= 0:
        return {}

    shares: Dict[str, float] = {}
    cumulative = 0.0

    # BFS 逐级分钱
    # 第一级: root 的子节点 → root 的分润
    # 后续: 每个子节点的子节点 → 该子节点的分润
    visited = {root.agent_no}
    queue = deque([(root, org_rate, org_t0)])

    while queue:
        parent_node, parent_rate, parent_t0 = queue.popleft()

        for child in parent_node.children:
            if child.agent_no in visited:
                continue
            visited.add(child.agent_no)

            child_rate = _extract_rate(child.rate_cost_info, rate_key)
            child_t0 = _extract_rate(child.t0_cost_info, t0_key)

            # 上级分润 = 交易金额 * (下级费率成本 - 上级费率成本) + (下级T0成本 - 上级T0成本)
            share = trade_amount * (child_rate - parent_rate) + (child_t0 - parent_t0)

            # 分润为负或零时，上级无收益，但仍继续探索下级（下级可能有正分润）
            if share <= 0:
                queue.append((child, child_rate, child_t0))
                continue

            if cumulative + share > total_pool:
                # 超出总分润池，只分剩余部分
                remaining = total_pool - cumulative
                if remaining > 0:
                    shares[parent_node.agent_no] = shares.get(parent_node.agent_no, 0.0) + remaining
                    cumulative = total_pool
                # 后续都不再分
                break
            else:
                shares[parent_node.agent_no] = shares.get(parent_node.agent_no, 0.0) + share
                cumulative += share
                queue.append((child, child_rate, child_t0))

        if cumulative >= total_pool:
            break

    return shares


# ── Excel 生成 ───────────────────────────────────────────

def _generate_excel(aggregated_data: List[dict], output_path: str):
    """生成分润 Excel 文件"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '代理分润明细'

    # 表头样式
    header_font = Font(bold=True, color='FFFFFF', size=11)
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    # 写表头
    for col_idx, header in enumerate(EXPORT_HEADERS, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.value = header
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # 写数据
    data_font = Font(size=10)
    data_align = Alignment(horizontal='left', vertical='center')

    for row_idx, row_data in enumerate(aggregated_data, 2):
        for col_idx, header in enumerate(EXPORT_HEADERS, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.value = row_data.get(header, '')
            cell.font = data_font
            cell.alignment = data_align
            cell.border = thin_border

            # 分润金额保留两位小数
            if header == '分润金额' and isinstance(cell.value, (int, float)):
                cell.number_format = '0.00'

    # 自动调整列宽
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column[:min(100, len(aggregated_data) + 1)]:
            try:
                if cell.value is not None:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length
            except Exception:
                pass
        ws.column_dimensions[column_letter].width = min(max_length + 2, 50)

    # 冻结首行
    ws.freeze_panes = 'A2'

    wb.save(output_path)


# ── 任务管理 ──────────────────────────────────────────────

class ProfitShareService:

    @staticmethod
    def find_database_connection(database_connection_id: int = None) -> Optional[DatabaseConnection]:
        """查找数据库连接，优先使用指定ID，否则按名称查找"""
        if database_connection_id:
            conn = DatabaseConnection.query.get(database_connection_id)
            if conn and conn.is_active:
                return conn
        # 按名称查找"融聚商户通(海科)"
        for name_pattern in ['融聚商户通(海科)', '融聚商户通（海科）', '融聚商户通', '海科']:
            conn = DatabaseConnection.query.filter(
                DatabaseConnection.name.like(f'%{name_pattern}%'),
                DatabaseConnection.is_active == True
            ).first()
            if conn:
                return conn
        return None

    @staticmethod
    def create_task(org_no: str, start_time: str, end_time: str,
                    database_connection_id: int = None, created_by: int = None) -> QueryTask:
        task_id = str(uuid.uuid4())
        task = QueryTask(
            task_id=task_id,
            status='pending',
            type='export',
            output_format='sheets',
        )
        task.set_script_ids_json([])
        task.set_params_values({
            'org_no': org_no,
            'start_time': start_time,
            'end_time': end_time,
            'database_connection_id': database_connection_id,
        })

        if database_connection_id:
            task.set_database_ids([database_connection_id])
            task.database_connection_id = database_connection_id

        if created_by:
            task.created_by = created_by

        db.session.add(task)
        db.session.commit()
        return task

    @staticmethod
    def execute_async(task_id: str, org_no: str, start_time: str, end_time: str,
                      database_connection_id: int, output_dir: str, on_complete=None):
        cancel_event = threading.Event()
        _task_cancel_events[task_id] = cancel_event
        thread = threading.Thread(
            target=ProfitShareService._execute_background,
            args=(task_id, org_no, start_time, end_time, database_connection_id, output_dir, on_complete, cancel_event),
            daemon=True
        )
        _task_threads[task_id] = thread
        thread.start()

    @staticmethod
    def _execute_background(task_id: str, org_no: str, start_time: str, end_time: str,
                            database_connection_id: int, output_dir: str,
                            on_complete=None, cancel_event: threading.Event = None):
        try:
            from app import create_app
            app = create_app()
        except Exception:
            from flask import current_app
            app = current_app._get_current_object()

        with app.app_context():
            task = QueryTask.query.filter_by(task_id=task_id).first()
            if not task:
                return

            try:
                task.status = 'running'
                task.started_at = datetime.utcnow()
                task.add_log('开始执行代理分润导出任务')
                task.progress = 5
                db.session.commit()
                _update_progress(task_id, 5, '开始执行代理分润导出任务')

                # 1. 查找数据库连接
                conn = ProfitShareService.find_database_connection(database_connection_id)
                if not conn:
                    raise RuntimeError('未找到融聚商户通(海科)数据库连接，请在系统中配置该数据库连接')
                task.add_log(f'数据库连接: {conn.name}')
                task.set_database_ids([conn.id])
                task.progress = 10
                db.session.commit()
                _update_progress(task_id, 10, f'数据库连接: {conn.name}')

                if cancel_event and cancel_event.is_set():
                    raise RuntimeError('任务已被手动终止')

                # 2. 获取数据库连接器
                from app.utils.connection_pool import ConnectionPoolManager
                pool = ConnectionPoolManager.get_instance()
                connector = pool.get_connector_with_health_check(conn.id)
                if not connector:
                    raise RuntimeError(f'数据库连接失败: {conn.name}')

                # 3. 执行脚本1: 查询代理费率配置
                task.add_log('查询代理费率配置...')
                task.progress = 15
                db.session.commit()
                _update_progress(task_id, 15, '查询代理费率配置...')

                agent_rows = connector.execute_query(
                    SQL_AGENT_RATE_CONFIG,
                    {'org_no': org_no},
                    timeout=120,
                    chunk_size=5000
                )

                # 将行元组转为字典
                agent_columns = [
                    '代理商编号', '代理商名称', '代理商等级', '代理手机号码',
                    '上级代理商编号', '所属上级', '所属一级', '终端类型',
                    '费率类型', '产品ID', '成本内容'
                ]
                agent_dicts = []
                for row in agent_rows:
                    row_dict = {}
                    for i, col in enumerate(agent_columns):
                        row_dict[col] = row[i] if i < len(row) else None
                    agent_dicts.append(row_dict)

                task.add_log(f'代理费率配置查询完成: {len(agent_dicts)} 行')
                task.progress = 30
                db.session.commit()
                _update_progress(task_id, 30, f'代理费率配置查询完成: {len(agent_dicts)} 行')

                if cancel_event and cancel_event.is_set():
                    raise RuntimeError('任务已被手动终止')

                # 4. 执行脚本2: 查询交易订单
                task.add_log('查询交易订单...')
                task.progress = 35
                db.session.commit()
                _update_progress(task_id, 35, '查询交易订单...')

                order_rows = connector.execute_query(
                    SQL_TRADE_ORDERS,
                    {'org_no': org_no, 'start_time': start_time, 'end_time': end_time},
                    timeout=300,
                    chunk_size=5000
                )

                order_columns = [
                    '交易时间', '一级代理商编号', '交易金额', '交易费率', '交易手续费', '交易T0服务费',
                    '服务商费率成本', '服务商T0成本', '一级代理费率成本', '一级代理T0成本',
                    '交易类型', '卡类型', '产品ID', '终端类型'
                ]
                order_dicts = []
                for row in order_rows:
                    row_dict = {}
                    for i, col in enumerate(order_columns):
                        row_dict[col] = row[i] if i < len(row) else None
                    order_dicts.append(row_dict)

                task.add_log(f'交易订单查询完成: {len(order_dicts)} 行')
                task.progress = 50
                db.session.commit()
                _update_progress(task_id, 50, f'交易订单查询完成: {len(order_dicts)} 行')

                if not order_dicts:
                    task.add_log('未查询到交易订单数据', 'warning')

                if cancel_event and cancel_event.is_set():
                    raise RuntimeError('任务已被手动终止')

                # 5. 构建代理配置
                task.add_log('构建代理层级关系...')
                task.progress = 55
                db.session.commit()

                agent_configs = _build_agent_configs(agent_dicts, org_no)
                task.add_log(f'代理配置分组: {len(agent_configs)} 组 (设备类型+产品ID)')

                # 6. 逐笔订单计算分润
                task.add_log('计算分润...')
                task.progress = 60
                db.session.commit()
                _update_progress(task_id, 60, '计算分润...')

                # 聚合: {(agent_no, month): share_sum}
                monthly_shares: Dict[Tuple[str, str], float] = defaultdict(float)
                # 记录代理信息: {agent_no: AgentNode}
                agent_info_map: Dict[str, AgentNode] = {}
                # 记录每个代理的上级关系
                agent_ancestor_chain: Dict[str, str] = {}
                # 层级树缓存: {config_key: root_node}（同一设备+产品组合只需构建一次）
                hierarchy_cache: Dict[Tuple, Optional[AgentNode]] = {}

                total_orders = len(order_dicts)
                processed = 0
                skipped_no_config = 0
                skipped_no_root = 0
                skipped_no_pool = 0
                skipped_no_share = 0
                # 按月份统计: {month: {'total': n, 'skipped': n, 'shared': n}}
                month_stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {'total': 0, 'skipped': 0, 'shared': 0})

                for order in order_dicts:
                    device_type = str(order.get('终端类型', '')).strip()
                    product_id = str(order.get('产品ID', '')).strip()
                    config_key = (device_type, product_id)

                    # 提取月份
                    trade_time = order.get('交易时间')
                    month_str = ''
                    if trade_time:
                        if isinstance(trade_time, datetime):
                            month_str = trade_time.strftime('%Y-%m')
                        elif isinstance(trade_time, str):
                            month_str = trade_time[:7]  # YYYY-MM
                        else:
                            month_str = str(trade_time)[:7]
                    month_stats[month_str]['total'] += 1

                    agents = agent_configs.get(config_key)
                    if not agents:
                        skipped_no_config += 1
                        month_stats[month_str]['skipped'] += 1
                        processed += 1
                        continue

                    # 从缓存获取层级树（同一设备+产品组合只构建一次）
                    if config_key not in hierarchy_cache:
                        hierarchy_cache[config_key] = _build_hierarchy(agents, org_no)
                    root = hierarchy_cache[config_key]

                    if root is None:
                        skipped_no_root += 1
                        month_stats[month_str]['skipped'] += 1
                        processed += 1
                        continue

                    # 计算分润
                    shares = _calculate_order_shares(order, root, agents, org_no)

                    if not shares:
                        skipped_no_share += 1
                        month_stats[month_str]['skipped'] += 1
                        processed += 1
                        continue

                    # 聚合
                    has_positive_share = False
                    for agent_no, share in shares.items():
                        if share == 0:
                            continue
                        monthly_shares[(agent_no, month_str)] += share
                        has_positive_share = True

                        # 记录代理信息
                        if agent_no not in agent_info_map:
                            node = agents.get(agent_no)
                            if node:
                                agent_info_map[agent_no] = node
                                chain = _get_ancestor_chain(node, agents)
                                agent_ancestor_chain[agent_no] = '-'.join(chain)

                    if has_positive_share:
                        month_stats[month_str]['shared'] += 1
                    else:
                        skipped_no_share += 1
                        month_stats[month_str]['skipped'] += 1

                    processed += 1
                    if processed % 1000 == 0:
                        task.add_log(f'已处理 {processed}/{total_orders} 笔订单')
                        task.progress = min(60 + int(30 * processed / max(total_orders, 1)), 85)
                        db.session.commit()

                # 输出详细统计
                task.add_log(f'分润计算完成: 处理 {processed} 笔订单')
                task.add_log(f'  - 无匹配代理配置: {skipped_no_config} 笔')
                task.add_log(f'  - 无根节点: {skipped_no_root} 笔')
                task.add_log(f'  - 无分润结果(total_pool<=0或其他): {skipped_no_share} 笔')
                for month_key in sorted(month_stats.keys()):
                    s = month_stats[month_key]
                    task.add_log(f'  月份 {month_key}: 总计 {s["total"]} 笔, 跳过 {s["skipped"]} 笔, 有分润 {s["shared"]} 笔')
                task.progress = 90
                db.session.commit()
                _update_progress(task_id, 90, '生成导出文件...')

                # 7. 准备导出数据
                export_rows = []
                for (agent_no, month), share in sorted(monthly_shares.items(), key=lambda x: (x[0][1], x[0][0])):
                    node = agent_info_map.get(agent_no)
                    if node:
                        export_rows.append({
                            '代理商编号': agent_no,
                            '代理商名称': node.agent_name,
                            '分润金额': round(share, 2),
                            '月份': month,
                            '代理商电话': node.login_phone,
                            '代理商等级': node.rank,
                            '所属一级代理商名称': node.root_name,
                            '上级代理商': node.parent_name,
                            '上级关系': agent_ancestor_chain.get(agent_no, ''),
                        })

                if not export_rows:
                    task.add_log('未生成分润数据', 'warning')

                # 8. 生成 Excel
                task.add_log('生成Excel文件...')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                output_filename = f'profit_share_{org_no}_{timestamp}.xlsx'
                output_path = os.path.join(output_dir, output_filename)

                _generate_excel(export_rows, output_path)

                task.add_log(f'导出完成，共 {len(export_rows)} 行分润记录')
                task.status = 'completed'
                task.completed_at = datetime.utcnow()
                task.output_file = output_path
                task.total_rows = len(export_rows)
                task.success_count = len(export_rows)
                task.failure_count = 0
                task.progress = 100
                task.error_message = None
                db.session.commit()
                _update_progress(task_id, 100, '导出完成')

                if on_complete:
                    try:
                        on_complete(task_id, 'completed')
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"代理分润导出失败: {str(e)}", exc_info=True)
                task.status = 'failed'
                task.completed_at = datetime.utcnow()
                task.error_message = str(e)
                task.progress = 100
                task.add_log(f'导出失败: {str(e)}', 'error')
                db.session.commit()
                _update_progress(task_id, 100, f'导出失败: {str(e)}', 'error')
                if on_complete:
                    try:
                        on_complete(task_id, 'failed')
                    except Exception:
                        pass

    @staticmethod
    def get_task_status(task_id: str) -> Optional[dict]:
        task = QueryTask.query.filter_by(task_id=task_id).first()
        if not task:
            return None
        result = task.to_dict()
        progress_info = _get_progress(task_id)
        if progress_info.get('progress', 0) > result.get('progress', 0):
            result['progress'] = progress_info['progress']
        return result

    @staticmethod
    def cancel_task(task_id: str) -> bool:
        task = QueryTask.query.filter_by(task_id=task_id, type='export').first()
        if not task:
            return False
        if task.status in ('pending', 'running'):
            cancel_event = _task_cancel_events.get(task_id)
            if cancel_event:
                cancel_event.set()

            thread = _task_threads.get(task_id)
            if thread and thread.is_alive():
                try:
                    import ctypes
                    tid = ctypes.c_long(thread.ident)
                    ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(SystemExit))
                except Exception:
                    pass

            task.status = 'manual_cancelled'
            task.completed_at = datetime.utcnow()
            task.add_log('任务已被手动终止', 'warning')
            db.session.commit()

            _task_threads.pop(task_id, None)
            _task_cancel_events.pop(task_id, None)
            return True
        return False
