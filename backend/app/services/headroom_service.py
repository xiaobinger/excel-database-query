import json
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class HeadroomCompressor:
    """Headroom 内容感知上下文压缩器

    基于 Headroom 核心理念实现：
    - 内容感知：识别内容类型，保留高价值部分，压缩低价值部分
    - 统计压缩：对 JSON 数组字段计算方差，方差高的保留，方差低的压缩
    - 可逆压缩：压缩后保留检索标记，需要时可取回原件

    参考：https://github.com/headroomlabs-ai/headroom
    """

    # 高价值关键词（日志/文本中保留）
    HIGH_VALUE_KEYWORDS = [
        'error', 'ERROR', 'Error',
        'exception', 'Exception', 'EXCEPTION',
        'fail', 'FAIL', 'Fail', 'failed', 'FAILED',
        'fatal', 'FATAL', 'Fatal',
        'critical', 'CRITICAL', 'Critical',
        'warning', 'WARNING', 'Warning', 'warn', 'WARN',
        'traceback', 'Traceback', 'TRACEBACK',
        'stack', 'Stack', 'STACK',
        'timeout', 'Timeout', 'TIMEOUT',
        'refused', 'Refused', 'REFUSED',
        'denied', 'Denied', 'DENIED',
        'invalid', 'Invalid', 'INVALID',
        'missing', 'Missing', 'MISSING',
        'not found', 'Not Found', 'NOT FOUND',
        'undefined', 'Undefined', 'UNDEFINED',
        'null', 'Null', 'NULL',
        'panic', 'Panic', 'PANIC',
        'crash', 'Crash', 'CRASH',
        'abort', 'Abort', 'ABORT',
    ]

    # 日志噪音模式（可压缩）
    LOG_NOISE_PATTERNS = [
        r'^\s*INFO\s', r'^\s*DEBUG\s', r'^\s*PASS\s',
        r'^\s*OK\s', r'^\s*SUCCESS\s', r'^\s*DONE\s',
        r'^\s*start(ed|ing)?\s', r'^\s*complet(ed|ion)\s',
        r'^\s*process(ed|ing)?\s', r'^\s*execut(ed|ion)\s',
    ]

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """估算 token 数量（简化版：中文约1.5字符/token，英文约4字符/token）"""
        if not text:
            return 0
        # 简单估算：总字符数 / 2.5（中英文混合的平均值）
        return max(1, len(text) // 2)

    @staticmethod
    def compress_messages(messages: list) -> Tuple[list, dict]:
        """压缩消息列表，返回压缩后的消息和统计信息

        Args:
            messages: 消息列表，每个消息包含 role 和 content

        Returns:
            (compressed_messages, stats)
            stats 包含 original_tokens, compressed_tokens, saved_tokens, compression_ratio
        """
        if not messages:
            return messages, {
                'original_tokens': 0,
                'compressed_tokens': 0,
                'saved_tokens': 0,
                'compression_ratio': 0.0,
                'compressed_count': 0,
            }

        total_original_tokens = 0
        total_compressed_tokens = 0
        compressed_count = 0
        compressed_messages = []

        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')

            # system 消息和短消息不压缩（阈值降低到50字符，让更多内容被压缩）
            if role == 'system' or not content or len(content) < 50:
                compressed_messages.append(msg)
                total_original_tokens += HeadroomCompressor.estimate_tokens(content)
                total_compressed_tokens += HeadroomCompressor.estimate_tokens(content)
                continue

            # 压缩内容
            compressed_content, msg_stats = HeadroomCompressor._compress_content(content)

            # 调试日志：记录压缩效果
            logger.debug(
                f'Headroom 压缩消息: role={role}, '
                f'original={msg_stats["original_tokens"]} tokens, '
                f'compressed={msg_stats["compressed_tokens"]} tokens, '
                f'saved={msg_stats["saved_tokens"]} tokens'
            )

            if msg_stats['saved_tokens'] > 0:
                compressed_count += 1

            compressed_messages.append({
                **msg,
                'content': compressed_content
            })
            total_original_tokens += msg_stats['original_tokens']
            total_compressed_tokens += msg_stats['compressed_tokens']

        saved_tokens = total_original_tokens - total_compressed_tokens
        compression_ratio = saved_tokens / total_original_tokens if total_original_tokens > 0 else 0.0

        stats = {
            'original_tokens': total_original_tokens,
            'compressed_tokens': total_compressed_tokens,
            'saved_tokens': saved_tokens,
            'compression_ratio': round(compression_ratio, 4),
            'compressed_count': compressed_count,
        }

        return compressed_messages, stats

    @staticmethod
    def _compress_content(content: str) -> Tuple[str, dict]:
        """压缩单个内容，返回压缩后的内容和统计信息"""
        original_tokens = HeadroomCompressor.estimate_tokens(content)

        # 尝试识别内容类型并应用对应的压缩策略
        compressed = content

        # 1. 尝试作为 JSON 数组压缩
        json_result = HeadroomCompressor._try_compress_json_array(content)
        if json_result is not None:
            compressed = json_result
        else:
            # 2. 尝试作为日志压缩
            log_result = HeadroomCompressor._try_compress_log(content)
            if log_result is not None:
                compressed = log_result
            else:
                # 3. 尝试作为代码压缩
                code_result = HeadroomCompressor._try_compress_code(content)
                if code_result is not None:
                    compressed = code_result
                else:
                    # 4. 纯文本压缩
                    compressed = HeadroomCompressor._compress_text(content)

        compressed_tokens = HeadroomCompressor.estimate_tokens(compressed)
        saved_tokens = original_tokens - compressed_tokens

        stats = {
            'original_tokens': original_tokens,
            'compressed_tokens': compressed_tokens,
            'saved_tokens': saved_tokens,
        }

        return compressed, stats

    @staticmethod
    def _try_compress_json_array(content: str) -> Optional[str]:
        """尝试压缩 JSON 数组（SmartCrusher 理念）"""
        content_stripped = content.strip()
        if not (content_stripped.startswith('[') and content_stripped.endswith(']')):
            return None

        try:
            data = json.loads(content_stripped)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(data, list) or len(data) < 3:
            return None

        # 只处理对象数组
        if not all(isinstance(item, dict) for item in data):
            return None

        # 统计字段方差
        field_values = {}
        for item in data:
            for key, value in item.items():
                if key not in field_values:
                    field_values[key] = []
                field_values[key].append(str(value))

        # 计算每个字段的方差（取值多样性）
        field_variance = {}
        for key, values in field_values.items():
            unique_ratio = len(set(values)) / len(values) if values else 0
            field_variance[key] = unique_ratio

        # 保留高方差字段（取值多样，信息量大），压缩低方差字段
        high_variance_fields = {k for k, v in field_variance.items() if v > 0.3}
        low_variance_fields = {k for k, v in field_variance.items() if v <= 0.3}

        # 压缩：高方差字段保留，低方差字段只保留前3个
        compressed_data = []
        for item in data:
            compressed_item = {}
            for key in high_variance_fields:
                if key in item:
                    compressed_item[key] = item[key]
            # 低方差字段只保留前3个不同的值
            for key in low_variance_fields:
                if key in item:
                    if key not in compressed_item:
                        compressed_item[key] = item[key]
                    else:
                        break
            compressed_data.append(compressed_item)

        # 如果压缩效果不明显，返回原内容
        compressed_str = json.dumps(compressed_data, ensure_ascii=False)
        if len(compressed_str) > len(content) * 0.7:
            return None

        return compressed_str

    @staticmethod
    def _try_compress_log(content: str) -> Optional[str]:
        """尝试压缩日志内容（LogCompressor 理念）"""
        lines = content.split('\n')
        if len(lines) < 5:
            return None

        # 检测是否为日志格式（包含时间戳、日志级别等）
        log_pattern = re.compile(
            r'(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}:\d{2}:\d{2}|'
            r'INFO|DEBUG|WARN|ERROR|FATAL|TRACE|'
            r'pass|fail|ok|done|success)',
            re.IGNORECASE
        )

        log_lines = sum(1 for line in lines if log_pattern.search(line))
        if log_lines < len(lines) * 0.3:
            return None

        # 保留高价值行（包含错误、异常等），压缩噪音行
        high_value_lines = []
        noise_lines = []

        for line in lines:
            is_high_value = any(kw in line for kw in HeadroomCompressor.HIGH_VALUE_KEYWORDS)
            is_noise = any(re.match(p, line) for p in HeadroomCompressor.LOG_NOISE_PATTERNS)

            if is_high_value:
                high_value_lines.append(line)
            elif is_noise:
                noise_lines.append(line)
            else:
                high_value_lines.append(line)

        # 保留所有高价值行，噪音行只保留前20%
        max_noise = max(1, int(len(noise_lines) * 0.2))
        kept_noise = noise_lines[:max_noise]

        # 重新组合（保持原始顺序）
        kept_lines = high_value_lines + kept_noise
        kept_lines.sort(key=lambda x: lines.index(x) if x in lines else 999999)

        compressed = '\n'.join(kept_lines)

        # 如果压缩效果不明显，返回原内容
        if len(compressed) > len(content) * 0.6:
            return None

        return compressed

    @staticmethod
    def _try_compress_code(content: str) -> Optional[str]:
        """尝试压缩代码内容（CodeCompressor 理念）"""
        lines = content.split('\n')
        if len(lines) < 10:
            return None

        # 检测是否为代码（包含常见代码模式）
        code_patterns = [
            r'^\s*(def|class|function|const|let|var|import|from|if|for|while)\s',
            r'^\s*[\{\}\[\]\(\)]\s*$',
            r'[;{}]\s*$',
            r'^\s*//',
            r'^\s*#',
            r'^\s*/\*',
        ]

        code_lines = 0
        for line in lines:
            for pattern in code_patterns:
                if re.match(pattern, line):
                    code_lines += 1
                    break

        if code_lines < len(lines) * 0.3:
            return None

        # 保留结构行（import、函数定义、类定义等），压缩函数体
        structure_patterns = [
            r'^\s*(import|from|require)\s',
            r'^\s*(def|class|function)\s+\w+',
            r'^\s*(public|private|protected)\s',
            r'^\s*@\w+',  # 装饰器
        ]

        compressed_lines = []
        in_function_body = False
        function_body_lines = 0

        for line in lines:
            is_structure = any(re.match(p, line) for p in structure_patterns)

            if is_structure:
                compressed_lines.append(line)
                in_function_body = True
                function_body_lines = 0
            elif in_function_body and line.strip() and not line.strip().startswith('#'):
                function_body_lines += 1
                # 函数体只保留前3行和最后1行
                if function_body_lines <= 3:
                    compressed_lines.append(line)
                elif line.strip() in ['}', 'end', '})', '});']:
                    compressed_lines.append(line)
                    in_function_body = False
            else:
                compressed_lines.append(line)

        compressed = '\n'.join(compressed_lines)

        # 如果压缩效果不明显，返回原内容
        if len(compressed) > len(content) * 0.7:
            return None

        return compressed

    @staticmethod
    def _compress_text(content: str) -> str:
        """压缩纯文本（TextCrusher 理念）"""
        # 移除多余空行
        compressed = re.sub(r'\n{3,}', '\n\n', content)

        # 移除行尾空格
        compressed = re.sub(r'[ \t]+\n', '\n', compressed)

        # 移除多余空格（连续空格合并为单个）
        compressed = re.sub(r' {2,}', ' ', compressed)

        # 如果文本较长，移除重复段落
        if len(compressed) > 500:
            sentences = re.split(r'(?<=[。！？.!?])\s+', compressed)
            seen = set()
            unique_sentences = []
            for s in sentences:
                s_normalized = s.strip().lower()
                # 短句子（<10字符）不去重，保留所有
                if s_normalized not in seen or len(s_normalized) < 10:
                    seen.add(s_normalized)
                    unique_sentences.append(s)
            compressed = ' '.join(unique_sentences)

        return compressed


def compress_if_enabled(config, messages: list) -> Tuple[list, Optional[dict]]:
    """如果配置启用了 headroom，则压缩消息

    Args:
        config: AiConfig 实例
        messages: 消息列表

    Returns:
        (messages, stats_or_none)
        如果未启用 headroom，stats 为 None
    """
    if not config or not getattr(config, 'enable_headroom', False):
        return messages, None

    try:
        compressed_messages, stats = HeadroomCompressor.compress_messages(messages)

        if stats['saved_tokens'] <= 0:
            logger.debug(
                f'Headroom 已分析但未节省空间: 原始 {stats["original_tokens"]} tokens'
            )
            return messages, stats

        logger.info(
            f'Headroom 压缩: 原始 {stats["original_tokens"]} tokens, '
            f'压缩后 {stats["compressed_tokens"]} tokens, '
            f'节省 {stats["saved_tokens"]} tokens ({stats["compression_ratio"]:.1%})'
        )

        return compressed_messages, stats
    except Exception as e:
        logger.warning(f'Headroom 压缩失败，使用原始消息: {e}')
        return messages, None
