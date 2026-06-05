const EdbScriptManager = {
    name: 'edb-script-manager',
    template: `
    <div>
        <div class="edb-page-header">
            <div>
                <h1 class="edb-page-header__title">SQL 脚本管理</h1>
                <p class="edb-page-header__desc">创建和管理查询脚本，支持参数化查询</p>
            </div>
            <button class="edb-btn edb-btn--primary" @click="openCreateModal">
                <i class="fas fa-plus"></i> 新建脚本
            </button>
        </div>

        <div class="edb-card edb-mb-lg">
            <div class="edb-flex edb-flex--between edb-flex--gap" style="margin-bottom:var(--space-lg)">
                <div class="edb-search" style="flex:1;max-width:320px">
                    <i class="fas fa-search edb-search__icon"></i>
                    <input type="text" class="edb-form-input edb-search__input" placeholder="搜索脚本名称..."
                           v-model="searchQuery">
                </div>
                <div class="edb-flex edb-flex--gap-sm">
                    <select class="edb-form-select" style="width:auto;min-width:160px" v-model="filterDbId">
                        <option value="">全部数据库</option>
                        <option v-for="db in databases" :key="db.id" :value="db.id">{{ db.name }}</option>
                    </select>
                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="refreshList">
                        <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i>
                    </button>
                </div>
            </div>

            <div v-if="loading" class="edb-text-center" style="padding:40px">
                <span class="edb-spinner edb-spinner--lg" style="color:var(--color-primary)"></span>
            </div>

            <div v-else-if="filteredScripts.length === 0" class="edb-empty">
                <div class="edb-empty__icon"><i class="fas fa-file-code"></i></div>
                <div class="edb-empty__title">{{ searchQuery ? '未找到匹配的脚本' : '尚未创建脚本' }}</div>
                <div class="edb-empty__desc">创建SQL脚本以开始批量查询</div>
                <button v-if="!searchQuery" class="edb-btn edb-btn--primary edb-btn--sm" @click="openCreateModal">
                    <i class="fas fa-plus"></i> 新建脚本
                </button>
            </div>

            <div v-else class="edb-table-wrap">
                <table class="edb-table">
                    <thead>
                        <tr>
                            <th>脚本名称</th>
                            <th>关联数据库</th>
                            <th>参数</th>
                            <th>验证状态</th>
                            <th>更新时间</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="script in filteredScripts" :key="script.id">
                            <td>
                                <div style="font-weight:600">{{ script.name }}</div>
                                <div style="font-size:0.72rem;color:var(--text-muted);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">
                                    {{ script.description || EDBHelpers.truncate(script.content, 60) }}
                                </div>
                            </td>
                            <td>
                                <span class="edb-flex edb-flex--gap-sm" style="align-items:center">
                                    <i :class="getDbIcon(script.database_id)" :style="{ color: getDbColor(script.database_id) }"></i>
                                    {{ script.database_name || getDbName(script.database_id) }}
                                </span>
                            </td>
                            <td>
                                <template v-if="script.parameters && script.parameters.length">
                                    <span v-for="p in script.parameters.slice(0, 3)" :key="p" class="edb-param-tag" style="margin:2px">
                                        {{ '{' + p + '}' }}
                                    </span>
                                    <span v-if="script.parameters.length > 3" class="edb-text-muted" style="font-size:0.72rem">
                                        +{{ script.parameters.length - 3 }}
                                    </span>
                                </template>
                                <span v-else class="edb-text-muted" style="font-size:0.78rem">无参数</span>
                            </td>
                            <td>
                                <span class="edb-badge" :class="script.is_valid ? 'edb-badge--success' : 'edb-badge--error'">
                                    <i class="fas" :class="script.is_valid ? 'fa-check' : 'fa-times'"></i>
                                    {{ script.is_valid ? '已验证' : '未通过' }}
                                </span>
                            </td>
                            <td style="font-size:0.82rem;color:var(--text-muted)">{{ EDBHelpers.formatRelativeTime(script.updated_at) }}</td>
                            <td>
                                <div class="edb-actions">
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="openEditModal(script)" title="编辑">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="validateScript(script)" title="验证"
                                            :disabled="validatingId === script.id">
                                        <i class="fas" :class="validatingId === script.id ? 'fa-spinner fa-spin' : 'fa-check-double'"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" style="color:var(--color-error)" @click="confirmDelete(script)" title="删除">
                                        <i class="fas fa-trash-alt"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

        <edb-modal :title="modalTitle" :visible="showModal" :loading="saving" size="xl"
                   @close="closeModal" @confirm="saveForm">
            <div class="edb-grid-2">
                <div class="edb-form-group">
                    <label class="edb-form-label">脚本名称 <span class="edb-required">*</span></label>
                    <input type="text" class="edb-form-input" :class="{ 'edb-form-input--error': formErrors.name }"
                           v-model="form.name" placeholder="如：商户信息查询">
                    <div v-if="formErrors.name" class="edb-form-error">{{ formErrors.name }}</div>
                </div>
                <div class="edb-form-group">
                    <label class="edb-form-label">关联数据库 <span class="edb-required">*</span></label>
                    <select class="edb-form-select" :class="{ 'edb-form-input--error': formErrors.database_id }" v-model="form.database_id">
                        <option value="">请选择数据库</option>
                        <option v-for="db in databases" :key="db.id" :value="db.id">{{ db.name }} ({{ db.type }})</option>
                    </select>
                    <div v-if="formErrors.database_id" class="edb-form-error">{{ formErrors.database_id }}</div>
                </div>
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">描述</label>
                <input type="text" class="edb-form-input" v-model="form.description" placeholder="脚本用途说明">
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">SQL 内容 <span class="edb-required">*</span></label>
                <div class="edb-code-editor">
                    <div class="edb-code-editor__header">
                        <span class="edb-code-editor__title">SQL Editor</span>
                        <div class="edb-flex edb-flex--gap-sm">
                            <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="formatSql" title="格式化">
                                <i class="fas fa-magic"></i>
                            </button>
                            <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="validateFormScript" :disabled="validatingForm" title="验证SQL">
                                <i class="fas" :class="validatingForm ? 'fa-spinner fa-spin' : 'fa-check-double'"></i> 验证
                            </button>
                        </div>
                    </div>
                    <div class="edb-code-editor__body">
                        <textarea v-model="form.content" @input="onSqlInput" placeholder="输入 SQL 查询语句...&#10;&#10;使用 {参数名} 作为参数占位符&#10;例如: SELECT * FROM users WHERE id IN :value"
                                  spellcheck="false"></textarea>
                    </div>
                    <div class="edb-code-editor__footer">
                        <span>参数占位符使用 <code style="color:var(--color-secondary)">{参数名}</code> 格式</span>
                        <span>{{ form.content?.length || 0 }} 字符</span>
                    </div>
                </div>
                <div v-if="formErrors.content" class="edb-form-error">{{ formErrors.content }}</div>
            </div>
            <div v-if="detectedParams.length" class="edb-form-group">
                <label class="edb-form-label">检测到的参数</label>
                <div class="edb-flex edb-flex--wrap" style="gap:6px">
                    <span v-for="p in detectedParams" :key="p" class="edb-param-tag">
                        <i class="fas fa-tag" style="font-size:10px"></i> {{ p }}
                    </span>
                </div>
            </div>
            <div v-if="validationResult" class="edb-form-group">
                <div class="edb-flex edb-flex--gap-sm" style="align-items:flex-start;padding:12px;border-radius:8px"
                     :style="{ background: validationResult.is_valid ? 'rgba(16,185,129,0.08)' : 'rgba(239,68,68,0.08)', border: '1px solid ' + (validationResult.is_valid ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)') }">
                    <i class="fas" :class="validationResult.is_valid ? 'fa-check-circle edb-text-success' : 'fa-times-circle edb-text-error'" style="margin-top:2px"></i>
                    <div>
                        <div :class="validationResult.is_valid ? 'edb-text-success' : 'edb-text-error'" style="font-weight:600;font-size:0.85rem">
                            {{ validationResult.is_valid ? 'SQL 验证通过' : 'SQL 验证失败' }}
                        </div>
                        <div v-if="validationResult.errors?.length" style="margin-top:4px">
                            <div v-for="(err, i) in validationResult.errors" :key="i" style="font-size:0.78rem;color:var(--color-error)">
                                行 {{ err.line }}: {{ err.message }}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </edb-modal>
    </div>
    `,
    data() {
        return {
            scripts: [],
            databases: [],
            loading: false,
            searchQuery: '',
            filterDbId: '',
            showModal: false,
            editingId: null,
            saving: false,
            validatingId: null,
            validatingForm: false,
            validationResult: null,
            formErrors: {},
            form: { name: '', description: '', content: '', database_id: '' },
            detectedParams: []
        };
    },
    computed: {
        modalTitle() { return this.editingId ? '编辑脚本' : '新建脚本'; },
        filteredScripts() {
            let list = this.scripts;
            if (this.searchQuery) {
                const q = this.searchQuery.toLowerCase();
                list = list.filter(s => s.name.toLowerCase().includes(q) || (s.description || '').toLowerCase().includes(q));
            }
            if (this.filterDbId) {
                list = list.filter(s => s.database_id === this.filterDbId);
            }
            return list;
        }
    },
    async mounted() {
        this.databases = await EdbStoreActions.fetchDatabases();
        await this.refreshList();
    },
    methods: {
        async refreshList() {
            this.loading = true;
            try {
                this.scripts = await EdbStoreActions.fetchScripts(true);
            } catch (e) {
                EdbStoreActions.toastError('加载脚本列表失败');
            }
            this.loading = false;
        },
        openCreateModal() {
            this.editingId = null;
            this.form = { name: '', description: '', content: '', database_id: '' };
            this.formErrors = {};
            this.validationResult = null;
            this.detectedParams = [];
            this.showModal = true;
        },
        openEditModal(script) {
            this.editingId = script.id;
            this.form = {
                name: script.name,
                description: script.description || '',
                content: script.content,
                database_id: script.database_id
            };
            this.formErrors = {};
            this.validationResult = null;
            this.detectedParams = script.parameters || EDBHelpers.extractSqlParams(script.content);
            this.showModal = true;
        },
        closeModal() { this.showModal = false; },
        onSqlInput() {
            this.detectedParams = EDBHelpers.extractSqlParams(this.form.content);
        },
        formatSql() {
            let sql = this.form.content;
            sql = sql.replace(/\b(SELECT|FROM|WHERE|AND|OR|LEFT|RIGHT|INNER|JOIN|ON|GROUP BY|ORDER BY|HAVING|LIMIT|IN|AS|SET|VALUES|INSERT INTO|UPDATE|DELETE FROM|CREATE|ALTER|DROP|CASE|WHEN|THEN|ELSE|END)\b/gi, '\n$1');
            sql = sql.replace(/\n{3,}/g, '\n\n').trim();
            this.form.content = sql;
        },
        async validateFormScript() {
            if (!this.form.content || !this.form.database_id) {
                EdbStoreActions.toastWarning('请先填写SQL内容和关联数据库');
                return;
            }
            this.validatingForm = true;
            try {
                const res = await EdbApi.scripts.validate({ content: this.form.content, database_id: this.form.database_id });
                this.validationResult = res.data;
                if (res.data.is_valid) {
                    EdbStoreActions.toastSuccess('SQL 验证通过');
                } else {
                    EdbStoreActions.toastError('SQL 验证未通过');
                }
            } catch (e) {
                EdbStoreActions.toastError(e.message);
            }
            this.validatingForm = false;
        },
        async validateScript(script) {
            this.validatingId = script.id;
            try {
                const res = await EdbApi.scripts.validate({ content: script.content, database_id: script.database_id });
                script.is_valid = res.data?.is_valid || false;
                if (res.data?.is_valid) {
                    EdbStoreActions.toastSuccess('脚本验证通过');
                } else {
                    EdbStoreActions.toastError('脚本验证未通过');
                }
            } catch (e) {
                EdbStoreActions.toastError(e.message);
            }
            this.validatingId = null;
        },
        async saveForm() {
            const validation = EDBValidators.validateScriptForm(this.form);
            if (!validation.valid) {
                this.formErrors = validation.errors;
                return;
            }
            this.formErrors = {};
            this.saving = true;
            try {
                const payload = { ...this.form };
                if (this.editingId) {
                    await EdbApi.scripts.update(this.editingId, payload);
                    EdbStoreActions.toastSuccess('脚本更新成功');
                } else {
                    await EdbApi.scripts.create(payload);
                    EdbStoreActions.toastSuccess('脚本创建成功');
                }
                this.showModal = false;
                await this.refreshList();
            } catch (e) {
                EdbStoreActions.toastError(e.message || '保存失败');
            }
            this.saving = false;
        },
        confirmDelete(script) {
            EdbStoreActions.showConfirm({
                title: '删除确认',
                message: `确定要删除脚本「${script.name}」吗？此操作不可恢复。`,
                type: 'danger',
                onConfirm: () => this.deleteScript(script.id)
            });
        },
        async deleteScript(id) {
            try {
                await EdbApi.scripts.delete(id);
                EdbStoreActions.toastSuccess('删除成功');
                await this.refreshList();
            } catch (e) {
                EdbStoreActions.toastError(e.message);
            }
        },
        getDbName(dbId) {
            const db = this.databases.find(d => d.id === dbId);
            return db ? db.name : '未知';
        },
        getDbIcon(dbId) {
            const db = this.databases.find(d => d.id === dbId);
            return db ? EDBHelpers.getDbTypeIcon(db.type) : 'fas fa-database';
        },
        getDbColor(dbId) {
            const db = this.databases.find(d => d.id === dbId);
            return db ? EDBHelpers.getDbTypeColor(db.type) : '#94a3b8';
        }
    }
};
