const EdbApi = (function () {
    const client = axios.create({
        baseURL: EDB_CONSTANTS.API_BASE,
        timeout: 30000,
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' }
    });

    client.interceptors.request.use(config => {
        const token = localStorage.getItem('auth_token');
        if (token) config.headers.Authorization = `Bearer ${token}`;
        return config;
    });

    client.interceptors.response.use(
        response => response.data,
        error => {
            const msg = error.response?.data?.message || error.response?.data?.error || error.message || '请求失败';
            console.error('[API Error]', error.response?.status, msg);
            return Promise.reject(new Error(msg));
        }
    );

    return {
        databases: {
            list() { return client.get('/databases'); },
            get(id) { return client.get(`/databases/${id}`); },
            create(data) { return client.post('/databases', data); },
            update(id, data) { return client.put(`/databases/${id}`, data); },
            delete(id) { return client.delete(`/databases/${id}`); },
            test(id) { return client.post(`/databases/${id}/test`); }
        },
        scripts: {
            list(params) { return client.get('/scripts', { params }); },
            get(id) { return client.get(`/scripts/${id}`); },
            create(data) { return client.post('/scripts', data); },
            update(id, data) { return client.put(`/scripts/${id}`, data); },
            delete(id) { return client.delete(`/scripts/${id}`); },
            validate(data) { return client.post('/scripts/validate', data); }
        },
        query: {
            upload(file, onProgress) {
                const formData = new FormData();
                formData.append('file', file);
                return client.post('/upload', formData, {
                    headers: { 'Content-Type': 'multipart/form-data' },
                    onUploadProgress: onProgress
                });
            },
            execute(data) { return client.post('/query/execute', data); },
            status(taskId) { return client.get(`/query/tasks/${taskId}/status`); },
            cancel(taskId) { return client.post(`/query/tasks/${taskId}/cancel`); },
            download(taskId) {
                return client.get(`/query/tasks/${taskId}/download`, { responseType: 'blob' });
            }
        },
        history: {
            list(params) { return client.get('/history', { params }); },
            get(id) { return client.get(`/history/${id}`); },
            reexecute(id) { return client.post(`/history/${id}/reexecute`); },
            delete(id) { return client.delete(`/history/${id}`); }
        },
        dashboard: {
            stats() { return client.get('/dashboard/stats'); },
            recentActivities(limit = 10) { return client.get('/dashboard/activities', { params: { limit } }); }
        }
    };
})();
