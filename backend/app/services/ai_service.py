import json
import logging
import re
import requests
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# ============ Tool Definitions ============
AI_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_export_options",
            "description": "列出所有可用的导出选项。导出选项是指从数据库导出数据到Excel的脚本，与查询任务和系统任务不同。当用户需要导出数据、下载报表时调用此工具。",
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
            "description": "列出所有可用的查询选项。查询选项是指根据Excel文件中的数据（如主键列）去数据库查询匹配数据的脚本，需要上传Excel文件。与导出任务和系统任务不同。当用户需要根据Excel数据查询匹配信息时调用此工具。",
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
            "description": "当用户明确要执行导出任务时调用此工具。需要指定导出选项名称和参数值。注意：必须从用户的自然语言描述中提取所有可能的参数值填入params对象，未能提取的参数不要填入（系统会自动将其标记为'全部'不筛选）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "export_option_name": {
                        "type": "string",
                        "description": "要使用的导出选项名称"
                    },
                    "params": {
                        "type": "object",
                        "description": "参数键值对，键为参数名，值为用户提供的参数值。务必从用户描述中提取所有参数值。例如用户说'导出商户123456的信息'，如果参数有merchant_no，则params为{\"merchant_no\": \"123456\"}",
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
    },
    {
        "type": "function",
        "function": {
            "name": "list_system_tasks",
            "description": "列出所有可用的系统任务。系统任务是指后台运维类任务（如数据清理、缓存刷新、终端解绑等），与导出任务和查询任务完全不同。只有当用户明确提到\"系统任务\"或描述的是运维类操作时才调用此工具。不要将查询任务或导出任务误认为是系统任务。返回结果中API类型任务可能包含response_mapping字段，表示响应字段的意义枚举映射。API类型任务参数齐全时会自动执行并返回结果，SQL类型任务需要用户确认后执行。",
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
            "name": "request_system_task",
            "description": "当用户明确要执行系统任务（运维类任务）时调用此工具。系统任务与导出任务、查询任务完全不同，只有运维类操作才属于系统任务。需要指定系统任务名称和参数值。注意：1、必须从用户的自然语言描述中提取所有可能的参数值填入params对象；2、params的键名必须使用list_system_tasks返回的参数配置中的name字段值，不要自己编造参数名；3、如果之前没有调用list_system_tasks，请先调用以获取正确的参数名；4、如果任务关联了多个数据库连接，请从用户描述中提取数据库名称填入database_name；5、API类型任务参数齐全时会自动执行，结果中包含mapping_summary（映射摘要）字段，请直接根据映射摘要用自然语言告诉用户执行结果；6、如果用户同时要求对多个对象执行同样的API任务（如解绑多个SN），请在同一次回复中同时调用多个request_system_task，每个调用对应一个对象，系统会自动并行执行，你只需汇总所有结果用列表形式反馈给用户。",
            "parameters": {
                "type": "object",
                "properties": {
                    "system_task_name": {
                        "type": "string",
                        "description": "要执行的系统任务名称"
                    },
                    "params": {
                        "type": "object",
                        "description": "参数键值对。键必须是系统任务参数配置中的name字段值（如device_sn、user_id等），值为用户提供的参数值。如果不知道参数名，请先调用list_system_tasks查看参数配置。",
                        "additionalProperties": {"type": "string"}
                    },
                    "database_name": {
                        "type": "string",
                        "description": "用户指定的数据库连接名称。如果任务关联了多个数据库且用户提到了数据库名称，填入此字段。"
                    },
                    "description": {
                        "type": "string",
                        "description": "用户原始需求的简要描述"
                    }
                },
                "required": ["system_task_name", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_lookup_options",
            "description": "列出所有可用的信息查询选项。信息查询是指根据用户提供的参数值（如SN号、商户号、订单号等）快速查询数据库返回结果，结果直接在对话中展示，不需要上传Excel文件也不需要下载。与导出任务、查询任务和系统任务完全不同。当用户询问某个实体的状态、信息、详情时调用此工具。重要：如果用户提供了具体的参数值，务必同时传入params参数，这样当匹配到唯一查询时系统可以自动执行查询，大幅加快响应速度。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "可选，按名称或描述筛选的关键词"
                    },
                    "params": {
                        "type": "object",
                        "description": "参数键值对。如果用户提供了具体的参数值（如SN号、商户号等），务必在此传入，这样当匹配到唯一查询时系统可以自动执行查询。键名应使用可能的查询参数名（如device_sn、merchant_no等）。",
                        "additionalProperties": {"type": "string"}
                    },
                    "description": {
                        "type": "string",
                        "description": "用户原始需求的简要描述"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_lookup",
            "description": "当用户要执行信息查询时调用此工具。信息查询是根据参数值快速查询数据库返回结果。注意：1、必须从用户的自然语言描述中提取所有参数值填入params对象；2、params的键名必须使用list_lookup_options返回的参数配置中的name字段值；3、如果之前没有调用list_lookup_options，请先调用以获取正确的参数名；4、默认情况下直接用自然语言回答用户的问题即可，只有当用户明确要求查看所有字段、详细信息、完整结果或卡片展示时，才将show_all_fields设为true；5、当用户的查询涉及多个不同维度的信息时，应在同一次回复中同时调用多个request_lookup工具分别查询，系统会归总所有结果后统一回答用户。",
            "parameters": {
                "type": "object",
                "properties": {
                    "lookup_name": {
                        "type": "string",
                        "description": "要使用的信息查询选项名称"
                    },
                    "params": {
                        "type": "object",
                        "description": "参数键值对。键必须是查询选项参数配置中的name字段值（如device_sn、merchant_no等），值为用户提供的参数值。",
                        "additionalProperties": {"type": "string"}
                    },
                    "description": {
                        "type": "string",
                        "description": "用户原始需求的简要描述"
                    },
                    "show_all_fields": {
                        "type": "boolean",
                        "description": "是否以卡片形式展示所有字段的查询结果。只有当用户明确要求查看所有字段、详细信息、完整结果或卡片展示时才设为true，默认为false。"
                    }
                },
                "required": ["lookup_name", "description"]
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
    def get_ordered_configs() -> list:
        """根据策略返回有序的模型配置列表，支持故障转移"""
        from app.models.ai_strategy import AiStrategy
        from app.models.ai_config import AiConfig
        from app import db

        strategy = AiStrategy.query.filter_by(is_active=True).first()
        if not strategy:
            # 无策略时回退到默认配置
            config = AiConfig.query.filter_by(is_default=True, is_active=True).first()
            if not config:
                config = AiConfig.query.filter_by(is_active=True).first()
            return [config] if config else []

        model_ids = strategy.get_model_ids()
        if not model_ids:
            config = AiConfig.query.filter_by(is_default=True, is_active=True).first()
            if not config:
                config = AiConfig.query.filter_by(is_active=True).first()
            return [config] if config else []

        configs = []
        for mid in model_ids:
            cfg = AiConfig.query.get(mid)
            if cfg and cfg.is_active:
                configs.append(cfg)

        if not configs:
            config = AiConfig.query.filter_by(is_active=True).first()
            return [config] if config else []

        # 根据策略类型重新排序
        if strategy.strategy_type == 'round_robin':
            idx = strategy.get_next_round_robin_index(len(configs))
            configs = configs[idx:] + configs[:idx]
            db.session.commit()
        elif strategy.strategy_type == 'token_balanced':
            usage = strategy.get_token_usage()
            configs.sort(key=lambda c: usage.get(str(c.id), 0))
        # priority 和 temperature 保持原顺序（priority已按优先级排列）
        # temperature 策略可以根据模型温度重排，暂时保持 priority 顺序

        return configs

    @staticmethod
    def chat_with_failover(messages: list, use_tools: bool = False, override_configs: list = None) -> Tuple:
        """支持故障转移的AI调用，自动尝试多个模型。如果提供 override_configs 则使用指定模型"""
        from app.models.ai_strategy import AiStrategy
        from app import db

        if override_configs:
            configs = override_configs
        else:
            configs = AiService.get_ordered_configs()
        if not configs:
            raise ValueError('没有可用的AI模型配置')

        strategy = AiStrategy.query.filter_by(is_active=True).first()
        failover = strategy.failover_enabled if strategy else True
        max_retries = strategy.failover_max_retries if strategy else 3
        timeout = strategy.failover_timeout if strategy else 120

        last_error = None
        for i, config in enumerate(configs):
            if not failover and i > 0:
                break
            try:
                logger.info(f"尝试使用模型: {config.name} ({config.model_name})")
                if use_tools:
                    result = AiService.chat_with_tools(config, messages)
                    # 记录token消耗
                    if strategy and result.get('tokens'):
                        strategy.record_token_usage(config.id, result['tokens'])
                        db.session.commit()
                    return result
                else:
                    content, tokens = AiService.chat(config, messages)
                    if strategy and tokens:
                        strategy.record_token_usage(config.id, tokens)
                        db.session.commit()
                    return content, tokens
            except Exception as e:
                last_error = e
                logger.warning(f"模型 {config.name} 调用失败: {str(e)}，尝试下一个")
                if not failover:
                    raise
                continue

        raise ValueError(f'所有模型均调用失败，最后错误: {str(last_error)}')

    @staticmethod
    def chat(config, messages: list) -> Tuple[str, int]:
        """调用AI对话（单模型）"""
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

        # Add tool call memories
        memory_context = AiService.build_memory_context(user_id)
        if memory_context:
            context_parts.append(memory_context)

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
        elif tool_name == 'list_system_tasks':
            return AiService._tool_list_system_tasks(args, user_id)
        elif tool_name == 'request_system_task':
            return AiService._tool_request_system_task(args, user_id)
        elif tool_name == 'list_lookup_options':
            return AiService._tool_list_lookup_options(args, user_id)
        elif tool_name == 'request_lookup':
            return AiService._tool_request_lookup(args, user_id)
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
                'params': params,  # 返回完整参数配置，前端参数设置对话框需要
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
            params = s.get_params_config()
            # 从SQL中提取查询字段
            query_fields = AiService._extract_select_columns(s.sql_text or '')
            item = {
                'id': s.id,
                'name': s.name,
                'description': s.description or '',
                'params': params,
                'primary_key': s.primary_key or '',
                'param_column': s.param_column or '',
                'new_sheet': s.new_sheet if s.new_sheet is not None else True,
                'query_fields': query_fields,
            }
            result.append(item)
        return {'scripts': result, 'total': len(result)}

    @staticmethod
    def _extract_select_columns(sql_text: str) -> list:
        """从SQL语句中提取SELECT的列名"""
        if not sql_text:
            return []
        import re
        columns = []
        # 匹配 SELECT ... FROM 模式（支持多行、大小写不敏感）
        # 先移除注释
        clean_sql = re.sub(r'--.*$', '', sql_text, flags=re.MULTILINE)
        clean_sql = re.sub(r'/\*.*?\*/', '', clean_sql, flags=re.DOTALL)

        # 查找所有SELECT...FROM块
        select_pattern = re.compile(
            r'\bSELECT\s+(.*?)\bFROM\b',
            re.IGNORECASE | re.DOTALL
        )
        for match in select_pattern.finditer(clean_sql):
            select_part = match.group(1).strip()
            if select_part == '*':
                columns.append('*')
                continue
            # 拆分列（注意处理嵌套括号和子查询）
            parts = []
            depth = 0
            current = []
            for char in select_part:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                elif char == ',' and depth == 0:
                    parts.append(''.join(current).strip())
                    current = []
                    continue
                current.append(char)
            if current:
                parts.append(''.join(current).strip())

            for part in parts:
                # 提取别名或列名
                part = part.strip()
                if not part:
                    continue
                # 处理 AS alias 或 空格alias
                alias_match = re.search(r'\b(?:AS|as)\s+["\`]?(\w+)["\`]?\s*$', part)
                if alias_match:
                    columns.append(alias_match.group(1))
                    continue
                # 处理 table.column 或 column
                # 去掉函数调用，取最后的标识符
                dot_match = re.search(r'["\`]?(\w+)["\`]?\s*$', part)
                if dot_match:
                    col = dot_match.group(1)
                    # 过滤掉SQL关键字
                    if col.upper() not in ('SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'NOT',
                                            'GROUP', 'ORDER', 'BY', 'HAVING', 'LIMIT',
                                            'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
                                            'ON', 'AS', 'DISTINCT', 'ALL', 'TOP'):
                        columns.append(col)
        return columns

    @staticmethod
    def _tool_list_system_tasks(args: dict, user_id: int = None) -> dict:
        """列出系统任务（按用户权限过滤）"""
        from app.models.system_task import SystemTask
        from app.models.script import Script
        from app.models.database import DatabaseConnection
        from app.models.user import User
        keyword = args.get('keyword', '').lower()
        tasks = SystemTask.query.filter_by(is_enabled=True).all()

        # 用户权限过滤
        if user_id:
            user = User.query.get(user_id)
            if user and not user.is_admin():
                allowed_ids = set(user.get_system_task_ids() or [])
                if allowed_ids:
                    tasks = [t for t in tasks if t.id in allowed_ids]
                else:
                    tasks = []

        result = []
        for t in tasks:
            if keyword and keyword not in t.name.lower() and keyword not in (t.description or '').lower():
                continue
            # For SQL tasks, params come from the linked script; for API tasks, from the task itself
            params = t.get_params_config()
            if (t.task_type or 'sql') == 'sql' and t.script_id:
                script = Script.query.get(t.script_id)
                if script and script.get_params_config():
                    params = script.get_params_config()
            # 获取数据库连接信息
            db_ids = t.get_database_ids()
            databases_info = []
            if db_ids:
                for db_id in db_ids:
                    conn = DatabaseConnection.query.get(db_id)
                    if conn:
                        databases_info.append({'id': conn.id, 'name': conn.name})
            # 获取响应字段映射（仅API类型任务）
            response_mapping_info = []
            if (t.task_type or 'sql') == 'api':
                response_mapping = t.get_response_mapping()
                if response_mapping:
                    response_mapping_info = response_mapping
            result.append({
                'id': t.id,
                'name': t.name,
                'description': t.description or '',
                'task_type': t.task_type or 'sql',
                'params': params or [],
                'databases': databases_info,
                'response_mapping': response_mapping_info,
            })
        return {'tasks': result, 'total': len(result)}

    @staticmethod
    def _tool_request_system_task(args: dict, user_id: int = None) -> dict:
        """处理系统任务执行请求 - API类型任务参数齐全时直接同步执行，其他返回结构化信息供前端确认"""
        from app.models.system_task import SystemTask
        from app.models.database import DatabaseConnection
        from app.models.user import User
        from app.services.system_task_service import SystemTaskService
        task_name = args.get('system_task_name', '')
        desc = args.get('description', '')
        params = args.get('params', {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}
        if not isinstance(params, dict):
            params = {}
        database_name = args.get('database_name', '')

        task = SystemTask.query.filter_by(name=task_name, is_enabled=True).first()
        if not task:
            task = SystemTask.query.filter(
                SystemTask.name.like(f'%{task_name}%'),
                SystemTask.is_enabled == True
            ).first()

        if not task:
            return {'error': f'未找到名为"{task_name}"的系统任务'}

        # 权限校验
        if user_id:
            user = User.query.get(user_id)
            if user and not user.is_admin():
                allowed_ids = set(user.get_system_task_ids() or [])
                if not allowed_ids or task.id not in allowed_ids:
                    return {'error': f'你没有权限执行系统任务"{task.name}"'}

        # 标准化neq参数 + 智能匹配参数名
        task_params = task.get_params_config() or []
        # For SQL tasks, params come from the linked script
        if (task.task_type or 'sql') == 'sql' and task.script_id:
            from app.models.script import Script
            script = Script.query.get(task.script_id)
            if script and script.get_params_config():
                task_params = script.get_params_config()

        # 智能匹配参数名：AI传入的key可能和配置中的name不完全一致
        if params and task_params:
            mapped_params = {}
            param_names = {p['name'] for p in task_params}
            # 先处理直接匹配的
            for key, val in params.items():
                if key in param_names:
                    mapped_params[key] = val
                else:
                    # 尝试模糊匹配：key包含在name中，或name包含key，或key包含在label中
                    matched = False
                    key_lower = key.lower().replace('_', '').replace('-', '')
                    for p in task_params:
                        p_name = p['name']
                        p_label = (p.get('label') or '').lower()
                        p_name_lower = p_name.lower().replace('_', '').replace('-', '')
                        # 精确匹配label
                        if p_label and key.lower() == p_label:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        # 模糊匹配：key和name去掉下划线后相同
                        if key_lower == p_name_lower:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        # key包含在name中，或name包含key
                        if key_lower in p_name_lower or p_name_lower in key_lower:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        # key包含在label中
                        if p_label and key_lower in p_label.replace('_', '').replace('-', ''):
                            mapped_params[p_name] = val
                            matched = True
                            break
                    if not matched:
                        # 无法匹配，保留原始key
                        mapped_params[key] = val
            params = mapped_params

        if params:
            for p in task_params:
                if p.get('enum_mode') == 'neq' and p.get('neq_value') and p.get('name') in params:
                    params[p['name']] = AiService._normalize_neq_value(params[p['name']])

        # 获取数据库连接信息
        db_ids = task.get_database_ids()
        databases_info = []
        matched_db_id = None
        if db_ids:
            for db_id in db_ids:
                conn = DatabaseConnection.query.get(db_id)
                if conn:
                    databases_info.append({'id': conn.id, 'name': conn.name})
                    # 匹配用户指定的数据库名称
                    if database_name and (database_name.lower() in conn.name.lower() or conn.name.lower() in database_name.lower()):
                        matched_db_id = conn.id

        # 获取响应字段映射（仅API类型任务）
        response_mapping_info = []
        if (task.task_type or 'sql') == 'api':
            response_mapping = task.get_response_mapping()
            if response_mapping:
                response_mapping_info = response_mapping

        # API类型任务 + 参数齐全 + 不需要选择数据库 → 直接同步执行
        is_api_task = (task.task_type or 'sql') == 'api'
        all_params_filled = len(task_params) == 0 or all(
            p.get('name') in params and params[p.get('name')] not in (None, '')
            for p in task_params if p.get('required', False)
        )
        needs_dbSelection = len(databases_info) > 1 and not matched_db_id

        if is_api_task and all_params_filled and not needsDbSelection:
            try:
                exec_result = SystemTaskService.execute_api_sync(task, params)
                # 构建返回给AI的结果，包含映射摘要
                result = {
                    'action_type': 'system_task',
                    'task_id': task.id,
                    'task_name': task.name,
                    'task_type': 'api',
                    'description': desc,
                    'params_values': params,
                    'auto_executed': True,
                    'success': exec_result.get('success', False),
                    'status_code': exec_result.get('status_code'),
                    'response': exec_result.get('response'),
                    'response_raw': exec_result.get('response_raw'),
                    'mapping_applied': exec_result.get('mapping_applied', False),
                    'mapping_info': exec_result.get('mapping_info', ''),
                    'mapping_summary': exec_result.get('mapping_summary', ''),
                    'response_mapping': response_mapping_info,
                    'confirm_message': f'系统任务「{task.name}」已自动执行完成',
                }
                if exec_result.get('error'):
                    result['error'] = exec_result['error']
                return result
            except Exception as e:
                logger.warning(f'API系统任务同步执行失败: {e}')
                # 执行失败，回退到确认卡片模式
                pass

        return {
            'action_type': 'system_task',
            'task_id': task.id,
            'task_name': task.name,
            'task_type': task.task_type or 'sql',
            'description': desc,
            'params': task_params,
            'params_values': params,
            'databases': databases_info,
            'database_id': matched_db_id,
            'response_mapping': response_mapping_info,
            'confirm_message': f'AI 准备执行系统任务：{task.name}'
        }

    @staticmethod
    def _tool_list_lookup_options(args: dict, user_id: int = None) -> dict:
        """列出信息查询选项（按用户权限过滤）"""
        from app.models.script import Script
        keyword = args.get('keyword', '').lower()
        scripts = Script.query.filter_by(type='lookup', is_active=True).all()
        scripts = AiService._filter_script_by_user(scripts, user_id)
        result = []
        for s in scripts:
            if keyword and keyword not in s.name.lower() and keyword not in (s.description or '').lower():
                continue
            params = s.get_params_config()
            query_fields = AiService._extract_select_columns(s.sql_text or '')
            result.append({
                'id': s.id,
                'name': s.name,
                'description': s.description or '',
                'params': params,
                'query_fields': query_fields,
            })
        return {'scripts': result, 'total': len(result)}

    @staticmethod
    def _tool_request_lookup(args: dict, user_id: int = None) -> dict:
        """处理信息查询请求 - 直接执行并返回结果"""
        from app.models.script import Script
        from app.models.user import User
        from app.services.lookup_service import LookupService
        lookup_name = args.get('lookup_name', '')
        desc = args.get('description', '')
        params = args.get('params', {})
        if isinstance(params, str):
            # AI可能将params传为字符串，尝试解析为dict
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}
        if not isinstance(params, dict):
            params = {}
        show_all_fields = args.get('show_all_fields', False)

        script = Script.query.filter_by(name=lookup_name, type='lookup', is_active=True).first()
        if not script:
            script = Script.query.filter(
                Script.name.like(f'%{lookup_name}%'),
                Script.type == 'lookup',
                Script.is_active == True
            ).first()

        if not script:
            return {'error': f'未找到名为"{lookup_name}"的信息查询选项', 'action_type': 'lookup'}

        # 权限校验
        if user_id:
            user = User.query.get(user_id)
            if user and not user.is_admin():
                allowed_ids = user.get_script_ids()
                if allowed_ids and script.id not in allowed_ids:
                    return {'error': f'你没有权限使用信息查询选项"{script.name}"', 'action_type': 'lookup'}

        # 智能匹配参数名
        task_params = script.get_params_config() or []
        if params and task_params:
            mapped_params = {}
            param_names = {p['name'] for p in task_params}
            for key, val in params.items():
                if key in param_names:
                    mapped_params[key] = val
                else:
                    key_lower = key.lower().replace('_', '').replace('-', '')
                    matched = False
                    for p in task_params:
                        p_name = p['name']
                        p_label = (p.get('label') or '').lower()
                        p_name_lower = p_name.lower().replace('_', '').replace('-', '')
                        if p_label and key.lower() == p_label:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        if key_lower == p_name_lower:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        if key_lower in p_name_lower or p_name_lower in key_lower:
                            mapped_params[p_name] = val
                            matched = True
                            break
                        if p_label and key_lower in p_label.replace('_', '').replace('-', ''):
                            mapped_params[p_name] = val
                            matched = True
                            break
                    if not matched:
                        mapped_params[key] = val
            params = mapped_params
            logger.info(f'Lookup参数匹配结果: 原始={args.get("params", {})}, 映射后={params}, 脚本参数={[p["name"] for p in task_params]}')
        elif not params and task_params:
            # AI没有传params，尝试从description中提取参数值
            logger.warning(f'Lookup未收到params参数, description={desc}, 脚本参数={[p["name"] for p in task_params]}')

        # 检查必填参数
        missing_required = []
        for p in task_params:
            if p.get('required') and p['name'] not in params:
                missing_required.append(p.get('label') or p['name'])

        if missing_required:
            return {
                'error': f'缺少必填参数：{", ".join(missing_required)}',
                'missing_required': missing_required,
                'action_type': 'lookup',
            }

        # 直接执行查询
        result = LookupService.execute_lookup(script.id, params, user_id)

        if result.get('success'):
            return {
                'action_type': 'lookup',
                'script_id': script.id,
                'script_name': script.name,
                'description': desc,
                'params': task_params,
                'params_values': params,
                'query_fields': result.get('columns', []),
                'results': result.get('results', []),
                'row_count': result.get('row_count', 0),
                'columns': result.get('columns', []),
                'confirm_message': f'查询完成：{script.name}',
                'show_all_fields': show_all_fields,
            }
        else:
            return {
                'action_type': 'lookup',
                'script_id': script.id,
                'script_name': script.name,
                'description': desc,
                'params': task_params,
                'params_values': params,
                'error': result.get('error_message', '查询执行失败'),
                'show_all_fields': show_all_fields,
            }

    @staticmethod
    def extract_params_from_message(message: str, param_configs: list) -> dict:
        """尝试从用户消息中提取参数值，作为AI未传params时的fallback"""
        if not message or not param_configs:
            return {}
        params = {}
        for p in param_configs:
            name = p['name']
            label = (p.get('label') or '').strip()
            # 构建搜索词列表
            search_terms = []
            if label:
                search_terms.append(label)
            search_terms.append(name)
            for term in search_terms:
                # 模式1: term=value, term：value, term: value
                match = re.search(rf'{re.escape(term)}\s*[=：:]\s*([^\s,，]+)', message, re.IGNORECASE)
                if match:
                    params[name] = match.group(1)
                    break
            if name not in params:
                # 模式2: 常见中文模式 "SN号 ABC123" "商户号12345"
                for term in search_terms:
                    match = re.search(rf'{re.escape(term)}\s*[号号码]?\s*[:：]?\s*([A-Za-z0-9_\-]+)', message, re.IGNORECASE)
                    if match and match.group(1).lower() not in ('的', '是', '有', '在', '了', '和', '不', '没'):
                        params[name] = match.group(1)
                        break
        return params

    @staticmethod
    def _normalize_neq_value(value: str) -> bool:
        """将非即不等于参数值标准化为布尔值
        
        注意：非即不等于参数中，is_checked=True 表示使用 = neq_value（包含该值），
        is_checked=False 表示使用 != neq_value（排除该值）。
        
        因此：
        - 用户说"排除/不要/不"等 → 想表达用 != 排除该值 → is_checked = False
        - 用户说"是/要/包含"等 → 想表达用 = 包含该值 → is_checked = True
        """
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            value = str(value)
        v = value.strip().lower()
        if not v:
            return True  # 默认使用 = 运算符

        # 先检查明确的否定/排除短语（这些意味着用 != 排除该值 → is_checked=False）
        negative_phrases = ['不要排除', '不需排除', '不用排除', '不启用', '不应用',
                           '不使用不等于', '不', '否', '不是', '不要', '不需要',
                           '不用', '没有', 'no', 'false', '排除', '不包含','未',
                           '0']
        for phrase in negative_phrases:
            if phrase in v:
                return False

        # 肯定词列表（这些意味着用 = 包含该值 → is_checked=True）
        positive_phrases = ['是', '要', '需要', '启用', '开启', '包含', '使用',
                           'yes', 'true','1']
        for phrase in positive_phrases:
            if phrase in v:
                return True

        # 默认值
        return True

    @staticmethod
    def _tool_request_export(args: dict, user_id: int = None) -> dict:
        """处理导出请求 - 返回结构化信息供前端确认（含权限校验）"""
        from app.models.script import Script
        from app.models.user import User
        export_name = args.get('export_option_name', '')
        params = args.get('params', {})
        if isinstance(params, str):
            try:
                params = json.loads(params)
            except (json.JSONDecodeError, TypeError):
                params = {}
        if not isinstance(params, dict):
            params = {}
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
        # 标准化非即不等于参数值：将自然语言中的否定/肯定词转为布尔值
        for p in script_params:
            if p.get('enum_enabled') and p.get('enum_mode') == 'neq' and p['name'] in params:
                params[p['name']] = AiService._normalize_neq_value(params[p['name']])

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
            'primary_key': script.primary_key or '',
            'param_column': script.param_column or '',
            'new_sheet': script.new_sheet if script.new_sheet is not None else True,
            'query_fields': AiService._extract_select_columns(script.sql_text or ''),
            'confirm_message': f'AI 准备执行查询：{script.name}'
        }

    # ============ 工具调用记忆 ============

    @staticmethod
    def record_tool_memory(user_id: int, intent: str, tool_name: str, tool_args: dict):
        """记录成功的工具调用模式，供后续对话参考"""
        from app.models.tool_memory import ToolMemory
        from app import db
        try:
            # 查找是否已有相同意图+工具的记录
            existing = ToolMemory.query.filter_by(
                user_id=user_id, intent=intent, tool_name=tool_name
            ).first()
            if existing:
                existing.success_count += 1
                existing.last_used_at = datetime.utcnow()
                existing.tool_args = json.dumps(tool_args, ensure_ascii=False)
            else:
                memory = ToolMemory(
                    user_id=user_id,
                    intent=intent,
                    tool_name=tool_name,
                    tool_args=json.dumps(tool_args, ensure_ascii=False),
                    success_count=1,
                )
                db.session.add(memory)
            db.session.commit()
        except Exception as e:
            logger.warning(f'记录工具调用记忆失败: {e}')
            try:
                db.session.rollback()
            except:
                pass

    @staticmethod
    def get_tool_memories(user_id: int, limit: int = 20) -> list:
        """获取用户的工具调用记忆，按成功次数和使用时间排序"""
        from app.models.tool_memory import ToolMemory
        try:
            memories = ToolMemory.query.filter_by(user_id=user_id)\
                .order_by(ToolMemory.success_count.desc(), ToolMemory.last_used_at.desc())\
                .limit(limit).all()
            return memories
        except Exception:
            return []

    @staticmethod
    def build_memory_context(user_id: int) -> str:
        """构建工具调用记忆上下文，注入到系统提示词中"""
        memories = AiService.get_tool_memories(user_id, limit=20)
        if not memories:
            return ''

        lines = ['\n## 用户操作记忆（以下是你之前成功执行过的操作模式，当用户表达类似意图时，请直接参考这些模式调用对应工具，不要重新分析）']
        for m in memories:
            args_str = m.tool_args or '{}'
            lines.append(f'- 意图"{m.intent}" → 调用 {m.tool_name}({args_str}) [成功{m.success_count}次]')
        return '\n'.join(lines)
