"""上传文件格式配置

从系统配置（system_configs）读取 AI 聊天附件、工单附件允许的扩展名。
未配置或配置为空时回退到默认值；扩展名统一存储为不带点的小写形式。
"""
import re
from typing import List

from app.models.system_config import SystemConfig

# AI 聊天附件默认格式（按表格文件解析）
DEFAULT_AI_UPLOAD_EXTENSIONS = ['xlsx', 'xls', 'csv']

# 工单附件默认格式：数据文件 + 压缩包 + 文档 + 图片
DEFAULT_TICKET_ATTACHMENT_EXTENSIONS = [
    'xlsx', 'xls', 'csv', 'txt', 'json', 'xml',
    'zip', 'rar', '7z', 'gz', 'tar',
    'pdf', 'doc', 'docx', 'md',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
]

_SPLIT_PATTERN = re.compile(r'[,，;；、\s]+')


def normalize_extensions(value) -> List[str]:
    """把配置值规范化为不带点的小写扩展名列表（去重且保持顺序）

    支持字符串（逗号/分号/空白分隔）与列表两种输入，自动去除前导点。
    """
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = _SPLIT_PATTERN.split(value)
    elif isinstance(value, (list, tuple, set)):
        raw_items = []
        for item in value:
            raw_items.extend(_SPLIT_PATTERN.split(str(item)))
    else:
        raw_items = _SPLIT_PATTERN.split(str(value))

    result = []
    for item in raw_items:
        ext = item.strip().lower().lstrip('.')
        if ext and ext not in result:
            result.append(ext)
    return result


def get_extensions(config_key: str, defaults: List[str]) -> List[str]:
    """读取指定配置项的扩展名列表，未配置或为空时返回默认值"""
    config = SystemConfig.query.filter_by(config_key=config_key).first()
    extensions = normalize_extensions(config.config_value if config else None)
    return extensions or list(defaults)


def get_ai_upload_extensions() -> List[str]:
    """AI 聊天附件允许的扩展名"""
    return get_extensions(
        SystemConfig.AI_UPLOAD_ALLOWED_EXTENSIONS,
        DEFAULT_AI_UPLOAD_EXTENSIONS,
    )


def get_ticket_attachment_extensions() -> List[str]:
    """工单附件允许的扩展名"""
    return get_extensions(
        SystemConfig.TICKET_ATTACHMENT_ALLOWED_EXTENSIONS,
        DEFAULT_TICKET_ATTACHMENT_EXTENSIONS,
    )
