const EdbToastContainer = {
    name: 'edb-toast-container',
    props: {
        toasts: { type: Array, default: () => [] }
    },
    emits: ['remove-toast'],
    template: `
    <div class="edb-toast-container">
        <transition-group name="edb-toast">
            <div v-for="toast in toasts" :key="toast.id"
                 class="edb-toast" :class="'edb-toast--' + toast.type">
                <i :class="toast.icon" class="edb-toast__icon"></i>
                <span class="edb-toast__message">{{ toast.message }}</span>
                <button class="edb-toast__close" @click="$emit('remove-toast', toast.id)">
                    <i class="fas fa-times"></i>
                </button>
            </div>
        </transition-group>
    </div>
    `
};

const EdbToastStyles = `
.edb-toast-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 2000;
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: 400px;
}

.edb-toast {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 16px;
    border-radius: 10px;
    font-size: 0.85rem;
    font-weight: 500;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
    border: 1px solid;
    animation: edb-toast-in 0.3s ease;
}

.edb-toast--success {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.3);
    color: #34d399;
}
.edb-toast--error {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.3);
    color: #f87171;
}
.edb-toast--warning {
    background: rgba(245, 158, 11, 0.15);
    border-color: rgba(245, 158, 11, 0.3);
    color: #fbbf24;
}
.edb-toast--info {
    background: rgba(59, 130, 246, 0.15);
    border-color: rgba(59, 130, 246, 0.3);
    color: #60a5fa;
}

.edb-toast__icon { font-size: 16px; flex-shrink: 0; }
.edb-toast__message { flex: 1; color: #f1f5f9; }

.edb-toast__close {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 2px;
    font-size: 12px;
    opacity: 0.6;
    transition: opacity 0.15s;
}
.edb-toast__close:hover { opacity: 1; }

.edb-toast-enter-active { transition: all 0.3s ease; }
.edb-toast-leave-active { transition: all 0.2s ease; }
.edb-toast-enter-from { opacity: 0; transform: translateX(40px); }
.edb-toast-leave-to { opacity: 0; transform: translateX(40px) scale(0.95); }

@keyframes edb-toast-in {
    from { opacity: 0; transform: translateX(40px); }
    to { opacity: 1; transform: translateX(0); }
}
`;

(function () {
    const style = document.createElement('style');
    style.textContent = EdbToastStyles;
    document.head.appendChild(style);
})();
