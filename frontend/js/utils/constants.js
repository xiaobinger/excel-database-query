const EDB_CONSTANTS = {
    API_BASE: 'http://192.168.3.221:5000/api',
    DB_TYPES: [
        { value: 'mysql', label: 'MySQL', icon: 'fas fa-database', color: '#00758f' },
        { value: 'postgresql', label: 'PostgreSQL', icon: 'fas fa-database', color: '#336791' },
        { value: 'sqlite', label: 'SQLite', icon: 'fas fa-file-alt', color: '#44a0e0' },
        { value: 'oracle', label: 'Oracle', icon: 'fas fa-database', color: '#f80000' },
        { value: 'sqlserver', label: 'SQL Server', icon: 'fas fa-database', color: '#cc2927' }
    ],
    TASK_STATUS: {
        PENDING: { value: 'pending', label: '等待中', badge: 'edb-badge--muted', icon: 'fas fa-clock' },
        RUNNING: { value: 'running', label: '执行中', badge: 'edb-badge--info', icon: 'fas fa-spinner fa-spin' },
        COMPLETED: { value: 'completed', label: '已完成', badge: 'edb-badge--success', icon: 'fas fa-check-circle' },
        FAILED: { value: 'failed', label: '失败', badge: 'edb-badge--error', icon: 'fas fa-times-circle' },
        CANCELLED: { value: 'cancelled', label: '已取消', badge: 'edb-badge--warning', icon: 'fas fa-ban' }
    },
    OUTPUT_MODES: [
        { value: 'new_sheet', label: '新建工作表', icon: 'fas fa-file-plus', desc: '在原Excel中创建新工作表' },
        { value: 'overwrite', label: '覆盖原表', icon: 'fas fa-file-edit', desc: '将结果填充到原工作表' },
        { value: 'new_file', label: '新建文件', icon: 'fas fa-file-export', desc: '生成新的Excel文件' }
    ],
    LOG_LEVELS: {
        DEBUG: { value: 'DEBUG', label: 'DEBUG', class: 'edb-log-entry__level--info' },
        INFO: { value: 'INFO', label: 'INFO', class: 'edb-log-entry__level--info' },
        WARN: { value: 'WARN', label: 'WARN', class: 'edb-log-entry__level--warn' },
        ERROR: { value: 'ERROR', label: 'ERROR', class: 'edb-log-entry__level--error' }
    },
    ALLOWED_FILE_TYPES: ['.xlsx', '.xls', '.csv'],
    MAX_FILE_SIZE: 100 * 1024 * 1024,
    POLL_INTERVAL: 2000,
    CACHE_TTL: 5 * 60 * 1000,
    TOAST_DURATION: 3000,
    ROUTES: {
        DASHBOARD: '/',
        DATABASES: '/databases',
        SCRIPTS: '/scripts',
        QUERY: '/query',
        HISTORY: '/history'
    }
};
