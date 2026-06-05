const EdbModal = {
    name: 'edb-modal',
    props: {
        title: { type: String, default: '' },
        size: { type: String, default: '' },
        visible: { type: Boolean, default: false },
        closable: { type: Boolean, default: true },
        showFooter: { type: Boolean, default: true },
        confirmText: { type: String, default: '确认' },
        cancelText: { type: String, default: '取消' },
        confirmType: { type: String, default: 'primary' },
        loading: { type: Boolean, default: false }
    },
    emits: ['close', 'confirm', 'cancel'],
    template: `
    <teleport to="body">
        <div v-if="visible" class="edb-modal-overlay" @click.self="handleOverlayClick">
            <div class="edb-modal" :class="sizeClass">
                <div class="edb-modal__header">
                    <h3 class="edb-modal__title">{{ title }}</h3>
                    <button v-if="closable" class="edb-modal__close" @click="handleClose">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="edb-modal__body">
                    <slot></slot>
                </div>
                <div v-if="showFooter" class="edb-modal__footer">
                    <slot name="footer">
                        <button class="edb-btn edb-btn--ghost" @click="handleCancel">{{ cancelText }}</button>
                        <button class="edb-btn" :class="'edb-btn--' + confirmType" :disabled="loading" @click="handleConfirm">
                            <span v-if="loading" class="edb-spinner edb-spinner--sm"></span>
                            {{ confirmText }}
                        </button>
                    </slot>
                </div>
            </div>
        </div>
    </teleport>
    `,
    computed: {
        sizeClass() {
            if (this.size) return `edb-modal--${this.size}`;
            return '';
        }
    },
    methods: {
        handleClose() {
            if (this.closable) this.$emit('close');
        },
        handleOverlayClick() {
            if (this.closable) this.$emit('close');
        },
        handleConfirm() {
            this.$emit('confirm');
        },
        handleCancel() {
            this.$emit('cancel');
            this.$emit('close');
        }
    },
    watch: {
        visible(val) {
            if (val) {
                document.body.style.overflow = 'hidden';
            } else {
                document.body.style.overflow = '';
            }
        }
    }
};
