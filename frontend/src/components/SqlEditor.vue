<template>
  <div class="sql-editor">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <el-button size="small" type="primary" :loading="validating" @click="handleValidate">
          <i class="fas fa-check-circle"></i> 验证
        </el-button>
        <el-button size="small" type="success" :loading="formatting" @click="handleFormat">
          <i class="fas fa-magic"></i> 美化
        </el-button>
        <el-button size="small" type="warning" :loading="simplifying" @click="handleSimplify">
          <i class="fas fa-compress-alt"></i> 简化
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-tag size="small" type="info">{{ lineCount }} 行</el-tag>
      </div>
    </div>
    <div class="editor-body">
      <div class="line-numbers" ref="lineNumbersRef">
        <div v-for="n in lineCount" :key="n" class="line-number">{{ n }}</div>
      </div>
      <div class="editor-area" ref="editorAreaRef">
        <textarea
          ref="textareaRef"
          class="sql-textarea"
          :value="modelValue"
          @input="onInput"
          @scroll="syncScroll"
          @keydown="handleKeydown"
          placeholder="请输入SQL语句，如：SELECT id, name FROM users WHERE id = :value"
          spellcheck="false"
        ></textarea>
        <pre class="sql-highlight" ref="highlightRef" aria-hidden="true"><code v-html="highlightedCode"></code></pre>
      </div>
    </div>
    <div v-if="suggestions.length > 0 && suggestionVisible" class="suggestion-panel">
      <div
        v-for="(sug, idx) in suggestions"
        :key="sug.value"
        class="suggestion-item"
        :class="{ active: idx === activeSuggestion }"
        @click="applySuggestion(sug)"
        @mouseenter="activeSuggestion = idx"
      >
        <span class="sug-keyword">{{ sug.value }}</span>
        <span class="sug-desc">{{ sug.desc }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import api from '../api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  modelValue: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: '450px'
  }
})

const emit = defineEmits(['update:modelValue'])

const textareaRef = ref(null)
const lineNumbersRef = ref(null)
const highlightRef = ref(null)
const editorAreaRef = ref(null)
const validating = ref(false)
const formatting = ref(false)
const simplifying = ref(false)
const suggestionVisible = ref(false)
const activeSuggestion = ref(0)

const SQL_KEYWORDS = [
  { value: 'SELECT', desc: '查询' },
  { value: 'FROM', desc: '数据源' },
  { value: 'WHERE', desc: '条件' },
  { value: 'AND', desc: '与' },
  { value: 'OR', desc: '或' },
  { value: 'NOT', desc: '非' },
  { value: 'IN', desc: '在...中' },
  { value: 'NOT IN', desc: '不在...中' },
  { value: 'LIKE', desc: '模糊匹配' },
  { value: 'BETWEEN', desc: '范围' },
  { value: 'IS NULL', desc: '为空' },
  { value: 'IS NOT NULL', desc: '不为空' },
  { value: 'JOIN', desc: '连接' },
  { value: 'INNER JOIN', desc: '内连接' },
  { value: 'LEFT JOIN', desc: '左连接' },
  { value: 'RIGHT JOIN', desc: '右连接' },
  { value: 'ON', desc: '连接条件' },
  { value: 'GROUP BY', desc: '分组' },
  { value: 'ORDER BY', desc: '排序' },
  { value: 'HAVING', desc: '分组条件' },
  { value: 'LIMIT', desc: '限制行数' },
  { value: 'OFFSET', desc: '偏移' },
  { value: 'UNION', desc: '合并' },
  { value: 'UNION ALL', desc: '合并(含重复)' },
  { value: 'DISTINCT', desc: '去重' },
  { value: 'AS', desc: '别名' },
  { value: 'INSERT', desc: '插入' },
  { value: 'UPDATE', desc: '更新' },
  { value: 'DELETE', desc: '删除' },
  { value: 'COUNT', desc: '计数' },
  { value: 'SUM', desc: '求和' },
  { value: 'AVG', desc: '平均' },
  { value: 'MAX', desc: '最大' },
  { value: 'MIN', desc: '最小' },
  { value: 'IF', desc: '条件函数' },
  { value: 'IFNULL', desc: '空值处理' },
  { value: 'CASE', desc: '条件表达式' },
  { value: 'WHEN', desc: '条件分支' },
  { value: 'THEN', desc: '条件结果' },
  { value: 'ELSE', desc: '其他' },
  { value: 'END', desc: '条件结束' },
  { value: 'EXISTS', desc: '存在' },
  { value: 'ASC', desc: '升序' },
  { value: 'DESC', desc: '降序' },
]

const lineCount = computed(() => {
  const lines = (props.modelValue || '').split('\n').length
  return Math.max(lines, 1)
})

const suggestions = computed(() => {
  const sql = props.modelValue || ''
  if (!sql) return []
  const lastWord = getLastWord(sql)
  if (!lastWord || lastWord.length < 1) return []
  const upper = lastWord.toUpperCase()
  return SQL_KEYWORDS.filter(k => k.value.startsWith(upper) && k.value !== upper).slice(0, 8)
})

function getLastWord(sql) {
  const text = sql.trimEnd()
  const match = text.match(/([A-Za-z_]+)$/)
  return match ? match[1] : ''
}

function highlightSql(sql) {
  if (!sql) return ''
  let result = escapeHtml(sql)
  const keywords = [
    'SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT', 'IN', 'LIKE', 'BETWEEN',
    'IS', 'NULL', 'JOIN', 'INNER', 'LEFT', 'RIGHT', 'OUTER', 'CROSS', 'FULL',
    'ON', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'UNION', 'ALL',
    'DISTINCT', 'AS', 'INSERT', 'INTO', 'UPDATE', 'DELETE', 'SET', 'VALUES',
    'CREATE', 'ALTER', 'DROP', 'TABLE', 'INDEX', 'VIEW', 'COUNT', 'SUM', 'AVG',
    'MAX', 'MIN', 'IF', 'IFNULL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'EXISTS', 'ASC', 'DESC', 'TRUE', 'FALSE', 'PRIMARY', 'KEY', 'FOREIGN',
    'REFERENCES', 'DEFAULT', 'NOT', 'CONSTRAINT', 'UNIQUE', 'CHECK', 'TOP',
    'CONCAT', 'SUBSTRING', 'TRIM', 'UPPER', 'LOWER', 'LENGTH', 'REPLACE',
    'CAST', 'CONVERT', 'COALESCE', 'NOW', 'CURDATE', 'DATE_FORMAT',
  ]
  const params = /(:\w+)/g
  result = result.replace(params, '<span class="hl-param">$1</span>')
  const strings = /('(?:[^']|'')*?'|"(?:[^"]|"")*?")/g
  result = result.replace(strings, '<span class="hl-string">$1</span>')
  for (const kw of keywords) {
    const re = new RegExp(`\\b(${kw})\\b`, 'gi')
    result = result.replace(re, (match) => {
      const isUpper = match === match.toUpperCase()
      return `<span class="hl-keyword">${isUpper ? kw : kw.toLowerCase()}</span>`
    })
  }
  const numbers = /\b(\d+(?:\.\d+)?)\b/g
  result = result.replace(numbers, '<span class="hl-number">$1</span>')
  return result
}

function escapeHtml(text) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const highlightedCode = computed(() => {
  return highlightSql(props.modelValue || '') + '\n'
})

function onInput(e) {
  emit('update:modelValue', e.target.value)
  updateSuggestionVisible(e.target.value)
  nextTick(() => syncScroll({ target: textareaRef.value }))
}

function updateSuggestionVisible(sql) {
  if (!sql) { suggestionVisible.value = false; return }
  const lastWord = getLastWord(sql)
  suggestionVisible.value = lastWord.length >= 1 && suggestions.value.length > 0
  activeSuggestion.value = 0
}

function applySuggestion(sug) {
  const sql = props.modelValue || ''
  const lastWord = getLastWord(sql)
  if (!lastWord) return
  const before = sql.slice(0, sql.length - lastWord.length)
  const newSql = before + sug.value + ' '
  emit('update:modelValue', newSql)
  suggestionVisible.value = false
  nextTick(() => {
    if (textareaRef.value) textareaRef.value.focus()
  })
}

function handleKeydown(e) {
  if (suggestionVisible.value && suggestions.value.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      activeSuggestion.value = (activeSuggestion.value + 1) % suggestions.value.length
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      activeSuggestion.value = (activeSuggestion.value - 1 + suggestions.value.length) % suggestions.value.length
      return
    }
    if (e.key === 'Enter' || e.key === 'Tab') {
      e.preventDefault()
      applySuggestion(suggestions.value[activeSuggestion.value])
      return
    }
    if (e.key === 'Escape') {
      suggestionVisible.value = false
      return
    }
  }
  if (e.key === 'Tab') {
    e.preventDefault()
    const textarea = e.target
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const val = props.modelValue || ''
    const newVal = val.substring(0, start) + '  ' + val.substring(end)
    emit('update:modelValue', newVal)
    nextTick(() => {
      textarea.selectionStart = textarea.selectionEnd = start + 2
    })
  }
}

function syncScroll(e) {
  if (!e?.target) return
  const scrollTop = e.target.scrollTop
  const scrollLeft = e.target.scrollLeft
  if (lineNumbersRef.value) lineNumbersRef.value.scrollTop = scrollTop
  if (highlightRef.value) {
    highlightRef.value.scrollTop = scrollTop
    highlightRef.value.scrollLeft = scrollLeft
  }
}

async function handleValidate() {
  if (!props.modelValue?.trim()) {
    ElMessage.warning('请先输入SQL语句')
    return
  }
  validating.value = true
  try {
    const res = await api.scripts.validateSql({ sql: props.modelValue })
    if (res.is_valid || res.valid) {
      const warnings = res.warnings || []
      if (warnings.length > 0) {
        ElMessage.warning(`验证通过，但有警告：${warnings.join('；')}`)
      } else {
        ElMessage.success('SQL语法验证通过')
      }
    } else {
      ElMessage.error(res.message || 'SQL语法验证失败')
    }
  } catch {
    // error handled by interceptor
  } finally {
    validating.value = false
  }
}

async function handleFormat() {
  if (!props.modelValue?.trim()) {
    ElMessage.warning('请先输入SQL语句')
    return
  }
  formatting.value = true
  try {
    const res = await api.scripts.formatSql({ sql: props.modelValue })
    const formatted = res.formatted_sql || res.formatted
    if (formatted) {
      emit('update:modelValue', formatted)
      ElMessage.success('SQL美化完成')
    } else {
      ElMessage.warning('美化结果为空')
    }
  } catch {
    // error handled by interceptor
  } finally {
    formatting.value = false
  }
}

async function handleSimplify() {
  if (!props.modelValue?.trim()) {
    ElMessage.warning('请先输入SQL语句')
    return
  }
  simplifying.value = true
  try {
    const res = await api.scripts.simplifySql({ sql: props.modelValue })
    const simplified = res.simplified_sql || res.simplified
    if (simplified) {
      emit('update:modelValue', simplified)
      ElMessage.success('SQL简化完成')
    } else {
      ElMessage.warning('简化结果为空')
    }
  } catch {
    // error handled by interceptor
  } finally {
    simplifying.value = false
  }
}

watch(() => props.modelValue, () => {
  nextTick(() => syncScroll({ target: textareaRef.value }))
})
</script>

<style scoped>
.sql-editor {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
  height: v-bind(height);
  min-height: 200px;
}

.editor-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
}

.toolbar-left {
  display: flex;
  gap: 6px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.editor-body {
  display: flex;
  flex: 1;
  min-height: 0;
  background: #1e1e1e;
  position: relative;
}

.line-numbers {
  width: 50px;
  background: #252526;
  color: #858585;
  text-align: right;
  padding: 10px 8px 10px 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  overflow: hidden;
  user-select: none;
  flex-shrink: 0;
}

.line-number {
  height: 22.4px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
}

.editor-area {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.sql-textarea {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: transparent;
  color: transparent;
  caret-color: #d4d4d4;
  border: none;
  outline: none;
  resize: none;
  padding: 10px 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  tab-size: 2;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre;
  word-wrap: normal;
  z-index: 2;
}

.sql-textarea::placeholder {
  color: #6a6a6a;
}

.sql-textarea::selection {
  background: rgba(38, 79, 120, 0.8);
  color: transparent;
}

.sql-highlight {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  margin: 0;
  padding: 10px 12px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 14px;
  line-height: 1.6;
  tab-size: 2;
  overflow-y: auto;
  overflow-x: auto;
  white-space: pre;
  word-wrap: normal;
  z-index: 1;
  pointer-events: none;
  color: #d4d4d4;
  background: transparent;
}

.sql-highlight code {
  font-family: inherit;
  font-size: inherit;
}

.sql-textarea::-webkit-scrollbar,
.sql-highlight::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

.sql-textarea::-webkit-scrollbar-track,
.sql-highlight::-webkit-scrollbar-track {
  background: #1e1e1e;
}

.sql-textarea::-webkit-scrollbar-thumb,
.sql-highlight::-webkit-scrollbar-thumb {
  background: #424242;
  border-radius: 4px;
}

:deep(.hl-keyword) {
  color: #569cd6;
  font-weight: 600;
}

:deep(.hl-param) {
  color: #9cdcfe;
}

:deep(.hl-string) {
  color: #ce9178;
}

:deep(.hl-number) {
  color: #b5cea8;
}

.suggestion-panel {
  position: absolute;
  bottom: 100%;
  left: 50px;
  right: 0;
  background: #252526;
  border: 1px solid #3c3c3c;
  border-radius: 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 10;
  box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.3);
}

.suggestion-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  cursor: pointer;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  color: #d4d4d4;
}

.suggestion-item.active {
  background: #094771;
}

.suggestion-item:hover {
  background: #094771;
}

.sug-keyword {
  color: #569cd6;
  font-weight: 600;
}

.sug-desc {
  color: #6a6a6a;
  font-size: 12px;
  margin-left: 12px;
}
</style>
