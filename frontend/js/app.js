const { createApp, ref, computed, watch, onMounted } = Vue;

const EdbApp = createApp({
    data() {
        return {
            sidebarCollapsed: false,
            currentRoute: '/',
            systemStatus: 'online',
            navItems: [
                { path: '/', label: '仪表盘', icon: 'fas fa-th-large' },
                { path: '/databases', label: '数据库管理', icon: 'fas fa-database' },
                { path: '/scripts', label: '脚本管理', icon: 'fas fa-code' },
                { path: '/query', label: '查询执行', icon: 'fas fa-play-circle' },
                { path: '/history', label: '执行历史', icon: 'fas fa-history' }
            ],
            toasts: EdbStore.toasts,
            confirmDialog: EdbStore.confirmDialog
        };
    },
    computed: {
        currentComponent() {
            const map = {
                '/': 'edb-dashboard',
                '/databases': 'edb-database-manager',
                '/scripts': 'edb-script-manager',
                '/query': 'edb-query-executor',
                '/history': 'edb-result-viewer'
            };
            return map[this.currentRoute] || 'edb-dashboard';
        },
        breadcrumbs() {
            const map = {
                '/': [{ icon: 'fas fa-home', label: '首页' }, { label: '仪表盘' }],
                '/databases': [{ icon: 'fas fa-home', label: '首页' }, { label: '数据库管理' }],
                '/scripts': [{ icon: 'fas fa-home', label: '首页' }, { label: '脚本管理' }],
                '/query': [{ icon: 'fas fa-home', label: '首页' }, { label: '查询执行' }],
                '/history': [{ icon: 'fas fa-home', label: '首页' }, { label: '执行历史' }]
            };
            return map[this.currentRoute] || [{ icon: 'fas fa-home', label: '首页' }];
        },
        systemStatusText() {
            return this.systemStatus === 'online' ? '服务正常' : '服务异常';
        }
    },
    methods: {
        toggleSidebar() {
            this.sidebarCollapsed = !this.sidebarCollapsed;
        },
        navigateTo(path) {
            window.location.hash = path;
        },
        removeToast(id) {
            EdbStoreActions.removeToast(id);
        },
        handleHashChange() {
            const hash = window.location.hash.slice(1) || '/';
            this.currentRoute = hash;
            EdbStore.app.currentRoute = hash;
        }
    },
    mounted() {
        window.addEventListener('hashchange', this.handleHashChange);
        this.handleHashChange();

        EdbApi.databases.list().then(() => {
            this.systemStatus = 'online';
        }).catch(() => {
            this.systemStatus = 'offline';
        });
    },
    beforeUnmount() {
        window.removeEventListener('hashchange', this.handleHashChange);
    }
});

EdbApp.component('edb-toast-container', EdbToastContainer);
EdbApp.component('edb-modal', EdbModal);
EdbApp.component('edb-confirm-dialog', EdbConfirmDialog);
EdbApp.component('edb-dashboard', EdbDashboard);
EdbApp.component('edb-database-manager', EdbDatabaseManager);
EdbApp.component('edb-script-manager', EdbScriptManager);
EdbApp.component('edb-query-executor', EdbQueryExecutor);
EdbApp.component('edb-result-viewer', EdbResultViewer);

EdbApp.mount('#app');
