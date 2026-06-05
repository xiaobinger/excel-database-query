const EdbDashboard = {
    name: 'edb-dashboard',
    template: `
    <div>
        <div class="edb-page-header">
            <div>
                <h1 class="edb-page-header__title">系统概览</h1>
                <p class="edb-page-header__desc">数据库查询平台运行状态一览</p>
            </div>
        </div>

        <div class="edb-grid-4 edb-mb-xl">
            <div class="edb-stat-card edb-stat-card--primary">
                <div class="edb-stat-card__icon"><i class="fas fa-database"></i></div>
                <div class="edb-stat-card__value">{{ stats.dbCount }}</div>
                <div class="edb-stat-card__label">数据库连接</div>
            </div>
            <div class="edb-stat-card edb-stat-card--secondary">
                <div class="edb-stat-card__icon"><i class="fas fa-code"></i></div>
                <div class="edb-stat-card__value">{{ stats.scriptCount }}</div>
                <div class="edb-stat-card__label">SQL 脚本</div>
            </div>
            <div class="edb-stat-card edb-stat-card--success">
                <div class="edb-stat-card__icon"><i class="fas fa-check-circle"></i></div>
                <div class="edb-stat-card__value">{{ stats.todayTasks }}</div>
                <div class="edb-stat-card__label">今日执行</div>
            </div>
            <div class="edb-stat-card edb-stat-card--warning">
                <div class="edb-stat-card__icon"><i class="fas fa-clock"></i></div>
                <div class="edb-stat-card__value">{{ stats.runningTasks }}</div>
                <div class="edb-stat-card__label">进行中任务</div>
            </div>
        </div>

        <div class="edb-grid-3 edb-mb-xl">
            <a href="#/databases" class="edb-quick-action" @click.prevent="$root.navigateTo('/databases')">
                <div class="edb-quick-action__icon" style="background:rgba(59,130,246,0.12);color:var(--color-primary)">
                    <i class="fas fa-plus-circle"></i>
                </div>
                <div class="edb-quick-action__label">新增连接</div>
                <div class="edb-quick-action__desc">配置数据库连接</div>
            </a>
            <a href="#/scripts" class="edb-quick-action" @click.prevent="$root.navigateTo('/scripts')">
                <div class="edb-quick-action__icon" style="background:rgba(139,92,246,0.12);color:var(--color-secondary)">
                    <i class="fas fa-file-code"></i>
                </div>
                <div class="edb-quick-action__label">新建脚本</div>
                <div class="edb-quick-action__desc">编写 SQL 查询</div>
            </a>
            <a href="#/query" class="edb-quick-action" @click.prevent="$root.navigateTo('/query')">
                <div class="edb-quick-action__icon" style="background:rgba(16,185,129,0.12);color:var(--color-success)">
                    <i class="fas fa-play-circle"></i>
                </div>
                <div class="edb-quick-action__label">发起查询</div>
                <div class="edb-quick-action__desc">上传 Excel 执行</div>
            </a>
        </div>

        <div class="edb-grid-2">
            <div class="edb-card">
                <div class="edb-card__header">
                    <div class="edb-card__title"><i class="fas fa-history"></i> 最近活动</div>
                </div>
                <div v-if="recentActivities.length === 0" class="edb-empty">
                    <div class="edb-empty__icon"><i class="fas fa-inbox"></i></div>
                    <div class="edb-empty__title">暂无活动记录</div>
                    <div class="edb-empty__desc">执行查询后将在此显示</div>
                </div>
                <div v-else class="edb-timeline">
                    <div v-for="activity in recentActivities" :key="activity.id"
                         class="edb-timeline-item"
                         :class="'edb-timeline-item--' + activity.statusClass">
                        <div class="edb-timeline-item__time">{{ activity.timeText }}</div>
                        <div class="edb-timeline-item__content">
                            <span class="edb-badge" :class="activity.badgeClass" style="margin-right:6px">
                                <span class="edb-badge__dot"></span>{{ activity.statusText }}
                            </span>
                            {{ activity.description }}
                        </div>
                    </div>
                </div>
            </div>

            <div class="edb-card">
                <div class="edb-card__header">
                    <div class="edb-card__title"><i class="fas fa-server"></i> 数据库连接状态</div>
                </div>
                <div v-if="dbList.length === 0" class="edb-empty">
                    <div class="edb-empty__icon"><i class="fas fa-plug"></i></div>
                    <div class="edb-empty__title">尚未配置数据库</div>
                    <div class="edb-empty__desc">添加数据库连接以开始使用</div>
                    <button class="edb-btn edb-btn--primary edb-btn--sm" @click="$root.navigateTo('/databases')">
                        <i class="fas fa-plus"></i> 添加连接
                    </button>
                </div>
                <div v-else>
                    <div v-for="db in dbList.slice(0, 6)" :key="db.id"
                         class="edb-flex edb-flex--between" style="padding:10px 0;border-bottom:1px solid var(--border-color)">
                        <div class="edb-flex edb-flex--gap-sm" style="align-items:center">
                            <i :class="getDbTypeIcon(db.type)" :style="{ color: getDbTypeColor(db.type) }"></i>
                            <div>
                                <div style="font-weight:600;font-size:0.85rem;color:var(--text-primary)">{{ db.name }}</div>
                                <div style="font-size:0.72rem;color:var(--text-muted)">{{ db.host }}:{{ db.port }}</div>
                            </div>
                        </div>
                        <span class="edb-badge" :class="db.status === 'connected' ? 'edb-badge--success' : db.status === 'error' ? 'edb-badge--error' : 'edb-badge--muted'">
                            <span class="edb-badge__dot"></span>
                            {{ db.status === 'connected' ? '已连接' : db.status === 'error' ? '异常' : '未连接' }}
                        </span>
                    </div>
                </div>
            </div>
        </div>
    </div>
    `,
    data() {
        return {
            stats: { dbCount: 0, scriptCount: 0, todayTasks: 0, runningTasks: 0 },
            recentActivities: [],
            dbList: [],
            loading: false
        };
    },
    async mounted() {
        this.loading = true;
        try {
            const [dbs, scripts] = await Promise.all([
                EdbStoreActions.fetchDatabases(),
                EdbStoreActions.fetchScripts()
            ]);
            this.dbList = dbs;
            this.stats.dbCount = dbs.length;
            this.stats.scriptCount = scripts.length;
            this.loadMockData();
        } catch (e) {
            this.loadMockData();
        }
        this.loading = false;
    },
    methods: {
        loadMockData() {
            this.recentActivities = [
                { id: '1', statusClass: 'success', timeText: EDBHelpers.formatRelativeTime(new Date(Date.now() - 300000).toISOString()), statusText: '完成', badgeClass: 'edb-badge--success', description: '查询融付商户通商户信息 - 150条记录' },
                { id: '2', statusClass: 'running', timeText: EDBHelpers.formatRelativeTime(new Date(Date.now() - 600000).toISOString()), statusText: '执行中', badgeClass: 'edb-badge--info', description: '终端交易情况匹配 - 进度 67%' },
                { id: '3', statusClass: 'error', timeText: EDBHelpers.formatRelativeTime(new Date(Date.now() - 1800000).toISOString()), statusText: '失败', badgeClass: 'edb-badge--error', description: '融聚金宝商户信息查询 - 连接超时' },
                { id: '4', statusClass: 'success', timeText: EDBHelpers.formatRelativeTime(new Date(Date.now() - 3600000).toISOString()), statusText: '完成', badgeClass: 'edb-badge--success', description: '乐商通商户信息 - 89条记录' },
                { id: '5', statusClass: 'success', timeText: EDBHelpers.formatRelativeTime(new Date(Date.now() - 7200000).toISOString()), statusText: '完成', badgeClass: 'edb-badge--success', description: '猛刷电银商户信息 - 234条记录' }
            ];
            this.stats.todayTasks = 12;
            this.stats.runningTasks = 1;
        },
        getDbTypeIcon(type) {
            return EDBHelpers.getDbTypeConfig(type)?.icon || 'fas fa-database';
        },
        getDbTypeColor(type) {
            return EDBHelpers.getDbTypeConfig(type)?.color || '#94a3b8';
        }
    }
};
