const EdbConfirmDialog = {
    name: 'edb-confirm-dialog',
    props: {
        title: { type: String, default: '确认操作' },
        message: { type: String, default: '确定要执行此操作吗？' },
        type: { type: String, default: 'danger' }
    },
    emits: ['confirm', 'cancel'],
    template: `
    <div class="edb-modal-overlay" @click.self="$emit('cancel')">
        <div class="edb-modal" style="max-width:440px">
            <div class="edb-modal__header">
                <h3 class="edb-modal__title">
                    <i class="fas" :class="typeIcon" :style="{ color: typeColor }" class="me-2"></i>
                    {{ title }}
                </h3>
            </div>
            <div class="edb-modal__body">
                <p style="color:var(--text-secondary);font-size:0.9rem;line-height:1.6">{{ message }}</p>
            </div>
            <div class="edb-modal__footer">
                <button class="edb-btn edb-btn--ghost" @click="$emit('cancel')">取消</button>
                <button class="edb-btn" :class="'edb-btn--' + type" @click="$emit('confirm')">
                    确认{{ type === 'danger' ? '删除' : '' }}
                </button>
            </div>
        </div>
    </div>
    `,
    computed: {
        typeIcon() {
            const map = { danger: 'fa-exclamation-triangle', warning: 'fa-exclamation-circle', info: 'fa-info-circle' };
            return map[this.type] || 'fa-question-circle';
        },
        typeColor() {
            const map = { danger: 'var(--color-error)', warning: 'var(--color-warning)', info: 'var(--color-primary)' };
            return map[this.type] || 'var(--color-primary)';
        }
    }
};
