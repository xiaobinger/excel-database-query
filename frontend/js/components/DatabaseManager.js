const EdbDatabaseManager = {
    name: 'edb-database-manager',
    template: `
    <div>
        <div class="edb-page-header">
            <div>
                <h1 class="edb-page-header__title">数据库连接管理</h1>
                <p class="edb-page-header__desc">配置和管理数据库连接，支持SSH隧道</p>
            </div>
            <button class="edb-btn edb-btn--primary" @click="openCreateModal">
                <i class="fas fa-plus"></i> 新增连接
            </button>
        </div>

        <div class="edb-card edb-mb-lg">
            <div class="edb-flex edb-flex--between edb-flex--gap" style="margin-bottom:var(--space-lg)">
                <div class="edb-search" style="flex:1;max-width:320px">
                    <i class="fas fa-search edb-search__icon"></i>
                    <input type="text" class="edb-form-input edb-search__input" placeholder="搜索连接名称或主机..."
                           v-model="searchQuery" @input="handleSearch">
                </div>
                <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="refreshList">
                    <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i> 刷新
                </button>
            </div>

            <div v-if="loading" class="edb-text-center" style="padding:40px">
                <span class="edb-spinner edb-spinner--lg" style="color:var(--color-primary)"></span>
                <div class="edb-text-muted edb-mt-md" style="font-size:0.85rem">加载中...</div>
            </div>

            <div v-else-if="filteredDatabases.length === 0" class="edb-empty">
                <div class="edb-empty__icon"><i class="fas fa-database"></i></div>
                <div class="edb-empty__title">{{ searchQuery ? '未找到匹配的连接' : '尚未配置数据库连接' }}</div>
                <div class="edb-empty__desc">{{ searchQuery ? '尝试其他关键词' : '点击上方按钮添加第一个数据库连接' }}</div>
                <button v-if="!searchQuery" class="edb-btn edb-btn--primary edb-btn--sm" @click="openCreateModal">
                    <i class="fas fa-plus"></i> 添加连接
                </button>
            </div>

            <div v-else class="edb-table-wrap">
                <table class="edb-table">
                    <thead>
                        <tr>
                            <th>名称</th>
                            <th>类型</th>
                            <th>主机</th>
                            <th>数据库</th>
                            <th>SSH隧道</th>
                            <th>状态</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="db in filteredDatabases" :key="db.id">
                            <td>
                                <div style="font-weight:600">{{ db.name }}</div>
                                <div style="font-size:0.72rem;color:var(--text-muted)">{{ db.description || '-' }}</div>
                            </td>
                            <td>
                                <span class="edb-flex edb-flex--gap-sm" style="align-items:center">
                                    <i :class="getDbTypeIcon(db.type)" :style="{ color: getDbTypeColor(db.type) }"></i>
                                    {{ getDbTypeLabel(db.type) }}
                                </span>
                            </td>
                            <td><span class="edb-text-mono" style="font-size:0.82rem">{{ db.host }}:{{ db.port }}</span></td>
                            <td>{{ db.database }}</td>
                            <td>
                                <span v-if="db.ssh_config && db.ssh_config.enabled" class="edb-badge edb-badge--info">
                                    <i class="fas fa-shield-alt"></i> 已启用
                                </span>
                                <span v-else class="edb-badge edb-badge--muted">未启用</span>
                            </td>
                            <td>
                                <span class="edb-badge" :class="getStatusBadge(db.status)">
                                    <span class="edb-badge__dot"></span>
                                    {{ getStatusText(db.status) }}
                                </span>
                            </td>
                            <td>
                                <div class="edb-actions">
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="testConnection(db)"
                                            :disabled="testingId === db.id" title="测试连接">
                                        <i class="fas" :class="testingId === db.id ? 'fa-spinner fa-spin' : 'fa-plug'"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="openEditModal(db)" title="编辑">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" style="color:var(--color-error)" @click="confirmDelete(db)" title="删除">
                                        <i class="fas fa-trash-alt"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <edb-modal :title="modalTitle" :visible="showModal" :loading="saving" size="lg"
                   @close="closeModal" @confirm="saveForm">
            <div class="edb-grid-2">
                <div class="edb-form-group">
                    <label class="edb-form-label">连接名称 <span class="edb-required">*</span></label>
                    <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.name }"
                           v-model="form.name" placeholder="如：生产环境MySQL">
                    <div v-if="formErrors.name" class="edb-form-error">{{ formErrors.name }}</div>
                </div>
                <div class="edb-form-group">
                    <label class="edb-form-label">数据库类型 <span class="edb-required">*</span></label>
                    <select class="edb-form-select" :class="{ 'edb-form-input--error': formErrors.type }" v-model="form.type">
                        <option value="">请选择</option>
                        <option v-for="t in dbTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
                    </select>
                    <div v-if="formErrors.type" class="edb-form-error">{{ formErrors.type }}</div>
                </div>
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">描述</label>
                <input type="text" class="edb-form-input" v-model="form.description" placeholder="连接用途描述">
            </div>
            <div class="edb-grid-2">
                <div class="edb-form-group">
                    <label class="edb-form-label">主机地址 <span class="edb-required">*</span></label>
                    <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.host }"
                           v-model="form.host" placeholder="如：localhost 或 192.168.1.100">
                    <div v-if="formErrors.host" class="edb-form-error">{{ formErrors.host }}</div>
                </div>
                <div class="edb-form-group">
                    <label class="edb-form-label">端口 <span class="edb-required">*</span></label>
                    <input type="number" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.port }"
                           v-model="form.port" placeholder="3306">
                    <div v-if="formErrors.port" class="edb-form-error">{{ formErrors.port }}</div>
                </div>
            </div>
            <div class="edb-grid-2">
                <div class="edb-form-group">
                    <label class="edb-form-label">用户名 <span class="edb-required">*</span></label>
                    <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.username }"
                           v-model="form.username" placeholder="数据库用户名">
                    <div v-if="formErrors.username" class="edb-form-error">{{ formErrors.username }}</div>
                </div>
                <div class="edb-form-group">
                    <label class="edb-form-label">密码</label>
                    <div class="edb-flex" style="gap:4px">
                        <input :type="showPassword ? 'text' : 'password'" class="edb-form-input" v-model="form.password" placeholder="数据库密码" style="flex:1">
                        <button class="edb-btn edb-btn--ghost edb-btn--icon" @click="showPassword = !showPassword" type="button">
                            <i class="fas" :class="showPassword ? 'fa-eye-slash' : 'fa-eye'"></i>
                        </button>
                    </div>
                </div>
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">数据库名 <span class="edb-required">*</span></label>
                <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.database }"
                       v-model="form.database" placeholder="如：posp_business">
                <div v-if="formErrors.database" class="edb-form-error">{{ formErrors.database }}</div>
            </div>

            <div class="edb-ssh-config">
                <div class="edb-ssh-config__header" @click="form.ssh_enabled = !form.ssh_enabled">
                    <div class="edb-ssh-config__title">
                        <i class="fas fa-shield-alt"></i> SSH 隧道配置
                        <span class="edb-badge" :class="form.ssh_enabled ? 'edb-badge--success' : 'edb-badge--muted'" style="margin-left:8px">
                            {{ form.ssh_enabled ? '已启用' : '未启用' }}
                        </span>
                    </div>
                    <i class="fas" :class="form.ssh_enabled ? 'fa-chevron-up' : 'fa-chevron-down'" style="color:var(--text-muted);font-size:12px"></i>
                </div>
                <div v-if="form.ssh_enabled" class="edb-ssh-config__body">
                    <div class="edb-grid-2">
                        <div class="edb-form-group">
                            <label class="edb-form-label">SSH 主机 <span class="edb-required">*</span></label>
                            <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.ssh_host }"
                                   v-model="form.ssh_host" placeholder="跳板机地址">
                            <div v-if="formErrors.ssh_host" class="edb-form-error">{{ formErrors.ssh_host }}</div>
                        </div>
                        <div class="edb-form-group">
                            <label class="edb-form-label">SSH 端口 <span class="edb-required">*</span></label>
                            <input type="number" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.ssh_port }"
                                   v-model="form.ssh_port" placeholder="22">
                            <div v-if="formErrors.ssh_port" class="edb-form-error">{{ formErrors.ssh_port }}</div>
                        </div>
                    </div>
                    <div class="edb-grid-2">
                        <div class="edb-form-group">
                            <label class="edb-form-label">SSH 用户名 <span class="edb-required">*</span></label>
                            <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.ssh_username }"
                                   v-model="form.ssh_username" placeholder="SSH登录用户名">
                            <div v-if="formErrors.ssh_username" class="edb-form-error">{{ formErrors.ssh_username }}</div>
                        </div>
                        <div class="edb-form-group">
                            <label class="edb-form-label">SSH 密码</label>
                            <input type="password" class="edb-form-input" v-model="form.ssh_password" placeholder="SSH登录密码">
                        </div>
                    </div>
                    <div class="edb-form-group">
                        <label class="edb-form-label">本地绑定端口</label>
                        <input type="number" class="edb-form-input" v-model="form.ssh_local_bind_port" placeholder="3307">
                    </div>
                </div>
            </div>
        </edb-modal>
    </div>
    `,
    data() {
        return {
            databases: [],
            loading: false,
            searchQuery: '',
            showModal: false,
            editingId: null,
            saving: false,
            testingId: null,
            showPassword: false,
            formErrors: {},
            form: this.getEmptyForm(),
            dbTypes: EDB_CONSTANTS.DB_TYPES
        };
    },
    computed: {
        modalTitle() { return this.editingId ? '编辑数据库连接' : '新增数据库连接'; },
        filteredDatabases() {
            if (!this.searchQuery) return this.databases;
            const q = this.searchQuery.toLowerCase();
            return this.databases.filter(db =>
                db.name.toLowerCase().includes(q) ||
                db.host.toLowerCase().includes(q) ||
                (db.description || '').toLowerCase().includes(q)
            );
        }
    },
    async mounted() {
        await this.refreshList();
    },
    methods: {
        getEmptyForm() {
            return {
                name: '', type: 'mysql', description: '', host: '', port: 3306,
                username: '', password: '', database: '',
                ssh_enabled: false, ssh_host: '', ssh_port: 22,
                ssh_username: '', ssh_password: '', ssh_local_bind_port: 3307
            };
        },
        async refreshList() {
            this.loading = true;
            try {
                this.databases = await EdbStoreActions.fetchDatabases(true);
            } catch (e) {
                EdbStoreActions.toastError('加载数据库列表失败');
            }
            this.loading = false;
        },
        handleSearch: EDBHelpers.debounce(function () { }, 200),
        openCreateModal() {
            this.editingId = null;
            this.form = this.getEmptyForm();
            this.formErrors = {};
            this.showPassword = false;
            this.showModal = true;
        },
        openEditModal(db) {
            this.editingId = db.id;
            this.form = {
                name: db.name, type: db.type, description: db.description || '',
                host: db.host, port: db.port, username: db.username,
                password: '', database: db.database,
                ssh_enabled: db.ssh_config?.enabled || false,
                ssh_host: db.ssh_config?.ssh_host || '',
                ssh_port: db.ssh_config?.ssh_port || 22,
                ssh_username: db.ssh_config?.ssh_username || '',
                ssh_password: '', ssh_local_bind_port: db.ssh_config?.local_bind_port || 3307
            };
            this.formErrors = {};
            this.showPassword = false;
            this.showModal = true;
        },
        closeModal() { this.showModal = false; },
        async saveForm() {
            const validation = EDBValidators.validateDatabaseForm(this.form);
            if (!validation.valid) {
                this.formErrors = validation.errors;
                return;
            }
            this.formErrors = {};
            this.saving = true;
            try {
                const payload = { ...this.form };
                if (payload.ssh_enabled) {
                    payload.ssh_config = {
                        enabled: true,
                        ssh_host: payload.ssh_host,
                        ssh_port: parseInt(payload.ssh_port),
                        ssh_username: payload.ssh_username,
                        ssh_password: payload.ssh_password || undefined,
                        local_bind_port: parseInt(payload.ssh_local_bind_port) || 3307
                    };
                }
                delete payload.ssh_host; delete payload.ssh_port;
                delete payload.ssh_username; delete payload.ssh_password;
                delete payload.ssh_local_bind_port;

                if (this.editingId) {
                    await EdbApi.databases.update(this.editingId, payload);
                    EdbStoreActions.toastSuccess('连接更新成功');
                } else {
                    await EdbApi.databases.create(payload);
                    EdbStoreActions.toastSuccess('连接创建成功');
                }
                this.showModal = false;
                await this.refreshList();
            } catch (e) {
                EdbStoreActions.toastError(e.message || '保存失败');
            }
            this.saving = false;
        },
        async testConnection(db) {
            this.testingId = db.id;
            try {
                const res = await EdbApi.databases.test(db.id);
                if (res.data?.success) {
                    EdbStoreActions.toastSuccess(`连接成功！延迟 ${res.data.latency_ms}ms`);
                    db.status = 'connected';
                } else {
                    EdbStoreActions.toastError(`连接失败：${res.data?.message || '未知错误'}`);
                    db.status = 'error';
                }
            } catch (e) {
                EdbStoreActions.toastError(`测试失败：${e.message}`);
                db.status = 'error';
            }
            this.testingId = null;
        },
        confirmDelete(db) {
            EdbStoreActions.showConfirm({
                title: '删除确认',
                message: `确定要删除数据库连接「${db.name}」吗？此操作不可恢复。`,
                type: 'danger',
                onConfirm: () => this.deleteDatabase(db.id)
            });
        },
        async deleteDatabase(id) {
            try {
                await EdbApi.databases.delete(id);
                EdbStoreActions.toastSuccess('删除成功');
                await this.refreshList();
            } catch (e) {
                EdbStoreActions.toastError(e.message || '删除失败');
            }
        },
        getDbTypeIcon(type) { return EDBHelpers.getDbTypeConfig(type)?.icon || 'fas fa-database'; },
        getDbTypeColor(type) { return EDBHelpers.getDbTypeConfig(type)?.color || '#94a3b8'; },
        getDbTypeLabel(type) { return EDBHelpers.getDbTypeConfig(type)?.label || type; },
        getStatusBadge(status) {
            const map = { connected: 'edb-badge--success', error: 'edb-badge--error', disconnected: 'edb-badge--muted' };
            return map[status] || 'edb-badge--muted';
        },
        getStatusText(status) {
            const map = { connected: '已连接', error: '异常', disconnected: '未连接' };
            return map[status] || '未知';
        }
    }
};
