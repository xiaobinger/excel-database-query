// 轻量全局事件总线：页面执行动作 → AI宠物互动信号
// 用法：emitPetEvent('operation', { type: 'query'|'export', label })
//      emitPetEvent('file_ready', { type, label })

const handlers = new Map()

export function onPetEvent(event, handler) {
  if (!handlers.has(event)) handlers.set(event, new Set())
  handlers.get(event).add(handler)
  return () => offPetEvent(event, handler)
}

export function offPetEvent(event, handler) {
  const set = handlers.get(event)
  if (set) set.delete(handler)
}

export function emitPetEvent(event, payload) {
  const set = handlers.get(event)
  if (!set) return
  set.forEach((fn) => {
    try {
      fn(payload)
    } catch {
      // 单个监听器异常不影响其他监听器
    }
  })
}
