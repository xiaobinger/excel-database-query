"""上传文件识别与读取

按扩展名识别文件类型并读取内容：
- 表格类（xlsx/xlsm/xls/csv）：解析工作表、列名、行数与数据预览
- 文本类（txt/md/json/xml/log/yaml/ini/sql/py/js/html/css 等）：读取正文
- 文档类：pdf（需 pypdf）、docx（标准库解析）、doc（仅返回提示）
- 图片：返回基本信息（无 OCR）
- 压缩包：返回文件清单
"""
import csv
import logging
import os
import zipfile
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TABLE_EXTS = {'xlsx', 'xlsm', 'xls', 'csv'}
TEXT_EXTS = {
    'txt', 'md', 'markdown', 'json', 'xml', 'log', 'yaml', 'yml', 'ini', 'conf', 'cfg',
    'sql', 'py', 'js', 'ts', 'html', 'htm', 'css', 'sh', 'bat', 'ps1',
}
IMAGE_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'}
ARCHIVE_EXTS = {'zip', 'rar', '7z', 'tar', 'gz', 'tgz'}
PDF_EXTS = {'pdf'}
WORD_EXTS = {'docx', 'doc'}

FILE_KIND_LABELS = {
    'table': '表格文件',
    'text': '文本文件',
    'pdf': 'PDF 文档',
    'document': 'Word 文档',
    'image': '图片',
    'archive': '压缩包',
    'other': '文件',
}

DEFAULT_MAX_CHARS = 20000
MAX_MAX_CHARS = 100000
MAX_ARCHIVE_ENTRIES = 200

_ENCODINGS = ('utf-8-sig', 'utf-8', 'gb18030', 'gbk', 'latin1')
_WORD_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def get_extension(file_path: str) -> str:
    """返回不带点的小写扩展名"""
    return os.path.splitext(file_path or '')[1].lower().lstrip('.')


def detect_file_kind(ext: str) -> str:
    """按扩展名判断文件大类"""
    ext = (ext or '').lower().lstrip('.')
    if ext in TABLE_EXTS:
        return 'table'
    if ext in TEXT_EXTS:
        return 'text'
    if ext in PDF_EXTS:
        return 'pdf'
    if ext in WORD_EXTS:
        return 'document'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in ARCHIVE_EXTS:
        return 'archive'
    return 'other'


def get_file_type_label(kind: str) -> str:
    return FILE_KIND_LABELS.get(kind, FILE_KIND_LABELS['other'])


def _detect_csv_encoding_and_delimiter(file_path: str):
    """探测 CSV 编码与分隔符"""
    for encoding in _ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                sample = f.read(4096)
            if not sample:
                return encoding, ','
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
                return encoding, dialect.delimiter
            except csv.Error:
                return encoding, ','
        except UnicodeDecodeError:
            continue
        except OSError:
            break
    raise ValueError('无法识别 CSV 文件编码，请确认文件未损坏')


def _read_text_file(file_path: str, max_chars: int) -> Dict[str, Any]:
    """按常见编码读取文本文件"""
    for encoding in _ENCODINGS:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read(max_chars + 1)
            truncated = len(content) > max_chars
            return {
                'content': content[:max_chars],
                'encoding': encoding,
                'truncated': truncated,
                'total_chars': None if truncated else len(content),
            }
        except UnicodeDecodeError:
            continue
    raise ValueError('无法识别文本文件编码，请确认文件未损坏')


def _read_pdf(file_path: str, max_chars: int, max_pages: int = 50) -> Dict[str, Any]:
    """提取 PDF 文本（优先 pypdf，兼容 PyPDF2）"""
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return {
                'content': '',
                'note': '当前环境未安装 PDF 解析库（pypdf），无法提取 PDF 正文；可让用户提供文本/表格文件，或联系管理员安装依赖',
            }

    reader = PdfReader(file_path)
    total_pages = len(reader.pages)
    limit_pages = min(total_pages, max_pages)
    parts = []
    total_chars = 0
    for index in range(limit_pages):
        text = reader.pages[index].extract_text() or ''
        parts.append(text)
        total_chars += len(text)
        if total_chars >= max_chars:
            break
    content = '\n'.join(parts)
    truncated = len(content) > max_chars or total_pages > limit_pages
    result = {
        'content': content[:max_chars],
        'total_pages': total_pages,
        'parsed_pages': limit_pages,
        'truncated': truncated,
    }
    if total_pages > limit_pages:
        result['note'] = f'PDF 共 {total_pages} 页，仅解析前 {limit_pages} 页'
    return result


def _read_docx(file_path: str, max_chars: int) -> Dict[str, Any]:
    """用标准库从 docx 提取段落文本"""
    with zipfile.ZipFile(file_path) as archive:
        xml_bytes = archive.read('word/document.xml')
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.iter(f'{_WORD_NS}p'):
        text = ''.join(node.text or '' for node in paragraph.iter(f'{_WORD_NS}t'))
        if text.strip():
            paragraphs.append(text)
    content = '\n'.join(paragraphs)
    return {
        'content': content[:max_chars],
        'truncated': len(content) > max_chars,
        'total_chars': len(content),
    }


def _read_archive(file_path: str, ext: str) -> Dict[str, Any]:
    """列出压缩包内文件清单"""
    entries: List[str] = []
    if ext == 'zip':
        with zipfile.ZipFile(file_path) as archive:
            entries = archive.namelist()
    elif ext in ('tar', 'gz', 'tgz'):
        import tarfile
        with tarfile.open(file_path) as archive:
            entries = archive.getnames()
    else:
        return {
            'entries': [],
            'note': f'暂不支持直接读取 {ext} 压缩包内容，请解压后上传其中的文件',
        }

    return {
        'entries': entries[:MAX_ARCHIVE_ENTRIES],
        'total_entries': len(entries),
        'truncated': len(entries) > MAX_ARCHIVE_ENTRIES,
    }


def _to_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_cell(value) -> Any:
    if value is None:
        return ''
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return ''
    except Exception:
        pass
    return str(value)


def _read_table_with_pandas(file_path: str, ext: str, options: Dict[str, Any]) -> Dict[str, Any]:
    """用 pandas 读取 xls / csv 表格"""
    import pandas as pd

    preview_rows = max(1, min(_to_int(options.get('preview_rows'), 5), 20))
    sheet_name = (options.get('sheet_name') or '').strip() or None
    columns = options.get('columns')
    if isinstance(columns, str):
        columns = [c.strip() for c in columns.split(',') if c.strip()]

    if ext == 'csv':
        encoding, _ = _detect_csv_encoding_and_delimiter(file_path)
        df = pd.read_csv(file_path, encoding=encoding, dtype=str, sep=None, engine='python')
        sheet_names = []
        active_sheet = 'CSV'
    else:
        excel = pd.ExcelFile(file_path)
        sheet_names = list(excel.sheet_names)
        active_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]
        df = pd.read_excel(excel, sheet_name=active_sheet, dtype=str)

    all_columns = [str(c) for c in df.columns]
    selected_columns = all_columns
    missing_columns = []
    if columns:
        selected_columns = []
        for name in columns:
            matched = next((c for c in all_columns if c == name), None)
            if matched is None:
                matched = next((c for c in all_columns if c.lower() == str(name).lower()), None)
            if matched is None:
                missing_columns.append(name)
            else:
                selected_columns.append(matched)

    preview_df = df[selected_columns].head(preview_rows) if selected_columns else df.head(0)
    preview_rows_data = [
        [_normalize_cell(cell) for cell in row]
        for row in preview_df.values.tolist()
    ]

    result = {
        'file_kind': 'table',
        'active_sheet': active_sheet,
        'row_count': int(len(df)),
        'columns': all_columns,
        'sheets': [{'name': name} for name in sheet_names],
        'preview': {
            'headers': selected_columns,
            'rows': preview_rows_data,
            'total_rows': int(len(df)),
            'missing_columns': missing_columns,
        },
    }

    values_column = (options.get('values_column') or '').strip()
    if values_column:
        column_name = next((c for c in all_columns if c == values_column), None)
        if column_name is None:
            column_name = next((c for c in all_columns if c.lower() == values_column.lower()), None)
        if column_name is None and len(values_column) <= 3:
            # 支持列字母（A/B/AA...）
            try:
                index = 0
                for ch in values_column.upper():
                    index = index * 26 + (ord(ch) - ord('A') + 1)
                index -= 1
                if 0 <= index < len(all_columns):
                    column_name = all_columns[index]
            except Exception:
                column_name = None
        if column_name is None:
            result['column_values'] = {'error': f'列 "{values_column}" 不存在'}
        else:
            max_values = max(1, min(_to_int(options.get('max_values'), 200), 1000))
            values = [
                str(v).strip() for v in df[column_name].dropna().tolist()
                if str(v).strip()
            ]
            result['column_values'] = {
                'column': column_name,
                'values': values[:max_values],
                'total_non_empty': len(values),
                'truncated': len(values) > max_values,
            }
    return result


def _read_table(file_path: str, ext: str, options: Dict[str, Any]) -> Dict[str, Any]:
    if ext in ('xlsx', 'xlsm'):
        from app.services.excel_service import ExcelService

        preview_rows = max(1, min(_to_int(options.get('preview_rows'), 5), 20))
        columns = options.get('columns') or None
        if isinstance(columns, str):
            columns = [c.strip() for c in columns.split(',') if c.strip()]
        values_column = (options.get('values_column') or '').strip() or None
        max_values = max(1, min(_to_int(options.get('max_values'), 200), 1000))

        data = ExcelService.parse_file(
            file_path,
            sheet_name=(options.get('sheet_name') or '').strip() or None,
            preview_rows=preview_rows,
            columns=columns,
            values_column=values_column,
            max_values=max_values,
        )

        def _truncate(value):
            if isinstance(value, str) and len(value) > 200:
                return value[:200] + '…'
            return value

        preview = data.get('preview', {})
        preview['rows'] = [[_truncate(cell) for cell in row] for row in preview.get('rows', [])]
        file_info = data.get('file_info', {})
        result = {
            'file_kind': 'table',
            'file_path': file_path,
            'filename': os.path.basename(file_path),
            'active_sheet': data.get('active_sheet'),
            'row_count': file_info.get('data_rows', 0),
            'columns': file_info.get('column_names', []),
            'sheets': data.get('sheets', []),
            'preview': preview,
        }
        if data.get('column_values') is not None:
            result['column_values'] = data['column_values']
        return result

    return _read_table_with_pandas(file_path, ext, options)


def get_table_summary(file_path: str) -> Dict[str, Any]:
    """轻量获取表格结构（上传后立即返回给前端展示）"""
    ext = get_extension(file_path)
    if ext in ('xlsx', 'xlsm'):
        from app.services.excel_service import ExcelService

        info = ExcelService.get_file_info(file_path)
        if not info:
            raise ValueError('无法解析表格文件，请确认文件未损坏')
        return {
            'row_count': info.get('data_rows', 0),
            'columns': info.get('column_names', []),
            'active_sheet': info.get('sheet_name'),
        }

    if ext == 'xls':
        import xlrd

        book = xlrd.open_workbook(file_path)
        sheet = book.sheet_by_index(0)
        columns = []
        if sheet.nrows:
            columns = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
        return {
            'row_count': max(sheet.nrows - 1, 0),
            'columns': columns,
            'active_sheet': sheet.name,
        }

    if ext == 'csv':
        encoding, delimiter = _detect_csv_encoding_and_delimiter(file_path)
        with open(file_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter=delimiter)
            header = next(reader, [])
            columns = [str(col).strip() for col in header]
            row_count = sum(1 for _ in reader)
        return {
            'row_count': row_count,
            'columns': columns,
            'active_sheet': 'CSV',
        }

    raise ValueError(f'不支持的表格格式: {ext or "无扩展名"}')


def inspect_uploaded_file(file_path: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
    """上传完成后返回的文件摘要：类型、大小，表格类附带行数与列名"""
    ext = get_extension(original_filename or file_path)
    kind = detect_file_kind(ext)
    result = {
        'file_path': os.path.abspath(file_path),
        'filename': original_filename or os.path.basename(file_path),
        'file_kind': kind,
        'file_type_label': get_file_type_label(kind),
        'file_size': os.path.getsize(file_path),
        'ext': ext,
    }
    if kind == 'table':
        result.update(get_table_summary(file_path))
    return result


def read_uploaded_file(file_path: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取已上传文件内容

    Args:
        file_path: 服务器文件路径
        options: preview_rows / columns / values_column / max_values / max_chars / sheet_name / max_pages
    """
    options = options or {}
    ext = get_extension(file_path)
    kind = detect_file_kind(ext)
    max_chars = max(1000, min(_to_int(options.get('max_chars'), DEFAULT_MAX_CHARS), MAX_MAX_CHARS))

    base = {
        'file_path': os.path.abspath(file_path),
        'filename': os.path.basename(file_path),
        'file_kind': kind,
        'file_type_label': get_file_type_label(kind),
        'file_size': os.path.getsize(file_path),
    }

    if kind == 'table':
        base.update(_read_table(file_path, ext, options))
        return base

    if kind == 'text':
        base.update(_read_text_file(file_path, max_chars))
        return base

    if kind == 'pdf':
        max_pages = max(1, min(_to_int(options.get('max_pages'), 50), 200))
        base.update(_read_pdf(file_path, max_chars, max_pages=max_pages))
        return base

    if kind == 'document':
        if ext == 'docx':
            base.update(_read_docx(file_path, max_chars))
        else:
            base['note'] = '暂不支持读取旧版 .doc 文件，请将文件另存为 .docx 后重新上传'
        return base

    if kind == 'image':
        base['note'] = '图片已上传，但系统暂不具备 OCR 能力，无法直接提取图片中的文字内容'
        return base

    if kind == 'archive':
        base.update(_read_archive(file_path, ext))
        return base

    base['note'] = f'暂不支持读取 {ext or "该"} 格式的文件内容'
    return base
