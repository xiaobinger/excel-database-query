import json
import logging
import requests
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


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
