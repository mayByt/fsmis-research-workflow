"""Classify Zotero transport failures without attempting to change host permissions."""
from __future__ import annotations
import errno
import socket
from urllib.error import HTTPError, URLError


class LocalAPIError(Exception):
    def __init__(self, endpoint: str, cause: Exception):
        self.payload = describe_failure(endpoint, cause)
        super().__init__(self.payload['error'])


def describe_failure(endpoint: str, exc: Exception) -> dict:
    result = {'state': 'STOPPED', 'error': str(exc), 'endpoint': endpoint,
              'error_code': 'ZOTERO_API_UNREACHABLE', 'retry_with_permission': False}
    if isinstance(exc, HTTPError):
        result['http_status'] = exc.code
        if exc.code == 403:
            result.update(error_code='ZOTERO_API_FORBIDDEN', next_action='已收到 Zotero HTTP 403；检查 Zotero 高级设置中的本机通信选项。')
        elif exc.code == 404:
            result.update(error_code='ZOTERO_API_NOT_FOUND', next_action='已收到 HTTP 404；检查 API 路径和 Zotero 条目 Key。')
        else:
            result.update(error_code='ZOTERO_API_HTTP_ERROR', next_action='已连接服务；按 HTTP 状态检查 Zotero 服务或请求，不将其视为沙箱权限错误。')
        return result
    reason = exc.reason if isinstance(exc, URLError) else exc
    if isinstance(reason, OSError) and reason.errno in {errno.EPERM, errno.EACCES}:
        result.update(error_code='LOCAL_API_PERMISSION_DENIED', retry_with_permission=True,
                      next_action='连接在收到 HTTP 响应前被宿主沙箱或系统权限拒绝。由 Codex 使用当前环境允许的审批机制，对同一命令请求本机 API 访问授权并重试一次；不要只在原沙箱内重复。审批被拒绝或不提供审批机制时停止并说明。脚本不会自行提权或修改权限配置。')
    elif isinstance(reason, (TimeoutError, socket.timeout)) or (isinstance(reason, OSError) and reason.errno == errno.ETIMEDOUT):
        result.update(error_code='ZOTERO_API_TIMEOUT', next_action='连接超时；检查 Zotero 是否响应、API 地址和本机网络策略。超时本身不能证明是权限拦截。')
    elif isinstance(reason, OSError) and (reason.errno == errno.ECONNREFUSED or getattr(reason, 'winerror', None) == 10061):
        result.update(error_code='ZOTERO_API_CONNECTION_REFUSED', next_action='本机端口拒绝连接；确认 Zotero 已运行、Local API 已启用且端口正确。')
    else:
        result['next_action'] = '检查原始网络错误、Zotero 运行状态与 API 地址；不要仅凭连接失败断言 Zotero 设置错误。'
    return result
