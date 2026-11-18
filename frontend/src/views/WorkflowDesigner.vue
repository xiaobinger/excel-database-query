<template>
  <div class="wf-page">
    <div class="wf-header">
      <div class="wf-title">
        <i class="fa fa-project-diagram"></i>
        <input v-if="current" v-model="current.name" class="wf-name-input" @input="dirty = true" />
        <span v-else class="wf-muted">混合工作流</span>
        <el-tag v-if="dirty" size="small" type="warning">未保存</el-tag>
      </div>
      <div class="wf-actions">
        <el-button size="small" @click="newWorkflow"><i class="fa fa-plus"></i> 新建</el-button>
        <el-button size="small" type="primary" :disabled="!current" @click="saveWorkflow"><i class="fa fa-save"></i> 保存</el-button>
        <el-button size="small" type="success" :disabled="!current" @click="openRunDialog"><i class="fa fa-play"></i> 一键运行</el-button>
        <el-button size="small" @click="openRunsDrawer"><i class="fa fa-history"></i> 执行记录</el-button>
        <el-button size="small" @click="openVariables"><i class="fa fa-code"></i> 变量</el-button>
        <el-button v-if="activeRun && isRunActive" size="small" type="danger" plain @click="cancelActiveRun">取消运行</el-button>
      </div>
    </div>

    <div class="wf-body">
      <aside class="wf-side">
        <div class="wf-side-section">
          <div class="wf-side-title">工作流</div>
          <el-input v-model="searchKeyword" size="small" placeholder="搜索工作流" clearable />
          <div class="wf-wf-list">
            <div v-for="w in filteredWorkflows" :key="w.id" class="wf-wf-item"
                 :class="{ active: current && current.id === w.id }" @click="loadWorkflow(w.id)">
              <div class="wf-wf-name">{{ w.name }}</div>
              <div class="wf-wf-meta">{{ w.node_count || 0 }} 个节点 · {{ w.is_enabled ? '启用' : '禁用' }}</div>
              <i class="fa fa-trash wf-wf-del" title="删除" @click.stop="removeWorkflow(w)"></i>
            </div>
            <el-empty v-if="!filteredWorkflows.length" description="暂无工作流" :image-size="60" />
          </div>
        </div>

        <div class="wf-side-section wf-palette-section">
          <div class="wf-side-title">节点面板 <span class="wf-tip">拖拽或点击添加</span></div>
          <div class="wf-palette">
            <div v-for="t in paletteTypes" :key="t" class="wf-palette-item" draggable="true"
                 @dragstart="onPaletteDragStart($event, t)" @click="addNodeAtCenter(t)">
              <span class="wf-palette-icon" :style="{ background: meta(t).color }"><i :class="['fa', meta(t).icon]"></i></span>
              <span>{{ meta(t).label }}</span>
            </div>
          </div>
        </div>

        <div class="wf-side-section">
          <div class="wf-side-title">运行图例</div>
          <div class="wf-legend">
            <span><i class="legend-dot running"></i>执行中</span>
            <span><i class="legend-dot success"></i>成功</span>
            <span><i class="legend-dot failed"></i>失败</span>
            <span><i class="legend-dot waiting"></i>待审批</span>
          </div>
        </div>
      </aside>

      <main ref="canvasRef" class="wf-canvas" @mousedown="onCanvasMouseDown" @wheel.prevent="onWheel"
            @dragover.prevent @drop="onDrop">
        <div class="wf-world" :style="worldStyle">
          <svg class="wf-edges" width="6000" height="4000">
            <defs>
              <marker id="wf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
              </marker>
            </defs>
            <g v-for="edge in graph.edges" :key="edge.id">
              <path class="wf-edge-hit" :d="edgePath(edge)" @mousedown.stop="selectEdge(edge)"></path>
              <path class="wf-edge" :class="edgeClass(edge)" :d="edgePath(edge)" marker-end="url(#wf-arrow)"></path>
              <text v-if="edge.branch && edge.branch !== 'default'" class="wf-edge-label"
                    :x="edgeLabelPos(edge).x" :y="edgeLabelPos(edge).y">{{ branchLabel(edge.branch) }}</text>
            </g>
            <g v-for="node in loopNodes" :key="'loop-' + node.id">
              <path class="wf-edge wf-self-loop" :class="{ active: nodeStatus[node.id] === 'running' }"
                    :d="selfLoopPath(node)" marker-end="url(#wf-arrow)"></path>
              <text class="wf-edge-label wf-loop-label" :x="node.x + 232" :y="node.y + 44">{{ loopLabel(node) }}</text>
            </g>
            <path v-if="connecting" class="wf-edge temp" :d="connectingPath"></path>
            <line v-if="guides.x !== null" class="wf-guide" :x1="guides.x" y1="0" :x2="guides.x" y2="4000" />
            <line v-if="guides.y !== null" class="wf-guide" x1="0" :y1="guides.y" x2="6000" :y2="guides.y" />
          </svg>

          <div v-for="node in graph.nodes" :key="node.id" class="wf-node" :class="nodeClass(node)"
               :data-node-id="node.id"
               :title="nodeTitle(node)"
               :style="{ left: node.x + 'px', top: node.y + 'px' }"
               @mousedown.stop="startNodeDrag($event, node)">
            <div class="wf-node-icon" :style="{ background: meta(node.type).color }">
              <i :class="['fa', meta(node.type).icon]"></i>
            </div>
            <div class="wf-node-body">
              <div class="wf-node-name">{{ node.name }}</div>
              <div class="wf-node-sub">
                {{ meta(node.type).label }}<span v-if="node.output_key"> → {{ node.output_key }}</span>
              </div>
            </div>
            <span class="wf-port" title="拖拽到目标节点连线" @mousedown.stop="startConnect($event, node)"></span>
            <span v-if="nodeStatus[node.id] === 'completed'" class="wf-node-badge ok"><i class="fa fa-check"></i></span>
            <span v-else-if="nodeStatus[node.id] === 'failed'" class="wf-node-badge bad"><i class="fa fa-times"></i></span>
            <span v-else-if="nodeStatus[node.id] === 'waiting_approval'" class="wf-node-badge wait"><i class="fa fa-user-clock"></i></span>
            <div v-if="nodeError(node.id)" class="wf-node-error" @mousedown.stop @click.stop="openRunsDrawer">
              <i class="fa fa-exclamation-circle"></i>
              <span>{{ nodeError(node.id) }}</span>
            </div>
          </div>
        </div>

        <div class="wf-canvas-toolbar">
          <el-button-group>
            <el-button size="small" @click="zoomBy(-0.1)"><i class="fa fa-minus"></i></el-button>
            <el-button size="small" @click="resetView">{{ Math.round(scale * 100) }}%</el-button>
            <el-button size="small" @click="zoomBy(0.1)"><i class="fa fa-plus"></i></el-button>
          </el-button-group>
          <span class="wf-canvas-hint">空白处拖拽框选 · Ctrl/Shift 加选 · Alt+拖拽或中键平移</span>
        </div>

        <div v-if="boxRect" class="wf-select-box" :style="boxRect"></div>

        <div v-if="activeRun && activeRun.status === 'waiting_approval'" class="wf-approval-bar">
          <div class="wf-approval-main">
            <div class="wf-approval-title"><i class="fa fa-user-clock"></i> 待审批：{{ activeRun.pending_approval?.node_name }}</div>
            <div class="wf-approval-msg">{{ activeRun.pending_approval?.message }}</div>
          </div>
          <el-input v-model="approvalComment" size="small" placeholder="审批意见（可选）" style="width: 220px" />
          <el-button size="small" type="success" @click="submitApproval(true)">通过</el-button>
          <el-button size="small" type="danger" @click="submitApproval(false)">拒绝</el-button>
        </div>

        <div v-if="activeRun" class="wf-run-status" :class="'st-' + activeRun.status">
          <i :class="['fa', runStatusIcon]"></i> {{ runStatusText }}
          <span v-if="activeRun.current_node_id" class="wf-run-node">当前节点：{{ nodeName(activeRun.current_node_id) }}</span>
          <span class="wf-run-id">{{ activeRun.run_id.slice(0, 8) }}</span>
        </div>

        <div v-if="!current" class="wf-empty-canvas">
          <i class="fa fa-project-diagram"></i>
          <p>选择左侧工作流，或新建一个混合工作流开始编排</p>
        </div>
      </main>

      <aside class="wf-props">
        <div v-if="selectedNodeIds.length > 1" class="wf-multi-tip">
          <i class="fa fa-object-group"></i> 已选择 {{ selectedNodeIds.length }} 个节点，拖拽任一节点可整体移动
        </div>
        <div v-if="selectedNode" class="wf-props-inner">
          <div class="wf-props-head">
            <span :style="{ color: meta(selectedNode.type).color }">
              <i :class="['fa', meta(selectedNode.type).icon]"></i> {{ meta(selectedNode.type).label }}
            </span>
            <el-button link type="danger" size="small" @click="deleteSelectedNode">删除节点</el-button>
          </div>

          <el-form label-position="top" size="small" @submit.prevent>
            <el-form-item label="节点名称">
              <el-input v-model="selectedNode.name" @input="dirty = true" />
            </el-form-item>
            <el-form-item label="输出变量名">
              <el-input v-model="selectedNode.output_key" placeholder="默认使用节点ID" @input="dirty = true" />
            </el-form-item>

            <template v-if="selectedNode.type === 'start'">
              <div class="wf-hint">流程入口。运行时可传入输入变量，通过 <code>&#123;&#123;inputs.xxx&#125;&#125;</code> 或 <code>&#123;&#123;变量名&#125;&#125;</code> 在后续节点引用。</div>
            </template>

            <template v-else-if="selectedNode.type === 'query'">
              <el-form-item label="查询脚本">
                <el-select v-model="selectedNode.config.script_ids" multiple filterable placeholder="选择查询脚本"
                           style="width: 100%" @change="onQueryScriptsChange(selectedNode)">
                  <el-option v-for="s in queryScripts" :key="s.id" :label="s.name" :value="s.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="数据库">
                <el-select v-model="selectedNode.config.database_ids" multiple filterable placeholder="默认取脚本绑定数据库"
                           style="width: 100%">
                  <el-option v-for="d in databases" :key="d.id" :label="d.name" :value="d.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="输入文件路径">
                <el-input v-model="selectedNode.config.input_file" placeholder="参数 Excel 文件绝对路径" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="参数列（可选）">
                <el-input v-model="selectedNode.config.param_column" placeholder="按该列逐行执行查询" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="合并方式">
                <el-select v-model="selectedNode.config.merge_strategy" style="width: 100%">
                  <el-option label="合并为一个文件" value="concat" />
                  <el-option label="分文件输出" value="separate" />
                </el-select>
              </el-form-item>
              <el-form-item label="模板参数 (JSON)">
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.param_values)"
                          @change="setJson(selectedNode.config, 'param_values', $event)" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'export'">
              <el-form-item label="导出脚本">
                <el-select v-model="selectedNode.config.script_ids" multiple filterable placeholder="选择导出脚本" style="width: 100%">
                  <el-option v-for="s in exportScripts" :key="s.id" :label="s.name" :value="s.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="输出格式">
                <el-select v-model="selectedNode.config.output_format" style="width: 100%">
                  <el-option label="多工作表" value="sheets" />
                  <el-option label="多文件压缩" value="zip" />
                </el-select>
              </el-form-item>
              <el-form-item label="导出参数 (JSON)">
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.param_values)"
                          @change="setJson(selectedNode.config, 'param_values', $event)" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'system_task'">
              <el-form-item label="系统任务">
                <el-select v-model="selectedNode.config.system_task_id" filterable placeholder="选择系统任务" style="width: 100%">
                  <el-option v-for="t in systemTasks" :key="t.id" :label="t.name + ' (' + t.task_type + ')'" :value="t.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="任务参数 (JSON)">
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.param_values)"
                          @change="setJson(selectedNode.config, 'param_values', $event)" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'script'">
              <el-form-item label="脚本类型">
                <el-select :model-value="selectedNode.config.script_type || selectedScriptType"
                           placeholder="先选择脚本类型" style="width: 100%" @change="onScriptTypeChange($event)">
                  <el-option v-for="t in scriptTypeOptions" :key="t.value" :label="t.label" :value="t.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="SQL 脚本">
                <el-select v-model="selectedNode.config.script_id" filterable
                           :disabled="!(selectedNode.config.script_type || selectedScriptType)"
                           :placeholder="(selectedNode.config.script_type || selectedScriptType) ? '选择该类型下的脚本' : '请先选择脚本类型'"
                           style="width: 100%" @change="dirty = true">
                  <el-option v-for="s in scriptOptions" :key="s.id" :label="s.name" :value="s.id" />
                </el-select>
              </el-form-item>
              <div class="wf-hint">
                按脚本自身类型调用原服务：query 执行查询、export 导出文件、lookup 信息查询、system 执行 SQL（DML/DDL，支持多语句）。
              </div>
              <div class="wf-param-head">
                <span>脚本参数映射</span>
                <span v-if="selectedScriptParams.length" class="wf-tip">脚本所需参数 ← 上游节点输出 / 变量 / 固定值</span>
              </div>
              <div v-if="!selectedNode.config.script_id" class="wf-hint">请先选择 SQL 脚本，脚本声明的输入参数会显示在这里。</div>
              <div v-else-if="!selectedScriptParams.length" class="wf-hint">该脚本未声明输入参数；如确需传递，可在下方「原始参数 JSON」中手动填写。</div>
              <div v-for="p in selectedScriptParams" :key="p.name" class="wf-param-row">
                <div class="wf-param-name">
                  <span class="wf-param-label">{{ p.label || p.name }}</span>
                  <code>{{ p.name }}</code>
                  <el-tag v-if="p.required" size="small" type="danger" effect="plain">必填</el-tag>
                  <span class="wf-param-type">{{ (p.multi || p.type === 'list') ? '列表' : (p.type || 'text') }}</span>
                </div>
                <div class="wf-param-map">
                  <el-select :model-value="paramSource(p.name)" size="small" style="width: 100%"
                             @change="onParamSourceChange(p.name, $event)">
                    <el-option label="上游节点输出" value="node" />
                    <el-option label="流程变量" value="var" />
                    <el-option label="固定值" value="const" />
                  </el-select>
                  <template v-if="paramSource(p.name) === 'node'">
                    <el-select :model-value="paramNodeId(p.name)" size="small" filterable style="width: 100%"
                               placeholder="选择上游节点" @change="onParamNodeChange(p.name, $event)">
                      <el-option v-for="n in paramNodeOptions" :key="n.id"
                                 :label="(n.name || meta(n.type).label) + ' · ' + meta(n.type).label" :value="n.id" />
                      <template #empty><span class="wf-tip">该节点没有上游节点（请先连线）</span></template>
                    </el-select>
                    <el-select :model-value="paramNodeField(p.name)" size="small" filterable allow-create
                               default-first-option clearable style="width: 100%"
                               placeholder="输出字段（如 inputs.deviceSn）"
                               @change="onParamFieldChange(p.name, $event)">
                      <el-option v-for="f in paramFieldOptions(paramNodeId(p.name))" :key="f" :label="f" :value="f" />
                    </el-select>
                    <span v-if="paramNodeId(p.name) && !paramFieldOptions(paramNodeId(p.name)).length" class="wf-tip">
                      该节点还没有运行输出，可先运行一次后选择字段，或直接输入字段路径
                    </span>
                  </template>
                  <el-select v-else-if="paramSource(p.name) === 'var'" :model-value="paramVarName(p.name)" size="small"
                             filterable allow-create default-first-option style="width: 100%"
                             placeholder="选择或输入变量名" @change="onParamVarChange(p.name, $event)">
                    <el-option v-for="v in paramVarOptions" :key="v" :label="v" :value="v" />
                  </el-select>
                  <el-input v-else size="small" :model-value="paramRaw(p.name)"
                            placeholder="固定值（也支持引用表达式）"
                            @input="onParamConstInput(p.name, $event)" />
                </div>
              </div>
              <details class="wf-param-advanced">
                <summary>原始参数 JSON</summary>
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.param_values)"
                          @change="setJson(selectedNode.config, 'param_values', $event)" />
              </details>
              <template v-if="selectedScriptType === 'query'">
                <el-form-item label="输入文件路径">
                  <el-input v-model="selectedNode.config.input_file" placeholder="参数 Excel 文件绝对路径" @input="dirty = true" />
                </el-form-item>
                <el-form-item label="数据库">
                  <el-select v-model="selectedNode.config.database_ids" multiple filterable
                             placeholder="默认取脚本绑定数据库" style="width: 100%">
                    <el-option v-for="d in databases" :key="d.id" :label="d.name" :value="d.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="参数列（可选）">
                  <el-input v-model="selectedNode.config.param_column" placeholder="按该列逐行执行查询" @input="dirty = true" />
                </el-form-item>
                <el-form-item label="合并方式">
                  <el-select v-model="selectedNode.config.merge_strategy" style="width: 100%">
                    <el-option label="合并为一个文件" value="concat" />
                    <el-option label="分文件输出" value="separate" />
                  </el-select>
                </el-form-item>
              </template>
              <template v-else-if="selectedScriptType === 'export'">
                <el-form-item label="输出格式">
                  <el-select v-model="selectedNode.config.output_format" style="width: 100%">
                    <el-option label="多工作表" value="sheets" />
                    <el-option label="多文件压缩" value="zip" />
                  </el-select>
                </el-form-item>
              </template>
              <template v-else-if="selectedScriptType === 'system'">
                <el-form-item label="数据库">
                  <el-select v-model="selectedNode.config.database_ids" multiple filterable
                             placeholder="默认取脚本绑定数据库" style="width: 100%">
                    <el-option v-for="d in databases" :key="d.id" :label="d.name" :value="d.id" />
                  </el-select>
                </el-form-item>
              </template>
            </template>

            <template v-else-if="selectedNode.type === 'lookup'">
              <el-form-item label="信息查询脚本">
                <el-select v-model="selectedNode.config.script_id" filterable placeholder="选择脚本" style="width: 100%">
                  <el-option v-for="s in lookupScripts" :key="s.id" :label="s.name" :value="s.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="查询参数 (JSON)">
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.param_values)"
                          @change="setJson(selectedNode.config, 'param_values', $event)" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'ai'">
              <el-form-item label="智能 Agent">
                <el-select v-model="selectedNode.config.agent_id" clearable filterable
                           placeholder="默认AI（不指定 Agent）" style="width: 100%" @change="dirty = true">
                  <el-option v-for="a in agents" :key="a.id"
                             :label="a.name + (a.agent_role ? ' (' + a.agent_role + ')' : '')" :value="a.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="能力">
                <el-select v-model="selectedNode.config.capability" style="width: 100%" @change="dirty = true">
                  <el-option label="自动判断" value="auto" />
                  <el-option label="发送邮件" value="email" />
                  <el-option label="查询分析日志" value="log_query" />
                  <el-option label="生成文件" value="file_generate" />
                  <el-option label="总结" value="summary" />
                  <el-option label="自定义" value="custom" />
                </el-select>
              </el-form-item>
              <el-form-item label="白话文指令">
                <el-input type="textarea" :rows="6" v-model="selectedNode.config.instruction"
                          placeholder="如：把上一个节点的查询结果整理成邮件，发送给 ops@example.com，并说明异常情况"
                          @input="dirty = true" />
              </el-form-item>
              <template v-if="selectedNode.config.capability === 'log_query'">
                <el-form-item label="日志类型">
                  <el-select v-model="selectedNode.config.log_type" style="width: 100%" @change="dirty = true">
                    <el-option label="操作日志" value="operation" />
                    <el-option label="登录日志" value="login" />
                  </el-select>
                </el-form-item>
                <el-form-item label="用户名关键字">
                  <el-input v-model="selectedNode.config.keyword" @input="dirty = true" />
                </el-form-item>
                <el-form-item v-if="selectedNode.config.log_type === 'operation'" label="操作类型">
                  <el-input v-model="selectedNode.config.action" placeholder="精确匹配 action" @input="dirty = true" />
                </el-form-item>
                <el-form-item label="条数上限">
                  <el-input-number v-model="selectedNode.config.limit" :min="1" :max="500" />
                </el-form-item>
              </template>
              <el-form-item label="注入流程上下文">
                <el-switch v-model="selectedNode.config.include_context" @change="dirty = true" />
              </el-form-item>
              <el-form-item v-if="selectedNode.config.include_context" label="上下文上限（字符）">
                <el-input-number v-model="selectedNode.config.context_limit" :min="500" :max="20000" :step="500" />
              </el-form-item>
              <el-form-item label="工具调用轮次">
                <el-input-number v-model="selectedNode.config.max_rounds" :min="1" :max="10" />
              </el-form-item>
              <div class="wf-hint">
                AI 结论写入节点输出的 <code>content</code> 字段，后续节点可用 <code v-pre>{{ 节点ID.content }}</code> 引用；指令支持模板变量。
              </div>
            </template>

            <template v-else-if="selectedNode.type === 'email'">
              <el-form-item label="收件人">
                <el-input v-model="selectedNode.config.to" placeholder="多个邮箱用逗号分隔" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="邮件主题">
                <el-input v-model="selectedNode.config.subject" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="邮件内容">
                <el-input type="textarea" :rows="5" v-model="selectedNode.config.content" @input="dirty = true" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'log_query'">
              <el-form-item label="日志类型">
                <el-select v-model="selectedNode.config.log_type" style="width: 100%">
                  <el-option label="操作日志" value="operation" />
                  <el-option label="登录日志" value="login" />
                </el-select>
              </el-form-item>
              <el-form-item label="用户名关键字">
                <el-input v-model="selectedNode.config.keyword" @input="dirty = true" />
              </el-form-item>
              <el-form-item v-if="selectedNode.config.log_type === 'operation'" label="操作类型">
                <el-input v-model="selectedNode.config.action" placeholder="精确匹配 action" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="条数上限">
                <el-input-number v-model="selectedNode.config.limit" :min="1" :max="500" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'file_generate'">
              <el-form-item label="文件名">
                <el-input v-model="selectedNode.config.filename" placeholder="如 月度报表.xlsx" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="文件标题">
                <el-input v-model="selectedNode.config.title" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="文件格式">
                <el-select v-model="selectedNode.config.fmt" style="width: 100%">
                  <el-option v-for="f in fileFormats" :key="f" :label="f" :value="f" />
                </el-select>
              </el-form-item>
              <el-form-item label="文本内容">
                <el-input type="textarea" :rows="5" v-model="selectedNode.config.content" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="表格数据 (JSON)">
                <el-input type="textarea" :rows="3" :model-value="jsonText(selectedNode.config.sheets)"
                          @change="setJson(selectedNode.config, 'sheets', $event, true)" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'approval'">
              <el-form-item label="审批方式">
                <el-radio-group v-model="selectedNode.config.mode">
                  <el-radio-button label="manual">指定审批人</el-radio-button>
                  <el-radio-button label="ai">AI 督查员</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label="审批事项">
                <el-input type="textarea" :rows="4" v-model="selectedNode.config.message" @input="dirty = true" />
              </el-form-item>
              <el-form-item v-if="selectedNode.config.mode === 'manual'" label="审批人">
                <el-select v-model="selectedNode.config.approvers" multiple filterable placeholder="选择审批人" style="width: 100%">
                  <el-option v-for="u in approvers" :key="u.id" :label="u.display_name" :value="u.id" />
                </el-select>
              </el-form-item>
              <template v-else>
                <el-form-item label="AI 督查要求">
                  <el-input type="textarea" :rows="4" v-model="selectedNode.config.ai_instruction"
                            placeholder="AI 将根据审批事项和上下文回答 PASS / REJECT" @input="dirty = true" />
                </el-form-item>
                <div class="wf-hint">AI 返回 PASS 走「通过」分支，返回 REJECT 走「拒绝」分支；未连接拒绝分支时流程失败。</div>
              </template>
            </template>

            <template v-else-if="selectedNode.type === 'condition'">
              <el-form-item label="条件表达式">
                <el-input type="textarea" :rows="3" v-model="selectedNode.config.expression"
                          placeholder="例如 nodes.lookup1.row_count > 0 或 vars.threshold >= 100" @input="dirty = true" />
              </el-form-item>

              <el-divider content-position="left">快捷条件</el-divider>
              <el-form-item label="取值来源">
                <el-radio-group v-model="condQuick.source" size="small">
                  <el-radio-button label="node">上游节点输出</el-radio-button>
                  <el-radio-button label="var">流程变量</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <template v-if="condQuick.source === 'node'">
                <el-form-item label="上游节点">
                  <el-select v-model="condQuick.nodeId" filterable placeholder="选择上游节点" style="width: 100%"
                             @change="onCondNodeChange">
                    <el-option v-for="n in paramNodeOptions" :key="n.id" :label="n.name" :value="n.id" />
                  </el-select>
                </el-form-item>
                <el-form-item label="判断字段">
                  <el-select v-model="condQuick.field" filterable allow-create default-first-option
                             placeholder="选择字段，或手动输入路径" style="width: 100%">
                    <el-option v-for="f in condFieldOptions" :key="f" :label="f" :value="f" />
                  </el-select>
                </el-form-item>
              </template>
              <el-form-item v-else label="流程变量">
                <el-select v-model="condQuick.varName" filterable allow-create default-first-option
                           placeholder="选择或输入变量名" style="width: 100%">
                  <el-option v-for="v in paramVarOptions" :key="v" :label="v" :value="v" />
                </el-select>
              </el-form-item>
              <el-form-item label="操作符">
                <el-select v-model="condQuick.operator" style="width: 100%">
                  <el-option v-for="op in condOperators" :key="op.value" :label="op.label" :value="op.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="比较值">
                <el-input v-model="condQuick.value" placeholder="常量，或 vars.变量名 / nodes.节点.字段" />
              </el-form-item>
              <el-form-item label="连接方式">
                <el-radio-group v-model="condQuick.connector" size="small">
                  <el-radio-button label="and">并且</el-radio-button>
                  <el-radio-button label="or">或者</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px">
                <el-button size="small" type="primary" plain @click="appendCondition">
                  <i class="fa fa-plus"></i> 添加到表达式
                </el-button>
                <span class="wf-tip">{{ condPreview }}</span>
              </div>
              <div class="wf-hint">
                快捷条件会按「并且(and) / 或者(or)」追加到上面的表达式。支持 &gt;、&lt;、&gt;=、&lt;=、==、!=、contains；条件为真走「是」分支，否则走「否」分支。
              </div>
            </template>

            <template v-else-if="selectedNode.type === 'delay'">
              <el-form-item label="等待秒数">
                <el-input-number v-model="selectedNode.config.seconds" :min="0" :max="300" />
              </el-form-item>
            </template>

            <template v-else-if="selectedNode.type === 'end'">
              <el-form-item label="结束提示">
                <el-input type="textarea" :rows="3" v-model="selectedNode.config.message" @input="dirty = true" />
              </el-form-item>
            </template>

            <template v-else>
              <div class="wf-hint">该节点类型暂无配置项。</div>
            </template>

            <template v-if="isLoopable(selectedNode.type)">
              <el-divider content-position="left">自循环</el-divider>
              <el-form-item label="启用自循环">
                <el-switch v-model="selectedNode.config.loop.enabled" @change="dirty = true" />
              </el-form-item>
              <template v-if="selectedNode.config.loop.enabled">
                <el-form-item label="最大循环次数">
                  <el-input-number v-model="selectedNode.config.loop.max_times" :min="1" :max="100" @change="dirty = true" />
                </el-form-item>
                <el-form-item label="循环跳出条件">
                  <el-input v-model="selectedNode.config.loop.exit_condition"
                            placeholder="留空则执行满最大次数后继续" @input="dirty = true" />
                </el-form-item>
                <el-form-item label="每次间隔（秒）">
                  <el-input-number v-model="selectedNode.config.loop.interval" :min="0" :max="60" @change="dirty = true" />
                </el-form-item>
                <div class="wf-hint">
                  节点执行完成后判断跳出条件：为真则离开循环继续后续节点，否则重复执行本节点；达到最大次数自动跳出，次数按本次运行累计。
                </div>
              </template>
            </template>
          </el-form>

          <div v-if="runNode(selectedNode.id)" class="wf-output-box wf-run-info-box">
            <div class="wf-output-title">
              最近运行
              <span class="wf-run-badge small" :class="'st-' + runNode(selectedNode.id).status">
                {{ statusLabel(runNode(selectedNode.id).status) }}
              </span>
              <span class="wf-run-info-time">{{ durationText(runNode(selectedNode.id)) }}</span>
            </div>
            <div v-if="nodeError(selectedNode.id)" class="wf-run-info-error">
              <i class="fa fa-exclamation-triangle"></i>
              <span>{{ nodeError(selectedNode.id) }}</span>
            </div>
            <div v-else-if="runNode(selectedNode.id).error_message" class="wf-run-info-error">
              <i class="fa fa-exclamation-triangle"></i>
              <span>{{ runNode(selectedNode.id).error_message }}</span>
            </div>
          </div>

          <div v-if="nodeOutput(selectedNode.id)" class="wf-output-box">
            <div class="wf-output-title">最近运行输出</div>
            <pre>{{ pretty(nodeOutput(selectedNode.id)) }}</pre>
          </div>
        </div>

        <div v-else-if="selectedEdge" class="wf-props-inner">
          <div class="wf-props-head">
            <span><i class="fa fa-link"></i> 连线配置</span>
            <el-button link type="danger" size="small" @click="deleteSelectedEdge">删除连线</el-button>
          </div>
          <el-form label-position="top" size="small">
            <el-form-item label="连线分支">
              <el-select v-model="selectedEdge.branch" style="width: 100%" @change="dirty = true">
                <el-option v-for="b in branchOptions" :key="b.value" :label="b.label" :value="b.value" />
              </el-select>
            </el-form-item>
            <div class="wf-hint">
              普通节点使用「默认 / 成功 / 失败」；条件节点使用「是 / 否」；审批节点使用「通过 / 拒绝」。
            </div>
          </el-form>
        </div>

        <div v-else class="wf-props-inner">
          <div class="wf-props-head">
            <span><i class="fa fa-sliders-h"></i> 工作流设置</span>
          </div>
          <template v-if="current">
            <el-form label-position="top" size="small">
              <el-form-item label="工作流名称">
                <el-input v-model="current.name" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="描述">
                <el-input type="textarea" :rows="3" v-model="current.description" @input="dirty = true" />
              </el-form-item>
              <el-form-item label="流程变量">
                <div class="wf-var-list">
                  <div v-for="(v, i) in current.variables" :key="i" class="wf-var-item">
                    <code>{{ v.name }}</code>
                    <span class="wf-var-default">{{ v.default }}</span>
                  </div>
                  <span v-if="!current.variables.length" class="wf-muted">暂无变量</span>
                </div>
              </el-form-item>
            </el-form>
            <el-button size="small" @click="openVariables"><i class="fa fa-code"></i> 编辑变量</el-button>
            <div class="wf-hint">
              拖拽左侧节点到画布；从节点右侧圆点拖到目标节点即可连线；点击节点或连线可在右侧配置。
            </div>
          </template>
          <div v-else class="wf-hint">请选择或新建一个工作流。</div>
        </div>
      </aside>
    </div>

    <el-dialog v-model="runDialog" title="运行工作流" width="520px" :close-on-click-modal="false">
      <el-form label-width="110px" size="small">
        <el-form-item v-for="v in current?.variables || []" :key="v.name" :label="v.label || v.name">
          <el-input v-model="runInputs[v.name]" :placeholder="v.default !== undefined ? String(v.default) : ''" />
        </el-form-item>
        <el-form-item v-if="!(current?.variables || []).length" label="提示">
          <span class="wf-muted">该工作流没有定义输入变量，可直接运行。</span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="runDialog = false">取消</el-button>
        <el-button size="small" type="success" @click="startRun"><i class="fa fa-play"></i> 启动</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="variablesDialog" title="流程变量" width="720px">
      <div class="wf-var-editor">
        <el-table :data="variablesDraft" size="small" border>
          <el-table-column label="变量名" width="180">
            <template #default="{ row }"><el-input v-model="row.name" size="small" placeholder="如 start_date" /></template>
          </el-table-column>
          <el-table-column label="显示名称" width="180">
            <template #default="{ row }"><el-input v-model="row.label" size="small" /></template>
          </el-table-column>
          <el-table-column label="默认值">
            <template #default="{ row }"><el-input v-model="row.default" size="small" /></template>
          </el-table-column>
          <el-table-column label="必填" width="80" align="center">
            <template #default="{ row }">
              <el-switch v-model="row.required" size="small" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="variablesDraft.splice($index, 1)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-button size="small" style="margin-top: 10px" @click="variablesDraft.push({ name: '', label: '', default: '', required: true })">
          <i class="fa fa-plus"></i> 添加变量
        </el-button>
        <div class="wf-hint" style="margin-top: 8px">
          必填变量在 AI 触发执行时会先向用户确认参数；未开启时若填写了默认值则自动使用默认值。
        </div>
      </div>
      <template #footer>
        <el-button size="small" @click="variablesDialog = false">取消</el-button>
        <el-button size="small" type="primary" @click="saveVariables">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="runsDrawer" title="执行记录" size="620px">
      <div class="wf-runs">
        <div v-for="r in runsList" :key="r.run_id" class="wf-run-item" :class="{ active: activeRun && activeRun.run_id === r.run_id }"
             @click="loadRunDetail(r.run_id)">
          <div class="wf-run-item-main">
            <span class="wf-run-badge" :class="'st-' + r.status">{{ statusLabel(r.status) }}</span>
            <span class="wf-run-item-id">{{ r.run_id.slice(0, 8) }}</span>
            <span class="wf-run-item-time">{{ formatTime(r.created_at) }}</span>
          </div>
          <div class="wf-run-item-sub">
            节点进度：{{ runProgressText(r) }}<span v-if="r.error_message" class="wf-run-error">{{ r.error_message }}</span>
          </div>
        </div>
        <el-empty v-if="!runsList.length" description="暂无执行记录" :image-size="60" />
      </div>

      <div v-if="activeRun" class="wf-run-detail">
        <div class="wf-run-detail-head">
          <span class="wf-run-badge" :class="'st-' + activeRun.status">{{ statusLabel(activeRun.status) }}</span>
          <span class="wf-run-detail-id">{{ activeRun.run_id.slice(0, 8) }}</span>
          <span class="wf-run-detail-time">{{ formatTime(activeRun.started_at) }} ~ {{ formatTime(activeRun.completed_at) || '进行中' }}</span>
        </div>

        <div v-if="activeRun.error_message" class="wf-run-detail-error">
          <i class="fa fa-times-circle"></i> {{ activeRun.error_message }}
        </div>

        <div class="wf-run-detail-title">节点执行明细</div>
        <div class="wf-run-detail-nodes">
          <div v-for="n in activeRun.nodes || []" :key="n.id" class="wf-run-detail-node" :class="'st-' + n.status">
            <div class="wf-run-detail-node-main">
              <i :class="['fa', statusIcon(n.status)]" class="wf-run-detail-node-icon"></i>
              <span class="wf-run-detail-node-name">{{ n.node_name }}</span>
              <span class="wf-run-detail-node-type">{{ meta(n.node_type).label }}</span>
              <span class="wf-run-badge small" :class="'st-' + n.status">{{ statusLabel(n.status) }}</span>
              <span class="wf-run-detail-node-dur">{{ durationText(n) }}</span>
            </div>
            <div v-if="n.error_message" class="wf-run-detail-node-error">
              <i class="fa fa-exclamation-triangle"></i>
              <span>{{ n.error_message }}</span>
            </div>
            <details v-if="n.output !== null && n.output !== undefined" class="wf-run-detail-node-output">
              <summary>查看输出</summary>
              <pre>{{ pretty(n.output) }}</pre>
            </details>
          </div>
          <div v-if="!(activeRun.nodes || []).length" class="wf-muted">暂无节点记录</div>
        </div>

        <div class="wf-run-detail-title">执行日志</div>
        <div class="wf-run-detail-logs">
          <div v-for="(l, i) in activeRun.logs || []" :key="i" class="wf-run-detail-log" :class="'lv-' + l.level">
            <span class="wf-run-detail-log-time">{{ formatTime(l.time).slice(11) }}</span>
            <span>{{ l.message }}</span>
          </div>
          <div v-if="!(activeRun.logs || []).length" class="wf-muted">暂无日志</div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const NODE_W = 190
const NODE_H = 72

const NODE_META = {
  start: { label: '开始', icon: 'fa-play', color: '#10b981' },
  query: { label: '查询任务', icon: 'fa-search', color: '#3b82f6' },
  export: { label: '导出任务', icon: 'fa-file-export', color: '#8b5cf6' },
  system_task: { label: '系统任务', icon: 'fa-cogs', color: '#f59e0b' },
  script: { label: '脚本执行', icon: 'fa-terminal', color: '#0ea5e9' },
  lookup: { label: '信息查询', icon: 'fa-search-plus', color: '#06b6d4' },
  ai: { label: '智能AI', icon: 'fa-robot', color: '#6366f1' },
  email: { label: '邮件通知', icon: 'fa-envelope', color: '#ec4899' },
  log_query: { label: '查询日志', icon: 'fa-clipboard-list', color: '#64748b' },
  file_generate: { label: '生成文件', icon: 'fa-file-alt', color: '#14b8a6' },
  approval: { label: '审批节点', icon: 'fa-user-check', color: '#ef4444' },
  condition: { label: '条件判断', icon: 'fa-code-branch', color: '#eab308' },
  delay: { label: '延时等待', icon: 'fa-clock', color: '#94a3b8' },
  end: { label: '结束', icon: 'fa-flag-checkered', color: '#475569' },
}
const paletteTypes = ['query', 'export', 'system_task', 'script', 'lookup', 'ai',
  'approval', 'condition', 'delay', 'start', 'end']
const branchOptions = [
  { value: 'default', label: '默认' },
  { value: 'success', label: '成功' },
  { value: 'fail', label: '失败' },
  { value: 'true', label: '是（条件为真）' },
  { value: 'false', label: '否（条件为假）' },
  { value: 'approved', label: '通过' },
  { value: 'rejected', label: '拒绝' },
]
const fileFormats = ['xlsx', 'csv', 'md', 'txt', 'json', 'html', 'docx', 'pdf']

const workflows = ref([])
const current = ref(null)
const graph = ref({ nodes: [], edges: [] })
const selectedNodeId = ref(null)
const selectedNodeIds = ref([])
const selectedEdgeId = ref(null)
const capabilities = ref({ scripts: [], databases: [], system_tasks: [], approvers: [], agents: [] })
const scale = ref(1)
const offsetX = ref(80)
const offsetY = ref(60)
const canvasRef = ref(null)
const dirty = ref(false)
const searchKeyword = ref('')

const variablesDialog = ref(false)
const variablesDraft = ref([])
const runDialog = ref(false)
const runInputs = ref({})
const runsDrawer = ref(false)
const runsList = ref([])
const activeRun = ref(null)
const nodeStatus = reactive({})
const nodeOutputs = reactive({})
const runNodeRecords = reactive({})
const approvalComment = ref('')

const dragState = ref(null)
const panState = ref(null)
const boxState = ref(null)
const guides = ref({ x: null, y: null })
const connecting = ref(null)
let pollTimer = null

const meta = (type) => NODE_META[type] || { label: type, icon: 'fa-circle', color: '#94a3b8' }
const filteredWorkflows = computed(() => {
  const kw = (searchKeyword.value || '').trim().toLowerCase()
  if (!kw) return workflows.value
  return workflows.value.filter(w => (w.name || '').toLowerCase().includes(kw))
})
const selectedNode = computed(() => graph.value.nodes.find(n => n.id === selectedNodeId.value) || null)
const SCRIPT_TYPE_LABELS = {
  query: '查询脚本', export: '导出脚本', system: '系统脚本', lookup: '信息查询', dashboard: '看板脚本',
}
const SCRIPT_TYPE_ORDER = ['query', 'export', 'lookup', 'system', 'dashboard']
const selectedScriptType = computed(() => {
  const cfg = selectedNode.value?.config
  if (!cfg) return ''
  if (cfg.script_type) return cfg.script_type
  const s = capabilities.value.scripts.find(item => item.id === cfg.script_id)
  return s ? s.type : ''
})
const scriptTypeOptions = computed(() => {
  const types = [...new Set(capabilities.value.scripts.map(s => s.type).filter(Boolean))]
  types.sort((a, b) => {
    const ia = SCRIPT_TYPE_ORDER.indexOf(a)
    const ib = SCRIPT_TYPE_ORDER.indexOf(b)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
  return types.map(t => ({ value: t, label: SCRIPT_TYPE_LABELS[t] || t }))
})
const scriptOptions = computed(() => {
  const type = selectedScriptType.value
  if (!type) return []
  return capabilities.value.scripts.filter(s => s.type === type)
})
function onScriptTypeChange(type) {
  if (!selectedNode.value) return
  selectedNode.value.config.script_type = type
  selectedNode.value.config.script_id = null
  dirty.value = true
}

// ---- 脚本参数映射：脚本声明的参数 ← 上游节点输出 / 流程变量 / 固定值 ----
const selectedScript = computed(() => {
  const id = selectedNode.value?.config?.script_id
  if (!id) return null
  return capabilities.value.scripts.find(s => String(s.id) === String(id)) || null
})
const selectedScriptParams = computed(() => selectedScript.value?.params_config || [])
// 上游节点集合：沿连线反向可达，只允许引用真正的上游输出
const upstreamNodeIds = computed(() => {
  const nodeId = selectedNode.value?.id
  const ids = new Set()
  if (!nodeId) return ids
  const incoming = {}
  ;(graph.value.edges || []).forEach(e => {
    if (!e || !e.target) return
    ;(incoming[e.target] = incoming[e.target] || []).push(e.source)
  })
  const stack = [...(incoming[nodeId] || [])]
  while (stack.length) {
    const id = stack.pop()
    if (!id || id === nodeId || ids.has(id)) continue
    ids.add(id)
    ;(incoming[id] || []).forEach(src => { if (src && src !== nodeId && !ids.has(src)) stack.push(src) })
  }
  return ids
})
const paramNodeOptions = computed(() => {
  const upstream = upstreamNodeIds.value
  return graph.value.nodes.filter(n => upstream.has(n.id) && n.type !== 'end')
})
const paramVarOptions = computed(() => {
  const names = (current.value?.variables || []).map(v => v && v.name).filter(Boolean)
  return [...new Set(names)]
})

const REF_RE = /^\{\{\s*([^{}]+?)\s*\}\}$/

function paramRaw(name) {
  const vals = selectedNode.value?.config?.param_values
  if (!vals || typeof vals !== 'object') return ''
  const v = vals[name]
  return v === undefined || v === null ? '' : String(v)
}

function paramRef(name) {
  const m = REF_RE.exec(paramRaw(name).trim())
  return m ? m[1].trim() : ''
}

function paramSource(name) {
  const ref = paramRef(name)
  if (ref.startsWith('nodes.')) return 'node'
  if (ref.startsWith('vars.') || ref.startsWith('inputs.')) return 'var'
  if (ref && paramVarOptions.value.includes(ref)) return 'var'
  return 'const'
}

function paramVarName(name) {
  const ref = paramRef(name)
  if (ref.startsWith('vars.')) return ref.slice(5)
  return ref
}

function paramNodeId(name) {
  const ref = paramRef(name)
  if (!ref.startsWith('nodes.')) return ''
  return ref.slice(6).split('.')[0]
}

function paramNodeField(name) {
  const ref = paramRef(name)
  if (!ref.startsWith('nodes.')) return ''
  return ref.split('.').slice(2).join('.')
}

// 展开输出对象的可取值路径：嵌套字段展平，数组取首行的字段（如 results.0.status）
function flattenOutputPaths(obj, prefix = '', depth = 0) {
  const paths = []
  if (Array.isArray(obj)) {
    const first = obj[0]
    if (first && typeof first === 'object' && !Array.isArray(first) && depth < 3) {
      Object.keys(first).forEach(k => paths.push(`${prefix}.0.${k}`))
    } else if (prefix) {
      paths.push(prefix)
    }
    return paths
  }
  if (!obj || typeof obj !== 'object') return paths
  Object.keys(obj).forEach(k => {
    const path = prefix ? `${prefix}.${k}` : k
    const val = obj[k]
    if (val && typeof val === 'object' && depth < 2) {
      const before = paths.length
      flattenOutputPaths(val, path, depth + 1).forEach(p => paths.push(p))
      if (paths.length === before) paths.push(path)
    } else {
      paths.push(path)
    }
  })
  return paths
}

function paramFieldOptions(nodeId) {
  if (!nodeId) return []
  const out = nodeOutputs[nodeId]
  if (out && typeof out === 'object') return flattenOutputPaths(out)
  // 还没运行过：开始节点的输出是 inputs，可直接按流程变量列出
  const node = graph.value.nodes.find(n => n.id === nodeId)
  if (node && node.type === 'start') {
    return paramVarOptions.value.map(v => `inputs.${v}`)
  }
  return []
}

function setParamRaw(name, value) {
  const cfg = selectedNode.value?.config
  if (!cfg) return
  if (!cfg.param_values || typeof cfg.param_values !== 'object') cfg.param_values = {}
  const text = value === undefined || value === null ? '' : String(value)
  if (text === '') delete cfg.param_values[name]
  else cfg.param_values[name] = text
  dirty.value = true
}

function onParamSourceChange(name, source) {
  if (source === 'node') {
    const first = paramNodeOptions.value[0]
    if (!first) return setParamRaw(name, '')
    const field = paramFieldOptions(first.id)[0]
    setParamRaw(name, `{{nodes.${first.id}${field ? '.' + field : ''}}}`)
  } else if (source === 'var') {
    const first = paramVarOptions.value[0]
    setParamRaw(name, first ? `{{vars.${first}}}` : '')
  } else {
    setParamRaw(name, '')
  }
}

function onParamNodeChange(name, nodeId) {
  if (!nodeId) return setParamRaw(name, '')
  const options = paramFieldOptions(nodeId)
  let field = paramNodeField(name)
  if (!field || (options.length && !options.includes(field))) field = options[0] || ''
  setParamRaw(name, `{{nodes.${nodeId}${field ? '.' + field : ''}}}`)
}

function onParamFieldChange(name, field) {
  const nodeId = paramNodeId(name)
  if (!nodeId) return
  const f = String(field || '').trim().replace(/^\./, '')
  setParamRaw(name, `{{nodes.${nodeId}${f ? '.' + f : ''}}}`)
}

function onParamVarChange(name, varName) {
  const v = String(varName || '').trim().replace(/^\{\{\s*|\s*\}\}$/g, '').replace(/^vars\./, '')
  if (!v) return setParamRaw(name, '')
  setParamRaw(name, v.startsWith('inputs.') ? `{{${v}}}` : `{{vars.${v}}}`)
}

function onParamConstInput(name, value) {
  setParamRaw(name, value)
}

// ---- 条件判断快捷配置：上游节点输出 / 流程变量 → 表达式 ----
const condOperators = [
  { value: '>', label: '大于 >' },
  { value: '>=', label: '大于等于 >=' },
  { value: '==', label: '等于 ==' },
  { value: '!=', label: '不等于 !=' },
  { value: '<', label: '小于 <' },
  { value: '<=', label: '小于等于 <=' },
  { value: 'contains', label: '包含 contains' }
]
const condQuick = reactive({
  source: 'node', nodeId: '', field: '', varName: '', operator: '==', value: '', connector: 'and'
})
const condFieldOptions = computed(() => (condQuick.nodeId ? paramFieldOptions(condQuick.nodeId) : []))
const condLeftExpr = computed(() => {
  if (condQuick.source === 'var') {
    const name = String(condQuick.varName || '').trim()
      .replace(/^\{\{\s*|\s*\}\}$/g, '').replace(/^vars\./, '').replace(/^inputs\./, '')
    return name ? `vars.${name}` : ''
  }
  if (!condQuick.nodeId) return ''
  const field = String(condQuick.field || '').trim().replace(/^\./, '')
  return `nodes.${condQuick.nodeId}${field ? '.' + field : ''}`
})
const condPreview = computed(() => {
  const left = condLeftExpr.value
  if (!left) return '请选择上游节点或流程变量'
  const value = String(condQuick.value ?? '').trim()
  return value ? `${left} ${condQuick.operator} ${value}` : `${left} ${condQuick.operator} ？`
})

function initCondQuick() {
  if (!selectedNode.value || selectedNode.value.type !== 'condition') return
  condQuick.source = 'node'
  condQuick.varName = ''
  condQuick.operator = '=='
  condQuick.value = ''
  condQuick.connector = 'and'
  const first = paramNodeOptions.value[0]
  condQuick.nodeId = first ? first.id : ''
  condQuick.field = first ? (paramFieldOptions(first.id)[0] || '') : ''
}

function onCondNodeChange(nodeId) {
  const options = paramFieldOptions(nodeId)
  if (!options.includes(condQuick.field)) condQuick.field = options[0] || ''
}

function appendCondition() {
  const cfg = selectedNode.value?.config
  if (!cfg) return
  const left = condLeftExpr.value
  if (!left) return ElMessage.warning('请先选择上游节点或流程变量')
  const value = String(condQuick.value ?? '').trim()
  if (!value) return ElMessage.warning('请填写比较值')
  const expr = `${left} ${condQuick.operator} ${value}`
  const current = String(cfg.expression || '').trim()
  cfg.expression = current ? `${current} ${condQuick.connector} ${expr}` : expr
  dirty.value = true
}

watch(() => selectedNode.value?.id, initCondQuick)
const selectedEdge = computed(() => graph.value.edges.find(e => e.id === selectedEdgeId.value) || null)
const queryScripts = computed(() => capabilities.value.scripts.filter(s => s.type === 'query'))
const exportScripts = computed(() => capabilities.value.scripts.filter(s => s.type === 'export'))
const lookupScripts = computed(() => capabilities.value.scripts.filter(s => s.type === 'lookup'))
const databases = computed(() => capabilities.value.databases)
const systemTasks = computed(() => capabilities.value.system_tasks)
const approvers = computed(() => capabilities.value.approvers)
const agents = computed(() => capabilities.value.agents || [])
const loopNodes = computed(() => graph.value.nodes.filter(
  n => isLoopable(n.type) && n.config && n.config.loop && n.config.loop.enabled))
const isRunActive = computed(() => activeRun.value &&
  ['pending', 'running', 'waiting_approval'].includes(activeRun.value.status))
const runStatusText = computed(() => {
  if (!activeRun.value) return ''
  const map = { pending: '等待启动', running: '执行中', waiting_approval: '等待审批',
    completed: '执行完成', failed: '执行失败', cancelled: '已取消' }
  return map[activeRun.value.status] || activeRun.value.status
})
const runStatusIcon = computed(() => {
  if (!activeRun.value) return 'fa-info-circle'
  const map = { pending: 'fa-hourglass-start', running: 'fa-spinner fa-spin', waiting_approval: 'fa-user-clock',
    completed: 'fa-check-circle', failed: 'fa-times-circle', cancelled: 'fa-ban' }
  return map[activeRun.value.status] || 'fa-info-circle'
})
const worldStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
}))
const boxRect = computed(() => {
  const bs = boxState.value
  const rect = canvasRef.value ? canvasRef.value.getBoundingClientRect() : null
  if (!bs || !rect || !bs.moved) return null
  return {
    left: Math.min(bs.startX, bs.currentX) - rect.left + 'px',
    top: Math.min(bs.startY, bs.currentY) - rect.top + 'px',
    width: Math.abs(bs.currentX - bs.startX) + 'px',
    height: Math.abs(bs.currentY - bs.startY) + 'px',
  }
})
const connectingPath = computed(() => {
  if (!connecting.value) return ''
  const s = graph.value.nodes.find(n => n.id === connecting.value.source)
  if (!s) return ''
  const x1 = s.x + NODE_W
  const y1 = s.y + NODE_H / 2
  const x2 = connecting.value.x
  const y2 = connecting.value.y
  const dx = Math.max(50, Math.abs(x2 - x1) / 2)
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
})

function uid(prefix) {
  return `${prefix}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`
}

function baseConfig(type) {
  switch (type) {
    case 'query':
      return { script_ids: [], database_ids: [], input_file: '', param_column: '', merge_strategy: 'concat', param_values: {} }
    case 'export':
      return { script_ids: [], output_format: 'sheets', param_values: {} }
    case 'system_task':
      return { system_task_id: null, param_values: {} }
    case 'script':
      return {
        script_type: '', script_id: null, param_values: {},
        input_file: '', database_ids: [], param_column: '', merge_strategy: 'concat',
        output_format: 'sheets',
      }
    case 'lookup':
      return { script_id: null, param_values: {} }
    case 'ai':
      return {
        agent_id: null, capability: 'auto', instruction: '',
        include_context: true, context_limit: 6000, max_rounds: 5,
        log_type: 'operation', keyword: '', action: '', limit: 50,
      }
    case 'email':
      return { to: '', subject: '', content: '' }
    case 'log_query':
      return { log_type: 'operation', keyword: '', action: '', limit: 50 }
    case 'file_generate':
      return { filename: '', title: '', fmt: 'xlsx', content: '', sheets: '' }
    case 'approval':
      return { mode: 'manual', approvers: [], message: '请确认该流程节点的执行结果', ai_instruction: '' }
    case 'condition':
      return { expression: '' }
    case 'delay':
      return { seconds: 3 }
    case 'end':
      return { message: '流程结束' }
    default:
      return {}
  }
}

// 业务任务节点支持自循环（开始/结束/条件/延时/审批等控制类节点除外）
const LOOPABLE_TYPES = ['query', 'export', 'system_task', 'script', 'lookup', 'ai', 'email', 'log_query', 'file_generate']

function isLoopable(type) {
  return LOOPABLE_TYPES.includes(type)
}

function defaultConfig(type) {
  const cfg = baseConfig(type)
  if (isLoopable(type)) {
    cfg.loop = { enabled: false, max_times: 3, exit_condition: '', interval: 0, ...(cfg.loop || {}) }
  }
  return cfg
}

function normalizeGraph(raw) {
  const out = { nodes: [], edges: [] }
  ;(raw?.nodes || []).forEach((n, i) => {
    if (!n || !n.id) return
    out.nodes.push({
      id: n.id,
      type: n.type || 'query',
      name: n.name || meta(n.type).label,
      x: Number.isFinite(Number(n.x)) ? Number(n.x) : 100 + (i % 3) * 240,
      y: Number.isFinite(Number(n.y)) ? Number(n.y) : 120 + Math.floor(i / 3) * 150,
      output_key: n.output_key || '',
      config: { ...defaultConfig(n.type), ...(n.config || {}) },
    })
  })
  ;(raw?.edges || []).forEach(e => {
    if (!e || !e.source || !e.target) return
    out.edges.push({ id: e.id || uid('e'), source: e.source, target: e.target, branch: e.branch || 'default' })
  })
  return out
}

async function loadCapabilities() {
  try {
    const res = await api.workflow.capabilities()
    capabilities.value = res.data || capabilities.value
  } catch (e) { /* 错误已由拦截器提示 */ }
}

async function loadWorkflows() {
  try {
    const res = await api.workflow.list({ per_page: 200 })
    workflows.value = res.data?.items || []
    if (!current.value && workflows.value.length) {
      await loadWorkflow(workflows.value[0].id)
    }
  } catch (e) { /* ignore */ }
}

async function loadWorkflow(id) {
  try {
    const res = await api.workflow.get(id)
    const data = res.data
    current.value = {
      id: data.id,
      name: data.name,
      description: data.description || '',
      variables: data.variables || [],
      is_enabled: data.is_enabled !== false,
    }
    const vp = data.graph?.viewport || {}
    graph.value = normalizeGraph(data.graph || {})
    scale.value = vp.scale || 1
    offsetX.value = vp.offsetX ?? 80
    offsetY.value = vp.offsetY ?? 60
    selectedNodeId.value = null
    selectedNodeIds.value = []
    selectedEdgeId.value = null
    dirty.value = false
    clearRunVisual()
    activeRun.value = null
    stopPolling()
  } catch (e) { /* ignore */ }
}

async function saveWorkflow() {
  if (!current.value) return
  const payload = {
    name: current.value.name,
    description: current.value.description,
    is_enabled: current.value.is_enabled,
    variables: current.value.variables,
    graph: {
      nodes: graph.value.nodes,
      edges: graph.value.edges,
      viewport: { scale: scale.value, offsetX: offsetX.value, offsetY: offsetY.value },
    },
  }
  try {
    const res = await api.workflow.update(current.value.id, payload)
    current.value.name = res.data.name
    dirty.value = false
    ElMessage.success('工作流已保存')
    await loadWorkflows()
  } catch (e) { /* ignore */ }
}

async function newWorkflow() {
  try {
    const { value } = await ElMessageBox.prompt('请输入工作流名称', '新建工作流', {
      inputPattern: /\S+/, inputErrorMessage: '名称不能为空',
    })
    const res = await api.workflow.create({
      name: value.trim(),
      graph: {
        nodes: [
          { id: 'start', type: 'start', name: '开始', x: 80, y: 200, config: {} },
          { id: 'end', type: 'end', name: '结束', x: 820, y: 200, config: { message: '流程结束' } },
        ],
        edges: [],
      },
      variables: [],
    })
    await loadWorkflows()
    await loadWorkflow(res.data.id)
  } catch (e) { /* 取消 */ }
}

async function removeWorkflow(row) {
  try {
    await ElMessageBox.confirm(`确定删除工作流「${row.name}」？其全部执行记录也会一并删除，且不可恢复。`, '提示', { type: 'warning' })
    await api.workflow.remove(row.id)
    ElMessage.success('已删除')
    if (current.value && current.value.id === row.id) {
      current.value = null
      graph.value = { nodes: [], edges: [] }
      selectedNodeId.value = null
      selectedNodeIds.value = []
      selectedEdgeId.value = null
      activeRun.value = null
    }
    await loadWorkflows()
  } catch (e) { /* 取消 */ }
}

function openVariables() {
  variablesDraft.value = (current.value?.variables || []).map(v => ({
    name: v.name || '', label: v.label || '', default: v.default ?? '',
    required: typeof v.required === 'boolean' ? v.required : (v.default === undefined || v.default === null || v.default === ''),
  }))
  variablesDialog.value = true
}

function saveVariables() {
  if (!current.value) return
  current.value.variables = variablesDraft.value
    .filter(v => (v.name || '').trim())
    .map(v => ({ name: v.name.trim(), label: v.label || v.name.trim(), default: v.default, required: !!v.required }))
  variablesDialog.value = false
  dirty.value = true
}

function selectNode(node, event) {
  const additive = !!(event && (event.ctrlKey || event.metaKey || event.shiftKey))
  if (additive) {
    if (selectedNodeIds.value.includes(node.id)) {
      selectedNodeIds.value = selectedNodeIds.value.filter(id => id !== node.id)
      if (selectedNodeId.value === node.id) selectedNodeId.value = selectedNodeIds.value[0] || null
      return
    }
    selectedNodeIds.value = [...selectedNodeIds.value, node.id]
  } else if (!selectedNodeIds.value.includes(node.id)) {
    selectedNodeIds.value = [node.id]
  }
  selectedNodeId.value = node.id
  selectedEdgeId.value = null
}

function selectEdge(edge) {
  selectedEdgeId.value = edge.id
  selectedNodeId.value = null
  selectedNodeIds.value = []
}

function deleteSelectedNode() {
  const ids = selectedNodeIds.value.length
    ? [...selectedNodeIds.value]
    : (selectedNodeId.value ? [selectedNodeId.value] : [])
  if (!ids.length) return
  const idSet = new Set(ids)
  graph.value.nodes = graph.value.nodes.filter(n => !idSet.has(n.id))
  graph.value.edges = graph.value.edges.filter(e => !idSet.has(e.source) && !idSet.has(e.target))
  selectedNodeIds.value = []
  selectedNodeId.value = null
  dirty.value = true
}

function deleteSelectedEdge() {
  if (!selectedEdgeId.value) return
  graph.value.edges = graph.value.edges.filter(e => e.id !== selectedEdgeId.value)
  selectedEdgeId.value = null
  dirty.value = true
}

function nodeClass(node) {
  const status = nodeStatus[node.id]
  return [
    'type-' + node.type,
    {
      selected: selectedNodeIds.value.includes(node.id),
      running: status === 'running',
      success: status === 'completed',
      failed: status === 'failed',
      waiting: status === 'waiting_approval',
    },
  ]
}

function nodeName(id) {
  const n = graph.value.nodes.find(x => x.id === id)
  return n ? n.name : id
}

function nodeOutput(id) {
  return nodeOutputs[id]
}

function pretty(value) {
  try { return JSON.stringify(value, null, 2) } catch (e) { return String(value) }
}

function jsonText(value) {
  if (value === undefined || value === null || value === '') return ''
  try { return JSON.stringify(value, null, 2) } catch (e) { return '' }
}

function setJson(target, key, text, allowEmpty = false) {
  if (!text || !String(text).trim()) {
    target[key] = allowEmpty ? '' : {}
    dirty.value = true
    return
  }
  try {
    target[key] = JSON.parse(text)
    dirty.value = true
  } catch (e) {
    ElMessage.warning('JSON 格式不正确，未保存')
  }
}

function onQueryScriptsChange(node) {
  const ids = new Set(node.config.database_ids || [])
  ;(node.config.script_ids || []).forEach(sid => {
    const script = capabilities.value.scripts.find(s => s.id === sid)
    ;(script?.database_ids || []).forEach(d => ids.add(d))
  })
  node.config.database_ids = Array.from(ids)
  dirty.value = true
}

// ---------------------------------------------------------------------------
// 画布坐标与节点增删
// ---------------------------------------------------------------------------

function toGraphPoint(clientX, clientY) {
  const rect = canvasRef.value ? canvasRef.value.getBoundingClientRect() : null
  if (!rect) return { x: 0, y: 0 }
  return {
    x: (clientX - rect.left - offsetX.value) / scale.value,
    y: (clientY - rect.top - offsetY.value) / scale.value,
  }
}

function addNode(type, x, y) {
  const node = {
    id: `${type}_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`,
    type,
    name: meta(type).label,
    x: Math.round(x),
    y: Math.round(y),
    output_key: '',
    config: defaultConfig(type),
  }
  graph.value.nodes.push(node)
  selectedNodeId.value = node.id
  selectedNodeIds.value = [node.id]
  selectedEdgeId.value = null
  dirty.value = true
  return node
}

function addNodeAtCenter(type) {
  if (!current.value) {
    ElMessage.warning('请先选择或新建工作流')
    return
  }
  const rect = canvasRef.value ? canvasRef.value.getBoundingClientRect() : null
  const clientX = (rect ? rect.left : 0) + (rect ? rect.width / 2 : 500)
  const clientY = (rect ? rect.top : 0) + (rect ? rect.height / 2 : 280)
  const p = toGraphPoint(clientX, clientY)
  const offset = (graph.value.nodes.length % 6) * 26
  addNode(type, p.x - NODE_W / 2 + offset, p.y - NODE_H / 2 + offset)
}

function onPaletteDragStart(event, type) {
  event.dataTransfer.setData('text/wf-node', type)
  event.dataTransfer.effectAllowed = 'copy'
}

function onDrop(event) {
  const type = event.dataTransfer.getData('text/wf-node')
  if (!type) return
  if (!current.value) {
    ElMessage.warning('请先选择或新建工作流')
    return
  }
  const p = toGraphPoint(event.clientX, event.clientY)
  addNode(type, p.x - NODE_W / 2, p.y - NODE_H / 2)
}

// ---------------------------------------------------------------------------
// 拖拽 / 连线 / 缩放
// ---------------------------------------------------------------------------

function startNodeDrag(event, node) {
  if (event.button !== 0) return
  selectNode(node, event)
  if (!selectedNodeIds.value.includes(node.id)) return
  const origins = graph.value.nodes
    .filter(n => selectedNodeIds.value.includes(n.id))
    .map(n => ({ id: n.id, x: n.x, y: n.y }))
  if (!origins.length) return
  dragState.value = {
    startX: event.clientX,
    startY: event.clientY,
    origins,
    moved: false,
  }
}

function startConnect(event, node) {
  if (event.button !== 0) return
  selectNode(node, event)
  const p = toGraphPoint(event.clientX, event.clientY)
  connecting.value = { source: node.id, x: p.x, y: p.y }
}

// 拖动时的对齐吸附：计算与其它节点左/中/右、上/中/下基准线最近的偏移
const SNAP_DISTANCE = 6

function snapDelta(origins, dx, dy) {
  if (!origins.length) return { dx, dy, guideX: null, guideY: null }
  const movingIds = new Set(origins.map(o => o.id))
  const others = graph.value.nodes.filter(n => !movingIds.has(n.id))
  if (!others.length) return { dx, dy, guideX: null, guideY: null }

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity
  origins.forEach(o => {
    minX = Math.min(minX, o.x)
    maxX = Math.max(maxX, o.x)
    minY = Math.min(minY, o.y)
    maxY = Math.max(maxY, o.y)
  })
  const vMoves = [minX + dx, (minX + maxX + NODE_W) / 2 + dx, maxX + NODE_W + dx]
  const hMoves = [minY + dy, (minY + maxY + NODE_H) / 2 + dy, maxY + NODE_H + dy]
  const threshold = SNAP_DISTANCE / scale.value
  let bestX = null
  let bestY = null

  others.forEach(n => {
    [n.x, n.x + NODE_W / 2, n.x + NODE_W].forEach(target => {
      vMoves.forEach(value => {
        const diff = target - value
        if (Math.abs(diff) <= threshold && (!bestX || Math.abs(diff) < Math.abs(bestX.diff))) {
          bestX = { diff, line: target }
        }
      })
    })
    ;[n.y, n.y + NODE_H / 2, n.y + NODE_H].forEach(target => {
      hMoves.forEach(value => {
        const diff = target - value
        if (Math.abs(diff) <= threshold && (!bestY || Math.abs(diff) < Math.abs(bestY.diff))) {
          bestY = { diff, line: target }
        }
      })
    })
  })

  return {
    dx: dx + (bestX ? bestX.diff : 0),
    dy: dy + (bestY ? bestY.diff : 0),
    guideX: bestX ? bestX.line : null,
    guideY: bestY ? bestY.line : null,
  }
}

function onCanvasMouseDown(event) {
  const target = event.target
  if (target.closest('.wf-node') || target.closest('.wf-canvas-toolbar') ||
      target.closest('.wf-approval-bar') || target.closest('.wf-run-status') ||
      target.closest('.wf-edge-hit')) {
    return
  }
  // 中键或 Alt+左键：平移画布；左键空白处：框选
  if (event.button === 1 || (event.button === 0 && event.altKey)) {
    event.preventDefault()
    panState.value = {
      startX: event.clientX,
      startY: event.clientY,
      ox: offsetX.value,
      oy: offsetY.value,
    }
    return
  }
  if (event.button !== 0) return
  boxState.value = {
    startX: event.clientX,
    startY: event.clientY,
    currentX: event.clientX,
    currentY: event.clientY,
    additive: event.ctrlKey || event.metaKey || event.shiftKey,
    baseIds: [...selectedNodeIds.value],
    moved: false,
  }
}

function onWindowMouseMove(event) {
  if (dragState.value) {
    const ds = dragState.value
    const rawDx = (event.clientX - ds.startX) / scale.value
    const rawDy = (event.clientY - ds.startY) / scale.value
    if (!ds.moved && (Math.abs(rawDx) > 1 || Math.abs(rawDy) > 1)) ds.moved = true
    const snap = snapDelta(ds.origins, rawDx, rawDy)
    ds.origins.forEach(o => {
      const node = graph.value.nodes.find(n => n.id === o.id)
      if (!node) return
      node.x = Math.round(o.x + snap.dx)
      node.y = Math.round(o.y + snap.dy)
    })
    guides.value = { x: snap.guideX, y: snap.guideY }
    return
  }
  if (panState.value) {
    const ps = panState.value
    offsetX.value = ps.ox + (event.clientX - ps.startX)
    offsetY.value = ps.oy + (event.clientY - ps.startY)
    return
  }
  if (boxState.value) {
    const bs = boxState.value
    bs.currentX = event.clientX
    bs.currentY = event.clientY
    if (!bs.moved && (Math.abs(bs.currentX - bs.startX) > 3 || Math.abs(bs.currentY - bs.startY) > 3)) {
      bs.moved = true
    }
    return
  }
  if (connecting.value) {
    const p = toGraphPoint(event.clientX, event.clientY)
    connecting.value.x = p.x
    connecting.value.y = p.y
  }
}

function onWindowMouseUp(event) {
  if (dragState.value) {
    if (dragState.value.moved) dirty.value = true
    dragState.value = null
    guides.value = { x: null, y: null }
  }
  if (panState.value) panState.value = null
  if (boxState.value) {
    const bs = boxState.value
    boxState.value = null
    if (bs.moved) {
      const p1 = toGraphPoint(Math.min(bs.startX, bs.currentX), Math.min(bs.startY, bs.currentY))
      const p2 = toGraphPoint(Math.max(bs.startX, bs.currentX), Math.max(bs.startY, bs.currentY))
      const hits = graph.value.nodes
        .filter(n => n.x < p2.x && n.x + NODE_W > p1.x && n.y < p2.y && n.y + NODE_H > p1.y)
        .map(n => n.id)
      const ids = bs.additive ? [...new Set([...bs.baseIds, ...hits])] : hits
      selectedNodeIds.value = ids
      selectedNodeId.value = ids[0] || null
      if (ids.length) selectedEdgeId.value = null
    } else if (!bs.additive) {
      selectedNodeIds.value = []
      selectedNodeId.value = null
      selectedEdgeId.value = null
    }
  }
  if (connecting.value) {
    const sourceId = connecting.value.source
    const el = document.elementFromPoint(event.clientX, event.clientY)
    const nodeEl = el && el.closest ? el.closest('[data-node-id]') : null
    const targetId = nodeEl ? nodeEl.getAttribute('data-node-id') : ''
    connecting.value = null
    if (targetId && targetId !== sourceId &&
        !graph.value.edges.some(e => e.source === sourceId && e.target === targetId)) {
      graph.value.edges.push({ id: uid('e'), source: sourceId, target: targetId, branch: 'default' })
      dirty.value = true
    }
  }
}

function onWheel(event) {
  const delta = event.deltaY > 0 ? -0.08 : 0.08
  zoomAt(scale.value + delta, event.clientX, event.clientY)
}

function zoomAt(nextScale, clientX, clientY) {
  const rect = canvasRef.value ? canvasRef.value.getBoundingClientRect() : null
  if (!rect) return
  const px = clientX - rect.left
  const py = clientY - rect.top
  const clamped = Math.min(2, Math.max(0.3, nextScale))
  const wx = (px - offsetX.value) / scale.value
  const wy = (py - offsetY.value) / scale.value
  scale.value = clamped
  offsetX.value = px - wx * clamped
  offsetY.value = py - wy * clamped
}

function zoomBy(delta) {
  const rect = canvasRef.value ? canvasRef.value.getBoundingClientRect() : null
  const cx = rect ? rect.left + rect.width / 2 : 0
  const cy = rect ? rect.top + rect.height / 2 : 0
  zoomAt(scale.value + delta, cx, cy)
}

function resetView() {
  scale.value = 1
  offsetX.value = 80
  offsetY.value = 60
}

// ---------------------------------------------------------------------------
// 连线绘制
// ---------------------------------------------------------------------------

function edgeAnchors(edge) {
  const s = graph.value.nodes.find(n => n.id === edge.source)
  const t = graph.value.nodes.find(n => n.id === edge.target)
  if (!s || !t) return null
  return {
    x1: s.x + NODE_W,
    y1: s.y + NODE_H / 2,
    x2: t.x,
    y2: t.y + NODE_H / 2,
  }
}

function edgePath(edge) {
  const a = edgeAnchors(edge)
  if (!a) return ''
  const dx = Math.max(60, Math.abs(a.x2 - a.x1) / 2)
  return `M ${a.x1} ${a.y1} C ${a.x1 + dx} ${a.y1}, ${a.x2 - dx} ${a.y2}, ${a.x2} ${a.y2}`
}

// 自循环连线：从节点右侧上方绕出、回到右侧下方
function selfLoopPath(node) {
  const sx = node.x + 190
  const sy = node.y + 14
  const ex = node.x + 190
  const ey = node.y + 58
  return `M ${sx} ${sy} C ${sx + 78} ${sy - 38}, ${sx + 78} ${ey + 38}, ${ex} ${ey}`
}

function loopLabel(node) {
  const loop = (node.config && node.config.loop) || {}
  return `循环 ≤${loop.max_times || 3}`
}

function edgeClass(edge) {
  return { active: selectedEdgeId.value === edge.id }
}

function edgeLabelPos(edge) {
  const a = edgeAnchors(edge)
  if (!a) return { x: 0, y: 0 }
  return { x: (a.x1 + a.x2) / 2, y: (a.y1 + a.y2) / 2 - 8 }
}

function branchLabel(branch) {
  const opt = branchOptions.find(b => b.value === branch)
  return opt ? opt.label : branch
}

// ---------------------------------------------------------------------------
// 运行 / 审批 / 轮询
// ---------------------------------------------------------------------------

async function openRunDialog() {
  if (!current.value) return
  if (dirty.value) await saveWorkflow()
  const inputs = {}
  ;(current.value.variables || []).forEach(v => {
    if (v.name) inputs[v.name] = v.default === undefined || v.default === null ? '' : v.default
  })
  runInputs.value = inputs
  runDialog.value = true
}

async function startRun() {
  if (!current.value) return
  const inputs = {}
  Object.entries(runInputs.value || {}).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) inputs[key] = value
  })
  try {
    const res = await api.workflow.run(current.value.id, inputs)
    runDialog.value = false
    clearRunVisual()
    applyRun(res.data)
    startPolling(res.data.run_id)
    ElMessage.success('工作流已启动')
  } catch (e) { /* 拦截器已提示 */ }
}

function startPolling(runId) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await api.workflow.getRun(runId)
      applyRun(res.data)
      const status = res.data.status
      if (!['pending', 'running', 'waiting_approval'].includes(status)) {
        stopPolling()
        loadRuns()
        if (status === 'completed') ElMessage.success('工作流执行完成')
        else if (status === 'failed') ElMessage.error('工作流执行失败：' + (res.data.error_message || '未知错误'))
      }
    } catch (e) {
      stopPolling()
    }
  }, 1200)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function applyRun(detail) {
  if (!detail) return
  activeRun.value = detail
  clearRunVisual()
  ;(detail.nodes || []).forEach(n => {
    nodeStatus[n.node_id] = n.status
    runNodeRecords[n.node_id] = n
    if (n.output !== undefined && n.output !== null) nodeOutputs[n.node_id] = n.output
  })
}

function clearRunVisual() {
  Object.keys(nodeStatus).forEach(k => delete nodeStatus[k])
  Object.keys(nodeOutputs).forEach(k => delete nodeOutputs[k])
  Object.keys(runNodeRecords).forEach(k => delete runNodeRecords[k])
}

async function submitApproval(approved) {
  if (!activeRun.value) return
  try {
    const res = await api.workflow.approve(activeRun.value.run_id, {
      approved,
      comment: approvalComment.value,
    })
    approvalComment.value = ''
    applyRun(res.data)
    ElMessage.success(approved ? '已通过审批，流程继续执行' : '已拒绝审批')
    if (['pending', 'running'].includes(res.data.status)) startPolling(res.data.run_id)
    else loadRuns()
  } catch (e) { /* 拦截器已提示 */ }
}

async function cancelActiveRun() {
  if (!activeRun.value) return
  try {
    await ElMessageBox.confirm('确定取消当前工作流执行？', '提示', { type: 'warning' })
    await api.workflow.cancelRun(activeRun.value.run_id)
    stopPolling()
    const res = await api.workflow.getRun(activeRun.value.run_id)
    applyRun(res.data)
    loadRuns()
    ElMessage.success('已取消执行')
  } catch (e) { /* 取消 */ }
}

// ---------------------------------------------------------------------------
// 执行记录
// ---------------------------------------------------------------------------

function openRunsDrawer() {
  runsDrawer.value = true
  loadRuns()
}

async function loadRuns() {
  try {
    const res = await api.workflow.runs({ per_page: 50, workflow_id: current.value ? current.value.id : undefined })
    runsList.value = res.data?.items || []
  } catch (e) { /* 拦截器已提示 */ }
}

async function loadRunDetail(runId) {
  try {
    const res = await api.workflow.getRun(runId)
    if (res.data.workflow_id && (!current.value || current.value.id !== res.data.workflow_id)) {
      await loadWorkflow(res.data.workflow_id)
    }
    applyRun(res.data)
    if (['pending', 'running', 'waiting_approval'].includes(res.data.status)) startPolling(runId)
    else stopPolling()
  } catch (e) { /* 拦截器已提示 */ }
}

const STATUS_LABELS = {
  pending: '待启动',
  running: '执行中',
  waiting_approval: '待审批',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}

function statusLabel(status) {
  return STATUS_LABELS[status] || status || ''
}

function statusIcon(status) {
  const map = {
    pending: 'fa-hourglass-start',
    running: 'fa-spinner fa-spin',
    waiting_approval: 'fa-user-clock',
    completed: 'fa-check-circle',
    failed: 'fa-times-circle',
    cancelled: 'fa-ban',
    skipped: 'fa-forward',
  }
  return map[status] || 'fa-info-circle'
}

function runNode(id) {
  return runNodeRecords[id] || null
}

function nodeError(id) {
  const rec = runNodeRecords[id]
  if (!rec || rec.status !== 'failed') return ''
  return rec.error_message || '节点执行失败（未返回错误信息）'
}

function nodeTitle(node) {
  const rec = runNodeRecords[node.id]
  if (!rec) return ''
  if (rec.status === 'failed') return '执行失败：' + (rec.error_message || '未知原因')
  return ''
}

function durationText(rec) {
  if (!rec || !rec.started_at) return ''
  const start = new Date(rec.started_at).getTime()
  const end = rec.completed_at ? new Date(rec.completed_at).getTime() : Date.now()
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return ''
  const sec = (end - start) / 1000
  if (sec < 1) return Math.round(sec * 1000) + 'ms'
  if (sec < 60) return sec.toFixed(1) + 's'
  return Math.floor(sec / 60) + 'm' + Math.round(sec % 60) + 's'
}

function formatTime(time) {
  if (!time) return ''
  return String(time).replace('T', ' ').slice(0, 19)
}

function runProgressText(run) {
  if (!run) return ''
  if (run.status === 'completed') return '全部节点已完成'
  if (run.status === 'cancelled') return '流程已取消'
  if (run.status === 'failed') return '流程执行中断'
  if (run.status === 'waiting_approval') {
    return '等待审批：' + ((run.pending_approval && run.pending_approval.node_name) || '')
  }
  return run.current_node_id ? '当前节点：' + nodeName(run.current_node_id) : '准备执行'
}

// ---------------------------------------------------------------------------
// 键盘与生命周期
// ---------------------------------------------------------------------------

function onKeyDown(event) {
  const tag = (event.target && event.target.tagName ? event.target.tagName : '').toLowerCase()
  if (['input', 'textarea', 'select'].includes(tag) || (event.target && event.target.isContentEditable)) return
  if (event.key === 'Delete' || event.key === 'Backspace') {
    if (selectedNodeIds.value.length) {
      event.preventDefault()
      deleteSelectedNode()
    } else if (selectedEdgeId.value) {
      event.preventDefault()
      deleteSelectedEdge()
    }
  }
}

onMounted(async () => {
  window.addEventListener('mousemove', onWindowMouseMove)
  window.addEventListener('mouseup', onWindowMouseUp)
  window.addEventListener('keydown', onKeyDown)
  await loadCapabilities()
  await loadWorkflows()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onWindowMouseMove)
  window.removeEventListener('mouseup', onWindowMouseUp)
  window.removeEventListener('keydown', onKeyDown)
  stopPolling()
})
</script>

<style scoped>
.wf-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 560px;
  gap: 10px;
}
.wf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.wf-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  min-width: 0;
}
.wf-title > i {
  color: #3b82f6;
}
.wf-name-input {
  border: 1px solid transparent;
  background: transparent;
  font-size: 15px;
  font-weight: 600;
  color: #1f2937;
  padding: 4px 6px;
  border-radius: 6px;
  outline: none;
  min-width: 180px;
  max-width: 320px;
}
.wf-name-input:hover,
.wf-name-input:focus {
  border-color: #cbd5e1;
  background: #f8fafc;
}
.wf-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.wf-body {
  flex: 1;
  display: flex;
  min-height: 0;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

/* 左侧 */
.wf-side {
  width: 236px;
  flex-shrink: 0;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
  background: #fbfcfe;
}
.wf-side-section {
  padding: 12px;
  border-bottom: 1px solid #eef2f7;
}
.wf-side-title {
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.wf-tip {
  font-weight: 400;
  color: #94a3b8;
  font-size: 11px;
}
.wf-wf-list {
  margin-top: 8px;
  max-height: 220px;
  overflow-y: auto;
}
.wf-wf-item {
  position: relative;
  padding: 8px 26px 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  margin-bottom: 6px;
  cursor: pointer;
  background: #fff;
  transition: all 0.15s;
}
.wf-wf-item:hover {
  border-color: #93c5fd;
}
.wf-wf-item.active {
  border-color: #3b82f6;
  background: #eff6ff;
}
.wf-wf-name {
  font-size: 13px;
  color: #1f2937;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-wf-meta {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 2px;
}
.wf-wf-del {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: #cbd5e1;
  font-size: 12px;
}
.wf-wf-del:hover {
  color: #ef4444;
}
.wf-palette {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.wf-palette-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  color: #334155;
  cursor: grab;
  user-select: none;
  transition: all 0.15s;
}
.wf-palette-item:hover {
  border-color: #93c5fd;
  background: #f0f9ff;
}
.wf-palette-icon {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  flex-shrink: 0;
}
.wf-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 11px;
  color: #64748b;
}
.wf-legend > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
}
.legend-dot.running { background: #f59e0b; }
.legend-dot.success { background: #10b981; }
.legend-dot.failed { background: #ef4444; }
.legend-dot.waiting { background: #f97316; }

/* 画布 */
.wf-canvas {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  cursor: default;
  background-color: #f8fafc;
  background-image: radial-gradient(circle, #d7dee8 1px, transparent 1px);
  background-size: 20px 20px;
}
.wf-world {
  position: absolute;
  top: 0;
  left: 0;
  width: 6000px;
  height: 4000px;
  transform-origin: 0 0;
}
.wf-edges {
  position: absolute;
  top: 0;
  left: 0;
  overflow: visible;
  pointer-events: none;
}
.wf-edge {
  fill: none;
  stroke: #94a3b8;
  stroke-width: 2;
}
.wf-edge.active {
  stroke: #3b82f6;
  stroke-width: 3;
}
.wf-edge.temp {
  stroke: #3b82f6;
  stroke-dasharray: 6 4;
}
.wf-self-loop {
  stroke: #0ea5e9;
  stroke-width: 2;
  stroke-dasharray: 7 5;
  opacity: 0.9;
}
.wf-self-loop.active {
  animation: wf-dash 0.8s linear infinite;
}
.wf-loop-label {
  fill: #0284c7;
  font-size: 11px;
}
@keyframes wf-dash {
  to { stroke-dashoffset: -24; }
}
.wf-edge-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 14;
  pointer-events: stroke;
  cursor: pointer;
}
.wf-edge-label {
  font-size: 11px;
  fill: #64748b;
  text-anchor: middle;
  pointer-events: none;
}
.wf-guide {
  stroke: #f43f5e;
  stroke-width: 1;
  stroke-dasharray: 4 4;
  vector-effect: non-scaling-stroke;
  pointer-events: none;
}
.wf-select-box {
  position: absolute;
  border: 1px dashed #3b82f6;
  background: rgba(59, 130, 246, 0.08);
  border-radius: 2px;
  pointer-events: none;
  z-index: 4;
}
.wf-node {
  position: absolute;
  width: 190px;
  height: 72px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  box-sizing: border-box;
  background: #fff;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
  cursor: move;
  user-select: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.wf-node:hover {
  border-color: #93c5fd;
}
.wf-node.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.16);
}
.wf-node.running {
  border-color: #f59e0b;
  animation: wf-pulse 1.2s ease-in-out infinite;
}
.wf-node.success {
  border-color: #10b981;
}
.wf-node.failed {
  border-color: #ef4444;
}
.wf-node.waiting {
  border-color: #f97316;
  border-style: dashed;
  animation: wf-pulse 1.4s ease-in-out infinite;
}
@keyframes wf-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.35); }
  50% { box-shadow: 0 0 0 7px rgba(245, 158, 11, 0); }
}
.wf-node-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  flex-shrink: 0;
}
.wf-node-body {
  flex: 1;
  min-width: 0;
}
.wf-node-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-node-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-port {
  position: absolute;
  right: -7px;
  top: 50%;
  transform: translateY(-50%);
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid #3b82f6;
  background: #fff;
  cursor: crosshair;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 2;
}
.wf-node:hover .wf-port {
  opacity: 1;
}
.wf-node-badge {
  position: absolute;
  top: -8px;
  right: -8px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.25);
  z-index: 2;
}
.wf-node-badge.ok { background: #10b981; }
.wf-node-badge.bad { background: #ef4444; }
.wf-node-badge.wait { background: #f97316; }
.wf-canvas-toolbar {
  position: absolute;
  right: 16px;
  bottom: 16px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  z-index: 5;
}
.wf-canvas-hint {
  padding: 3px 8px;
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.55);
  color: #e2e8f0;
  font-size: 11px;
  line-height: 1.5;
  white-space: nowrap;
  pointer-events: none;
}
.wf-approval-bar {
  position: absolute;
  top: 12px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  max-width: calc(100% - 32px);
  padding: 10px 14px;
  background: #fff7ed;
  border: 1px solid #fdba74;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.12);
  z-index: 6;
}
.wf-approval-main {
  min-width: 180px;
  max-width: 420px;
}
.wf-approval-title {
  font-size: 13px;
  font-weight: 600;
  color: #c2410c;
}
.wf-approval-msg {
  font-size: 12px;
  color: #92400e;
  margin-top: 2px;
  word-break: break-all;
}
.wf-run-status {
  position: absolute;
  left: 16px;
  bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.85);
  color: #fff;
  font-size: 12px;
  z-index: 5;
}
.wf-run-status.st-completed { background: #059669; }
.wf-run-status.st-failed { background: #dc2626; }
.wf-run-status.st-waiting_approval { background: #ea580c; }
.wf-run-status.st-cancelled { background: #64748b; }
.wf-run-node {
  opacity: 0.85;
}
.wf-run-id {
  opacity: 0.6;
  font-family: Consolas, Monaco, monospace;
}
.wf-empty-canvas {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
  pointer-events: none;
}
.wf-empty-canvas > i {
  font-size: 42px;
  margin-bottom: 10px;
  opacity: 0.6;
}

/* 右侧属性面板 */
.wf-props {
  width: 320px;
  flex-shrink: 0;
  border-left: 1px solid #e5e7eb;
  overflow-y: auto;
  background: #fbfcfe;
}
.wf-props-inner {
  padding: 14px;
}
.wf-multi-tip {
  margin: 10px 12px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  color: #1d4ed8;
  font-size: 12px;
  line-height: 1.6;
}
.wf-props-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid #eef2f7;
}
.wf-hint {
  font-size: 12px;
  line-height: 1.7;
  color: #64748b;
  background: #f1f5f9;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 10px;
  word-break: break-all;
}
.wf-hint code {
  background: #e2e8f0;
  border-radius: 3px;
  padding: 0 4px;
  color: #0f172a;
}
.wf-param-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
  margin: 4px 0 8px;
}
.wf-param-row {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  padding: 8px 10px;
  margin-bottom: 8px;
}
.wf-param-name {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #1f2937;
  margin-bottom: 6px;
}
.wf-param-name code {
  background: #f1f5f9;
  border-radius: 3px;
  padding: 0 4px;
  color: #475569;
  font-size: 11px;
}
.wf-param-label {
  font-weight: 600;
}
.wf-param-type {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
}
.wf-param-map {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.wf-param-advanced {
  margin: 4px 0 10px;
  font-size: 12px;
  color: #64748b;
}
.wf-param-advanced summary {
  cursor: pointer;
  margin-bottom: 6px;
}
.wf-output-box {
  margin-top: 10px;
  border-top: 1px dashed #e2e8f0;
  padding-top: 10px;
}
.wf-output-title {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.wf-output-box pre {
  margin: 0;
  max-height: 240px;
  overflow: auto;
  background: #0f172a;
  color: #cbd5e1;
  font-size: 11px;
  line-height: 1.6;
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
.wf-var-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.wf-var-item {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  padding: 4px 8px;
  background: #f1f5f9;
  border-radius: 4px;
}
.wf-var-default {
  color: #94a3b8;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-muted {
  color: #94a3b8;
  font-size: 12px;
}
.wf-var-editor {
  width: 100%;
}

/* 执行记录抽屉 */
.wf-runs {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wf-run-item {
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  cursor: pointer;
  background: #fff;
  transition: all 0.15s;
}
.wf-run-item:hover {
  border-color: #93c5fd;
}
.wf-run-item.active {
  border-color: #3b82f6;
  background: #eff6ff;
}
.wf-run-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475569;
}
.wf-run-badge {
  padding: 1px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 11px;
}
.wf-run-badge.st-running { background: #fef3c7; color: #b45309; }
.wf-run-badge.st-waiting_approval { background: #ffedd5; color: #c2410c; }
.wf-run-badge.st-completed { background: #d1fae5; color: #047857; }
.wf-run-badge.st-failed { background: #fee2e2; color: #b91c1c; }
.wf-run-badge.st-cancelled { background: #e2e8f0; color: #475569; }
.wf-run-item-id {
  font-family: Consolas, Monaco, monospace;
  color: #64748b;
}
.wf-run-item-time {
  margin-left: auto;
  color: #94a3b8;
}
.wf-run-item-sub {
  margin-top: 4px;
  font-size: 12px;
  color: #64748b;
}
.wf-run-error {
  display: block;
  margin-top: 3px;
  color: #dc2626;
  word-break: break-all;
}

/* 节点失败原因浮层 */
.wf-node-error {
  position: absolute;
  left: 0;
  top: 78px;
  width: 260px;
  display: flex;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 6px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 11px;
  line-height: 1.5;
  word-break: break-all;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.16);
  max-height: 84px;
  overflow: hidden;
  cursor: pointer;
  z-index: 60;
}
.wf-node-error i {
  margin-top: 2px;
}

/* 属性栏最近运行 */
.wf-run-info-box .wf-output-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.wf-run-badge.small {
  padding: 0 6px;
  font-size: 10px;
}
.wf-run-badge.st-pending { background: #e0e7ff; color: #4338ca; }
.wf-run-info-time {
  margin-left: auto;
  color: #94a3b8;
}
.wf-run-info-error {
  display: flex;
  gap: 6px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}

/* 执行记录详情 */
.wf-run-detail {
  margin-top: 18px;
  border-top: 1px solid #e5e7eb;
  padding-top: 14px;
}
.wf-run-detail-head {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #475569;
}
.wf-run-detail-id {
  font-family: Consolas, Monaco, monospace;
  color: #64748b;
}
.wf-run-detail-time {
  margin-left: auto;
  color: #94a3b8;
}
.wf-run-detail-error {
  margin-top: 10px;
  padding: 8px 10px;
  border-radius: 6px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}
.wf-run-detail-title {
  margin: 16px 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}
.wf-run-detail-nodes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.wf-run-detail-node {
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
}
.wf-run-detail-node.st-failed {
  border-color: #fecaca;
  background: #fff7f7;
}
.wf-run-detail-node-main {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475569;
}
.wf-run-detail-node-icon {
  color: #94a3b8;
}
.wf-run-detail-node.st-completed .wf-run-detail-node-icon { color: #10b981; }
.wf-run-detail-node.st-failed .wf-run-detail-node-icon { color: #ef4444; }
.wf-run-detail-node.st-running .wf-run-detail-node-icon { color: #f59e0b; }
.wf-run-detail-node-name {
  font-weight: 600;
  color: #1e293b;
}
.wf-run-detail-node-type {
  color: #94a3b8;
}
.wf-run-detail-node-dur {
  margin-left: auto;
  color: #94a3b8;
  font-size: 11px;
}
.wf-run-detail-node-error {
  margin-top: 6px;
  display: flex;
  gap: 6px;
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
}
.wf-run-detail-node-output {
  margin-top: 6px;
}
.wf-run-detail-node-output summary {
  cursor: pointer;
  color: #2563eb;
  font-size: 12px;
}
.wf-run-detail-node-output pre {
  margin: 6px 0 0;
  max-height: 200px;
  overflow: auto;
  background: #0f172a;
  color: #cbd5e1;
  font-size: 11px;
  line-height: 1.6;
  padding: 10px;
  border-radius: 6px;
  white-space: pre-wrap;
  word-break: break-all;
}
.wf-run-detail-logs {
  max-height: 260px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  background: #f8fafc;
}
.wf-run-detail-log {
  display: flex;
  gap: 8px;
  font-size: 12px;
  line-height: 1.8;
  color: #475569;
  word-break: break-all;
}
.wf-run-detail-log-time {
  flex: none;
  color: #94a3b8;
  font-family: Consolas, Monaco, monospace;
}
.wf-run-detail-log.lv-warning { color: #b45309; }
.wf-run-detail-log.lv-error { color: #b91c1c; }

@media (max-width: 1280px) {
  .wf-props { width: 280px; }
  .wf-side { width: 210px; }
}
</style>