"""AI 文件生成服务：把对话内容生成为可下载的真实文件，并支持调用图片生成模型产出图片。"""

import base64
import csv
import io
import json
import logging
import os
import re
import uuid
import zipfile
from datetime import datetime
from xml.sax.saxutils import escape

logger = logging.getLogger(__name__)

# 纯文本类格式，直接按文本写入
TEXT_FORMATS = {
    'txt', 'md', 'markdown', 'csv', 'json', 'html', 'htm', 'xml', 'yaml', 'yml',
    'sql', 'log', 'py', 'js', 'ts', 'java', 'c', 'cpp', 'h', 'sh', 'bat', 'ini',
    'toml', 'cfg', 'conf', 'properties', 'srt',
}
TABLE_FORMATS = {'xlsx'}
DOCUMENT_FORMATS = {'docx'}
PDF_FORMATS = {'pdf'}
IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'webp', 'gif', 'bmp', 'svg'}

SUPPORTED_FORMATS = sorted(TEXT_FORMATS | TABLE_FORMATS | DOCUMENT_FORMATS | PDF_FORMATS)

MAX_CONTENT_CHARS = 5 * 1024 * 1024

FILE_KIND_LABELS = {
    'table': '表格文件',
    'document': 'Word 文档',
    'pdf': 'PDF 文档',
    'image': '图片',
    'text': '文本文件',
    'archive': '压缩包',
}


def _output_folder() -> str:
    from flask import current_app
    folder = current_app.config.get('OUTPUT_FOLDER') or './outputs'
    os.makedirs(folder, exist_ok=True)
    return folder


def _file_kind(ext: str) -> str:
    if ext in TABLE_FORMATS or ext == 'csv':
        return 'table'
    if ext in DOCUMENT_FORMATS:
        return 'document'
    if ext in PDF_FORMATS:
        return 'pdf'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in {'zip', 'rar', '7z', 'tar', 'gz'}:
        return 'archive'
    return 'text'


def _strip_code_fence(text: str) -> str:
    """去掉模型偶尔包裹在内容外层的 Markdown 代码围栏。"""
    if not text:
        return ''
    stripped = text.strip()
    match = re.match(r'^```[a-zA-Z0-9_+-]*\s*\n([\s\S]*?)\n?```$', stripped)
    if match:
        return match.group(1)
    return text


def safe_filename(name: str, default_stem: str = '生成文件', default_ext: str = 'txt') -> str:
    """清洗文件名：保留中文，去掉路径与非法字符，限制长度。"""
    raw = (name or '').strip().replace('\\', '/')
    raw = raw.split('/')[-1]
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', raw).strip(' .')
    if not raw:
        raw = f'{default_stem}.{default_ext}'
    stem, ext = os.path.splitext(raw)
    if not ext:
        raw = f'{raw}.{default_ext}'
        stem, ext = os.path.splitext(raw)
    if len(stem) > 100:
        stem = stem[:100]
    return f'{stem}{ext}'


def _stored_path(safe_name: str) -> tuple:
    folder = _output_folder()
    stored_name = f'ai_{uuid.uuid4().hex[:12]}_{safe_name}'
    return os.path.join(folder, stored_name), stored_name


def _build_result(path: str, safe_name: str, extra: dict = None) -> dict:
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    kind = _file_kind(ext)
    size = os.path.getsize(path)
    result = {
        'action_type': 'file',
        'success': True,
        'file_path': path,
        'filename': safe_name,
        'file_size': size,
        'file_kind': kind,
        'file_type_label': FILE_KIND_LABELS.get(kind, '文件'),
        'download_url': f'/api/download/generated/{os.path.basename(path)}',
        'message': f'文件已生成：{safe_name}（{size} 字节），可在卡片中下载',
    }
    if kind == 'image':
        result['preview_url'] = result['download_url'] + '?inline=1'
    if extra:
        result.update(extra)
    return result


def _parse_delimited(text: str) -> list:
    text = (text or '').lstrip('\ufeff')
    if not text.strip():
        return []
    sample = text[:8192]
    delimiter = ','
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=',\t;').delimiter
    except Exception:
        delimiter = '\t' if sample.count('\t') > sample.count(',') else ','
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _normalize_sheets(sheets, content: str) -> list:
    """把工具入参统一成 [{name, headers, rows}] 结构。"""
    normalized = []
    if isinstance(sheets, list) and sheets:
        for idx, sheet in enumerate(sheets):
            if not isinstance(sheet, dict):
                continue
            headers = sheet.get('headers') or sheet.get('columns') or []
            rows = sheet.get('rows') or sheet.get('data') or []
            if not isinstance(rows, list):
                rows = []
            # 兼容 AI 传入对象数组的情况
            if rows and isinstance(rows[0], dict):
                if not headers:
                    headers = list(rows[0].keys())
                rows = [[row.get(h) for h in headers] for row in rows]
            normalized.append({
                'name': sheet.get('name') or sheet.get('sheet_name') or f'Sheet{idx + 1}',
                'headers': list(headers) if isinstance(headers, (list, tuple)) else [],
                'rows': rows,
            })
        return normalized

    parsed = _parse_delimited(content)
    if parsed:
        return [{
            'name': 'Sheet1',
            'headers': parsed[0],
            'rows': parsed[1:],
        }]
    return [{'name': 'Sheet1', 'headers': [], 'rows': []}]


def _sheet_title(name: str, index: int) -> str:
    name = re.sub(r'[\[\]:*?/\\]', '_', str(name or '')).strip()[:31]
    return name or f'Sheet{index + 1}'


def _write_xlsx(path: str, sheets, content: str):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    workbook.remove(workbook.active)
    sheet_defs = _normalize_sheets(sheets, content)

    for idx, sheet_def in enumerate(sheet_defs):
        ws = workbook.create_sheet(title=_sheet_title(sheet_def['name'], idx))
        headers = sheet_def['headers']
        rows = sheet_def['rows']

        row_offset = 0
        if headers:
            ws.append(headers)
            row_offset = 1
            header_font = Font(bold=True, color='FFFFFF')
            header_fill = PatternFill('solid', fgColor='409EFF')
            for cell in ws[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal='center', vertical='center')

        for row in rows:
            if isinstance(row, dict):
                keys = headers or list(row.keys())
                ws.append([row.get(k) for k in keys])
            elif isinstance(row, (list, tuple)):
                ws.append(list(row))
            else:
                ws.append([row])

        if ws.max_row > 1:
            ws.freeze_panes = 'A2'

        # 按内容估算列宽（中文按 2 个字符宽度计算）
        for col_idx in range(1, ws.max_column + 1):
            max_width = 0
            for cell in ws[get_column_letter(col_idx)]:
                value = '' if cell.value is None else str(cell.value)
                width = sum(2 if ord(ch) > 127 else 1 for ch in value)
                max_width = max(max_width, width)
            ws.column_dimensions[get_column_letter(col_idx)].width = min(max(max_width + 2, 8), 60)

    if not workbook.worksheets:
        workbook.create_sheet(title='Sheet1')
    workbook.save(path)


def _markdown_blocks(content: str) -> list:
    """把 Markdown 风格文本拆成 (级别, 文本) 块，级别 0=正文，1/2/3=标题，-1=列表。"""
    blocks = []
    in_code = False
    for raw_line in (content or '').splitlines():
        line = raw_line.rstrip()
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        stripped = line.strip()
        if not stripped:
            blocks.append((0, ''))
            continue
        if in_code:
            blocks.append((0, line))
            continue
        if stripped.startswith('#'):
            level = min(len(stripped) - len(stripped.lstrip('#')), 3)
            text = stripped[level:].strip()
            if text:
                blocks.append((level, text))
            continue
        if re.match(r'^[-*+]\s+', stripped):
            blocks.append((-1, re.sub(r'^[-*+]\s+', '', stripped)))
            continue
        if stripped.startswith('|') and stripped.endswith('|'):
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if all(re.match(r'^:?-{3,}:?$', c) for c in cells):
                continue
            blocks.append((0, '    '.join(cells)))
            continue
        blocks.append((0, line))
    return blocks


def _docx_paragraph(text: str, level: int = 0) -> str:
    text = escape(text)
    size = {1: 32, 2: 28, 3: 24}.get(level, 22)
    bold = '<w:b/>' if level > 0 else ''
    indent = ''
    if level == -1:
        text = '• ' + text
        indent = '<w:ind w:left="360"/>'
    jc = '<w:jc w:val="center"/>' if level == 1 else ''
    return (
        '<w:p><w:pPr><w:spacing w:after="120" w:line="320" w:lineRule="auto"/>'
        f'{indent}{jc}</w:pPr><w:r><w:rPr>{bold}<w:sz w:val="{size}"/>'
        f'<w:szCs w:val="{size}"/></w:rPr><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
    )


def _write_docx(path: str, content: str, title: str = ''):
    body = []
    if title:
        body.append(_docx_paragraph(title, 1))
    for level, text in _markdown_blocks(content):
        body.append(_docx_paragraph(text, level))

    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body>' + ''.join(body) +
        '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" '
        'w:header="851" w:footer="992" w:gutter="0"/></w:sectPr>'
        '</w:body></w:document>'
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '</Types>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        '</Relationships>'
    )
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml', content_types)
        zf.writestr('_rels/.rels', rels)
        zf.writestr('word/document.xml', document_xml)


def _write_pdf(path: str, content: str, title: str = ''):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    except ImportError:
        raise RuntimeError('当前环境未安装 reportlab，暂不支持生成 PDF，请改用 docx 或安装 reportlab')

    try:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        font_name = 'STSong-Light'
    except Exception:
        font_name = 'Helvetica'

    styles = {
        0: ParagraphStyle('body', fontName=font_name, fontSize=10.5, leading=17, spaceAfter=4),
        -1: ParagraphStyle('bullet', fontName=font_name, fontSize=10.5, leading=17, leftIndent=14, spaceAfter=2),
        1: ParagraphStyle('h1', fontName=font_name, fontSize=18, leading=26, spaceBefore=6, spaceAfter=10),
        2: ParagraphStyle('h2', fontName=font_name, fontSize=15, leading=22, spaceBefore=4, spaceAfter=8),
        3: ParagraphStyle('h3', fontName=font_name, fontSize=13, leading=20, spaceBefore=2, spaceAfter=6),
    }
    story = []
    if title:
        story.append(Paragraph(escape(title), styles[1]))
    for level, text in _markdown_blocks(content):
        if not text:
            story.append(Spacer(1, 6))
            continue
        if level == -1:
            text = '• ' + text
        story.append(Paragraph(escape(text).replace('\n', '<br/>'), styles.get(level, styles[0])))

    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm)
    doc.build(story)


def _write_text_file(path: str, ext: str, content: str):
    if ext == 'json':
        try:
            json.loads(content)
        except Exception:
            raise ValueError('JSON 内容格式不合法，请提供合法的 JSON 字符串')
    if ext == 'html':
        if '<html' not in content.lower():
            content = (
                '<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width, initial-scale=1">'
                '<title>生成文档</title></head><body>' + content + '</body></html>'
            )
    encoding = 'utf-8-sig' if ext == 'csv' else 'utf-8'
    with open(path, 'w', encoding=encoding, newline='') as fh:
        fh.write(content)


def create_file(filename: str = None, content: str = None, sheets=None,
                title: str = None, fmt: str = None) -> dict:
    """根据入参生成文件，返回下载信息或 error。"""
    if content is None:
        content = ''
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False, indent=2)
    content = _strip_code_fence(content)
    if len(content) > MAX_CONTENT_CHARS:
        return {'error': f'文件内容过长（{len(content)} 字符），请拆分后分批生成'}

    fmt = (fmt or '').lower().lstrip('.')
    if fmt and fmt not in SUPPORTED_FORMATS:
        return {'error': f'不支持的文件格式 .{fmt}，当前支持：{", ".join(SUPPORTED_FORMATS)}'}
    if not filename and not fmt:
        fmt = 'xlsx' if sheets else 'txt'

    safe_name = safe_filename(filename or f'生成文件.{fmt or "txt"}', default_ext=fmt or 'txt')
    ext = (fmt or os.path.splitext(safe_name)[1].lstrip('.')).lower()

    if ext not in SUPPORTED_FORMATS:
        return {'error': f'不支持的文件格式 .{ext}，当前支持：{", ".join(SUPPORTED_FORMATS)}'}

    # 扩展名与显式 format 不一致时以 format 为准
    if os.path.splitext(safe_name)[1].lstrip('.').lower() != ext:
        safe_name = f'{os.path.splitext(safe_name)[0]}.{ext}'

    path, _stored = _stored_path(safe_name)
    try:
        if ext == 'xlsx':
            _write_xlsx(path, sheets, content)
        elif ext == 'docx':
            _write_docx(path, content, title=title or '')
        elif ext == 'pdf':
            _write_pdf(path, content, title=title or '')
        else:
            _write_text_file(path, ext, content)
    except Exception as exc:
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        logger.error(f'生成文件失败: {safe_name}, 错误: {exc}', exc_info=True)
        return {'error': f'生成文件失败：{exc}'}

    return _build_result(path, safe_name)


# ---------------- 图片生成 ----------------

IMAGE_MODEL_HINTS = (
    'dall-e', 'gpt-image', 'cogview', 'flux', 'seedream', 'kolors',
    'qwen-image', 'stable-diffusion', 'sd3', 'hunyuan-image', 'wanx', 'image',
)


def _resolve_image_config(model: str = None):
    """从环境变量或已启用的 AI 配置中挑选图片生成配置。"""
    env_base = (os.getenv('IMAGE_GENERATION_API_BASE') or os.getenv('IMAGE_GEN_API_BASE') or '').strip()
    env_key = (os.getenv('IMAGE_GENERATION_API_KEY') or os.getenv('IMAGE_GEN_API_KEY') or '').strip()
    env_model = (os.getenv('IMAGE_GENERATION_MODEL') or os.getenv('IMAGE_GEN_MODEL') or '').strip()
    if env_base and env_key and (model or env_model):
        return {'api_base': env_base, 'api_key': env_key, 'model': model or env_model, 'name': '环境变量配置'}

    from app.models.ai_config import AiConfig
    configs = AiConfig.query.filter_by(is_active=True).order_by(AiConfig.is_default.desc(), AiConfig.id.asc()).all()
    fallback = None
    for cfg in configs:
        api_key = cfg.get_api_key()
        if not api_key or not cfg.api_base:
            continue
        model_list = [m for m in ([cfg.model_name] + cfg.get_models()) if m]
        if model and model in model_list:
            return {'api_base': cfg.api_base, 'api_key': api_key, 'model': model, 'name': cfg.name}
        image_models = [m for m in model_list if any(h in str(m).lower() for h in IMAGE_MODEL_HINTS)]
        if image_models:
            return {'api_base': cfg.api_base, 'api_key': api_key, 'model': image_models[0], 'name': cfg.name}
        if not fallback:
            fallback = {'api_base': cfg.api_base, 'api_key': api_key, 'model': cfg.model_name, 'name': cfg.name}

    if model and fallback:
        fallback['model'] = model
        return fallback
    return None


def _detect_image_ext(raw: bytes, default: str = 'png') -> str:
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if raw.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'webp'
    if raw.startswith(b'GIF8'):
        return 'gif'
    if raw.startswith(b'BM'):
        return 'bmp'
    if raw.lstrip()[:5].lower() in (b'<svg ', b'<?xml'):
        return 'svg'
    return default


def generate_image(prompt: str, size: str = None, model: str = None, filename: str = None) -> dict:
    """调用 OpenAI 兼容的 /images/generations 接口生成图片并保存。"""
    import requests

    prompt = (prompt or '').strip()
    if not prompt:
        return {'error': '请提供图片描述 prompt'}

    cfg = _resolve_image_config(model)
    if not cfg:
        return {
            'error': '未找到可用的图片生成模型。请先在 AI 配置中添加支持图片生成的模型'
                     '（如 cogview-3-flash、dall-e-3、flux.1-schnell 等，需兼容 OpenAI /images/generations 接口），'
                     '或通过环境变量 IMAGE_GENERATION_API_BASE / IMAGE_GENERATION_API_KEY / IMAGE_GENERATION_MODEL 配置',
        }

    endpoint = cfg['api_base'].rstrip('/')
    if not endpoint.endswith('/images/generations'):
        endpoint += '/images/generations'
    payload = {'model': cfg['model'], 'prompt': prompt, 'n': 1}
    if size:
        payload['size'] = size

    headers = {
        'Authorization': f"Bearer {cfg['api_key']}",
        'Content-Type': 'application/json',
    }
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=180)
    except Exception as exc:
        logger.error(f'图片生成请求失败: {exc}', exc_info=True)
        return {'error': f'图片生成请求失败：{exc}'}

    if resp.status_code >= 400:
        detail = (resp.text or '')[:300]
        logger.error(f'图片生成接口返回错误 HTTP {resp.status_code}: {detail}')
        return {'error': f'图片生成接口调用失败（HTTP {resp.status_code}）：{detail}'}

    try:
        data = resp.json()
    except Exception:
        return {'error': '图片生成接口返回内容不是合法 JSON'}

    item = {}
    if isinstance(data.get('data'), list) and data['data']:
        item = data['data'][0] or {}
    elif isinstance(data.get('images'), list) and data['images']:
        item = data['images'][0] or {}
    elif isinstance(data.get('output'), dict):
        results = data['output'].get('results') or []
        if results:
            item = results[0] or {}

    raw = None
    if item.get('b64_json'):
        try:
            raw = base64.b64decode(item['b64_json'])
        except Exception:
            return {'error': '图片生成接口返回的 base64 数据无法解析'}
    elif item.get('url'):
        try:
            img_resp = requests.get(item['url'], timeout=120)
            if img_resp.status_code < 400:
                raw = img_resp.content
        except Exception as exc:
            logger.error(f'下载生成图片失败: {exc}', exc_info=True)
    if not raw:
        return {'error': '图片生成接口未返回图片数据，请检查模型是否支持该接口'}

    ext = _detect_image_ext(raw)
    safe_name = safe_filename(filename or f'AI生成图片_{datetime.now().strftime("%Y%m%d_%H%M%S")}.{ext}',
                              default_ext=ext)
    given_ext = os.path.splitext(safe_name)[1].lstrip('.').lower()
    if given_ext not in IMAGE_EXTS:
        safe_name = f'{os.path.splitext(safe_name)[0]}.{ext}'
    elif given_ext != ext:
        # 实际图片格式优先，避免扩展名与内容不一致
        safe_name = f'{os.path.splitext(safe_name)[0]}.{ext}'

    path, _stored = _stored_path(safe_name)
    with open(path, 'wb') as fh:
        fh.write(raw)

    return _build_result(path, safe_name, extra={
        'prompt': prompt,
        'image_model': cfg['model'],
        'image_provider': cfg['name'],
    })