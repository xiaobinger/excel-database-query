-- =====================================================
-- Excel Database Query Tool - 初始化脚本
-- 版本: 3.0
-- 说明: 本脚本用于初始化应用数据库（SQLite由ORM自动创建，此脚本仅用于MySQL等外部数据库参考）
-- =====================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- 角色表
-- ----------------------------
CREATE TABLE IF NOT EXISTS roles (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE COMMENT '角色名称',
    description VARCHAR(500) COMMENT '角色描述',
    menu_permissions TEXT COMMENT '菜单权限(JSON数组)',
    button_permissions TEXT COMMENT '按钮权限(JSON数组)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ----------------------------
-- 用户表
-- ----------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    email VARCHAR(100) COMMENT '邮箱',
    phone VARCHAR(20) COMMENT '手机号',
    gender VARCHAR(10) DEFAULT 'other' COMMENT '性别: male/female/other',
    role_id INT COMMENT '角色ID',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    theme VARCHAR(50) DEFAULT 'default' COMMENT '用户主题偏好',
    auto_task_ids TEXT COMMENT '授权的自动导出任务ID列表(JSON)',
    last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_role_id (role_id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------
-- SSH配置表
-- ----------------------------
CREATE TABLE IF NOT EXISTS ssh_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '配置名称',
    host VARCHAR(255) NOT NULL COMMENT 'SSH主机地址',
    port INT NOT NULL DEFAULT 22 COMMENT 'SSH端口',
    username VARCHAR(100) NOT NULL COMMENT 'SSH用户名',
    encrypted_password TEXT COMMENT '加密后的SSH密码',
    pkey_path VARCHAR(500) COMMENT 'SSH私钥路径',
    local_bind_port INT COMMENT 'SSH本地绑定端口',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SSH配置表';

-- ----------------------------
-- 数据库连接配置表
-- ----------------------------
CREATE TABLE IF NOT EXISTS database_connections (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '连接名称',
    description VARCHAR(500) COMMENT '连接描述',
    db_type VARCHAR(50) NOT NULL DEFAULT 'mysql' COMMENT '数据库类型',
    host VARCHAR(255) NOT NULL COMMENT '主机地址',
    port INT NOT NULL DEFAULT 3306 COMMENT '端口号',
    database_name VARCHAR(255) NOT NULL COMMENT '数据库名',
    username VARCHAR(100) NOT NULL COMMENT '用户名',
    encrypted_password TEXT NOT NULL COMMENT '加密后的密码',
    pool_size INT DEFAULT 5 COMMENT '连接池大小',
    max_overflow INT DEFAULT 10 COMMENT '最大溢出连接数',
    ssh_enabled BOOLEAN DEFAULT FALSE COMMENT '是否启用SSH隧道',
    ssh_config_id INT COMMENT '关联SSH配置',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (ssh_config_id) REFERENCES ssh_configs(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='数据库连接配置表';

-- ----------------------------
-- 查询/导出选项表
-- ----------------------------
CREATE TABLE IF NOT EXISTS scripts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE COMMENT '脚本名称',
    description VARCHAR(500) COMMENT '脚本描述',
    sql_text TEXT NOT NULL COMMENT 'SQL语句',
    tag VARCHAR(100) COMMENT '标签',
    result_sheet_name VARCHAR(100) DEFAULT '查询结果' COMMENT '结果工作表名',
    batch_size INT DEFAULT 100 COMMENT '批处理大小',
    timeout INT DEFAULT 30 COMMENT '超时时间(秒)',
    query_mode VARCHAR(20) DEFAULT 'batch' COMMENT '查询模式: batch/in',
    param_column VARCHAR(100) COMMENT '参数列名',
    database_connection_id INT COMMENT '关联数据库连接',
    database_ids TEXT COMMENT '关联数据库ID列表(JSON)',
    merge_strategy VARCHAR(20) DEFAULT 'concat' COMMENT '结果合并策略: concat/separate',
    column_mapping TEXT COMMENT '列映射配置(JSON)',
    new_sheet BOOLEAN DEFAULT TRUE COMMENT '是否新建工作表',
    primary_key VARCHAR(100) COMMENT '主键字段(不新建工作表时使用)',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    type VARCHAR(20) DEFAULT 'query' COMMENT '类型: query/export',
    params_config TEXT COMMENT '导出参数配置(JSON)',
    sql_template TEXT COMMENT 'SQL模板(Jinja2语法)',
    template_config TEXT COMMENT '模板变量配置(JSON)',
    is_template BOOLEAN DEFAULT FALSE COMMENT '是否启用SQL模板',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_is_active (is_active),
    INDEX idx_type (type),
    FOREIGN KEY (database_connection_id) REFERENCES database_connections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询/导出选项表';

-- ----------------------------
-- 查询/导出任务表
-- ----------------------------
CREATE TABLE IF NOT EXISTS query_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL UNIQUE COMMENT '任务ID',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/running/completed/failed/cancelled',
    script_id INT COMMENT '关联脚本',
    database_connection_id INT COMMENT '关联数据库连接',
    database_ids TEXT COMMENT '关联数据库ID列表(JSON)',
    input_file VARCHAR(500) COMMENT '输入文件路径',
    output_file VARCHAR(500) COMMENT '输出文件路径',
    total_rows INT DEFAULT 0 COMMENT '总行数',
    success_count INT DEFAULT 0 COMMENT '成功行数',
    failure_count INT DEFAULT 0 COMMENT '失败行数',
    progress INT DEFAULT 0 COMMENT '执行进度(0-100)',
    logs TEXT COMMENT '执行日志(JSON)',
    merge_strategy VARCHAR(20) DEFAULT 'concat' COMMENT '结果合并策略',
    error_message TEXT COMMENT '错误信息',
    started_at TIMESTAMP NULL COMMENT '开始时间',
    completed_at TIMESTAMP NULL COMMENT '完成时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INT COMMENT '创建用户ID',
    type VARCHAR(20) DEFAULT 'query' COMMENT '任务类型: query/export',
    params_values TEXT COMMENT '导出参数值(JSON)',
    output_format VARCHAR(20) DEFAULT 'sheets' COMMENT '导出格式: sheets/zip',
    script_ids_json TEXT COMMENT '关联脚本ID列表(JSON)',
    is_auto BOOLEAN DEFAULT FALSE COMMENT '是否自动执行任务',
    auto_task_id INT COMMENT '关联自动任务ID',
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    INDEX idx_type (type),
    INDEX idx_created_by (created_by),
    FOREIGN KEY (script_id) REFERENCES scripts(id),
    FOREIGN KEY (database_connection_id) REFERENCES database_connections(id),
    FOREIGN KEY (created_by) REFERENCES users(id),
    FOREIGN KEY (auto_task_id) REFERENCES auto_export_tasks(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询/导出任务表';

-- ----------------------------
-- 自动导出任务表
-- ----------------------------
CREATE TABLE IF NOT EXISTS auto_export_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '任务名称',
    description VARCHAR(500) COMMENT '描述',
    script_ids TEXT NOT NULL COMMENT '关联导出选项ID列表(JSON)',
    cron_expression VARCHAR(100) NOT NULL COMMENT 'Cron表达式',
    output_format VARCHAR(20) DEFAULT 'sheets' COMMENT '导出格式: sheets/zip',
    auto_params TEXT COMMENT '自动参数配置(JSON)',
    is_enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    last_run_at TIMESTAMP NULL COMMENT '上次执行时间',
    last_run_status VARCHAR(20) COMMENT '上次执行状态',
    last_task_id VARCHAR(64) COMMENT '上次执行的任务ID',
    next_run_at TIMESTAMP NULL COMMENT '下次预计执行时间',
    created_by INT COMMENT '创建用户ID',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    notify_enabled BOOLEAN DEFAULT FALSE COMMENT '是否启用通知',
    notify_emails TEXT COMMENT '通知邮箱列表(JSON数组)',
    notify_attach_file BOOLEAN DEFAULT FALSE COMMENT '是否附件发送结果文件',
    INDEX idx_is_enabled (is_enabled),
    INDEX idx_created_by (created_by),
    FOREIGN KEY (created_by) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动导出任务表';

-- ----------------------------
-- 系统配置表
-- ----------------------------
CREATE TABLE IF NOT EXISTS system_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    config_key VARCHAR(100) NOT NULL UNIQUE COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    encrypted_value TEXT COMMENT '加密值(敏感配置)',
    description VARCHAR(500) COMMENT '描述',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统配置表';

-- ----------------------------
-- AI模型配置表
-- ----------------------------
CREATE TABLE IF NOT EXISTS ai_configs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '配置名称',
    provider VARCHAR(50) NOT NULL DEFAULT 'openai' COMMENT 'AI提供商: openai/zhipu/deepseek/custom',
    api_key TEXT COMMENT 'API密钥(加密存储)',
    api_base VARCHAR(500) COMMENT 'API基础URL',
    model_name VARCHAR(100) COMMENT '模型名称',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否默认配置',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    max_tokens INT DEFAULT 4096 COMMENT '最大token数',
    temperature FLOAT DEFAULT 0.7 COMMENT '温度参数',
    system_prompt TEXT COMMENT '系统提示词',
    description VARCHAR(500) COMMENT '描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_provider (provider),
    INDEX idx_is_default (is_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI模型配置表';

-- ----------------------------
-- AI对话表
-- ----------------------------
CREATE TABLE IF NOT EXISTS ai_chats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    title VARCHAR(200) COMMENT '对话标题',
    is_archived BOOLEAN DEFAULT FALSE COMMENT '是否归档',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI对话表';

-- ----------------------------
-- AI对话消息表
-- ----------------------------
CREATE TABLE IF NOT EXISTS ai_chat_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chat_id INT NOT NULL COMMENT '对话ID',
    role VARCHAR(20) NOT NULL COMMENT '角色: user/assistant/system',
    content TEXT COMMENT '消息内容',
    tokens_used INT DEFAULT 0 COMMENT '消耗token数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_chat_id (chat_id),
    FOREIGN KEY (chat_id) REFERENCES ai_chats(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI对话消息表';

-- ----------------------------
-- AI技能表
-- ----------------------------
CREATE TABLE IF NOT EXISTS ai_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '技能名称',
    skill_type VARCHAR(50) NOT NULL DEFAULT 'system' COMMENT '技能类型: system/user/auto',
    category VARCHAR(50) COMMENT '分类: query/export/ui/behavior/workflow',
    description VARCHAR(500) COMMENT '描述',
    content TEXT COMMENT '技能内容JSON',
    trigger_conditions TEXT COMMENT '触发条件JSON',
    user_id INT COMMENT '所属用户ID(system类型为空)',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    version INT DEFAULT 1 COMMENT '版本号',
    usage_count INT DEFAULT 0 COMMENT '使用次数',
    source VARCHAR(50) DEFAULT 'manual' COMMENT '来源: manual/auto_learn/ai_generated',
    parent_id INT COMMENT '父技能ID(版本继承)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_skill_type (skill_type),
    INDEX idx_user_id (user_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (parent_id) REFERENCES ai_skills(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI技能表';

-- ----------------------------
-- 用户行为记录表
-- ----------------------------
CREATE TABLE IF NOT EXISTS user_behaviors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    action VARCHAR(100) NOT NULL COMMENT '行为类型: query/export/view/create/edit/delete/chat',
    target_type VARCHAR(50) COMMENT '目标类型: script/task/database/export_script/auto_task',
    target_id INT COMMENT '目标ID',
    detail TEXT COMMENT '行为详情JSON',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户行为记录表';

-- ----------------------------
-- 业务系统表
-- ----------------------------
CREATE TABLE IF NOT EXISTS business_systems (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL COMMENT '系统名称',
    description VARCHAR(500) COMMENT '系统描述',
    logo_url VARCHAR(500) COMMENT 'Logo URL或图标class',
    website_url VARCHAR(500) NOT NULL COMMENT '系统网址',
    category VARCHAR(50) COMMENT '分类',
    sort_order INT DEFAULT 0 COMMENT '排序',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    sso_enabled BOOLEAN DEFAULT FALSE COMMENT '是否启用SSO',
    sso_url VARCHAR(500) COMMENT 'SSO登录地址',
    sso_method VARCHAR(10) DEFAULT 'POST' COMMENT 'SSO请求方式 GET/POST',
    sso_phone_field VARCHAR(50) DEFAULT 'phone' COMMENT '手机号字段名',
    sso_token_field VARCHAR(50) DEFAULT 'token' COMMENT 'Token字段名',
    sso_extra_params TEXT COMMENT '额外参数(JSON)',
    sso_token_key VARCHAR(100) COMMENT 'SSO签名密钥(加密)',
    sso_response_token_key VARCHAR(100) DEFAULT 'token' COMMENT 'SSO响应中token的路径',
    sso_token_pass_key VARCHAR(50) DEFAULT 'token' COMMENT '跳转网站时传递token的参数名',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='业务系统表';

SET FOREIGN_KEY_CHECKS = 1;

-- ----------------------------
-- 初始数据
-- ----------------------------
-- 默认角色：超级管理员
INSERT INTO roles (name, description, menu_permissions, button_permissions) VALUES
('admin', '超级管理员', '["dashboard","query","export","history","scripts","export_options","databases","auto_export","system_config","ai_config","ai_chat","skills","business_systems","user_manager","role_manager"]', '["query:execute","query:download","export:execute","export:download","script:create","script:edit","script:delete","database:create","database:edit","database:delete","database:test","ssh:create","ssh:edit","ssh:delete","auto_task:create","auto_task:edit","auto_task:delete","auto_task:execute","business:create","business:edit","business:delete","business:sso","ai:config","ai:chat","ai:skill","user:create","user:edit","user:delete","role:create","role:edit","role:delete"]');

-- 默认管理员用户（密码: admin123）
-- 注意: 实际部署时应通过应用注册接口创建，此处密码哈希由Werkzeug生成
INSERT INTO users (username, password_hash, email, role_id, is_active) VALUES
('admin', 'pbkdf2:sha256:600000$placeholder$please_change_this_via_app_registration', 'admin@example.com', 1, TRUE);
