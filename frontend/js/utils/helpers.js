const EDBHelpers = {
    formatDate(dateStr) {
        if (!dateStr) return '-';
        const d = new Date(dateStr);
        const pad = n => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    },

    formatRelativeTime(dateStr) {
        if (!dateStr) return '-';
        const now = Date.now();
        const diff = now - new Date(dateStr).getTime();
        const seconds = Math.floor(diff / 1000);
        if (seconds < 60) return '刚刚';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}分钟前`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}小时前`;
        const days = Math.floor(hours / 24);
        if (days < 30) return `${days}天前`;
        return this.formatDate(dateStr);
    },

    formatDuration(seconds) {
        if (!seconds && seconds !== 0) return '-';
        if (seconds < 60) return `${seconds.toFixed(1)}秒`;
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        if (m < 60) return `${m}分${s}秒`;
        const h = Math.floor(m / 60);
        const rm = m % 60;
        return `${h}时${rm}分${s}秒`;
    },

    formatFileSize(bytes) {
        if (!bytes) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) {
            size /= 1024;
            i++;
        }
        return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
    },

    debounce(fn, delay = 300) {
        let timer = null;
        return function (...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },

    throttle(fn, limit = 300) {
        let inThrottle = false;
        return function (...args) {
            if (!inThrottle) {
                fn.apply(this, args);
                inThrottle = true;
                setTimeout(() => { inThrottle = false; }, limit);
            }
        };
    },

    generateId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    },

    getStatusConfig(status) {
        return EDB_CONSTANTS.TASK_STATUS[status?.toUpperCase()] || EDB_CONSTANTS.TASK_STATUS.PENDING;
    },

    getDbTypeConfig(type) {
        return EDB_CONSTANTS.DB_TYPES.find(t => t.value === type) || EDB_CONSTANTS.DB_TYPES[0];
    },

    extractSqlParams(sql) {
        if (!sql) return [];
        const regex = /\{(\w+)\}/g;
        const params = [];
        let match;
        while ((match = regex.exec(sql)) !== null) {
            if (!params.includes(match[1])) {
                params.push(match[1]);
            }
        }
        return params;
    },

    highlightSql(sql) {
        if (!sql) return '';
        let highlighted = sql
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'JOIN', 'ON', 'AS', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'IF', 'EXISTS', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'LIKE', 'BETWEEN', 'IS', 'NULL', 'DISTINCT', 'COUNT', 'SUM', 'AVG', 'MAX', 'MIN', 'UNION', 'ALL', 'SET', 'VALUES', 'INTO', 'TABLE', 'INDEX', 'VIEW', 'CONCAT', 'IFNULL', 'COALESCE', 'DATE_FORMAT', 'TIMESTAMPDIFF', 'NOW'];
        keywords.forEach(kw => {
            const regex = new RegExp(`\\b(${kw})\\b`, 'gi');
            highlighted = highlighted.replace(regex, '<span style="color:#79c0ff;font-weight:600">$1</span>');
        });
        highlighted = highlighted.replace(/'([^']*)'/g, '<span style="color:#a5d6ff">\'$1\'</span>');
        highlighted = highlighted.replace(/--([^\n]*)/g, '<span style="color:#8b949e">--$1</span>');
        highlighted = highlighted.replace(/\{(\w+)\}/g, '<span style="color:#d2a8ff;font-weight:600">{$1}</span>');
        return highlighted;
    },

    truncate(str, maxLen = 50) {
        if (!str || str.length <= maxLen) return str;
        return str.substring(0, maxLen) + '...';
    },

    copyToClipboard(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text);
        }
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        return Promise.resolve();
    },

    downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
};
