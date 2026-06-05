const EDBValidators = {
    required(value, fieldName) {
        if (!value || (typeof value === 'string' && !value.trim())) {
            return { valid: false, message: `${fieldName}不能为空` };
        }
        return { valid: true };
    },

    minLength(value, min, fieldName) {
        if (value && value.length < min) {
            return { valid: false, message: `${fieldName}至少${min}个字符` };
        }
        return { valid: true };
    },

    port(value) {
        const num = parseInt(value);
        if (isNaN(num) || num < 1 || num > 65535) {
            return { valid: false, message: '端口号必须在1-65535之间' };
        }
        return { valid: true };
    },

    host(value) {
        if (!value || !value.trim()) {
            return { valid: false, message: '主机地址不能为空' };
        }
        return { valid: true };
    },

    excelFile(file) {
        if (!file) {
            return { valid: false, message: '请选择文件' };
        }
        const ext = '.' + file.name.split('.').pop().toLowerCase();
        if (!EDB_CONSTANTS.ALLOWED_FILE_TYPES.includes(ext)) {
            return { valid: false, message: `不支持的文件类型，仅支持 ${EDB_CONSTANTS.ALLOWED_FILE_TYPES.join(', ')}` };
        }
        if (file.size > EDB_CONSTANTS.MAX_FILE_SIZE) {
            return { valid: false, message: `文件大小不能超过 ${EDBHelpers.formatFileSize(EDB_CONSTANTS.MAX_FILE_SIZE)}` };
        }
        return { valid: true };
    },

    validateDatabaseForm(form) {
        const errors = {};
        let r;
        r = this.required(form.name, '连接名称');
        if (!r.valid) errors.name = r.message;
        r = this.required(form.type, '数据库类型');
        if (!r.valid) errors.type = r.message;
        r = this.host(form.host);
        if (!r.valid) errors.host = r.message;
        r = this.port(form.port);
        if (!r.valid) errors.port = r.message;
        r = this.required(form.username, '用户名');
        if (!r.valid) errors.username = r.message;
        r = this.required(form.database, '数据库名');
        if (!r.valid) errors.database = r.message;
        if (form.ssh_enabled) {
            r = this.host(form.ssh_host);
            if (!r.valid) errors.ssh_host = r.message;
            r = this.port(form.ssh_port);
            if (!r.valid) errors.ssh_port = r.message;
            r = this.required(form.ssh_username, 'SSH用户名');
            if (!r.valid) errors.ssh_username = r.message;
        }
        return { valid: Object.keys(errors).length === 0, errors };
    },

    validateScriptForm(form) {
        const errors = {};
        let r;
        r = this.required(form.name, '脚本名称');
        if (!r.valid) errors.name = r.message;
        r = this.required(form.content, 'SQL内容');
        if (!r.valid) errors.content = r.message;
        r = this.required(form.database_id, '关联数据库');
        if (!r.valid) errors.database_id = r.message;
        return { valid: Object.keys(errors).length === 0, errors };
    }
};
