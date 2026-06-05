const EdbQueryExecutor = {
    name: 'edb-query-executor',
    template: `
    <div>
        <div class="edb-page-header">
            <div>
                <h1 class="edb-page-header__title">查询执行</h1>
                <p class="edb-page-header__desc">上传 Excel 文件，选择脚本，执行批量查询</p>
            </div>
        </div>

        <div class="edb-step-wizard">
            <div class="edb-step" :class="{ 'edb-step--active': currentStep === 1, 'edb-step--done': currentStep > 1 }">
                <div class="edb-step__number">{{ currentStep > 1 ? '✓' : '1' }}</div>
                <div class="edb-step__label">上传文件</div>
            </div>
            <div class="edb-step-connector" :class="{ 'edb-step-connector--done': currentStep > 1 }"></div>
            <div class="edb-step" :class="{ 'edb-step--active': currentStep === 2, 'edb-step--done': currentStep > 2 }">
                <div class="edb-step__number">{{ currentStep > 2 ? '✓' : '2' }}</div>
                <div class="edb-step__label">配置参数</div>
            </div>
            <div class="edb-step-connector" :class="{ 'edb-step-connector--done': currentStep > 2 }"></div>
            <div class="edb-step" :class="{ 'edb-step--active': currentStep === 3, 'edb-step--done': currentStep > 3 }">
                <div class="edb-step__number">{{ currentStep > 3 ? '✓' : '3' }}</div>
                <div class="edb-step__label">选择脚本</div>
            </div>
            <div class="edb-step-connector" :class="{ 'edb-step-connector--done': currentStep > 3 }"></div>
            <div class="edb-step" :class="{ 'edb-step--active': currentStep === 4 }">
                <div class="edb-step__number">4</div>
                <div class="edb-step__label">执行查询</div>
            </div>
        </div>

        <div v-if="currentStep === 1" class="edb-card">
            <div class="edb-card__header">
                <div class="edb-card__title"><i class="fas fa-cloud-upload-alt"></i> 上传 Excel 文件</div>
            </div>
            <div class="edb-upload-zone" :class="{ 'edb-upload-zone--dragover': isDragover }"
                 @click="triggerFileInput" @dragover.prevent="isDragover = true" @dragleave="isDragover = false"
                 @drop.prevent="handleDrop">
                <div class="edb-upload-zone__icon"><i class="fas fa-cloud-upload-alt"></i></div>
                <div class="edb-upload-zone__text">拖拽文件到此处，或点击选择文件</div>
                <div class="edb-upload-zone__hint">支持 .xlsx, .xls 格式，最大 100MB</div>
                <input type="file" ref="fileInput" style="display:none" accept=".xlsx,.xls,.csv"
                       @change="handleFileSelect">
            </div>
            <div v-if="uploadedFile" class="edb-file-info edb-mt-lg">
                <div class="edb-file-info__icon"><i class="fas fa-file-excel"></i></div>
                <div style="flex:1">
                    <div class="edb-file-info__name">{{ uploadedFile.filename }}</div>
                    <div class="edb-file-info__meta">
                        {{ EDBHelpers.formatFileSize(uploadedFile.size) }} · {{ uploadedFile.sheets?.length || 0 }} 个工作表
                    </div>
                </div>
                <button class="edb-btn edb-btn--ghost edb-btn--sm" @click="removeFile">
                    <i class="fas fa-times"></i> 移除
                </button>
            </div>
            <div v-if="uploadedFile && uploadedFile.columns?.length" class="edb-mt-lg">
                <label class="edb-form-label">检测到的列名 ({{ uploadedFile.columns.length }} 列)</label>
                <div class="edb-flex edb-flex--wrap" style="gap:6px">
                    <span v-for="col in uploadedFile.columns" :key="col" class="edb-param-tag" style="background:rgba(59,130,246,0.1);color:var(--color-primary)">
                        {{ col }}
                    </span>
                </div>
            </div>
            <div v-if="uploadedFile" class="edb-mt-lg" style="text-align:right">
                <button class="edb-btn edb-btn--primary" @click="currentStep = 2">
                    下一步 <i class="fas fa-arrow-right"></i>
                </button>
            </div>
        </div>

        <div v-if="currentStep === 2" class="edb-card">
            <div class="edb-card__header">
                <div class="edb-card__title"><i class="fas fa-sliders-h"></i> 参数配置</div>
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">参数列 <span class="edb-required">*</span></label>
                <select class="edb-form-select" v-model="selectedColumn">
                    <option value="">请选择参数列</option>
                    <option v-for="col in fileColumns" :key="col" :value="col">{{ col }}</option>
                </select>
                <div style="font-size:0.75rem;color:var(--text-muted);margin-top:4px">选择 Excel 中作为查询参数的列</div>
            </div>
            <div class="edb-form-group">
                <label class="edb-form-label">输出模式</label>
                <div class="edb-grid-3">
                    <label v-for="mode in outputModes" :key="mode.value" class="edb-form-check"
                           style="padding:12px;border:1px solid var(--border-color);border-radius:8px;cursor:pointer"
                           :style="{ borderColor: options.output_mode === mode.value ? 'var(--color-primary)' : '' }">
                        <input type="radio" :value="mode.value" v-model="options.output_mode" style="display:none">
                        <div>
                            <div style="font-weight:600;font-size:0.85rem;color:var(--text-primary)">{{ mode.label }}</div>
                            <div style="font-size:0.72rem;color:var(--text-muted)">{{ mode.desc }}</div>
                        </div>
                    </label>
                </div>
            </div>
            <div class="edb-grid-2">
                <div class="edb-form-group">
                    <label class="edb-form-label">并发数</label>
                    <input type="number" class="edb-form-input" v-model.number="options.concurrency" min="1" max="10">
                </div>
                <div class="edb-form-group">
                    <label class="edb-form-label">每行超时 (秒)</label>
                    <input type="number" class="edb-form-input" v-model.number="options.timeout_per_row" min="5" max="300">
                </div>
            </div>
            <div class="edb-flex edb-flex--between edb-mt-lg">
                <button class="edb-btn edb-btn--ghost" @click="currentStep = 1">
                    <i class="fas fa-arrow-left"></i> 上一步
                </button>
                <button class="edb-btn edb-btn--primary" :disabled="!selectedColumn" @click="currentStep = 3">
                    下一步 <i class="fas fa-arrow-right"></i>
                </button>
            </div>
        </div>

        <div v-if="currentStep === 3" class="edb-card">
            <div class="edb-card__header">
                <div class="edb-card__title"><i class="fas fa-code"></i> 选择查询脚本</div>
            </div>
            <div v-if="scripts.length === 0" class="edb-empty">
                <div class="edb-empty__icon"><i class="fas fa-file-code"></i></div>
                <div class="edb-empty__title">暂无可用脚本</div>
                <div class="edb-empty__desc">请先创建 SQL 脚本</div>
                <button class="edb-btn edb-btn--primary edb-btn--sm" @click="$root.navigateTo('/scripts')">
                    <i class="fas fa-plus"></i> 创建脚本
                </button>
            </div>
            <div v-else>
                <div class="edb-search edb-mb-lg" style="max-width:320px">
                    <i class="fas fa-search edb-search__icon"></i>
                    <input type="text" class="edb-form-input edb-search__input" placeholder="搜索脚本..." v-model="scriptSearch">
                </div>
                <div v-for="script in filteredScriptList" :key="script.id"
                     style="padding:14px;border:1px solid var(--border-color);border-radius:8px;margin-bottom:8px;cursor:pointer;transition:all 0.15s"
                     :style="{ borderColor: selectedScripts.includes(script.id) ? 'var(--color-primary)' : '', background: selectedScripts.includes(script.id) ? 'rgba(59,130,246,0.06)' : '' }"
                     @click="toggleScript(script.id)">
                    <div class="edb-flex edb-flex--between">
                        <div class="edb-flex edb-flex--gap-sm" style="align-items:center">
                            <input type="checkbox" :checked="selectedScripts.includes(script.id)"
                                   @click.stop style="accent-color:var(--color-primary);width:16px;height:16px">
                            <div>
                                <div style="font-weight:600;font-size:0.9rem">{{ script.name }}</div>
                                <div style="font-size:0.75rem;color:var(--text-muted)">{{ script.database_name || '未知数据库' }}</div>
                            </div>
                        </div>
                        <div class="edb-flex edb-flex--gap-sm" style="align-items:center">
                            <span v-for="p in (script.parameters || []).slice(0, 2)" :key="p" class="edb-param-tag">{{ p }}</span>
                            <span class="edb-badge" :class="script.is_valid ? 'edb-badge--success' : 'edb-badge--error'" style="font-size:0.65rem">
                                {{ script.is_valid ? '有效' : '无效' }}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
            <div class="edb-flex edb-flex--between edb-mt-lg">
                <button class="edb-btn edb-btn--ghost" @click="currentStep = 2">
                    <i class="fas fa-arrow-left"></i> 上一步
                </button>
                <button class="edb-btn edb-btn--primary" :disabled="selectedScripts.length === 0" @click="currentStep = 4">
                    下一步 <i class="fas fa-arrow-right"></i>
                </button>
            </div>
        </div>

        <div v-if="currentStep === 4" class="edb-card">
            <div class="edb-card__header">
                <div class="edb-card__title"><i class="fas fa-play-circle"></i> 执行查询</div>
            </div>

            <div v-if="!isExecuting && !executionResult" class="edb-mb-lg">
                <h3 style="font-size:0.95rem;font-weight:600;margin-bottom:12px">执行摘要</h3>
                <div style="background:rgba(15,23,42,0.5);border:1px solid var(--border-color);border-radius:8px;padding:16px">
                    <div class="edb-flex edb-flex--between" style="margin-bottom:8px">
                        <span class="edb-text-muted" style="font-size:0.82rem">Excel 文件</span>
                        <span style="font-size:0.82rem">{{ uploadedFile?.filename }}</span>
                    </div>
                    <div class="edb-flex edb-flex--between" style="margin-bottom:8px">
                        <span class="edb-text-muted" style="font-size:0.82rem">参数列</span>
                        <span style="font-size:0.82rem">{{ selectedColumn }}</span>
                    </div>
                    <div class="edb-flex edb-flex--between" style="margin-bottom:8px">
                        <span class="edb-text-muted" style="font-size:0.82rem">选中脚本</span>
                        <span style="font-size:0.82rem">{{ selectedScripts.length }} 个</span>
                    </div>
                    <div class="edb-flex edb-flex--between" style="margin-bottom:8px">
                        <span class="edb-text-muted" style="font-size:0.82rem">输出模式</span>
                        <span style="font-size:0.82rem">{{ getOutputModeLabel() }}</span>
                    </div>
                    <div class="edb-flex edb-flex--between">
                        <span class="edb-text-muted" style="font-size:0.82rem">并发数</span>
                        <span style="font-size:0.82rem">{{ options.concurrency }}</span>
                    </div>
                </div>
            </div>

            <div v-if="isExecuting" class="edb-text-center edb-mb-lg" style="padding:20px">
                <div class="edb-progress-circle" style="margin:0 auto 20px">
                    <svg viewBox="0 0 120 120">
                        <defs>
                            <linearGradient id="edb-progress-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                                <stop offset="0%" style="stop-color:#3b82f6" />
                                <stop offset="100%" style="stop-color:#06b6d4" />
                            </linearGradient>
                        </defs>
                        <circle class="edb-progress-circle__bg" cx="60" cy="60" r="52" />
                        <circle class="edb-progress-circle__fill" cx="60" cy="60" r="52"
                                :stroke-dasharray="circumference"
                                :stroke-dashoffset="circumference - (progress.percentage / 100) * circumference" />
                    </svg>
                    <div class="edb-progress-circle__text">
                        <div class="edb-progress-circle__value">{{ progress.percentage }}%</div>
                        <div class="edb-progress-circle__label">进度</div>
                    </div>
                </div>
                <div style="font-size:0.9rem;font-weight:600;color:var(--text-primary);margin-bottom:4px">
                    正在执行查询...
                </div>
                <div style="font-size:0.82rem;color:var(--text-muted)">
                    已处理 {{ progress.current }} / {{ progress.total }} 行
                    <span v-if="progress.eta_seconds">· 预计剩余 {{ EDBHelpers.formatDuration(progress.eta_seconds) }}</span>
                </div>
                <button class="edb-btn edb-btn--danger edb-btn--sm edb-mt-lg" @click="cancelExecution">
                    <i class="fas fa-stop"></i> 取消执行
                </button>
            </div>

            <div v-if="executionResult" class="edb-mb-lg">
                <div class="edb-flex edb-flex--center" style="padding:20px;gap:20px"
                     :style="{ background: executionResult.status === 'completed' ? 'rgba(16,185,129,0.06)' : 'rgba(239,68,68,0.06)', borderRadius: '12px', border: '1px solid ' + (executionResult.status === 'completed' ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)') }">
                    <i class="fas" :class="executionResult.status === 'completed' ? 'fa-check-circle edb-text-success' : 'fa-times-circle edb-text-error'" style="font-size:36px"></i>
                    <div>
                        <div style="font-size:1.1rem;font-weight:700" :class="executionResult.status === 'completed' ? 'edb-text-success' : 'edb-text-error'">
                            {{ executionResult.status === 'completed' ? '执行完成' : '执行失败' }}
                        </div>
                        <div style="font-size:0.85rem;color:var(--text-secondary);margin-top:4px">
                            成功 {{ executionResult.success_count }} 条 · 失败 {{ executionResult.failed_count }} 条 · 耗时 {{ EDBHelpers.formatDuration(executionResult.duration) }}
                        </div>
                    </div>
                </div>
                <div class="edb-mt-lg edb-flex edb-flex--gap">
                    <button v-if="executionResult.download_url" class="edb-btn edb-btn--success" @click="downloadResult">
                        <i class="fas fa-download"></i> 下载结果
                    </button>
                    <button class="edb-btn edb-btn--ghost" @click="resetExecutor">
                        <i class="fas fa-redo"></i> 重新执行
                    </button>
                </div>
            </div>

            <div v-if="executionLogs.length" class="edb-mt-lg">
                <label class="edb-form-label">执行日志</label>
                <div class="edb-log-viewer" ref="logViewer">
                    <div v-for="(log, i) in executionLogs" :key="i" class="edb-log-entry">
                        <span class="edb-log-entry__time">{{ log.time }}</span>
                        <span class="edb-log-entry__level" :class="log.levelClass">{{ log.level }}</span>
                        <span class="edb-log-entry__msg">{{ log.message }}</span>
                    </div>
                </div>
            </div>

            <div v-if="!isExecuting && !executionResult" class="edb-flex edb-flex--between edb-mt-lg">
                <button class="edb-btn edb-btn--ghost" @click="currentStep = 3">
                    <i class="fas fa-arrow-left"></i> 上一步
                </button>
                <button class="edb-btn edb-btn--primary edb-btn--lg" @click="startExecution">
                    <i class="fas fa-play"></i> 开始执行
                </button>
            </div>
        </div>
    </div>
    `,
    data() {
        return {
            currentStep: 1,
            isDragover: false,
            uploadedFile: null,
            selectedColumn: '',
            scripts: [],
            selectedScripts: [],
            scriptSearch: '',
            isExecuting: false,
            executionResult: null,
            executionLogs: [],
            pollTimer: null,
            progress: { current: 0, total: 0, percentage: 0, eta_seconds: null },
            options: { output_mode: 'new_sheet', concurrency: 4, timeout_per_row: 30 },
            outputModes: EDB_CONSTANTS.OUTPUT_MODES,
            circumference: 2 * Math.PI * 52
        };
    },
    computed: {
        fileColumns() {
            return this.uploadedFile?.columns || [];
        },
        filteredScriptList() {
            if (!this.scriptSearch) return this.scripts;
            const q = this.scriptSearch.toLowerCase();
            return this.scripts.filter(s => s.name.toLowerCase().includes(q));
        }
    },
    async mounted() {
        this.scripts = await EdbStoreActions.fetchScripts();
    },
    beforeUnmount() {
        if (this.pollTimer) clearInterval(this.pollTimer);
    },
    methods: {
        triggerFileInput() { this.$refs.fileInput?.click(); },
        handleFileSelect(e) {
            const file = e.target.files?.[0];
            if (file) this.processFile(file);
        },
        handleDrop(e) {
            this.isDragover = false;
            const file = e.dataTransfer.files?.[0];
            if (file) this.processFile(file);
        },
        async processFile(file) {
            const validation = EDBValidators.excelFile(file);
            if (!validation.valid) {
                EdbStoreActions.toastError(validation.message);
                return;
            }
            try {
                EdbStoreActions.toastInfo('正在上传文件...');
                const res = await EdbApi.query.upload(file, (e) => {
                    const pct = Math.round((e.loaded / e.total) * 100);
                });
                this.uploadedFile = res.data;
                EdbStoreActions.toastSuccess('文件上传成功');
                if (this.uploadedFile.columns?.length > 0) {
                    this.selectedColumn = this.uploadedFile.columns[0];
                }
            } catch (e) {
                EdbStoreActions.toastError('文件上传失败：' + e.message);
            }
        },
        removeFile() {
            this.uploadedFile = null;
            this.selectedColumn = '';
            if (this.$refs.fileInput) this.$refs.fileInput.value = '';
        },
        toggleScript(id) {
            const idx = this.selectedScripts.indexOf(id);
            if (idx > -1) this.selectedScripts.splice(idx, 1);
            else this.selectedScripts.push(id);
        },
        getOutputModeLabel() {
            const mode = this.outputModes.find(m => m.value === this.options.output_mode);
            return mode ? mode.label : '';
        },
        async startExecution() {
            if (!this.uploadedFile || !this.selectedColumn || this.selectedScripts.length === 0) {
                EdbStoreActions.toastWarning('请完成所有配置步骤');
                return;
            }
            this.isExecuting = true;
            this.executionResult = null;
            this.executionLogs = [];
            this.progress = { current: 0, total: 0, percentage: 0, eta_seconds: null };
            this.addLog('INFO', '开始执行批量查询...');
            this.addLog('INFO', `文件: ${this.uploadedFile.filename}, 参数列: ${this.selectedColumn}, 脚本数: ${this.selectedScripts.length}`);
            try {
                const res = await EdbApi.query.execute({
                    file_id: this.uploadedFile.file_id,
                    script_ids: this.selectedScripts,
                    parameter_mapping: { value: this.selectedColumn },
                    options: this.options
                });
                this.addLog('INFO', `任务已创建，ID: ${res.data?.task_id}`);
                this.startPolling(res.data?.task_id);
            } catch (e) {
                this.isExecuting = false;
                this.addLog('ERROR', `执行失败: ${e.message}`);
                EdbStoreActions.toastError('执行失败：' + e.message);
            }
        },
        startPolling(taskId) {
            if (this.pollTimer) clearInterval(this.pollTimer);
            this.pollTimer = setInterval(async () => {
                try {
                    const res = await EdbApi.query.status(taskId);
                    const data = res.data;
                    this.progress = {
                        current: data.progress?.current || 0,
                        total: data.progress?.total || 0,
                        percentage: data.progress?.percentage || 0,
                        eta_seconds: data.progress?.eta_seconds
                    };
                    if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
                        clearInterval(this.pollTimer);
                        this.pollTimer = null;
                        this.isExecuting = false;
                        this.executionResult = {
                            status: data.status,
                            success_count: data.results?.success_count || 0,
                            failed_count: data.results?.failed_count || 0,
                            duration: data.duration_seconds || 0,
                            download_url: data.result_file_url
                        };
                        this.addLog(data.status === 'completed' ? 'INFO' : 'ERROR',
                            data.status === 'completed' ? '查询执行完成！' : `查询执行${data.status === 'failed' ? '失败' : '已取消'}`);
                        EdbStoreActions.toastSuccess(data.status === 'completed' ? '查询执行完成' : '查询已结束');
                    }
                } catch (e) {
                    this.addLog('ERROR', `状态查询失败: ${e.message}`);
                }
            }, EDB_CONSTANTS.POLL_INTERVAL);
        },
        async cancelExecution() {
            EdbStoreActions.showConfirm({
                title: '取消确认',
                message: '确定要取消正在执行的查询任务吗？',
                type: 'warning',
                onConfirm: async () => {
                    try {
                        await EdbApi.query.cancel('current');
                        this.addLog('WARN', '用户取消了执行');
                        EdbStoreActions.toastWarning('正在取消...');
                    } catch (e) {
                        EdbStoreActions.toastError(e.message);
                    }
                }
            });
        },
        async downloadResult() {
            try {
                const res = await EdbApi.query.download('current');
                const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                EDBHelpers.downloadBlob(blob, `query_result_${Date.now()}.xlsx`);
                EdbStoreActions.toastSuccess('下载成功');
            } catch (e) {
                EdbStoreActions.toastError('下载失败：' + e.message);
            }
        },
        resetExecutor() {
            this.currentStep = 1;
            this.isExecuting = false;
            this.executionResult = null;
            this.executionLogs = [];
            this.progress = { current: 0, total: 0, percentage: 0, eta_seconds: null };
            this.removeFile();
            this.selectedScripts = [];
        },
        addLog(level, message) {
            const levelConfig = EDB_CONSTANTS.LOG_LEVELS[level] || EDB_CONSTANTS.LOG_LEVELS.INFO;
            this.executionLogs.push({
                time: new Date().toLocaleTimeString(),
                level: levelConfig.label,
                levelClass: levelConfig.class,
                message
            });
            this.$nextTick(() => {
                const viewer = this.$refs.logViewer;
                if (viewer) viewer.scrollTop = viewer.scrollHeight;
            });
        }
    }
};
