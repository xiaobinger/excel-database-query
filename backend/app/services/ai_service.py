import json
import logging
import re
import requests
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ============ Tool Definitions ============
AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_export_options",
            "description": "列出所有可用的导出选项，包括名称、描述、参数等信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "可选，按名称或描述筛选的关键词"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "parse_uploaded_file",
            "description": "解析用户上传的Excel/CSV文件，获取列名、行数、数据预览等信息。当用户提到上传了文件或附件时调用此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {
                        "type": "string",
                        "description": "上传的文件名"
                    }
                },
                "required": ["filename"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_query_options",
            "description": "列出所有可用的查询选项，包括名称、描述等信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "可选，按名称或描述筛选的关键词"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_export",
            "description": "当用户明确要执行导出任务时调用此工具。需要指定导出选项名称和参数值。",
            "parameters": {
                "type": "object",
                "properties": {
                    "export_option_name": {
                        "type": "string",
                        "description": "要使用的导出选项名称"
                    },
                    "params": {
                        "type": "object",
                        "description": "参数键值对，键为参数名，值为用户提供的参数值",
                        "additionalProperties": {"type": "string"}
                    },
                    "output_format": {
                        "type": "string",
                        "enum": ["sheets", "zip"],
                        "description": "输出格式：sheets=多工作表，zip=多文件压缩"
                    },
                    "description": {
                        "type": "string",
                        "description": "用户原始需求的简要描述"
                    }
                },
                "required": ["export_option_name", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_query",
            "description": "当用户明确要执行查询任务时调用此工具。需要指定查询选项名称。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query_option_name": {
                        "type": "string",
                        "description": "要使用的查询选项名称"
                    },
                    "description": {
                        "type": "string",
                        "description": "用户原始需求的简要描述"
                    }
                },
                "required": ["query_option_name", "description"]
            }
        }
    }
]


class AiService:

    @staticmethod
    def test_connection(config) -> dict:
        """测试AI配置连接"""
        api_key = config.get_api_key()
        if not api_key:
            raise ValueError('API密钥未配置')

        api_base = config.api_base or 'https://api.openai.com/v1'
        url = f"{api_base.rstrip('/')}/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': config.model_name or 'gpt-3.5-turbo',
            'messages': [{'role': 'user', 'content': 'Hello, test connection.'}],
            'max_tokens': 10,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        return {
            'model': result.get('model', ''),
            'usage': result.get('usage', {}),
        }

    @staticmethod
    def chat(config, messages: list) -> Tuple[str, int]:
        """调用AI对话"""
        api_key = config.get_api_key()
        if not api_key:
            raise ValueError('API密钥未配置')

        api_base = config.api_base or 'https://api.openai.com/v1'
        url = f"{api_base.rstrip('/')}/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': config.model_name or 'gpt-3.5-turbo',
            'messages': messages,
            'max_tokens': config.max_tokens or 4096,
            'temperature': config.temperature if config.temperature is not None else 0.7,
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        content = ''
        if result.get('choices') and len(result['choices']) > 0:
            content = result['choices'][0].get('message', {}).get('content', '')

        tokens = result.get('usage', {}).get('total_tokens', 0)
        return content, tokens

    @staticmethod
    def build_chat_context(user_id: int, chat_id: int = None) -> str:
        """构建AI对话上下文，包含用户Skills和行为摘要"""
        from app.models.ai_skill import AiSkill
        from app.models.user_behavior import UserBehavior

        context_parts = ['你是Excel数据库查询系统的AI助手。你可以帮助用户：\n'
                        '1. 根据自然语言需求生成SQL查询语句\n'
                        '2. 创建查询选项和导出选项\n'
                        '3. 配置自动导出任务\n'
                        '4. 优化SQL语句\n'
                        '5. 分析数据并提供洞察\n'
                        '6. 解答系统使用问题\n']

        # Add user skills
        skills = AiSkill.query.filter(
            (AiSkill.skill_type == 'system') | (AiSkill.user_id == user_id),
            AiSkill.is_active == True
        ).all()

        if skills:
            context_parts.append('\n## 用户技能库')
            for skill in skills:
                context_parts.append(f'- {skill.name}({skill.category}): {skill.description}')

        # Add recent behavior summary
        recent_behaviors = UserBehavior.query.filter_by(user_id=user_id)\
            .order_by(UserBehavior.created_at.desc()).limit(20).all()

        if recent_behaviors:
            action_counts = {}
            for b in recent_behaviors:
                key = f"{b.action}:{b.target_type or ''}"
                action_counts[key] = action_counts.get(key, 0) + 1

            context_parts.append('\n## 用户近期行为摘要')
            for key, count in sorted(action_counts.items(), key=lambda x: -x[1]):
                context_parts.append(f'- {key}: {count}次')

        return '\n'.join(context_parts)

    @staticmethod
    def generate_sql_from_natural_language(config, description: str, db_type: str = 'mysql') -> dict:
        """从自然语言生成SQL"""
        messages = [
            {'role': 'system', 'content': f'你是一个SQL专家。根据用户的自然语言描述，生成{db_type}兼容的SQL查询语句。'
                                           '只返回SQL语句，不要解释。如果无法生成，返回空字符串。'},
            {'role': 'user', 'content': description},
        ]

        sql, tokens = AiService.chat(config, messages)
        return {'sql': sql.strip(), 'tokens': tokens}

    @staticmethod
    def analyze_and_learn(user_id: int) -> list:
        """分析用户行为，自动生成Skills"""
        from app.models.ai_skill import AiSkill
        from app.models.user_behavior import UserBehavior
        from app import db

        new_skills = []

        # Analyze query patterns
        query_behaviors = UserBehavior.query.filter_by(
            user_id=user_id, action='query', target_type='script'
        ).order_by(UserBehavior.created_at.desc()).limit(50).all()

        if len(query_behaviors) >= 5:
            # Check if we already have a skill for frequent queries
            existing = AiSkill.query.filter_by(
                user_id=user_id, category='query', source='auto_learn'
            ).first()

            if not existing:
                skill = AiSkill(
                    name='频繁查询模式',
                    skill_type='user',
                    category='query',
                    description='基于用户频繁查询行为自动生成的技能',
                    content=json.dumps({'behavior_count': len(query_behaviors)}, ensure_ascii=False),
                    user_id=user_id,
                    source='auto_learn',
                )
                db.session.add(skill)
                new_skills.append(skill)

        if new_skills:
            db.session.commit()

        return new_skills

    @staticmethod
    def chat_with_tools(config, messages: list) -> dict:
        """调用AI对话，支持 Function Calling"""
        api_key = config.get_api_key()
        if not api_key:
            raise ValueError('API密钥未配置')

        api_base = config.api_base or 'https://api.openai.com/v1'
        url = f"{api_base.rstrip('/')}/chat/completions"

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }

        payload = {
            'model': config.model_name or 'gpt-3.5-turbo',
            'messages': messages,
            'max_tokens': config.max_tokens or 4096,
            'temperature': config.temperature if config.temperature is not None else 0.7,
            'tools': AI_TOOLS,
            'tool_choice': 'auto',
        }

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()

        choice = result.get('choices', [{}])[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        tool_calls = message.get('tool_calls', [])
        tokens = result.get('usage', {}).get('total_tokens', 0)

        return {
            'content': content,
            'tool_calls': tool_calls,
            'tokens': tokens,
        }

    @staticmethod
    def execute_tool_call(tool_name: str, arguments_str: str, user_id: int = None) -> dict:
        """执行AI请求的工具调用"""
        try:
            args = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            return {'error': f'参数解析失败: {arguments_str}'}

        if tool_name == 'list_export_options':
            return AiService._tool_list_export_options(args, user_id)
        elif tool_name == 'list_query_options':
            return AiService._tool_list_query_options(args, user_id)
        elif tool_name == 'parse_uploaded_file':
            return AiService._tool_parse_file(args, user_id)
        elif tool_name == 'request_export':
            return AiService._tool_request_export(args, user_id)
        elif tool_name == 'request_query':
            return AiService._tool_request_query(args, user_id)
        else:
            return {'error': f'未知工具: {tool_name}'}

    @staticmethod
    def _filter_script_by_user(scripts, user_id: int = None):
        """根据用户权限过滤脚本"""
        if not user_id:
            return scripts
        from app.models.user import User
        user = User.query.get(user_id)
        if not user or user.is_admin():
            return scripts
        allowed_ids = set(user.get_script_ids())
        return [s for s in scripts if s.id in allowed_ids]

    @staticmethod
    def _tool_parse_file(args: dict, user_id: int = None) -> dict:
        """解析上传的文件信息"""
        filename = args.get('filename', '')
        if not filename:
            return {'error': '未提供文件名'}
        # 文件实际由前端上传后通过upload-file接口解析
        # 这里只返回提示信息，让AI知道文件已上传
        return {
            'filename': filename,
            'status': 'uploaded',
            'message': f'文件"{filename}"已上传，请根据文件列名分析并执行相应操作'
        }

    @staticmethod
    def _tool_list_export_options(args: dict, user_id: int = None) -> dict:
        """列出导出选项（按用户权限过滤）"""
        from app.models.script import Script
        keyword = args.get('keyword', '').lower()
        scripts = Script.query.filter_by(type='export').all()
        scripts = AiService._filter_script_by_user(scripts, user_id)
        result = []
        for s in scripts:
            if keyword and keyword not in s.name.lower() and keyword not in (s.description or '').lower():
                continue
            params = s.get_params_config()
            result.append({
                'id': s.id,
                'name': s.name,
                'description': s.description or '',
                'params': [{'name': p['name'], 'label': p.get('label', p['name']), 'type': p.get('type', 'text')} for p in params],
            })
        return {'scripts': result, 'total': len(result)}

    @staticmethod
    def _tool_list_query_options(args: dict, user_id: int = None) -> dict:
        """列出查询选项（按用户权限过滤）"""
        from app.models.script import Script
        keyword = args.get('keyword', '').lower()
        scripts = Script.query.filter_by(type='query').all()
        scripts = AiService._filter_script_by_user(scripts, user_id)
        result = []
        for s in scripts:
            if keyword and keyword not in s.name.lower() and keyword not in (s.description or '').lower():
                continue
            result.append({
                'id': s.id,
                'name': s.name,
                'description': s.description or '',
            })
        return {'scripts': result, 'total': len(result)}

    @staticmethod
    def _tool_request_export(args: dict, user_id: int = None) -> dict:
        """处理导出请求 - 返回结构化信息供前端确认（含权限校验）"""
        from app.models.script import Script
        from app.models.user import User
        export_name = args.get('export_option_name', '')
        params = args.get('params', {})
        desc = args.get('description', '')

        # 查找匹配的导出选项
        script = Script.query.filter_by(name=export_name, type='export').first()
        if not script:
            # 尝试模糊匹配
            script = Script.query.filter(Script.name.like(f'%{export_name}%'), Script.type == 'export').first()

        if not script:
            return {'error': f'未找到名为"{export_name}"的导出选项'}

        # 权限校验
        if user_id:
            user = User.query.get(user_id)
            if user and not user.is_admin():
                allowed_ids = user.get_script_ids()
                if allowed_ids and script.id not in allowed_ids:
                    return {'error': f'你没有权限使用导出选项"{script.name}"'}

        script_params = script.get_params_config()
        # 自动将未提供且支持 allow_all 的参数标记为"全部"
        all_checked = {}
        for p in script_params:
            if p.get('allow_all') and p['name'] not in params:
                # 构建前端 allChecked 的 key（导出执行时是参数名本身，非独立参数用脚本ID_参数名）
                all_checked[p['name']] = True

        required_params = [p for p in script_params if p.get('required') and p['name'] not in params and p['name'] not in all_checked]

        return {
            'action_type': 'export',
            'script_id': script.id,
            'script_name': script.name,
            'params': params,
            'all_checked': all_checked,
            'output_format': args.get('output_format', 'sheets'),
            'required_missing': [p['name'] for p in required_params],
            'description': desc,
            'confirm_message': f'AI 准备执行导出：{script.name}，参数：{json.dumps(params, ensure_ascii=False)}，输出格式：{args.get("output_format", "sheets")}'
        }

    @staticmethod
    def _tool_request_query(args: dict, user_id: int = None) -> dict:
        """处理查询请求 - 返回结构化信息供前端确认（含权限校验）"""
        from app.models.script import Script
        from app.models.user import User
        query_name = args.get('query_option_name', '')
        desc = args.get('description', '')

        script = Script.query.filter_by(name=query_name, type='query').first()
        if not script:
            script = Script.query.filter(Script.name.like(f'%{query_name}%'), Script.type == 'query').first()

        if not script:
            return {'error': f'未找到名为"{query_name}"的查询选项'}

        # 权限校验
        if user_id:
            user = User.query.get(user_id)
            if user and not user.is_admin():
                allowed_ids = user.get_script_ids()
                if allowed_ids and script.id not in allowed_ids:
                    return {'error': f'你没有权限使用查询选项"{script.name}"'}

        return {
            'action_type': 'query',
            'script_id': script.id,
            'script_name': script.name,
            'description': desc,
            'confirm_message': f'AI 准备执行查询：{script.name}'
        }
