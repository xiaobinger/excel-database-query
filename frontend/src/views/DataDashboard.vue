<template>
  <div class="data-dashboard">
    <!-- 查询工具栏 -->
    <el-card shadow="hover" class="toolbar-card">
      <div class="toolbar-row">
        <el-select v-model="state.scriptId" placeholder="选择查询脚本" filterable style="width: 200px" @change="onScriptChange">
          <el-option v-for="s in scripts" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>

        <el-select v-model="state.connName" placeholder="数据源" clearable style="width: 160px" :disabled="!currentScript">
          <el-option v-for="c in scriptConnections" :key="c.name" :label="c.name" :value="c.name">
            <span>{{ c.name }}</span>
            <span style="float: right; color: var(--el-text-color-secondary); font-size: 12px">{{ c.db_type }}</span>
          </el-option>
        </el-select>

        <el-radio-group v-model="state.dimension" size="default" @change="onDimensionChange">
          <el-radio-button value="day">按日</el-radio-button>
          <el-radio-button value="month">按月</el-radio-button>
          <el-radio-button value="year">按年</el-radio-button>
        </el-radio-group>

        <el-date-picker v-if="state.dimension === 'day'" v-model="state.dateValue" type="month"
          placeholder="选择月份" value-format="YYYY-MM" style="width: 140px" />
        <el-date-picker v-else-if="state.dimension === 'month'" v-model="state.dateValue" type="year"
          placeholder="选择年份" value-format="YYYY" style="width: 120px" />
        <template v-else>
          <el-date-picker v-model="state.startYear" type="year" placeholder="起始年" value-format="YYYY" style="width: 110px" />
          <span style="color: var(--el-text-color-secondary)">~</span>
          <el-date-picker v-model="state.endYear" type="year" placeholder="结束年" value-format="YYYY" style="width: 110px" />
        </template>

        <el-input v-for="p in customParamNames" :key="p" v-model="state.customParams[p]" :placeholder="p"
          style="width: 120px" clearable />

        <el-button type="primary" :loading="executing" @click="execute()">
          <i class="fas fa-play"></i> 执行查询
        </el-button>
        <el-tooltip content="跳过缓存强制刷新" placement="top">
          <el-button :loading="executing" @click="execute(true)"><i class="fas fa-sync-alt"></i></el-button>
        </el-tooltip>

        <div class="toolbar-spacer"></div>

        <el-select v-model="selectedQuickQueryId" placeholder="快捷查询" clearable style="width: 160px" @change="onQuickQueryChange">
          <el-option v-for="q in quickQueries" :key="q.id" :label="q.name" :value="q.id" />
        </el-select>
        <el-button @click="openSaveQuickQuery"><i class="fas fa-bookmark"></i> 保存</el-button>
        <el-button @click="scriptDialogVisible = true"><i class="fas fa-cogs"></i> 脚本管理</el-button>
      </div>

      <!-- 多数据源合并控制 -->
      <div v-if="currentScript && (currentScript.merge_conn_names || []).length > 0" class="merge-row">
        <span class="merge-label">合并数据源：</span>
        <el-checkbox-group v-model="state.mergeNames">
          <el-checkbox v-for="c in currentScript.merge_conn_names" :key="c" :value="c">{{ c }}</el-checkbox>
        </el-checkbox-group>
        <el-radio-group v-model="state.mergeMode" size="small" style="margin-left: 12px">
          <el-radio-button value="separate">分源展示</el-radio-button>
          <el-radio-button value="aggregate">聚合求和</el-radio-button>
        </el-radio-group>
        <el-select v-if="state.mergeMode === 'aggregate'" v-model="state.mergeKey" placeholder="聚合键" size="small" style="width: 120px; margin-left: 8px">
          <el-option v-for="c in availableColumns" :key="c" :label="c" :value="c" />
        </el-select>
      </div>
    </el-card>

    <!-- 钻取面包屑 -->
    <div v-if="drillStack.length" class="drill-breadcrumb">
      <span v-for="(d, i) in drillStack" :key="i" class="drill-chip" @click="drillTo(i)">{{ d.label }}</span>
      <el-button size="small" text type="primary" @click="drillUp"><i class="fas fa-level-up-alt"></i> 返回上级</el-button>
    </div>

    <!-- 图表布局控制 -->
    <el-card shadow="hover" class="layout-card">
      <div class="layout-row">
        <span class="layout-label"><i class="fas fa-th"></i> 图表数量：</span>
        <el-radio-group v-model="state.layoutCount" size="small" @change="renderAllCharts">
          <el-radio-button v-for="n in maxLayoutCount" :key="n" :value="n">{{ n }}</el-radio-button>
        </el-radio-group>
        <span class="layout-label" style="margin-left: 16px"><i class="fas fa-eye-slash"></i> 隐藏字段：</span>
        <el-select v-model="state.hideFields" multiple collapse-tags placeholder="选择要隐藏的列" size="small" style="width: 220px">
          <el-option v-for="c in availableColumns" :key="c" :label="c" :value="c" />
        </el-select>
        <span v-if="lastResult" class="result-info">
          <i class="fas fa-database"></i> {{ lastResult.row_count }} 行
          <el-tag v-if="lastResult.from_cache" size="small" type="info" style="margin-left: 6px">缓存</el-tag>
        </span>
      </div>
    </el-card>

    <!-- 图表网格 -->
    <div class="chart-grid" :class="'g' + state.layoutCount" v-loading="executing">
      <div v-for="i in state.layoutCount" :key="i" class="chart-card">
        <div class="chart-card-toolbar">
          <span class="chart-title">图表 {{ i }}</span>
          <el-select v-model="chartAt(i - 1).xCol" placeholder="X轴" size="small" style="width: 110px" @change="renderChart(i - 1)">
            <el-option v-for="c in availableColumns" :key="c" :label="c" :value="c" />
          </el-select>
          <el-select v-model="chartAt(i - 1).yCols" multiple collapse-tags placeholder="Y轴" size="small" style="width: 150px" @change="renderChart(i - 1)">
            <el-option v-for="c in availableColumns" :key="c" :label="c" :value="c" />
          </el-select>
          <div class="type-btns">
            <button v-for="t in displayChartTypes" :key="t" class="type-btn" :class="{ active: chartAt(i - 1).chartType === t }"
              :title="t" @click="chartAt(i - 1).chartType = t; renderChart(i - 1)">{{ t }}</button>
          </div>
          <div class="toolbar-spacer"></div>
          <el-button size="small" text :icon="FullScreen" @click="openFullscreen(i - 1)" title="全屏" />
          <el-button v-if="chartAt(i - 1).chartType !== 'table'" size="small" text :icon="Camera" @click="saveChartImage(i - 1)" title="保存图片" />
          <el-button v-else size="small" text :icon="Download" @click="exportExcel(i - 1)" title="导出Excel" />
        </div>
        <div class="chart-body" :ref="el => setChartRef(i - 1, el)"></div>
      </div>
    </div>

    <!-- 脚本管理对话框 -->
    <el-dialog v-model="scriptDialogVisible" title="看板脚本管理" width="860px" top="5vh">
      <div class="script-manager">
        <div class="script-list">
          <div class="script-list-header">
            <span>脚本列表（{{ scripts.length }}）</span>
            <el-button size="small" type="primary" @click="newScript"><i class="fas fa-plus"></i> 新建</el-button>
          </div>
          <div class="script-items">
            <div v-for="s in scripts" :key="s.id" class="script-item" :class="{ active: editingScript?.id === s.id }" @click="editScript(s)">
              <i class="fas fa-file-code"></i> {{ s.name }}
            </div>
            <el-empty v-if="!scripts.length" description="暂无脚本" :image-size="60" />
          </div>
        </div>
        <div class="script-editor">
          <el-form label-width="80px" size="small">
            <el-form-item label="名称">
              <el-input v-model="scriptForm.name" placeholder="脚本名称" />
            </el-form-item>
            <el-form-item label="数据源">
              <el-select v-model="scriptForm.conn_name" placeholder="主数据源" clearable style="width: 100%">
                <el-option v-for="c in connections" :key="c.name" :label="c.name" :value="c.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="合并源">
              <el-select v-model="scriptForm.merge_conn_names" multiple placeholder="可多选（多源合并查询）" style="width: 100%">
                <el-option v-for="c in connections" :key="c.name" :label="c.name" :value="c.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="图表类型">
              <el-select v-model="scriptForm.chart_type" style="width: 100%">
                <el-option v-for="t in metaConfig.chart_types" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
            <el-form-item label="SQL">
              <el-input v-model="scriptForm.sql" type="textarea" :rows="9" placeholder="支持 {{start_date}} {{end_date}} {{date_format}} {{year}} {{month}} 等内置参数和自定义 {{参数}}" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="scriptForm.description" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
          <div class="script-editor-actions">
            <el-button v-if="editingScript?.id" type="danger" plain @click="deleteScript"><i class="fas fa-trash"></i> 删除</el-button>
            <div class="toolbar-spacer"></div>
            <el-button @click="scriptDialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="savingScript" @click="saveScript"><i class="fas fa-save"></i> 保存</el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- 保存快捷查询对话框 -->
    <el-dialog v-model="quickQueryDialogVisible" title="保存快捷查询" width="420px">
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="quickQueryName" placeholder="快捷查询名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickQueryDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingQuickQuery" @click="saveQuickQuery">保存</el-button>
      </template>
    </el-dialog>

    <!-- 全屏图表对话框 -->
    <el-dialog v-model="fullscreenVisible" :title="'图表 ' + (fullscreenIdx + 1)" width="92%" top="3vh" :close-on-click-modal="false">
      <div class="fullscreen-chart" ref="fullscreenChartRef"></div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { FullScreen, Camera, Download } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import * as XLSX from 'xlsx'
import api from '../api'
import { useAppStore } from '../stores'

const store = useAppStore()

const META_COLS = new Set(['_source', '_source_db'])
const DATE_KEYWORDS = ['日期', 'date', 'time', 'datetime', 'day', 'month', 'year', '时间']

const scripts = ref([])
const connections = ref([])
const quickQueries = ref([])
const metaConfig = ref({ chart_types: ['line', 'bar', 'area', 'pie', 'scatter', 'table'], dimensions: ['day', 'month', 'year'], settings: {} })
const customParamNames = ref([])
const executing = ref(false)
const lastResult = ref(null)
const drillStack = ref([])
// 初始即填充1个默认配置，避免首次渲染时模板访问 chartConfigs[0] 为 undefined 导致组件崩溃
const chartConfigs = ref([{ xCol: '', yCols: [], chartType: 'line' }])
const chartInstances = {}
const scriptDialogVisible = ref(false)
const quickQueryDialogVisible = ref(false)
const fullscreenVisible = ref(false)
const fullscreenIdx = ref(-1)
const fullscreenChartRef = ref(null)
const fullscreenInst = ref(null)
const savingScript = ref(false)
const savingQuickQuery = ref(false)
const quickQueryName = ref('')
const selectedQuickQueryId = ref(null)
const editingScript = ref(null)
const scriptForm = reactive({ name: '', sql: '', conn_name: '', merge_conn_names: [], chart_type: 'line', description: '' })
const chartBodyRefs = {}

const state = reactive({
  scriptId: null,
  connName: '',
  mergeNames: [],
  dimension: 'day',
  dateValue: '',
  startYear: '',
  endYear: '',
  customParams: {},
  mergeMode: 'separate',
  mergeKey: '',
  hideFields: [],
  layoutCount: 1,
})

const maxLayoutCount = computed(() => metaConfig.value.settings?.max_chart_count || 4)
const displayChartTypes = computed(() => ['line', 'bar', 'area', 'pie', 'scatter', 'table', 'mix'])
const currentScript = computed(() => scripts.value.find(s => s.id === state.scriptId) || null)

const scriptConnections = computed(() => {
  if (!currentScript.value) return connections.value
  const names = [currentScript.value.conn_name, ...(currentScript.value.merge_conn_names || [])].filter(Boolean)
  if (!names.length) return connections.value
  const filtered = connections.value.filter(c => names.includes(c.name))
  return filtered.length ? filtered : connections.value
})

const availableColumns = computed(() => {
  if (!lastResult.value) return []
  return lastResult.value.columns.filter(c => !META_COLS.has(c))
})

// 模板安全访问图表配置：索引越界时自动补全默认配置，杜绝 undefined.xxx 崩溃
function chartAt(idx) {
  if (!chartConfigs.value[idx]) {
    chartConfigs.value[idx] = { xCol: '', yCols: [], chartType: 'line' }
  }
  return chartConfigs.value[idx]
}

function setChartRef(idx, el) {
  if (el) chartBodyRefs[idx] = el
  else delete chartBodyRefs[idx] // 元素卸载时清除引用，避免持有已销毁 DOM
}

// ── 数据加载 ──

async function loadMeta() {
  try {
    const res = await api.dataDashboard.getMetaConfig()
    if (res.success) metaConfig.value = { ...metaConfig.value, ...res.data }
  } catch (e) { /* ignore */ }
}

async function loadScripts() {
  try {
    const res = await api.dataDashboard.listScripts()
    scripts.value = res.data || []
  } catch (e) {
    scripts.value = []
  }
}

async function loadConnections() {
  try {
    const res = await api.dataDashboard.listConnections()
    connections.value = res.data || []
  } catch (e) {
    connections.value = []
  }
}

async function loadQuickQueries() {
  try {
    const res = await api.dataDashboard.listQuickQueries()
    quickQueries.value = res.data || []
  } catch (e) {
    quickQueries.value = []
  }
}

// ── 脚本变更 ──

async function onScriptChange() {
  const s = currentScript.value
  if (!s) return
  state.connName = s.conn_name || ''
  state.mergeNames = [...(s.merge_conn_names || [])]
  state.customParams = {}
  drillStack.value = []
  try {
    const res = await api.dataDashboard.parseParams({ sql: s.sql })
    customParamNames.value = res.data?.custom || []
  } catch (e) { customParamNames.value = [] }
}

function onDimensionChange() {
  state.dateValue = ''
  state.startYear = ''
  state.endYear = ''
}

// ── 执行查询 ──

function buildExecuteBody(forceRefresh) {
  const s = currentScript.value
  if (!s) return null
  const body = {
    sql: s.sql,
    conn_name: state.connName,
    merge_conn_names: state.mergeNames,
    dimension: state.dimension,
    custom_params: { ...state.customParams },
    chart_type: s.chart_type || 'line',
    merge_mode: state.mergeMode,
    merge_key: state.mergeKey,
    hide_fields: state.hideFields,
    force_refresh: !!forceRefresh,
  }
  if (state.dimension === 'day' && state.dateValue) body.date = state.dateValue + '-01'
  else if (state.dimension === 'month' && state.dateValue) body.date = state.dateValue + '-01-01'
  else if (state.dimension === 'year') {
    if (state.startYear) body.start_year = parseInt(state.startYear)
    if (state.endYear) body.end_year = parseInt(state.endYear)
  }
  return body
}

async function execute(forceRefresh = false, drillOverride = null) {
  const s = currentScript.value
  if (!s) return ElMessage.warning('请先选择查询脚本')
  if (!state.connName && !state.mergeNames.length) return ElMessage.warning('请选择数据源')
  const body = buildExecuteBody(forceRefresh)
  if (!body) return
  if (drillOverride) {
    body.dimension = drillOverride.dimension
    body.drill_start_date = drillOverride.start_date
    body.drill_end_date = drillOverride.end_date
    body.date = ''
    body.start_year = null
    body.end_year = null
  }
  executing.value = true
  try {
    const res = await api.dataDashboard.execute(body)
    if (!res.success) return ElMessage.error(res.message || '查询失败')
    lastResult.value = res.data
    if (!drillOverride) { drillStack.value = [] }
    autoAssignColumns()
    await nextTick()
    renderAllCharts()
  } catch (e) {
    // axios 拦截器已提示
  } finally {
    executing.value = false
  }
}

function autoAssignColumns() {
  const cols = availableColumns.value
  if (!cols.length) return
  const xCol = cols.find(c => DATE_KEYWORDS.some(k => c.toLowerCase().includes(k))) || cols[0]
  const yAll = cols.filter(c => c !== xCol)
  const perChart = Math.max(1, Math.ceil(yAll.length / state.layoutCount))
  const defaultTypes = ['line', 'bar', 'area', 'pie']
  ensureChartConfigs()
  for (let i = 0; i < state.layoutCount; i++) {
    const cfg = chartConfigs.value[i]
    cfg.xCol = xCol
    const slice = yAll.slice(i * perChart, i * perChart + perChart)
    cfg.yCols = slice.length ? slice : yAll
    cfg.chartType = currentScript.value?.chart_type || defaultTypes[i % defaultTypes.length]
    if (cfg.chartType === 'table' && i > 0) cfg.chartType = defaultTypes[i % defaultTypes.length]
  }
}

function ensureChartConfigs() {
  while (chartConfigs.value.length < state.layoutCount) {
    chartConfigs.value.push({ xCol: '', yCols: [], chartType: 'line' })
  }
  chartConfigs.value.length = state.layoutCount
}

watch(() => state.layoutCount, () => {
  ensureChartConfigs()
  // 布局数量缩小时，dispose 超出范围的图表实例，防止泄漏
  Object.keys(chartInstances).forEach(k => {
    if (+k >= state.layoutCount) { chartInstances[k].dispose(); delete chartInstances[k] }
  })
})

// ── 图表渲染 ──

function isDark() {
  try {
    const bg = getComputedStyle(document.body).backgroundColor
    const m = bg.match(/\d+/g)
    if (m && m.length >= 3) {
      const lum = 0.299 * +m[0] + 0.587 * +m[1] + 0.114 * +m[2]
      return lum < 128
    }
  } catch (e) { /* ignore */ }
  return store.theme === 'dark'
}

function themeVars() {
  const dark = isDark()
  return dark
    ? { text: '#e5e7eb', textDim: '#9ca3af', axis: '#374151', split: 'rgba(255,255,255,0.08)', bg: '#1f2937', tipBg: '#111827', tipBorder: '#374151' }
    : { text: '#1f2937', textDim: '#6b7280', axis: '#d1d5db', split: 'rgba(0,0,0,0.06)', bg: '#ffffff', tipBg: '#ffffff', tipBorder: '#e5e7eb' }
}

const COLORS = ['#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de', '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc']

function parseNum(v) {
  if (typeof v === 'number') return v
  if (v == null) return NaN
  return parseFloat(String(v).replace(/[%％,，\s]/g, ''))
}
function isPctCol(vals) {
  let pct = 0
  for (const v of vals) { const s = String(v); if (s.includes('%') || s.includes('％')) pct++ }
  return pct > vals.length * 0.4
}
function _sfix(n) { if (n >= 100) return Math.round(n).toString(); if (n >= 10) return n.toFixed(1).replace(/\.0$/, ''); return n.toFixed(2).replace(/\.?0+$/, '') }
function fmtNum(v) {
  if (v == null || v === '') return ''
  const n = typeof v === 'number' ? v : parseNum(v)
  if (isNaN(n)) return String(v)
  const abs = Math.abs(n)
  if (abs < 1e4) return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  const sign = n < 0 ? '-' : ''
  if (abs >= 1e8) return sign + _sfix(abs / 1e8) + '亿'
  if (abs >= 1e7) return sign + _sfix(abs / 1e7) + '千万'
  if (abs >= 1e6) return sign + _sfix(abs / 1e6) + '百万'
  return sign + _sfix(abs / 1e4) + '万'
}

function buildChartOption(result, cfg) {
  const { columns, rows } = result
  if (!rows || !rows.length || !cfg.xCol || !cfg.yCols?.length) return null
  const xData = rows.map(r => String(r[columns.indexOf(cfg.xCol)]))
  const numericCols = cfg.yCols.filter(col => {
    const idx = columns.indexOf(col); if (idx < 0) return false
    const vals = rows.map(r => r[idx])
    return vals.filter(v => !isNaN(parseNum(v))).length > vals.length * 0.3
  })
  if (!numericCols.length) return null

  const pctCols = new Set()
  numericCols.forEach(col => {
    const idx = columns.indexOf(col)
    if (isPctCol(rows.map(r => r[idx]))) pctCols.add(col)
  })
  const absCols = numericCols.filter(c => !pctCols.has(c))
  const hasDual = absCols.length > 0 && pctCols.size > 0
  const T = themeVars()
  const chartType = cfg.chartType
  const seriesFullData = {}
  numericCols.forEach(col => {
    const idx = columns.indexOf(col)
    seriesFullData[col] = rows.map(r => { const v = parseNum(r[idx]); return isNaN(v) ? 0 : v })
  })

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: ['pie', 'funnel', 'gauge'].includes(chartType) ? 'item' : 'axis',
      backgroundColor: T.tipBg, borderColor: T.tipBorder, textStyle: { color: T.text, fontSize: 12 }, borderWidth: 1,
      formatter: ['pie', 'funnel', 'gauge'].includes(chartType)
        ? (p) => p ? `<b>${p.name}</b><br/>${p.marker}${fmtNum(parseNum(p.value))}${pctCols.size ? '%' : ''}` : ''
        : (params) => {
            if (!Array.isArray(params)) params = [params]
            let tip = `<b>${params[0].axisValue}</b><br/>`
            params.forEach(p => {
              const isPct = pctCols.has(p.seriesName)
              const curVal = parseNum(p.value)
              tip += `${p.marker}${p.seriesName}: <b>${isPct ? curVal : fmtNum(curVal)}${isPct ? '%' : ''}</b><br/>`
            })
            return tip
          },
    },
    animation: metaConfig.value.settings?.animation_enabled !== false,
  }

  if (chartType === 'pie') {
    const col = numericCols[0]
    const vals = rows.map(r => { const v = parseNum(r[columns.indexOf(col)]); return isNaN(v) ? 0 : v })
    option.series = [{ type: 'pie', radius: ['30%', '65%'], center: ['50%', '55%'],
      data: xData.map((n, i) => ({ name: n, value: vals[i] })),
      label: { color: T.textDim, fontSize: 11 }, itemStyle: { borderRadius: 6, borderColor: T.bg, borderWidth: 2 } }]
  } else if (chartType === 'radar') {
    const indicators = xData.map(n => ({ name: n, max: 0 }))
    numericCols.forEach(col => {
      seriesFullData[col].forEach((v, i) => { if (v > indicators[i].max) indicators[i].max = Math.ceil(v * 1.2) || 100 })
    })
    option.radar = { indicator: indicators, shape: 'polygon', axisName: { color: T.textDim, fontSize: 10 }, splitLine: { lineStyle: { color: T.axis } } }
    option.series = [{ type: 'radar', data: numericCols.map((col, idx) => ({ name: col, value: seriesFullData[col], lineStyle: { color: COLORS[idx % COLORS.length] }, itemStyle: { color: COLORS[idx % COLORS.length] } })) }]
  } else if (chartType === 'gauge') {
    const col = numericCols[0]
    const vals = seriesFullData[col]
    const maxVal = Math.max(...vals) * 1.2 || 100
    const avgVal = vals.reduce((a, b) => a + b, 0) / (vals.length || 1)
    option.series = [{ type: 'gauge', min: 0, max: maxVal, detail: { formatter: v => fmtNum(v), color: T.text }, data: [{ value: avgVal, name: col }], title: { color: T.textDim } }]
  } else if (chartType === 'funnel') {
    const col = numericCols[0]
    const vals = seriesFullData[col]
    option.series = [{ type: 'funnel', left: '10%', width: '80%', sort: 'descending', gap: 4,
      label: { show: true, position: 'inside', color: '#fff', fontSize: 11 },
      data: xData.map((n, i) => ({ name: n, value: vals[i] })).sort((a, b) => b.value - a.value) }]
  } else {
    option.grid = { left: '3%', right: hasDual ? '8%' : '4%', top: 40, bottom: '3%', containLabel: true }
    option.xAxis = { type: 'category', data: xData, axisLine: { lineStyle: { color: T.axis } },
      axisLabel: { color: T.textDim, rotate: xData.length > 10 ? 30 : 0, fontSize: 10 }, boundaryGap: chartType === 'bar' || chartType === 'mix' }
    option.yAxis = hasDual
      ? [
          { type: 'value', axisLabel: { color: T.textDim, formatter: v => fmtNum(v) }, splitLine: { lineStyle: { color: T.split, type: 'dashed' } } },
          { type: 'value', name: '百分比', axisLabel: { color: T.textDim, formatter: '{value}%' }, splitLine: { show: false } },
        ]
      : { type: 'value', axisLabel: { color: T.textDim, formatter: pctCols.size ? '{value}%' : (v => fmtNum(v)) }, splitLine: { lineStyle: { color: T.split, type: 'dashed' } } }
    option.legend = { data: numericCols, top: 4, textStyle: { color: T.textDim, fontSize: 10 } }
    if (rows.length > 15) option.dataZoom = [{ type: 'inside', start: 0, end: 60 }]

    option.series = numericCols.map((col, idx) => {
      const color = COLORS[idx % COLORS.length]
      const isPct = pctCols.has(col)
      const yAxisIndex = hasDual && isPct ? 1 : 0
      const yData = seriesFullData[col]
      const base = { name: col, data: yData, yAxisIndex, itemStyle: { color } }
      if (chartType === 'bar') return { ...base, type: 'bar', barMaxWidth: 36, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color }, { offset: 1, color: color + '44' }] }, borderRadius: [4, 4, 0, 0] } }
      if (chartType === 'area') return { ...base, type: 'line', smooth: 0.4, showSymbol: rows.length < 40, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '66' }, { offset: 1, color: color + '05' }] } } }
      if (chartType === 'scatter') return { ...base, type: 'scatter', symbolSize: 9 }
      if (chartType === 'mix') return isPct
        ? { ...base, type: 'line', smooth: 0.35, showSymbol: rows.length < 40 }
        : { ...base, type: 'bar', barMaxWidth: 36, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color }, { offset: 1, color: color + '44' }] }, borderRadius: [4, 4, 0, 0] } }
      return { ...base, type: 'line', smooth: 0.35, showSymbol: rows.length < 40, lineStyle: { width: 2.5 } }
    })
  }
  return option
}

function renderChart(idx) {
  const el = chartBodyRefs[idx]
  const cfg = chartConfigs.value[idx]
  if (!el || !cfg || !lastResult.value) return
  if (chartInstances[idx]) { chartInstances[idx].dispose(); delete chartInstances[idx] }

  if (cfg.chartType === 'table') {
    el.innerHTML = buildTableHtml(lastResult.value, cfg)
    return
  }
  el.innerHTML = ''
  const inst = echarts.init(el)
  chartInstances[idx] = inst
  const option = buildChartOption(lastResult.value, cfg)
  if (option) {
    inst.setOption(option, true)
    inst.off('dblclick')
    inst.on('dblclick', (params) => handleDrill(idx, params))
  } else {
    inst.clear()
  }
}

function renderAllCharts() {
  ensureChartConfigs()
  nextTick(() => {
    for (let i = 0; i < state.layoutCount; i++) renderChart(i)
    setTimeout(() => Object.values(chartInstances).forEach(c => c.resize()), 100)
  })
}

function escapeHtml(v) {
  return String(v)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function buildTableHtml(result, cfg) {
  const { columns, rows } = result
  if (!rows?.length) return '<div class="empty-hint">暂无数据</div>'
  const displayCols = [cfg.xCol, ...cfg.yCols.filter(c => columns.includes(c))]
  const pctCols = new Set()
  cfg.yCols.forEach(col => {
    const idx = columns.indexOf(col); if (idx < 0) return
    if (isPctCol(rows.map(r => r[idx]))) pctCols.add(col)
  })
  let html = '<div class="table-wrap"><table class="data-table"><thead><tr>'
  displayCols.forEach(col => { html += `<th>${escapeHtml(col)}</th>` })
  html += '</tr></thead><tbody>'
  rows.forEach(row => {
    html += '<tr>'
    displayCols.forEach((col, ci) => {
      const idx = columns.indexOf(col)
      const raw = idx >= 0 ? row[idx] : ''
      const numV = parseNum(raw)
      const isNum = !isNaN(numV) && ci > 0
      if (ci === 0) html += `<td>${raw != null ? escapeHtml(raw) : ''}</td>`
      else if (pctCols.has(col)) html += `<td class="pct">${raw != null ? escapeHtml(raw) : ''}</td>`
      else if (isNum) html += `<td class="num">${escapeHtml(fmtNum(numV))}</td>`
      else html += `<td>${raw != null ? escapeHtml(raw) : ''}</td>`
    })
    html += '</tr>'
  })
  html += '</tbody></table></div>'
  return html
}

// ── 钻取 ──

function detectXColDimension(xData) {
  const sample = xData[0] || ''
  if (/^\d{4}$/.test(sample)) return 'year'
  if (/^\d{4}[-/]\d{1,2}$/.test(sample)) return 'month'
  return 'day'
}

function handleDrill(idx, params) {
  const cfg = chartConfigs.value[idx]
  if (!cfg || !lastResult.value || cfg.chartType === 'table') return
  const xData = lastResult.value.rows.map(r => String(r[lastResult.value.columns.indexOf(cfg.xCol)]))
  const dim = detectXColDimension(xData)
  const clicked = String(params.name ?? '')
  let targetDim = null, startDate = '', endDate = '', label = ''

  if (dim === 'year') {
    targetDim = 'month'; label = clicked + '年'
    startDate = clicked + '-01-01'; endDate = clicked + '-12-31'
  } else if (dim === 'month') {
    const [y, m] = clicked.split(/[-/]/)
    targetDim = 'day'; label = clicked
    startDate = `${y}-${m.padStart(2, '0')}-01`
    const lastDay = new Date(+y, +m, 0).getDate()
    endDate = `${y}-${m.padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`
  } else return

  drillStack.value.push({ dimension: state.dimension, label: label, start_date: startDate, end_date: endDate })
  state.dimension = targetDim
  execute(false, { dimension: targetDim, start_date: startDate, end_date: endDate })
}

function drillTo(index) {
  if (index === drillStack.value.length - 1) return
  const target = drillStack.value[index]
  drillStack.value = drillStack.value.slice(0, index)
  execute(false, { dimension: target.dimension, start_date: target.start_date, end_date: target.end_date })
}

function drillUp() {
  if (!drillStack.value.length) return
  drillStack.value.pop()
  if (drillStack.value.length) {
    const prev = drillStack.value[drillStack.value.length - 1]
    execute(false, { dimension: prev.dimension, start_date: prev.start_date, end_date: prev.end_date })
  } else {
    state.dimension = state.dimension
    execute(false)
  }
}

// ── 导出 / 截图 ──

function saveChartImage(idx) {
  const inst = chartInstances[idx]
  if (!inst) return ElMessage.warning('当前无图表可保存')
  const url = inst.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: themeVars().bg })
  const a = document.createElement('a')
  a.href = url; a.download = `chart_${idx + 1}_${Date.now()}.png`
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  ElMessage.success('图片已保存')
}

function exportExcel(idx) {
  if (!lastResult.value) return ElMessage.warning('无数据可导出')
  const cfg = chartConfigs.value[idx]
  if (!cfg) return
  const { columns, rows } = lastResult.value
  const displayCols = [cfg.xCol, ...cfg.yCols.filter(c => columns.includes(c))]
  const filterCols = displayCols.length ? displayCols : columns
  const data = rows.map(r => filterCols.map(c => { const i = columns.indexOf(c); return i >= 0 ? r[i] : '' }))
  const ws = XLSX.utils.aoa_to_sheet([filterCols, ...data])
  ws['!cols'] = filterCols.map(() => ({ wch: 16 }))
  const wb = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(wb, ws, '数据')
  XLSX.writeFile(wb, `dashboard_${idx + 1}_${Date.now()}.xlsx`)
  ElMessage.success('Excel已导出')
}

function openFullscreen(idx) {
  fullscreenIdx.value = idx
  fullscreenVisible.value = true
  nextTick(() => {
    if (!fullscreenChartRef.value || !lastResult.value) return
    if (fullscreenInst.value) { fullscreenInst.value.dispose(); fullscreenInst.value = null }
    const cfg = chartConfigs.value[idx]
    if (!cfg) return
    if (cfg.chartType === 'table') {
      fullscreenChartRef.value.innerHTML = buildTableHtml(lastResult.value, cfg)
      return
    }
    fullscreenChartRef.value.innerHTML = ''
    fullscreenInst.value = echarts.init(fullscreenChartRef.value)
    const option = buildChartOption(lastResult.value, cfg)
    if (option) fullscreenInst.value.setOption(option, true)
  })
}
watch(fullscreenVisible, (v) => { if (!v && fullscreenInst.value) { fullscreenInst.value.dispose(); fullscreenInst.value = null } })

// ── 脚本管理 ──

function newScript() {
  editingScript.value = null
  Object.assign(scriptForm, { name: '', sql: '', conn_name: '', merge_conn_names: [], chart_type: 'line', description: '' })
}

function editScript(s) {
  editingScript.value = s
  Object.assign(scriptForm, {
    name: s.name, sql: s.sql, conn_name: s.conn_name,
    merge_conn_names: [...(s.merge_conn_names || [])],
    chart_type: s.chart_type || 'line', description: s.description || '',
  })
}

async function saveScript() {
  if (!scriptForm.name || !scriptForm.sql) return ElMessage.warning('请填写名称和SQL')
  savingScript.value = true
  try {
    if (editingScript.value?.id) {
      const res = await api.dataDashboard.updateScript(editingScript.value.id, scriptForm)
      if (!res.success) return ElMessage.error(res.message)
      ElMessage.success('已更新')
    } else {
      const res = await api.dataDashboard.createScript(scriptForm)
      if (!res.success) return ElMessage.error(res.message)
      ElMessage.success('已创建')
    }
    await loadScripts()
    scriptDialogVisible.value = false
  } catch (e) { /* interceptor */ } finally { savingScript.value = false }
}

async function deleteScript() {
  if (!editingScript.value?.id) return
  try {
    await ElMessageBox.confirm(`确定删除脚本 '${editingScript.value.name}'？`, '提示', { type: 'warning' })
  } catch (e) { return }
  try {
    const res = await api.dataDashboard.deleteScript(editingScript.value.id)
    if (res.success) {
      ElMessage.success('已删除')
      newScript()
      await loadScripts()
    }
  } catch (e) { /* interceptor */ }
}

// ── 快捷查询 ──

function openSaveQuickQuery() {
  if (!currentScript.value) return ElMessage.warning('请先选择脚本并执行查询')
  quickQueryName.value = ''
  quickQueryDialogVisible.value = true
}

async function saveQuickQuery() {
  if (!quickQueryName.value) return ElMessage.warning('请输入名称')
  savingQuickQuery.value = true
  try {
    const payload = {
      name: quickQueryName.value,
      script_name: currentScript.value.name,
      conn_name: state.connName,
      merge_names: state.mergeNames,
      merge_mode: state.mergeMode,
      merge_key: state.mergeKey,
      hide_fields: state.hideFields,
      dimension: state.dimension,
      dp_year: state.startYear ? parseInt(state.startYear) : null,
      dp_year_end: state.endYear ? parseInt(state.endYear) : null,
      custom_params: state.customParams,
      layout_count: state.layoutCount,
      chart_configs: chartConfigs.value.map(c => ({ xCol: c.xCol, yCols: c.yCols, chartType: c.chartType })),
    }
    const res = await api.dataDashboard.createQuickQuery(payload)
    if (!res.success) return ElMessage.error(res.message)
    ElMessage.success('快捷查询已保存')
    quickQueryDialogVisible.value = false
    await loadQuickQueries()
  } catch (e) { /* interceptor */ } finally { savingQuickQuery.value = false }
}

function onQuickQueryChange(id) {
  const q = quickQueries.value.find(x => x.id === id)
  if (!q) return
  const script = scripts.value.find(s => s.name === q.script_name)
  if (!script) return ElMessage.warning(`关联脚本 '${q.script_name}' 不存在`)
  state.scriptId = script.id
  state.connName = q.conn_name
  state.mergeNames = [...(q.merge_names || [])]
  state.mergeMode = q.merge_mode || 'separate'
  state.mergeKey = q.merge_key || ''
  state.hideFields = [...(q.hide_fields || [])]
  state.dimension = q.dimension || 'day'
  state.customParams = { ...(q.custom_params || {}) }
  state.layoutCount = q.layout_count || 1
  if (q.chart_configs?.length) {
    chartConfigs.value = q.chart_configs.map(c => ({ xCol: c.xCol, yCols: [...(c.yCols || [])], chartType: c.chartType }))
    ensureChartConfigs()
  }
  nextTick(() => execute())
}

// ── 生命周期 ──

function handleResize() {
  Object.values(chartInstances).forEach(c => c.resize())
  if (fullscreenInst.value) fullscreenInst.value.resize()
}

// 统一清理所有 echarts 实例（失活/卸载共用）
function disposeAllCharts() {
  Object.keys(chartInstances).forEach(k => { chartInstances[k].dispose(); delete chartInstances[k] })
  if (fullscreenInst.value) { fullscreenInst.value.dispose(); fullscreenInst.value = null }
}

onMounted(async () => {
  ensureChartConfigs()
  window.addEventListener('resize', handleResize)
  await Promise.all([loadMeta(), loadConnections(), loadQuickQueries(), loadScripts()])
})

// 本应用所有路由页面被 Layout.vue 的 keep-alive 缓存：
// 切走时 onBeforeUnmount 不会触发，必须用 onDeactivated 清理资源，
// 否则 resize 监听器与 echarts 实例永久泄漏
onDeactivated(() => {
  window.removeEventListener('resize', handleResize)
  disposeAllCharts()
})

// 从缓存切回：DOM 已恢复但 echarts 实例已 dispose，需重新渲染并恢复监听
onActivated(() => {
  window.addEventListener('resize', handleResize)
  if (lastResult.value) renderAllCharts()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  disposeAllCharts()
})
</script>

<style scoped>
.data-dashboard { padding: 4px; display: flex; flex-direction: column; gap: 12px; }
.toolbar-row, .layout-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.merge-row { display: flex; align-items: center; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.merge-label, .layout-label { color: var(--el-text-color-secondary); font-size: 13px; }
.toolbar-spacer { flex: 1; }
.result-info { margin-left: auto; color: var(--el-text-color-secondary); font-size: 13px; }

.drill-breadcrumb { display: flex; align-items: center; gap: 6px; padding: 8px 12px; background: var(--el-bg-color); border-radius: 8px; border: 1px solid var(--el-border-color-lighter); }
.drill-chip { padding: 3px 10px; background: var(--el-color-primary-light-9); color: var(--el-color-primary); border-radius: 12px; font-size: 12px; cursor: pointer; }
.drill-chip:hover { opacity: 0.8; }

.chart-grid { display: grid; gap: 12px; }
.chart-grid.g1 { grid-template-columns: 1fr; }
.chart-grid.g2 { grid-template-columns: repeat(2, 1fr); }
.chart-grid.g3 { grid-template-columns: repeat(3, 1fr); }
.chart-grid.g4 { grid-template-columns: repeat(2, 1fr); }

.chart-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-lighter); border-radius: 8px; padding: 10px; display: flex; flex-direction: column; }
.chart-card-toolbar { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; flex-wrap: wrap; }
.chart-title { font-weight: 600; font-size: 13px; color: var(--el-text-color-primary); margin-right: 4px; }
.type-btns { display: flex; gap: 2px; }
.type-btn { border: 1px solid var(--el-border-color); background: transparent; color: var(--el-text-color-secondary); padding: 2px 7px; font-size: 11px; cursor: pointer; border-radius: 4px; }
.type-btn.active { background: var(--el-color-primary); color: #fff; border-color: var(--el-color-primary); }
.chart-body { flex: 1; min-height: 320px; width: 100%; }
.empty-hint { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--el-text-color-placeholder); }

.table-wrap { overflow: auto; max-height: 420px; }
.data-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.data-table th, .data-table td { border: 1px solid var(--el-border-color-lighter); padding: 6px 8px; text-align: left; white-space: nowrap; }
.data-table th { background: var(--el-fill-color-light); position: sticky; top: 0; }
.data-table td.num, .data-table td.pct { text-align: right; font-variant-numeric: tabular-nums; }
.data-table td.pct { color: var(--el-color-success); }

.script-manager { display: flex; gap: 16px; }
.script-list { width: 220px; border-right: 1px solid var(--el-border-color-lighter); padding-right: 12px; }
.script-list-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; font-weight: 600; }
.script-items { max-height: 460px; overflow: auto; display: flex; flex-direction: column; gap: 4px; }
.script-item { padding: 8px 10px; border-radius: 6px; cursor: pointer; font-size: 13px; }
.script-item:hover { background: var(--el-fill-color-light); }
.script-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.script-editor { flex: 1; }
.script-editor-actions { display: flex; gap: 8px; margin-top: 8px; }

.fullscreen-chart { width: 100%; height: 72vh; min-height: 480px; }
</style>
