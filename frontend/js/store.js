const EdbStore = Vue.reactive({
    app: {
        sidebarCollapsed: false,
        currentRoute: '/',
        loading: false
    },
    shared: {
        databases: [],
        scripts: [],
        lastFetchTime: {
            databases: null,
            scripts: null
        }
    },
    toasts: [],
    confirmDialog: {
        visible: false,
        title: '',
        message: '',
        type: 'danger',
        onConfirm: null,
        onCancel: null
    }
});

const EdbStoreActions = {
    async fetchDatabases(force = false) {
        const now = Date.now();
        const last = EdbStore.shared.lastFetchTime.databases;
        if (!force && last && now - last < EDB_CONSTANTS.CACHE_TTL && EdbStore.shared.databases.length > 0) {
            return EdbStore.shared.databases;
        }
        try {
            const res = await EdbApi.databases.list();
            EdbStore.shared.databases = res.data || [];
            EdbStore.shared.lastFetchTime.databases = Date.now();
            return EdbStore.shared.databases;
        } catch (e) {
            console.error('Failed to fetch databases:', e);
            return EdbStore.shared.databases;
        }
    },

    async fetchScripts(force = false) {
        const now = Date.now();
        const last = EdbStore.shared.lastFetchTime.scripts;
        if (!force && last && now - last < EDB_CONSTANTS.CACHE_TTL && EdbStore.shared.scripts.length > 0) {
            return EdbStore.shared.scripts;
        }
        try {
            const res = await EdbApi.scripts.list();
            EdbStore.shared.scripts = res.data || [];
            EdbStore.shared.lastFetchTime.scripts = Date.now();
            return EdbStore.shared.scripts;
        } catch (e) {
            console.error('Failed to fetch scripts:', e);
            return EdbStore.shared.scripts;
        }
    },

    addToast(toast) {
        const id = EDBHelpers.generateId();
        EdbStore.toasts.push({ id, ...toast, createdAt: Date.now() });
        const duration = toast.duration || EDB_CONSTANTS.TOAST_DURATION;
        if (duration > 0) {
            setTimeout(() => this.removeToast(id), duration);
        }
        return id;
    },

    removeToast(id) {
        const idx = EdbStore.toasts.findIndex(t => t.id === id);
        if (idx > -1) EdbStore.toasts.splice(idx, 1);
    },

    showConfirm({ title, message, type = 'danger', onConfirm, onCancel }) {
        EdbStore.confirmDialog = {
            visible: true,
            title,
            message,
            type,
            onConfirm: () => {
                EdbStore.confirmDialog.visible = false;
                if (onConfirm) onConfirm();
            },
            onCancel: () => {
                EdbStore.confirmDialog.visible = false;
                if (onCancel) onCancel();
            }
        };
    },

    toastSuccess(message) {
        return this.addToast({ type: 'success', message, icon: 'fas fa-check-circle' });
    },
    toastError(message) {
        return this.addToast({ type: 'error', message, icon: 'fas fa-times-circle', duration: 5000 });
    },
    toastWarning(message) {
        return this.addToast({ type: 'warning', message, icon: 'fas fa-exclamation-triangle' });
    },
    toastInfo(message) {
        return this.addToast({ type: 'info', message, icon: 'fas fa-info-circle' });
    }
};
