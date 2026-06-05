import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.ssh_config import SshConfig
from app.models.database import DatabaseConnection
from app.models.script import Script

SSH_CONFIGS = [
    {
        'name': 'juheba_jumpserver',
        'host': 'tb.juheba.top',
        'port': 60022,
        'username': 'xiongbing',
        'password': os.environ.get('RFSHT_SSH_PASSWORD', ''),
    },
]

DB_CONNECTIONS = [
    {
        'name': 'rfsht_pro_db',
        'description': '融付商户通-生产环境 MySQL 数据库 (通过SSH隧道连接)',
        'db_type': 'mysql',
        'host': 'zf-rfsht.rwlb.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'posp_business',
        'username': 'db_read',
        'password': os.environ.get('RFSHT_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
    {
        'name': 'rjjb_pro_db',
        'description': '融聚金宝-生产环境 MySQL 数据库 (通过SSH密钥连接)',
        'db_type': 'mysql',
        'host': 'zf-rjjb-polardb.rwlb.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'zf_jhb_kysplus',
        'username': 'db_read',
        'password': os.environ.get('RJJB_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
    {
        'name': 'rjsht_pro_db',
        'description': '融聚商户通-生产环境 MySQL 数据库 (通过SSH隧道连接)',
        'db_type': 'mysql',
        'host': 'rm-uf680gyj33i537072.mysql.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'posp_business',
        'username': 'db_read',
        'password': os.environ.get('RJSHT_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
    {
        'name': 'rtjb_pro_db',
        'description': '融通金宝-生产环境 MySQL 数据库 (通过SSH密钥连接)',
        'db_type': 'mysql',
        'host': 'rtjb-polardb.rwlb.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'kqbiz',
        'username': 'db_read',
        'password': os.environ.get('RTJB_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
    {
        'name': 'dy_pro_db',
        'description': '猛刷电银-生产环境 MySQL 数据库 (通过SSH隧道连接)',
        'db_type': 'mysql',
        'host': 'zftpro-td.rwlb.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'posp_business',
        'username': 'db_read',
        'password': os.environ.get('DY_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
    {
        'name': 'lst_pro_db',
        'description': '乐商通-生产环境 MySQL 数据库 (通过SSH隧道连接)',
        'db_type': 'mysql',
        'host': 'pc-uf6z53x05773qun08.rwlb.rds.aliyuncs.com',
        'port': 3306,
        'database_name': 'posp_business',
        'username': 'db_read',
        'password': os.environ.get('LST_PRO_DB_PASSWORD', ''),
        'ssh_enabled': True,
        'ssh_config_name': 'juheba_jumpserver',
    },
]

SQL_SCRIPTS = [
    {
        'name': 'user_basic_info_rfsht',
        'tag': '融付商户通-商户信息',
        'description': '匹配融付商户通商户信息',
        'sql_text': "SELECT a.channel_merchant_no 中付商户编号, m.merchant_no 我方商户号, a.legal_person_name 商户姓名, m.phone 商户电话, m.device_sn SN FROM posp_business.merchant_archive_v2 a LEFT JOIN posp_business.merchant m ON a.merchant_no = m.merchant_no WHERE a.channel_merchant_no in :value",
        'query_mode': 'in',
        'database_connection_name': 'rfsht_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'user_basic_info_rjjb',
        'tag': '融聚金宝-商户信息',
        'description': '匹配融聚金宝商户信息',
        'sql_text': "SELECT m.`code` 中付商户编号, m.`code` 我方商户号, i.real_name 商户姓名, m.phone 商户电话, p.sn SN FROM zf_jhb_kysplus.merchant m LEFT JOIN zf_jhb_kysplus.merchant_identity_info i ON m.id = i.merchant_id LEFT JOIN zf_jhb_kysplus.merchant_device pd ON pd.merchant_id = m.id LEFT JOIN zf_jhb_kysplus.pos p ON pd.pos_id = p.id WHERE m.`code` IN :value",
        'query_mode': 'in',
        'database_connection_name': 'rjjb_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'user_basic_info_rjsht',
        'tag': '融聚商户通-商户信息',
        'description': '匹配融聚商户通商户信息',
        'sql_text': "SELECT a.channel_merchant_no 注册商户号, m.merchant_no 我方商户号, a.legal_person_name 商户姓名, m.phone 商户电话, m.device_sn SN, o.org_name 所属机构, o.org_name 所属顶级机构, o.alias_name 别称 FROM posp_business.merchant_archive_v2 a LEFT JOIN posp_business.merchant m ON a.merchant_no = m.merchant_no LEFT JOIN posp_business.`org` o ON m.org_code = o.org_code WHERE a.channel_merchant_no IN :value",
        'query_mode': 'in',
        'database_connection_name': 'rjsht_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'user_basic_info_rtjb',
        'tag': '融通金宝-商户信息',
        'description': '匹配融通金宝商户信息',
        'sql_text': "SELECT m.`code` 注册商户号, m.`code` 我方商户号, i.real_name 商户姓名, m.phone 商户电话, p.sn SN, o.`name` 所属机构, pa.`name` 所属顶级机构 FROM kqbiz.merchant m LEFT JOIN kqbiz.merchant_identity_info i ON m.id=i.merchant_id LEFT JOIN kqbiz.merchant_device pd ON pd.merchant_id=m.id LEFT JOIN kqbiz.pos p ON pd.pos_id=p.id LEFT JOIN kqbiz.merchant_employee me ON me.merchant_id=m.id AND me.end_time> '20260326111900' LEFT JOIN kqbiz.org o ON me.org_id=o.id LEFT JOIN kqbiz.org pa ON o.root_id=pa.id WHERE m.`code` IN :value",
        'query_mode': 'in',
        'database_connection_name': 'rtjb_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'user_basic_info_dy',
        'tag': '猛刷电银-商户信息',
        'description': '匹配猛刷电银商户信息',
        'sql_text': "SELECT a.channel_merchant_no 注册商户号, m.merchant_no 我方商户号, a.legal_person_name 商户姓名, m.phone 商户电话, m.device_sn SN FROM posp_business.merchant_archive_v2 a LEFT JOIN posp_business.merchant m ON a.merchant_no = m.merchant_no WHERE a.channel_merchant_no in :value",
        'query_mode': 'in',
        'database_connection_name': 'dy_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'user_basic_info_lst',
        'tag': '乐商通-商户信息',
        'description': '匹配乐商通商户信息',
        'sql_text': "SELECT a.channel_merchant_no 注册商户号, m.merchant_no 我方商户号, a.legal_person_name 商户姓名, m.phone 商户电话, m.device_sn SN FROM posp_business.merchant_archive_v2 a LEFT JOIN posp_business.merchant m ON a.merchant_no = m.merchant_no WHERE a.channel_merchant_no in :value",
        'query_mode': 'in',
        'database_connection_name': 'lst_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '用户基本信息',
    },
    {
        'name': 'terminal_trade_status',
        'tag': '终端交易情况匹配',
        'description': '需要匹配前置所有通道',
        'sql_text': "SELECT d.device_sn SN, IF(TIMESTAMPDIFF(MONTH,max(t.trade_time),NOW())<=6,'有','无') 近6个月交易, IF(TIMESTAMPDIFF(MONTH,max(t.trade_time),NOW())<=9,'有','无') 近9个月交易, IF(TIMESTAMPDIFF(MONTH,max(t.trade_time),NOW())<=12,'有','无') 近12个月交易, d.bind_time 绑定时间, o.org_name 终端所属机构名称, o.org_code 终端所属机构编号, o.org_name 终端所属一级机构名称, o.org_code 终端所属一级机构编号, m.merchant_name 商户名称, m.merchant_no 商户编号, ds.supplier_name 终端厂商, CONCAT(IF(d.is_bind=1,'已绑定','未绑定'),'-',IF(d.activate_time IS NOT NULL,'已激活','未激活')) 终端状态, CASE WHEN d.channel IN ('dyin','helipay') THEN '掌银刷' WHEN d.channel='lepass' THEN '乐势通' WHEN d.channel='zf' THEN '融付商户通' WHEN d.channel IN ('zft_plus','hkrt') THEN '融聚商户通' END 所属前置, DATE_FORMAT(NOW(),'%Y-%m-%d') 取数时间 FROM posp_business.device d LEFT JOIN posp_business.device_supplier ds ON d.supplier=ds.id LEFT JOIN posp_business.merchant m ON d.device_sn=m.device_sn LEFT JOIN posp_business.org o ON d.agent_no=o.org_code LEFT JOIN posp_business.trade_order t ON d.device_sn=t.device_sn WHERE d.device_sn IN :value GROUP BY d.device_sn",
        'query_mode': 'in',
        'database_connection_name': 'rfsht_pro_db',
        'batch_size': 100,
        'timeout': 30,
        'result_sheet_name': '查询结果',
    },
]


def seed():
    app = create_app()

    with app.app_context():
        db.create_all()

        ssh_count = 0
        ssh_map = {}
        for ssh_data in SSH_CONFIGS:
            existing = SshConfig.query.filter_by(name=ssh_data['name']).first()
            if existing:
                print(f"  [SKIP] SSH配置已存在: {ssh_data['name']}")
                ssh_map[ssh_data['name']] = existing
                continue

            password = ssh_data.pop('password')
            ssh_config = SshConfig(**ssh_data)
            if password:
                ssh_config.set_password(password)
            else:
                ssh_config.set_password('placeholder_change_me')

            db.session.add(ssh_config)
            ssh_map[ssh_data['name']] = ssh_config
            ssh_count += 1
            print(f"  [ADD] SSH配置: {ssh_data['name']}")

        db.session.flush()

        conn_count = 0
        conn_map = {}
        for conn_data in DB_CONNECTIONS:
            existing = DatabaseConnection.query.filter_by(name=conn_data['name']).first()
            if existing:
                print(f"  [SKIP] 数据库连接已存在: {conn_data['name']}")
                conn_map[conn_data['name']] = existing
                continue

            ssh_config_name = conn_data.pop('ssh_config_name', None)
            password = conn_data.pop('password')

            ssh_config_id = None
            if ssh_config_name and ssh_config_name in ssh_map:
                ssh_config_id = ssh_map[ssh_config_name].id

            conn = DatabaseConnection(**conn_data, ssh_config_id=ssh_config_id)
            if password:
                conn.set_password(password)
            else:
                conn.set_password('placeholder_change_me')

            db.session.add(conn)
            conn_map[conn_data['name']] = conn
            conn_count += 1
            print(f"  [ADD] 数据库连接: {conn_data['name']}")

        db.session.flush()

        script_count = 0
        for script_data in SQL_SCRIPTS:
            existing = Script.query.filter_by(name=script_data['name']).first()
            if existing:
                print(f"  [SKIP] SQL脚本已存在: {script_data['name']}")
                continue

            conn_name = script_data.pop('database_connection_name')
            conn = DatabaseConnection.query.filter_by(name=conn_name).first()
            if conn:
                script_data['database_connection_id'] = conn.id

            script = Script(**script_data)
            db.session.add(script)
            script_count += 1
            print(f"  [ADD] SQL脚本: {script_data['name']}")

        db.session.commit()

        print(f"\n种子数据初始化完成!")
        print(f"  SSH配置: 新增 {ssh_count} 个")
        print(f"  数据库连接: 新增 {conn_count} 个")
        print(f"  SQL脚本: 新增 {script_count} 个")
        print(f"  SSH配置总数: {SshConfig.query.count()}")
        print(f"  数据库连接总数: {DatabaseConnection.query.count()}")
        print(f"  SQL脚本总数: {Script.query.count()}")


if __name__ == '__main__':
    seed()
