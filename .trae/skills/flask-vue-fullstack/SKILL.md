---
name: "flask-vue-fullstack"
description: "Guide Flask+Vue fullstack feature development with layered architecture. Invoke when adding new features, models, routes, services, or Vue components to this project."
---

# Flask+Vue 全栈功能开发指南

本项目的全栈架构为 Flask(后端) + Vue 3 + Element Plus(前端)，遵循分层架构。每次新增功能必须按以下步骤完整实现，确保不遗漏。

## 项目结构

```
backend/app/
  ├── models/          # 数据模型 (SQLAlchemy)
  │   └── __init__.py  # 必须注册新模型到 __all__
  ├── services/        # 业务逻辑层
  ├── routes/          # API路由层 (Blueprint)
  ├── utils/           # 工具类
  └── __init__.py      # 应用工厂，注册Blueprint

frontend/src/
  ├── api/index.js     # 统一API方法定义
  ├── views/           # 页面组件 (.vue)
  ├── stores/          # Pinia状态管理
  └── router/          # 路由配置
```

## 新功能开发检查清单

### 1. 后端 Model 层

文件位置: `backend/app/models/<model_name>.py`

```python
from app import db
from datetime import datetime

class NewModel(db.Model):
    __tablename__ = 'new_table'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
```

**必须操作**:
- 在 `backend/app/models/__init__.py` 中 import 新模型并加入 `__all__` 列表
- 如果新模型有关联字段(外键)，确保被引用的模型已在该文件中 import

### 2. 后端 Service 层

文件位置: `backend/app/services/<service_name>.py`

```python
import logging
from app import db
from app.models.new_model import NewModel

logger = logging.getLogger(__name__)

class NewService:
    @staticmethod
    def create(data):
        item = NewModel(**data)
        db.session.add(item)
        db.session.commit()
        return item

    @staticmethod
    def get_by_id(item_id):
        return NewModel.query.get(item_id)

    @staticmethod
    def update(item_id, data):
        item = NewModel.query.get(item_id)
        if not item:
            return None
        for key, value in data.items():
            setattr(item, key, value)
        db.session.commit()
        return item

    @staticmethod
    def delete(item_id):
        item = NewModel.query.get(item_id)
        if item:
            db.session.delete(item)
            db.session.commit()
            return True
        return False

    @staticmethod
    def list_all():
        return NewModel.query.all()
```

**数据库连接调用规范**:
- 获取连接器必须使用 `pool.get_connector_with_health_check(conn_id)`，不要用 `pool.get_connector()`
- 所有数据库查询操作使用 `stream_results=True` 流式结果集
- 批量查询单参数SQL会自动转IN模式

### 3. 后端 Route 层

文件位置: `backend/app/routes/<route_name>.py`

```python
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.services.new_service import NewService

bp = Blueprint('new_feature', __name__, url_prefix='/new-feature')

@bp.route('', methods=['GET'])
@login_required
def list_items():
    items = NewService.list_all()
    return jsonify([item.to_dict() for item in items])

@bp.route('', methods=['POST'])
@login_required
def create_item():
    data = request.get_json()
    item = NewService.create(data)
    return jsonify(item.to_dict()), 201

@bp.route('/<int:item_id>', methods=['PUT'])
@login_required
def update_item(item_id):
    data = request.get_json()
    item = NewService.update(item_id, data)
    if not item:
        return jsonify({'error': '未找到'}), 404
    return jsonify(item.to_dict())

@bp.route('/<int:item_id>', methods=['DELETE'])
@login_required
def delete_item(item_id):
    if NewService.delete(item_id):
        return jsonify({'message': '删除成功'})
    return jsonify({'error': '未找到'}), 404

@bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    ids = request.get_json().get('ids', [])
    for item_id in ids:
        NewService.delete(item_id)
    return jsonify({'message': f'已删除 {len(ids)} 条记录'})
```

**必须操作**:
- 在 `backend/app/__init__.py` 中注册 Blueprint: `from app.routes.<route_name> import bp as <route_name>_bp; app.register_blueprint(<route_name>_bp)`

### 4. 权限控制（如需要）

**后端**: 在路由函数上加权限检查

**前端 RoleManager.vue**:
- 在 `menuPermLabels` 中添加菜单权限项
- 在 `buttonPermLabels` 中添加按钮权限项
- 在 `menuOptions` 中添加菜单选项
- 在 `buttonPermGroups` 中将按钮权限分组到对应菜单下

**前端组件中使用**:
```vue
<el-button v-hasPermi="['feature:action']">操作</el-button>
```

**后端 store 中的权限检查**:
```javascript
store.hasButtonPermission('feature:action')
```

### 5. 前端 API 层

文件位置: `frontend/src/api/index.js`

在对应的 API 分组中添加方法:

```javascript
const newFeature = {
  list: () => http.get('/new-feature'),
  create: (data) => http.post('/new-feature', data),
  update: (id, data) => http.put(`/new-feature/${id}`, data),
  delete: (id) => http.delete(`/new-feature/${id}`),
  batchDelete: (ids) => http.post('/new-feature/batch-delete', { ids }),
}

// 在 export default 中添加 newFeature
```

### 6. 前端 Vue 组件

文件位置: `frontend/src/views/<ComponentName>.vue`

遵循 Element Plus 组件库规范:

```vue
<template>
  <div class="feature-name">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <span><i class="fas fa-icon"></i> 功能名称</span>
          <div class="card-header-actions">
            <el-button type="primary" @click="openDialog()">
              <i class="fas fa-plus"></i> 新建
            </el-button>
          </div>
        </div>
      </template>
      <!-- 内容 -->
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/api'

// 响应式数据
const loading = ref(false)
const dataList = ref([])

// 生命周期
onMounted(() => {
  fetchData()
})

// 方法
const fetchData = async () => {
  loading.value = true
  try {
    const res = await api.newFeature.list()
    dataList.value = res.data || res
  } catch (e) {
    // 错误已由拦截器处理
  } finally {
    loading.value = false
  }
}
</script>
```

### 7. 路由注册

文件位置: `frontend/src/router/index.js`

```javascript
{
  path: '/new-feature',
  name: 'NewFeature',
  component: () => import('@/views/NewFeature.vue'),
  meta: { title: '功能名称', requiresAuth: true }
}
```

## 常见陷阱与规范

1. **模型注册**: 新模型必须在 `models/__init__.py` 中注册，否则数据库迁移不会创建表
2. **Blueprint注册**: 新路由必须在 `app/__init__.py` 中注册，否则404
3. **连接器获取**: 统一使用 `get_connector_with_health_check()`，不要用 `get_connector()`
4. **流式查询**: 大数据量查询必须 `execution_options(stream_results=True)`
5. **API export**: 新增的API分组必须加到 `export default` 中
6. **权限同步**: 添加新功能时同步更新 RoleManager 的权限定义
7. **缩进检查**: `__init__.py` 中的 import 缩进必须正确，2个空格偏差就会导致 `IndentationError`
8. **批量操作**: 每个模块都要提供 `batch-delete` 端点，遵循 `POST /xxx/batch-delete` + `{ ids: [] }` 格式
