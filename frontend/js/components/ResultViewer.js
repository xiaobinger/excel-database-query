const EdbResultViewer = {
    name: 'edb-result-viewer',
    template: `
    <div>
        <div class="edb-page-header">
            <div>
                <h1 class="edb-page-header__title">执行历史</h1>
                <p class="edb-page-header__desc">查看所有查询任务的执行记录和详情</p>
            </div>
        </div>

        <div class="edb-card edb-mb-lg">
            <div class="edb-flex edb-flex--between edb-flex--wrap edb-flex--gap" style="margin-bottom:var(--space-lg)">
                <div class="edb-flex edb-flex--gap-sm" style="align-items:center;flex-wrap:wrap">
                    <div class="edb-search" style="min-width:200px">
                        <i class="fas fa-search edb-search__icon"></i>
                        <input type="text" class="edb-form-input edb-search__input" placeholder="搜索任务..."
                               v-model="filters.keyword">
                    </div>
                    <select class="edb-form-select" style="width:auto;min-width:130px" v-model="filters.status">
                        <option value="">全部状态</option>
                        <option value="completed">已完成</option>
                        <option value="failed">失败</option>
                        <option value="running">执行中</option>
                        <option value="cancelled">已取消</option>
                    </select>
                </div>
                <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="refreshList">
                    <i class="fas fa-sync-alt" :class="{ 'fa-spin': loading }"></i> 刷新
                </button>
            </div>

            <div v-if="loading" class="edb-text-center" style="padding:40px">
                <span class="edb-spinner edb-spinner--lg" style="color:var(--color-primary)"></span>
            </div>

            <div v-else-if="filteredTasks.length === 0" class="edb-empty">
                <div class="edb-empty__icon"><i class="fas fa-history"></i></div>
                <div class="edb-empty__title">暂无执行记录</div>
                <div class="edb-empty__desc">执行查询后记录将在此显示</div>
                <button class="edb-btn edb-btn--primary edb-btn--sm" @click="$root.navigateTo('/query')">
                    <i class="fas fa-play"></i> 发起查询
                </button>
            </div>

            <div v-else class="edb-table-wrap">
                <table class="edb-table">
                    <thead>
                        <tr>
                            <th>任务ID</th>
                            <th>执行时间</th>
                            <th>状态</th>
                            <th>Excel 文件</th>
                            <th>脚本数</th>
                            <th>数据行</th>
                            <th>耗时</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="task in filteredTasks" :key="task.id">
                            <td><span class="edb-text-mono" style="font-size:0.78rem;color:var(--color-primary)">{{ task.id?.substring(0, 8) }}</span></td>
                            <td style="font-size:0.82rem">{{ EDBHelpers.formatRelativeTime(task.created_at) }}</td>
                            <td>
                                <span class="edb-badge" :class="getStatusBadge(task.status)">
                                    <i :class="getStatusIcon(task.status)" style="font-size:10px"></i>
                                    {{ getStatusLabel(task.status) }}
                                </span>
                            </td>
                            <td style="font-size:0.82rem">{{ task.excel_filename || '-' }}</td>
                            <td>{{ task.scripts_used?.length || 0 }}</td>
                            <td>
                                <span style="font-size:0.82rem">{{ task.processed_rows || 0 }} / {{ task.total_rows || 0 }}</span>
                            </td>
                            <td style="font-size:0.82rem">{{ EDBHelpers.formatDuration(task.duration_seconds) }}</td>
                            <td>
                                <div class="edb-actions">
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="viewDetail(task)" title="查看详情">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                    <button v-if="task.status === 'completed'" class="edb-btn edb-btn--ghost edb-btn--sm" @click="downloadResult(task)" title="下载">
                                        <i class="fas fa-download"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="reexecute(task)" title="重新执行">
                                        <i class="fas fa-redo"></i>
                                    </button>
                                    <button class="edb-btn edb-btn--ghost edb-btn--sm" style="color:var(--color-error)" @click="confirmDelete(task)" title="删除">
                                        <i class="fas fa-trash-alt"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <div v-if="filteredTasks.length > 0" class="edb-flex edb-flex--between edb-flex--center edb-mt-lg" style="padding-top:var(--space-md);border-top:1px solid var(--border-color)">
                <span style="font-size:0.82rem;color:var(--text-muted)">共 {{ filteredTasks.length }} 条记录</span>
                <div class="edb-flex edb-flex--gap-sm">
                    <button class="edb-btn edb-btn--ghost edb-btn--sm" :disabled="pagination.page <= 1" @click="pagination.page--">
                        <i class="fas fa-chevron-left"></i>
                    </button>
                    <span style="font-size:0.82rem;color:var(--text-secondary);padding:6px 8px">第 {{ pagination.page }} 页</span>
                    <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="pagination.page++">
                        <i class="fas fa-chevron-right"></i>
                    </button>
                </div>
            </div>
        </div>

        <edb-modal title="任务详情" :visible="showDetail" size="xl" :show-footer="false" @close="showDetail = false">
            <div v-if="detailTask">
                <div class="edb-grid-2 edb-mb-lg">
                    <div>
                        <div class="edb-form-label" style="margin-bottom:8px">基本信息</div>
                        <div style="background:rgba(15,23,42,0.5);border-radius:8px;padding:14px;font-size:0.85rem">
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">任务ID</span>
                                <span class="edb-text-mono">{{ detailTask.id }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">状态</span>
                                <span class="edb-badge" :class="getStatusBadge(detailTask.status)">{{ getStatusLabel(detailTask.status) }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">Excel 文件</span>
                                <span>{{ detailTask.excel_filename }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">数据行数</span>
                                <span>{{ detailTask.total_rows }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">成功/失败</span>
                                <span>
                                    <span class="edb-text-success">{{ detailTask.success_rows }}</span> /
                                    <span class="edb-text-error">{{ detailTask.failed_rows }}</span>
                                </span>
                            </div>
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">耗时</span>
                                <span>{{ EDBHelpers.formatDuration(detailTask.duration_seconds) }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between">
                                <span class="edb-text-muted">执行时间</span>
                                <span>{{ EDBHelpers.formatDate(detailTask.created_at) }}</span>
                            </div>
                        </div>
                    </div>
                    <div>
                        <div class="edb-form-label" style="margin-bottom:8px">使用的脚本</div>
                        <div style="background:rgba(15,23,42,0.5);border-radius:8px;padding:14px">
                            <div v-for="s in detailTask.scripts_used" :key="s.id" style="padding:6px 0;border-bottom:1px solid var(--border-color);font-size:0.85rem">
                                <i class="fas fa-file-code" style="color:var(--color-secondary);margin-right:6px"></i>{{ s.name }}
                            </div>
                            <div v-if="!detailTask.scripts_used?.length" class="edb-text-muted" style="font-size:0.82rem">无脚本信息</div>
                        </div>
                        <div class="edb-form-label" style="margin-bottom:8px;margin-top:16px">执行选项</div>
                        <div style="background:rgba(15,23,42,0.5);border-radius:8px;padding:14px;font-size:0.85rem">
                            <div class="edb-flex edb-flex--between" style="margin-bottom:6px">
                                <span class="edb-text-muted">输出模式</span>
                                <span>{{ getOutputModeLabel(detailTask.options?.output_mode) }}</span>
                            </div>
                            <div class="edb-flex edb-flex--between">
                                <span class="edb-text-muted">并发数</span>
                                <span>{{ detailTask.options?.concurrency || '-' }}</span>
                            </div>
                        </div>
                    </div>
                </div>
                <div v-if="detailTask.execution_logs?.length">
                    <div class="edb-form-label" style="margin-bottom:8px">执行日志</div>
                    <div class="edb-log-viewer" style="max-height:250px">
                        <div v-for="(log, i) in detailTask.execution_logs" :key="i" class="edb-log-entry">
                            <span class="edb-log-entry__time">{{ log.timestamp?.split(' ')[1]?.substring(0, 8) || '' }}</span>
                            <span class="edb-log-entry__level" :class="getLogLevelClass(log.level)">{{ log.level }}</span>
                            <span class="edb-log-entry__msg">{{ log.message }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </edb-modal>
    </div>
    `,
    data() {
        return {
            tasks: [],
            loading: false,
            filters: { keyword: '', status: '' },
            pagination: { page: 1, pageSize: 20 },
            showDetail: false,
            detailTask: null
        };
    },
    computed: {
        filteredTasks() {
            let list = this.tasks;
            if (this.filters.status) {
                list = list.filter(t => t.status === this.filters.status);
            }
            if (this.filters.keyword) {
                const q = this.filters.keyword.toLowerCase();
                list = list.filter(t =>
                    t.id?.toLowerCase().includes(q) ||
                    t.excel_filename?.toLowerCase().includes(q)
                );
            }
            return list;
        }
    },
    async mounted() {
        await this.refreshList();
    },
    methods: {
        async refreshList() {
            this.loading = true;
            try {
                const res = await EdbApi.history.list({
                    page: this.pagination.page,
                    page_size: this.pagination.pageSize,
                    status: this.filters.status || undefined,
                    keyword: this.filters.keyword || undefined
                });
                this.tasks = res.data || [];
            } catch (e) {
                this.tasks = this.getMockTasks();
            }
            this.loading = false;
        },
        getMockTasks() {
            return [
                { id: 'task_001', status: 'completed', excel_filename: '商户查询_0528.xlsx', scripts_used: [{ id: 's1', name: '融付商户通-商户信息' }], total_rows: 150, processed_rows: 150, success_rows: 148, failed_rows: 2, duration_seconds: 45.3, options: { output_mode: 'new_sheet', concurrency: 4 }, created_at: new Date(Date.now() - 1800000).toISOString(), execution_logs: [{ timestamp: '2026-05-28 09:30:00', level: 'INFO', message: '开始执行查询' }, { timestamp: '2026-05-28 09:30:45', level: 'INFO', message: '查询完成，成功 148 条，失败 2 条' }] },
                { id: 'task_002', status: 'failed', excel_filename: '终端查询_0527.xlsx', scripts_used: [{ id: 's2', name: '终端交易情况匹配' }], total_rows: 89, processed_rows: 45, success_rows: 43, failed_rows: 2, duration_seconds: 120.5, options: { output_mode: 'new_sheet', concurrency: 4 }, created_at: new Date(Date.now() - 7200000).toISOString(), execution_logs: [{ timestamp: '2026-05-28 08:00:00', level: 'INFO', message: '开始执行查询' }, { timestamp: '2026-05-28 08:02:00', level: 'ERROR', message: '数据库连接超时' }] },
                { id: 'task_003', status: 'completed', excel_filename: '批量查询_0526.xlsx', scripts_used: [{ id: 's3', name: '融聚金宝-商户信息' }, { id: 's4', name: '猛刷电银-商户信息' }], total_rows: 234, processed_rows: 234, success_rows: 234, failed_rows: 0, duration_seconds: 67.8, options: { output_mode: 'new_file', concurrency: 8 }, created_at: new Date(Date.now() - 86400000).toISOString(), execution_logs: [] }
            ];
        },
        async viewDetail(task) {
            try {
                const res = await EdbApi.history.get(task.id);
                this.detailTask = res.data;
            } catch (e) {
                this.detailTask = task;
            }
            this.showDetail = true;
        },
        async downloadResult(task) {
            try {
                const res = await EdbApi.query.download(task.id);
                const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                EDBHelpers.downloadBlob(blob, task.excel_filename || 'result.xlsx');
                EdbStoreActions.toastSuccess('下载成功');
            } catch (e) {
                EdbStoreActions.toastError('下载失败：' + e.message);
            }
        },
        async reexecute(task) {
            try {
                const res = await EdbApi.history.reexecute(task.id);
                EdbStoreActions.toastSuccess('已重新发起查询');
                this.$root.navigateTo('/query');
            } catch (e) {
                EdbStoreActions.toastError(e.message);
            }
        },
        confirmDelete(task) {
            EdbStoreActions.showConfirm({
                title: '删除确认',
                message: `确定要删除任务记录「${task.id?.substring(0, 8)}」吗？`,
                type: 'danger',
                onConfirm: async () => {
                    try {
                        await EdbApi.history.delete(task.id);
                        EdbStoreActions.toastSuccess('删除成功');
                        await this.refreshList();
                    } catch (e) {
                        EdbStoreActions.toastError(e.message);
                    }
                }
            });
        },
        getStatusBadge(status) {
            return EDBHelpers.getStatusConfig(status)?.badge || 'edb-badge--muted';
        },
        getStatusLabel(status) {
            return EDBHelpers.getStatusConfig(status)?.label || '未知';
        },
        getStatusIcon(status) {
            return EDBHelpers.getStatusConfig(status)?.icon || 'fas fa-question';
        },
        getOutputModeLabel(mode) {
            const m = EDB_CONSTANTS.OUTPUT_MODES.find(o => o.value === mode);
            return m ? m.label : mode || '-';
        },
        getLogLevelClass(level) {
            return EDB_CONSTANTS.LOG_LEVELS[level?.toUpperCase()]?.class || 'edb-log-entry__level--info';
        }
    }
};
