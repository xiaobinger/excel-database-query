<template>
  <div class="md-editor">
    <!-- 工具栏 -->
    <div v-if="toolbar" class="md-toolbar">
      <button type="button" class="md-btn" title="加粗" @click="insert('**', '**', '粗体')"><i class="fas fa-bold"></i></button>
      <button type="button" class="md-btn" title="斜体" @click="insert('*', '*', '斜体')"><i class="fas fa-italic"></i></button>
      <button type="button" class="md-btn" title="删除线" @click="insert('~~', '~~', '删除线')"><i class="fas fa-strikethrough"></i></button>
      <span class="md-divider"></span>
      <button type="button" class="md-btn" title="标题" @click="insertLine('## ', '标题')"><i class="fas fa-heading"></i></button>
      <button type="button" class="md-btn" title="无序列表" @click="insertLine('- ', '列表项')"><i class="fas fa-list-ul"></i></button>
      <button type="button" class="md-btn" title="有序列表" @click="insertLine('1. ', '列表项')"><i class="fas fa-list-ol"></i></button>
      <button type="button" class="md-btn" title="引用" @click="insertLine('> ', '引用')"><i class="fas fa-quote-right"></i></button>
      <span class="md-divider"></span>
      <button type="button" class="md-btn" title="代码块" @click="insert('\n```\n', '\n```\n', '代码')"><i class="fas fa-code"></i></button>
      <button type="button" class="md-btn" title="链接" @click="insert('[', '](https://)', '链接文字')"><i class="fas fa-link"></i></button>
      <button type="button" class="md-btn" title="插入图片" @click="triggerUpload('image')"><i class="fas fa-image"></i></button>
      <button type="button" class="md-btn" title="插入视频" @click="triggerUpload('video')"><i class="fas fa-video"></i></button>
      <span class="md-divider"></span>
      <button type="button" class="md-btn" :class="{ active: previewMode }" title="预览" @click="previewMode = !previewMode"><i class="fas fa-eye"></i></button>
    </div>
    <div class="md-body">
      <textarea
        v-show="!previewMode"
        ref="textareaRef"
        :value="modelValue"
        :placeholder="placeholder"
        :style="{ height: height + 'px' }"
        class="md-textarea"
        @input="onInput"
        @blur="emitBlur"
      ></textarea>
      <div v-show="previewMode" class="md-preview" :style="{ height: height + 'px' }" v-html="renderedHtml"></div>
    </div>
    <input ref="fileInputRef" type="file" :accept="acceptAttr" style="display: none" @change="onFileChange" />
    <div v-if="uploading" class="md-uploading"><i class="fas fa-spinner fa-spin"></i> 上传中...</div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { marked } from 'marked'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '请输入内容...' },
  height: { type: Number, default: 200 },
  toolbar: { type: Boolean, default: true },
  uploadFn: { type: Function, default: null },
})

const emit = defineEmits(['update:modelValue', 'blur'])

const textareaRef = ref(null)
const fileInputRef = ref(null)
const previewMode = ref(false)
const uploading = ref(false)
let uploadType = 'image'

const acceptAttr = computed(() => {
  return uploadType === 'image' ? 'image/*' : 'video/*'
})

const renderedHtml = computed(() => {
  try {
    return marked.parse(props.modelValue || '')
  } catch {
    return props.modelValue || ''
  }
})

function onInput(e) {
  emit('update:modelValue', e.target.value)
}

function emitBlur() {
  emit('blur')
}

// 插入文本
function insert(before, after, placeholder) {
  const ta = textareaRef.value
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const text = props.modelValue || ''
  const selected = text.substring(start, end) || placeholder
  const newText = text.substring(0, start) + before + selected + after + text.substring(end)
  emit('update:modelValue', newText)
  // 恢复焦点和选区
  setTimeout(() => {
    ta.focus()
    const pos = start + before.length
    ta.setSelectionRange(pos, pos + selected.length)
  }, 0)
}

function insertLine(prefix, placeholder) {
  const ta = textareaRef.value
  if (!ta) return
  const start = ta.selectionStart
  const text = props.modelValue || ''
  const lineStart = text.lastIndexOf('\n', start - 1) + 1
  const selected = text.substring(start, ta.selectionEnd) || placeholder
  const newText = text.substring(0, lineStart) + prefix + selected + text.substring(ta.selectionEnd)
  emit('update:modelValue', newText)
  setTimeout(() => {
    ta.focus()
    const pos = lineStart + prefix.length
    ta.setSelectionRange(pos, pos + selected.length)
  }, 0)
}

function triggerUpload(type) {
  uploadType = type
  fileInputRef.value && (fileInputRef.value.value = '')
  fileInputRef.value && fileInputRef.value.click()
}

async function onFileChange(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  if (!props.uploadFn) {
    console.warn('MarkdownEditor: 未提供 uploadFn')
    return
  }
  uploading.value = true
  try {
    const result = await props.uploadFn(file)
    const url = result.url
    const filename = result.filename || file.name
    let mdText
    if (uploadType === 'image') {
      mdText = `\n![${filename}](${url})\n`
    } else {
      // 视频用 HTML video 标签（marked 支持 HTML）
      mdText = `\n<video controls src="${url}" style="max-width:100%"></video>\n`
    }
    const ta = textareaRef.value
    const start = ta ? ta.selectionStart : (props.modelValue || '').length
    const text = props.modelValue || ''
    const newText = text.substring(0, start) + mdText + text.substring(start)
    emit('update:modelValue', newText)
  } catch (err) {
    console.error('上传失败', err)
    alert('上传失败: ' + (err.message || '未知错误'))
  } finally {
    uploading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
}

// 切换回编辑模式时同步内容
watch(previewMode, (v) => {
  if (!v && textareaRef.value) {
    setTimeout(() => textareaRef.value.focus(), 0)
  }
})
</script>

<style scoped>
.md-editor {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
  background: #fff;
}

.md-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 8px;
  background: #f5f7fa;
  border-bottom: 1px solid #dcdfe6;
  flex-wrap: wrap;
}

.md-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #606266;
  cursor: pointer;
  border-radius: 4px;
  font-size: 13px;
  transition: all 0.15s;
}

.md-btn:hover {
  background: #ecf5ff;
  color: var(--primary-color, #409eff);
}

.md-btn.active {
  background: var(--primary-color, #409eff);
  color: #fff;
}

.md-divider {
  width: 1px;
  height: 18px;
  background: #dcdfe6;
  margin: 0 4px;
}

.md-body {
  position: relative;
}

.md-textarea {
  width: 100%;
  border: none;
  outline: none;
  resize: vertical;
  padding: 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #303133;
  background: #fff;
  min-height: 80px;
}

.md-preview {
  width: 100%;
  padding: 12px 16px;
  overflow-y: auto;
  background: #fff;
  line-height: 1.7;
  color: #303133;
}

.md-preview :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}

.md-preview :deep(video) {
  max-width: 100%;
  border-radius: 6px;
  margin: 8px 0;
}

.md-preview :deep(pre) {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 13px;
}

.md-preview :deep(code) {
  background: #f0f0f0;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}

.md-preview :deep(pre code) {
  background: transparent;
  padding: 0;
}

.md-uploading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(0, 0, 0, 0.7);
  color: #fff;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  z-index: 10;
}
</style>
