import re


def sanitize_error_for_user(error_message: str, is_admin: bool) -> dict:
    """对错误信息进行脱敏处理，普通用户不显示SQL和堆栈详情"""
    if is_admin or not error_message:
        return {
            'error_message': error_message,
            'raw_error_message': error_message,
            'ai_suggestion': None
        }

    raw = error_message

    # 移除SQL语句（SELECT, INSERT, UPDATE, DELETE 等开头的长字符串）
    sql_pattern = re.compile(r'(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\s+.*?(?=\n|$)', re.IGNORECASE | re.DOTALL)
    clean = sql_pattern.sub('[SQL语句已隐藏]', raw)

    # 移除堆栈跟踪（Traceback开头到下一个空行的整段）
    traceback_pattern = re.compile(r'Traceback\s*\(most recent call last\):.*?(?=\n\S|\Z)', re.IGNORECASE | re.DOTALL)
    clean = traceback_pattern.sub('', clean)

    # 移除Python异常堆栈行（File "...", line N, in ...）
    file_pattern = re.compile(r'^\s*File\s+".*?"\s*,\s*line\s+\d+.*$', re.MULTILINE)
    clean = file_pattern.sub('', clean)

    # 移除SQLAlchemy相关错误详情 [SQL: ...] 部分
    clean = re.sub(r'\[SQL:\s*.*?\]', '[SQL已隐藏]', clean, flags=re.IGNORECASE | re.DOTALL)

    # 移除SQLAlchemy参数绑定详情 [parameters: ...]
    clean = re.sub(r'\[parameters:\s*.*?\]', '[参数已隐藏]', clean, flags=re.IGNORECASE | re.DOTALL)

    # 移除Python模块路径 (如 app.services.export_service 之类的)
    clean = re.sub(r'(?:app|backend)\.\w+\.\w+', '[模块路径]', clean)

    # 清理多余空行
    clean = re.sub(r'\n{3,}', '\n\n', clean)
    clean = clean.strip()

    # 如果清理后为空或太短，使用通用提示
    if not clean or len(clean) < 5:
        clean = '任务执行失败，请检查参数配置或联系管理员'

    # 生成修正建议
    ai_suggestion = _generate_error_suggestion(clean, raw)
    return {
        'error_message': clean,
        'raw_error_message': raw,
        'ai_suggestion': ai_suggestion
    }


def _generate_error_suggestion(clean_error: str, raw_error: str) -> str:
    """根据错误类型生成修正建议"""
    lower = (raw_error or '').lower()

    suggestions = []

    if 'timeout' in lower or 'timed out' in lower:
        suggestions.append('查询超时：请尝试缩小查询范围（如指定日期范围、减少筛选条件）后重试')
    if 'connection' in lower or 'connect' in lower:
        suggestions.append('数据库连接异常：请检查数据库配置是否正确，或联系管理员确认数据库服务状态')
    if 'permission' in lower or 'access denied' in lower or 'forbidden' in lower:
        suggestions.append('权限不足：请确认当前账号有足够权限访问相关数据，或联系管理员授权')
    if 'no results' in lower or 'no rows' in lower or '没有数据' in lower or '没有结果' in lower:
        suggestions.append('未查询到数据：请检查筛选参数是否正确，尝试调整查询条件后重试')
    if 'syntax' in lower or ('sql' in lower and 'error' in lower):
        suggestions.append('SQL语法错误：请联系管理员检查查询选项的SQL配置')
    if '参数' in lower or 'param' in lower or 'missing' in lower:
        suggestions.append('参数缺失或格式错误：请检查必填参数是否已正确填写')
    if 'file' in lower or '文件' in lower:
        suggestions.append('文件操作失败：请检查文件路径和磁盘空间，或联系管理员处理')
    if '导出失败' in lower or '所有查询均失败' in lower:
        suggestions.append('导出执行失败：请检查筛选条件是否正确，或联系管理员查看详细日志')

    if not suggestions:
        suggestions.append('如果问题持续存在，请联系管理员查看详细错误日志')

    return '\n'.join(suggestions)
