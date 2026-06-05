SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

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
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_is_active (is_active),
    FOREIGN KEY (database_connection_id) REFERENCES database_connections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='SQL脚本配置表';

CREATE TABLE IF NOT EXISTS query_tasks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(64) NOT NULL UNIQUE COMMENT '任务ID',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/running/completed/failed',
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
    INDEX idx_task_id (task_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (script_id) REFERENCES scripts(id),
    FOREIGN KEY (database_connection_id) REFERENCES database_connections(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='查询任务表';

CREATE TABLE IF NOT EXISTS execution_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    task_id VARCHAR(50) NOT NULL COMMENT '任务ID',
    level ENUM('INFO', 'WARNING', 'ERROR', 'DEBUG') DEFAULT 'INFO' COMMENT '日志级别',
    message TEXT NOT NULL COMMENT '日志内容',
    details JSON COMMENT '详细信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_id (task_id),
    INDEX idx_level (level),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='执行日志表';

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    email VARCHAR(100) COMMENT '邮箱',
    role ENUM('admin', 'user') DEFAULT 'user' COMMENT '角色',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
    last_login_at TIMESTAMP NULL COMMENT '最后登录时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

SET FOREIGN_KEY_CHECKS = 1;

INSERT INTO users (username, password_hash, email, role, is_active) VALUES
('admin', '$2a$12$LQj3z6T2hQJ5vXqY7KZPpeV5mN8XwR1sT3uB6cF9dE2gH4iJ7kL0nM', 'admin@example.com', 'admin', TRUE);
