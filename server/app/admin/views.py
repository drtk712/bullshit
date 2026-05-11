"""FastHTML admin UI views and helpers."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import Request
from fasthtml.common import *
from itsdangerous import BadSignature, URLSafeSerializer
from urllib.parse import urlencode

from starlette.responses import HTMLResponse, RedirectResponse

from app.cloudbase.nosql import FEATURE_CONFIG_COLLECTION
from app.cloudbase.storage import get_storage

load_dotenv()

COOKIE_NAME = "bullshit_admin"

TX_TYPE_OPTIONS = [
    ("", "全部"),
    ("grant", "赠送 grant"),
    ("consume", "消耗 consume"),
    ("refund", "退款 refund"),
    ("adjust", "调整 adjust"),
]

TX_REASON_OPTIONS = [
    ("", "全部"),
    ("first_login", "首次登录"),
    ("daily_check_in", "每日签到"),
    ("share_reward", "分享奖励"),
    ("create_feature_job", "生成任务扣分"),
    ("job_failed_refund", "失败退款"),
    ("manual_adjust", "人工调整"),
]

TASK_STATUS_OPTIONS = [
    ("", "全部"),
    ("init", "提交中 init"),
    ("pending", "等待中 pending"),
    ("processing", "生成中 processing"),
    ("completed", "已完成 completed"),
    ("failed", "失败 failed"),
]

FEATURE_CATEGORIES = ("趣味", "人像", "风格化", "创意", "工具", "营销")

BOOL_FILTER_OPTIONS = [
    ("", "全部"),
    ("true", "是"),
    ("false", "否"),
]


def _serializer() -> URLSafeSerializer:
    secret = os.getenv("ADMIN_SESSION_SECRET") or os.getenv("POSTER_SERVER_TOKEN") or ""
    if not secret:
        raise RuntimeError("ADMIN_SESSION_SECRET 或 POSTER_SERVER_TOKEN 未设置")
    return URLSafeSerializer(secret, salt="admin-session")


def _admin_password() -> str:
    return os.getenv("ADMIN_PASSWORD") or os.getenv("POSTER_SERVER_TOKEN") or ""


def _is_authenticated(request: Request) -> bool:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return False
    try:
        return _serializer().loads(token) == "admin"
    except BadSignature:
        return False


def _redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=302)


def _require_auth(request: Request) -> RedirectResponse | None:
    if _is_authenticated(request):
        return None
    return _redirect("/admin/login")


def _page(title: str, *children: Any) -> HTMLResponse:
    doc = Html(
        Head(
            Meta(charset="utf-8"),
            Meta(name="viewport", content="width=device-width, initial-scale=1"),
            Title(title),
            Style(
                """
                :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
                * { box-sizing: border-box; }
                body { margin: 0; background: #f6f7f9; color: #17202a; }
                a { color: #1f5fbf; text-decoration: none; }
                a:hover { text-decoration: underline; }
                .topbar { height: 56px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; background: #111827; color: white; }
                .topbar a { color: white; opacity: .9; }
                .wrap { max-width: 1080px; margin: 0 auto; padding: 28px; }
                .panel { background: white; border: 1px solid #dfe4ea; border-radius: 8px; padding: 22px; box-shadow: 0 1px 2px rgba(16,24,40,.05); }
                .cards { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin-bottom: 18px; }
                .metric { background: white; border: 1px solid #dfe4ea; border-radius: 8px; padding: 16px; }
                .metric strong { display: block; font-size: 26px; margin-top: 4px; }
                .dash-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(320px, .65fr); gap: 16px; }
                .status-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; }
                .status-box { border: 1px solid #dfe4ea; border-radius: 8px; padding: 12px; background: #fbfcfe; }
                .status-box strong { display: block; font-size: 22px; margin-top: 4px; }
                .pill { display: inline-flex; align-items: center; border-radius: 999px; padding: 3px 8px; background: #eef2f7; color: #344054; font-size: 12px; }
                .pill.active { background: #fff7df; color: #7a4d00; }
                .pill.failed { background: #fff1f1; color: #981b1b; }
                .pill.done { background: #eefaf2; color: #166534; }
                .avatar-sm { width: 40px; height: 40px; border-radius: 999px; object-fit: cover; background: #eef2f7; display: inline-flex; align-items: center; justify-content: center; color: #667085; font-weight: 700; }
                .preview-mask { position: fixed; inset: 0; z-index: 80; display: flex; align-items: center; justify-content: center; padding: 32px; background: rgba(15, 23, 42, .56); }
                .preview-modal { width: min(900px, 100%); max-height: calc(100vh - 64px); overflow: auto; border-radius: 8px; background: white; padding: 20px; box-shadow: 0 20px 60px rgba(15, 23, 42, .26); }
                .preview-modal img { display: block; max-width: 100%; max-height: 70vh; margin: 16px auto 0; border-radius: 8px; border: 1px solid #dfe4ea; background: #fff; }
                .stack { display: grid; gap: 16px; }
                .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
                .actions { display: flex; gap: 10px; align-items: center; margin-top: 20px; }
                .muted { color: #667085; font-size: 14px; }
                .banner { border: 1px solid #f0c36d; background: #fff7df; color: #6f4e00; border-radius: 8px; padding: 12px 14px; margin-bottom: 18px; }
                .success { border: 1px solid #9fd7b2; background: #eefaf2; color: #166534; border-radius: 8px; padding: 12px 14px; margin-bottom: 18px; }
                .error { border: 1px solid #f1a8a8; background: #fff1f1; color: #981b1b; border-radius: 8px; padding: 12px 14px; margin-bottom: 18px; }
                .section-title { margin: 24px 0 0; padding-top: 18px; border-top: 1px solid #e6e9ee; font-size: 18px; }
                table { width: 100%; border-collapse: collapse; }
                th, td { text-align: left; padding: 12px 10px; border-bottom: 1px solid #e6e9ee; vertical-align: top; }
                th { color: #667085; font-weight: 600; font-size: 13px; }
                code { background: #f2f4f7; border-radius: 5px; padding: 2px 5px; }
                label { display: grid; gap: 6px; font-size: 13px; color: #4b5563; }
                input, textarea, select { width: 100%; border: 1px solid #cfd6df; border-radius: 7px; padding: 10px 11px; font: inherit; color: #17202a; background: white; }
                textarea { min-height: 116px; resize: vertical; line-height: 1.45; }
                textarea.code { min-height: 180px; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 13px; }
                input[type="checkbox"] { width: auto; }
                .checkline { display: flex; align-items: center; gap: 8px; min-height: 40px; }
                button, .button { border: 0; border-radius: 7px; background: #1f2937; color: white; padding: 10px 14px; font: inherit; cursor: pointer; display: inline-flex; align-items: center; min-height: 40px; }
                .button.secondary { background: #e9edf2; color: #17202a; }
                .danger { background: #b42318; }
                .danger-zone { margin-top: 24px; border-color: #f1a8a8; background: #fffafa; }
                .login { max-width: 420px; margin: 10vh auto 0; }
                @media (max-width: 900px) { .dash-grid, .status-strip { grid-template-columns: 1fr; } }
                @media (max-width: 760px) { .wrap { padding: 18px; } .grid, .cards { grid-template-columns: 1fr; } .topbar { padding: 0 18px; } }
                """
            ),
        ),
        Body(
            Div(
                Strong("Bullshit Admin"),
                Div(A("仪表盘", href="/admin/dashboard"), " · ", A("玩法配置", href="/admin/features"), " · ", A("用户管理", href="/admin/users"), " · ", A("积分流水", href="/admin/transactions"), " · ", A("生成任务", href="/admin/tasks"), " · ", A("云存储", href="/admin/storage"), " · ", A("退出", href="/admin/logout")),
                cls="topbar",
            ),
            Main(Div(*children, cls="wrap")),
        ),
    )
    return HTMLResponse(to_xml(doc))


def _login_page(error: str | None = None) -> HTMLResponse:
    return _page(
        "登录",
        Div(
            H1("登录"),
            P("管理端连接正式数据，请谨慎操作。", cls="muted"),
            Div(error, cls="error") if error else "",
            Form(
                Label("密码", Input(type="password", name="password", autofocus=True)),
                Div(Button("登录", type="submit"), cls="actions"),
                method="post",
                action="/admin/login",
                cls="stack",
            ),
            cls="panel login",
        ),
    )


def _value(doc: dict[str, Any], path: str, default: Any = "") -> Any:
    current: Any = doc
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part, default)
    return current


def _text(doc: dict[str, Any], path: str) -> str:
    value = _value(doc, path, "")
    if isinstance(value, list):
        return "\n".join(str(item) for item in value)
    return "" if value is None else str(value)


def _json_text(doc: dict[str, Any], path: str, default: Any = None) -> str:
    value = _value(doc, path, [] if default is None else default)
    return json.dumps(value, ensure_ascii=False, indent=2)


def _field(
    label: str,
    name: str,
    value: str = "",
    multiline: bool = False,
    code: bool = False,
    readonly: bool = False,
) -> Any:
    if multiline:
        control = Textarea(value, name=name, cls="code" if code else None, readonly=readonly)
    else:
        control = Input(type="text", name=name, value=value, readonly=readonly)
    return Label(label, control)


def _select_field(label: str, name: str, value: str, options: list[tuple[str, str]]) -> Any:
    rendered = [
        Option(option_label, value=option_value, selected=value == option_value)
        for option_value, option_label in options
    ]
    return Label(label, Select(*rendered, name=name))


def _message(kind: str | None) -> str | None:
    return {
        "created": "已新增玩法",
        "saved": "已保存玩法",
        "deleted": "已删除玩法",
        "points_adjusted": "已调整用户积分，并写入积分流水",
        "user_blocked": "已封禁用户",
        "user_unblocked": "已解除用户封禁",
        "user_deleted": "已删除用户",
    }.get(kind or "")


def _status_pill(status: str, label: str | None = None) -> Any:
    cls = "pill"
    if status in {"init", "pending", "processing"}:
        cls += " active"
    if status == "completed":
        cls += " done"
    if status == "failed":
        cls += " failed"
    return Span(label or status or "-", cls=cls)


def _dashboard_page(
    summary: dict[str, Any],
    features_total: int,
    features_enabled: int,
    error: str | None = None,
    queue_stats: dict[str, Any] | None = None,
) -> HTMLResponse:
    task_counts = summary.get("taskCounts", {})
    active_tasks = summary.get("activeTasks", [])
    queue = queue_stats or {}
    active_queue_ids = [str(task_id) for task_id in queue.get("activeTaskIds") or []]
    active_queue_rows = [
        Tr(
            Td(Code(task_id)),
            Td(A("查看", href=f"/admin/tasks?task_id={task_id}", cls="button secondary")),
        )
        for task_id in active_queue_ids
    ]
    active_rows = [
        Tr(
            Td(Code(str(task.get("_id", "")))),
            Td(_status_pill(str(task.get("status") or ""), _task_status_text(task))),
            Td(str(task.get("type") or "-")),
            Td(Code(_mask_openid(task.get("openid")))),
            Td(_fmt_time(task.get("updatedAt") or task.get("createdAt"))),
            Td(A("查看", href=f"/admin/tasks?task_id={task.get('_id', '')}", cls="button secondary")),
        )
        for task in active_tasks
    ]
    return _page(
        "仪表盘",
        Div("仪表盘读取正式 users / feature_configs / point_transactions / feature_jobs。", cls="banner"),
        Div(error, cls="error") if error else "",
        Div(
            Div(Div("用户总数", cls="muted"), Strong(str(summary.get("usersTotal", 0))), cls="metric"),
            Div(Div("资料完成", cls="muted"), Strong(str(summary.get("profileCompleted", 0))), cls="metric"),
            Div(Div("玩法配置", cls="muted"), Strong(f"{features_enabled}/{features_total}"), cls="metric"),
            Div(Div("任务总数", cls="muted"), Strong(str(summary.get("tasksTotal", 0))), cls="metric"),
            cls="cards",
        ),
        Div(
            Div(
                H2("任务状态"),
                Div(
                    Div(Div("提交中", cls="muted"), Strong(str(task_counts.get("init", 0))), cls="status-box"),
                    Div(Div("等待中", cls="muted"), Strong(str(task_counts.get("pending", 0))), cls="status-box"),
                    Div(Div("生成中", cls="muted"), Strong(str(task_counts.get("processing", 0))), cls="status-box"),
                    Div(Div("已完成", cls="muted"), Strong(str(task_counts.get("completed", 0))), cls="status-box"),
                    Div(Div("失败", cls="muted"), Strong(str(task_counts.get("failed", 0))), cls="status-box"),
                    cls="status-strip",
                ),
                cls="panel",
            ),
        ),
        Div(
            H2("服务端队列"),
            P("内存队列状态，仅代表当前服务进程；服务重启后队列会重新开始统计。", cls="muted"),
            Div(
                Div(Div("Worker", cls="muted"), Strong(f"{queue.get('aliveWorkers', 0)}/{queue.get('workerCount', 0)}"), cls="status-box"),
                Div(Div("等待队列", cls="muted"), Strong(str(queue.get("queueSize", 0))), cls="status-box"),
                Div(Div("已排队", cls="muted"), Strong(str(queue.get("queuedTasks", 0))), cls="status-box"),
                Div(Div("处理中", cls="muted"), Strong(str(queue.get("activeTasks", 0))), cls="status-box"),
                cls="status-strip",
            ),
            H3("当前 Worker 任务"),
            Table(
                Thead(Tr(Th("任务 ID"), Th("操作"))),
                Tbody(*active_queue_rows) if active_queue_rows else Tbody(Tr(Td("当前没有 Worker 正在处理任务", colspan="2", cls="muted"))),
            ),
            cls="panel",
        ),
        Div(
            H2("当前正在处理的任务"),
            P("包含 init / pending / processing，按更新时间从旧到新排列。", cls="muted"),
            Table(
                Thead(Tr(Th("任务 ID"), Th("状态"), Th("玩法"), Th("OpenID"), Th("更新时间"), Th("操作"))),
                Tbody(*active_rows) if active_rows else Tbody(Tr(Td("当前没有进行中的任务", colspan="6", cls="muted"))),
            ),
            cls="panel",
        ),
    )


def _features_page(
    features: list[dict[str, Any]],
    error: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    rows = [
        Tr(
            Td(A(str(doc.get("_id", "")), href=f"/admin/features/{doc.get('_id', '')}")),
            Td(str(doc.get("type", ""))),
            Td(str(_value(doc, "public.title", ""))),
            Td("开启" if doc.get("enabled") else "关闭"),
            Td(str(doc.get("order", ""))),
        )
        for doc in features
    ]
    return _page(
        "玩法配置",
        Div(f"正式集合：{FEATURE_CONFIG_COLLECTION}。这里会直接读写线上玩法配置。", cls="banner"),
        Div(message, cls="success") if message else "",
        Div(error, cls="error") if error else "",
        Div(
            Div(
                H1("玩法配置"),
                A("新增玩法", href="/admin/features/new", cls="button"),
                style="display:flex;align-items:center;justify-content:space-between;gap:12px;",
            ),
            P("修改会直接影响小程序读取到的玩法配置。", cls="muted"),
            Table(
                Thead(Tr(Th("文档 ID"), Th("类型"), Th("标题"), Th("状态"), Th("排序"))),
                Tbody(*rows),
            ),
            cls="panel",
        ),
    )


def _edit_page(doc: dict[str, Any], error: str | None = None, is_new: bool = False) -> HTMLResponse:
    doc_id = str(doc.get("_id", ""))
    requirements = _text(doc, "ui.requirements")
    action = "/admin/features" if is_new else f"/admin/features/{doc_id}"
    title = "新增玩法" if is_new else f"编辑：{doc_id}"
    return _page(
        title,
        Div(f"正式集合：{FEATURE_CONFIG_COLLECTION}。保存会直接写入线上玩法配置。", cls="banner"),
        Div(error, cls="error") if error else "",
        Div(
            H1(title),
            Form(
                Div(
                    _field("文档 ID", "_id", doc_id, readonly=not is_new),
                    _field("类型", "type", str(doc.get("type", ""))),
                    _field("排序", "order", str(doc.get("order", ""))),
                    Label("卡片尺寸", Select(Option("normal", value="normal", selected=_text(doc, "public.cardSize") == "normal"), Option("wide", value="wide", selected=_text(doc, "public.cardSize") == "wide"), name="public.cardSize")),
                    Label(Span(Input(type="checkbox", name="enabled", checked=bool(doc.get("enabled"))), " 启用"), cls="checkline"),
                    cls="grid",
                ),
                H2("公开展示", cls="section-title"),
                Div(
                    _field("标题", "public.title", _text(doc, "public.title")),
                    Label(
                        "首页分类",
                        Select(
                            *(
                                Option(category, value=category, selected=_text(doc, "public.category") == category)
                                for category in FEATURE_CATEGORIES
                            ),
                            name="public.category",
                        ),
                    ),
                    _field("首页描述", "public.homeDesc", _text(doc, "public.homeDesc")),
                    _field("上传页标题", "public.uploadTitle", _text(doc, "public.uploadTitle")),
                    _field("预览图云存储 ID", "public.previewImageHD", _text(doc, "public.previewImageHD")),
                    _field("描述", "public.description", _text(doc, "public.description"), multiline=True),
                    cls="grid",
                ),
                H2("UI 渲染", cls="section-title"),
                Div(
                    _field("进度页文案", "ui.progressTitle", _text(doc, "ui.progressTitle")),
                    _field("详情页副标题", "ui.detailSubtitle", _text(doc, "ui.detailSubtitle")),
                    _field("要求（每行一条）", "ui.requirements", requirements, multiline=True),
                    cls="grid",
                ),
                Div(
                    _field("上传要求对象 requirementItems（JSON 数组）", "ui.requirementItems", _json_text(doc, "ui.requirementItems"), multiline=True, code=True),
                    _field("分析维度 analysisItems（JSON 数组）", "ui.analysisItems", _json_text(doc, "ui.analysisItems"), multiline=True, code=True),
                    _field("进度检查 progressChecks（JSON 数组）", "ui.progressChecks", _json_text(doc, "ui.progressChecks"), multiline=True, code=True),
                    _field("标签 tags（JSON 数组）", "ui.tags", _json_text(doc, "ui.tags"), multiline=True, code=True),
                    cls="grid",
                ),
                H2("校验和生成", cls="section-title"),
                Div(
                    _field("验证服务 URL", "validation.serviceUrl", _text(doc, "validation.serviceUrl")),
                    _field("模型", "validation.model", _text(doc, "validation.model")),
                    _field("校验失败提示", "validation.failMessage", _text(doc, "validation.failMessage"), multiline=True),
                    _field("校验提示词", "validation.prompt", _text(doc, "validation.prompt"), multiline=True),
                    _field("生成提示词", "generation.prompt", _text(doc, "generation.prompt"), multiline=True),
                    _field("参数说明", "generation.paramHint", _text(doc, "generation.paramHint"), multiline=True),
                    _field("测试 Poster FileID", "test.posterFileID", _text(doc, "test.posterFileID")),
                    cls="stack",
                ),
                Div(
                    Button("保存", type="submit"),
                    A("返回", href="/admin/features", cls="button secondary"),
                    cls="actions",
                ),
                method="post",
                action=action,
                cls="stack",
            ),
            cls="panel",
        ),
        "" if is_new else _delete_panel(doc_id),
    )


def _delete_panel(doc_id: str) -> Any:
    return Div(
        H2("删除玩法"),
        P("会删除正式集合里的当前文档。请输入文档 ID 后再删除。", cls="muted"),
        Form(
            Input(type="text", name="confirm_delete", placeholder=doc_id),
            Div(Button("删除", type="submit", cls="danger"), cls="actions"),
            method="post",
            action=f"/admin/features/{doc_id}/delete",
        ),
        cls="panel danger-zone",
    )


def _parse_json_array(form: dict[str, Any], name: str) -> list[Any]:
    raw = str(form.get(name, "")).strip()
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} 必须是合法 JSON") from exc
    if not isinstance(value, list):
        raise ValueError(f"{name} 必须是 JSON 数组")
    return value


def _reject_emoji(value: Any, path: str = "") -> None:
    if isinstance(value, str):
        bad = [char for char in value if ord(char) > 0xFFFF]
        if bad:
            raise ValueError(f"{path or '字段'} 包含 CloudBase 不支持的 emoji 字符：{bad[0]}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_emoji(item, f"{path}[{index}]")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_emoji(item, f"{path}.{key}" if path else str(key))


def _require_text(data: dict[str, Any], fields: list[str]) -> None:
    for field in fields:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} 不能为空")


def _form_patch(form: dict[str, Any]) -> dict[str, Any]:
    requirements = [
        line.strip()
        for line in str(form.get("ui.requirements", "")).splitlines()
        if line.strip()
    ]
    order_raw = str(form.get("order", "0")).strip()
    try:
        order = int(order_raw)
    except ValueError as exc:
        raise ValueError("排序必须是整数") from exc

    data = {
        "type": str(form.get("type", "")).strip(),
        "enabled": "enabled" in form,
        "order": order,
        "public.title": str(form.get("public.title", "")).strip(),
        "public.category": str(form.get("public.category", "")).strip(),
        "public.description": str(form.get("public.description", "")).strip(),
        "public.homeDesc": str(form.get("public.homeDesc", "")).strip(),
        "public.uploadTitle": str(form.get("public.uploadTitle", "")).strip(),
        "public.cardSize": str(form.get("public.cardSize", "normal")).strip() or "normal",
        "public.previewImageHD": str(form.get("public.previewImageHD", "")).strip(),
        "ui.progressTitle": str(form.get("ui.progressTitle", "")).strip(),
        "ui.detailSubtitle": str(form.get("ui.detailSubtitle", "")).strip(),
        "ui.requirements": requirements,
        "ui.requirementItems": _parse_json_array(form, "ui.requirementItems"),
        "ui.analysisItems": _parse_json_array(form, "ui.analysisItems"),
        "ui.progressChecks": _parse_json_array(form, "ui.progressChecks"),
        "ui.tags": _parse_json_array(form, "ui.tags"),
        "validation.serviceUrl": str(form.get("validation.serviceUrl", "")).strip(),
        "validation.model": str(form.get("validation.model", "")).strip(),
        "validation.prompt": str(form.get("validation.prompt", "")).strip(),
        "validation.failMessage": str(form.get("validation.failMessage", "")).strip(),
        "generation.prompt": str(form.get("generation.prompt", "")).strip(),
        "generation.paramHint": str(form.get("generation.paramHint", "")).strip(),
        "test.posterFileID": str(form.get("test.posterFileID", "")).strip(),
    }
    _require_text(
        data,
        [
            "type",
            "public.title",
            "public.category",
            "public.description",
            "public.uploadTitle",
            "ui.progressTitle",
            "ui.detailSubtitle",
            "validation.serviceUrl",
            "validation.model",
            "validation.prompt",
            "validation.failMessage",
            "generation.prompt",
        ],
    )
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,31}", data["type"]):
        raise ValueError("type 必须以小写字母开头，只能包含小写字母、数字、连字符、下划线，长度 2-32")
    if data["public.category"] not in FEATURE_CATEGORIES:
        raise ValueError(f"public.category 只能是：{'、'.join(FEATURE_CATEGORIES)}")
    if not data["ui.requirements"]:
        raise ValueError("ui.requirements 至少需要一条")
    if data["public.cardSize"] not in {"normal", "wide"}:
        raise ValueError("public.cardSize 只能是 normal 或 wide")
    _reject_emoji(data)
    return data


def _set_path(doc: dict[str, Any], path: str, value: Any) -> None:
    target = doc
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def _doc_from_patch(doc_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    doc: dict[str, Any] = {"_id": doc_id}
    for key, value in patch.items():
        if "." in key:
            _set_path(doc, key, value)
        else:
            doc[key] = value
    return doc


def _blank_feature() -> dict[str, Any]:
    doc_id = f"test_{uuid4().hex[:12]}"
    now = int(time.time() * 1000)
    return {
        "_id": doc_id,
        "type": "test-feature",
        "enabled": False,
        "order": 9999,
        "public": {
            "title": "新玩法",
            "category": "趣味",
            "description": "仅用于管理后台开发验证",
            "homeDesc": "玩法说明",
            "uploadTitle": "上传测试图片",
            "cardSize": "normal",
            "previewImageHD": "",
        },
        "ui": {
            "progressTitle": "正在生成...",
            "detailSubtitle": "测试详情",
            "requirements": ["清晰图片"],
            "requirementItems": [{"text": "图片清晰"}],
            "analysisItems": [{"title": "测试维度", "items": ["测试项"]}],
            "progressChecks": [{"title": "图片检测", "status": "等待中"}],
            "tags": [{"text": "测试"}],
        },
        "validation": {
            "serviceUrl": "http://36.156.154.98:8010/v1/chat/completions",
            "model": "qwen3.6",
            "prompt": "这张图片是否符合当前玩法？请只回答'是'或'否'。",
            "failMessage": "图片不符合要求，请重新上传",
        },
        "generation": {"prompt": "Generate a test poster based on this image.", "paramHint": ""},
        "test": {"posterFileID": ""},
        "createdAt": now,
    }


def _mask_openid(openid: str | None) -> str:
    value = str(openid or "")
    if len(value) <= 8:
        return value or "-"
    return f"{value[:4]}...{value[-6:]}"


def _fmt_time(timestamp: Any) -> str:
    try:
        value = int(timestamp)
    except (TypeError, ValueError):
        return "-"
    if value <= 0:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(value / 1000))


def _fmt_amount(amount: Any) -> str:
    try:
        value = int(amount)
    except (TypeError, ValueError):
        return "0"
    return f"+{value}" if value > 0 else str(value)


def _reason_text(reason: str | None) -> str:
    return {
        "first_login": "首次登录赠送",
        "create_feature_job": "生成消耗",
        "job_failed_refund": "失败退款",
        "manual_adjust": "人工调整",
        "daily_check_in": "每日签到",
        "share_reward": "分享奖励",
    }.get(str(reason or ""), str(reason or "-"))


def _task_status_text(task: dict[str, Any]) -> str:
    status = str(task.get("status") or "")
    if status == "failed" and task.get("pointsRefunded"):
        return "失败已退款"
    return {
        "init": "提交中",
        "pending": "等待中",
        "processing": "生成中",
        "completed": "已完成",
        "failed": "失败",
    }.get(status, status or "-")


def _users_page(
    users: list[dict[str, Any]],
    total: int,
    filters: dict[str, Any],
    error: str | None = None,
) -> HTMLResponse:
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    rows = [
        Tr(
            Td(A(str(user.get("_id", "")), href=f"/admin/users/{user.get('_id', '')}")),
            Td(_avatar_node(user)),
            Td(str(user.get("nickName") or "-")),
            Td(Code(_mask_openid(user.get("openid")))),
            Td(str(user.get("points", 0))),
            Td(str(user.get("totalGrantedPoints", 0))),
            Td(str(user.get("totalUsedPoints", 0))),
            Td(str(user.get("totalRefundedPoints", 0))),
            Td(_fmt_time(user.get("lastLoginAt"))),
            Td(_fmt_time(user.get("createdAt"))),
        )
        for user in users
    ]
    return _page(
        "用户管理",
        Div("用户管理当前为只读模式，会读取生产 users / point_transactions / feature_jobs，但不会修改积分。", cls="banner"),
        Div(error, cls="error") if error else "",
        Div(
            H1("用户管理"),
            Form(
                Div(
                    _field("OpenID", "openid", str(filters.get("openid") or "")),
                    _field("昵称", "nick_name", str(filters.get("nick_name") or "")),
                    _field("每页数量", "page_size", str(page_size)),
                    cls="grid",
                ),
                Div(Button("筛选", type="submit"), A("清空", href="/admin/users", cls="button secondary"), cls="actions"),
                method="get",
                action="/admin/users",
                cls="stack",
            ),
            P(f"共匹配 {total} 条，当前第 {page} 页。", cls="muted"),
            Table(
                Thead(Tr(Th("用户 ID"), Th("头像"), Th("昵称"), Th("OpenID"), Th("积分"), Th("累计赠送"), Th("累计消耗"), Th("累计退款"), Th("最近登录"), Th("注册时间"))),
                Tbody(*rows),
            ),
            Div(
                _page_link("/admin/users", filters, max(1, page - 1), "上一页", page <= 1),
                _page_link("/admin/users", filters, page + 1, "下一页", page * page_size >= total),
                cls="actions",
            ),
            cls="panel",
        ),
    )


def _user_detail_page(
    user: dict[str, Any],
    error: str | None = None,
    message: str | None = None,
) -> HTMLResponse:
    user_id = str(user.get("_id", ""))
    openid = str(user.get("openid", ""))
    user_status = str(user.get("status") or "active")
    return _page(
        "用户详情",
        Div("用户详情会读取生产 users / point_transactions / feature_jobs；积分调整会写入余额和流水。", cls="banner"),
        Div(message, cls="success") if message else "",
        Div(error, cls="error") if error else "",
        Div(
            A("返回用户列表", href="/admin/users", cls="button secondary"),
            cls="actions",
            style="margin-top:0;margin-bottom:16px;",
        ),
        Div(
            Div(Div("当前积分", cls="muted"), Strong(str(user.get("points", 0))), cls="metric"),
            Div(Div("累计赠送", cls="muted"), Strong(str(user.get("totalGrantedPoints", 0))), cls="metric"),
            Div(Div("累计消耗", cls="muted"), Strong(str(user.get("totalUsedPoints", 0))), cls="metric"),
            Div(Div("累计退款", cls="muted"), Strong(str(user.get("totalRefundedPoints", 0))), cls="metric"),
            cls="cards",
        ),
        Div(
            H1(f"用户：{user_id}"),
            Div(
                P("昵称：", str(user.get("nickName") or "-")),
                P("头像：", _avatar_node(user), " ", Code(str(user.get("avatarFileID") or "-"))),
                P("OpenID：", Code(str(user.get("openid", "-")))),
                P("状态：", _user_status_pill(user)),
                P("封禁原因：", str(user.get("blockedReason") or "-")) if user_status == "blocked" else "",
                P("封禁时间：", _fmt_time(user.get("blockedAt"))) if user_status == "blocked" else "",
                P("资料完成：", "是" if user.get("profileCompleted") else "否"),
                P("资料完成时间：", _fmt_time(user.get("profileCompletedAt"))),
                P("最近登录：", _fmt_time(user.get("lastLoginAt"))),
                P("注册时间：", _fmt_time(user.get("createdAt"))),
                P("最近签到：", _fmt_time(user.get("lastCheckInAt"))),
                P("连续签到：", str(user.get("checkInDays", 0))),
            ),
            cls="panel",
        ),
        Div(
            H2("关联数据"),
            Div(
                A("查看该用户积分流水", href=f"/admin/transactions?openid={openid}", cls="button"),
                A("查看该用户生成任务", href=f"/admin/tasks?openid={openid}", cls="button secondary"),
                cls="actions",
            ),
            cls="panel",
        ),
        _points_adjust_panel(user_id),
        _user_moderation_panel(user),
    )


def _user_status_pill(user: dict[str, Any]) -> Any:
    status = str(user.get("status") or "active")
    if status == "blocked":
        return Span("已封禁", cls="pill failed")
    return Span("正常", cls="pill done")


def _avatar_node(user: dict[str, Any]) -> Any:
    avatar = str(user.get("avatarFileID") or "")
    if avatar:
        return Img(src=_storage_url(avatar) or avatar, cls="avatar-sm")
    nick = str(user.get("nickName") or "?")
    return Span(nick[:1], cls="avatar-sm")


def _storage_url(cloud_object_id: Any) -> str:
    value = str(cloud_object_id or "")
    if not value.startswith("cloud://"):
        return value
    return get_storage().get_download_url(value)


def _task_file_button(task_id: Any, field: str, label: str, filters: dict[str, Any]) -> Any:
    if not task_id:
        return "-"
    hidden_fields = [
        Input(type="hidden", name=key, value=str(value))
        for key, value in filters.items()
        if value not in ("", None)
    ]
    return Form(
        *hidden_fields,
        Input(type="hidden", name="preview_task_id", value=str(task_id)),
        Input(type="hidden", name="field", value=field),
        Button(label, type="submit", cls="button secondary"),
        method="post",
        action="/admin/tasks/preview",
    )


def _points_adjust_panel(user_id: str) -> Any:
    return Div(
        H2("积分调整"),
        P("会同时更新用户余额并写入 point_transactions，原因会显示在积分流水中。", cls="muted"),
        Form(
            Div(
                _field("调整数量（正数增加，负数扣减）", "amount", "1"),
                _field("调整原因", "reason", "manual_adjust"),
                _field("确认用户 ID", "confirm_user_id", ""),
                _field("操作人", "operator", "admin"),
                cls="grid",
            ),
            Div(Button("提交调整", type="submit"), cls="actions"),
            method="post",
            action=f"/admin/users/{user_id}/points",
        ),
        cls="panel danger-zone",
    )


def _user_moderation_panel(user: dict[str, Any]) -> Any:
    user_id = str(user.get("_id", ""))
    is_blocked = str(user.get("status") or "active") == "blocked"
    return Div(
        H2("用户状态"),
        P("封禁会阻止该用户继续使用登录、积分奖励和图片处理入口；删除会同时删除用户、积分流水和处理记录。", cls="muted"),
        Form(
            Div(
                _field("封禁原因", "reason", str(user.get("blockedReason") or "违规使用")),
                _field("操作人", "operator", "admin"),
                cls="grid",
            ),
            Div(Button("解除封禁" if is_blocked else "封禁用户", type="submit", cls="danger" if not is_blocked else None), cls="actions"),
            method="post",
            action=f"/admin/users/{user_id}/{'unblock' if is_blocked else 'block'}",
        ),
        H3("删除用户"),
        P("危险操作：删除后用户再次进入小程序会被当作新用户重新创建，历史积分流水和处理记录也会被删除。请输入用户 ID 确认。", cls="muted"),
        Form(
            Input(type="text", name="confirm_user_id", placeholder=user_id),
            Div(Button("删除用户", type="submit", cls="danger"), cls="actions"),
            method="post",
            action=f"/admin/users/{user_id}/delete",
        ),
        cls="panel danger-zone",
    )


def _page_link(base_path: str, params: dict[str, Any], page: int, label: str, disabled: bool = False) -> Any:
    if disabled:
        return Span(label, cls="button secondary", style="opacity:.45;cursor:not-allowed;")
    next_params = {key: value for key, value in params.items() if value not in ("", None)}
    next_params["page"] = page
    return A(label, href=f"{base_path}?{urlencode(next_params)}", cls="button secondary")


def _transactions_page(
    transactions: list[dict[str, Any]],
    total: int,
    filters: dict[str, Any],
    error: str | None = None,
) -> HTMLResponse:
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    rows = [
        Tr(
            Td(_fmt_time(item.get("createdAt"))),
            Td(Code(_mask_openid(item.get("openid")))),
            Td(str(item.get("type", ""))),
            Td(_reason_text(item.get("reason"))),
            Td(_fmt_amount(item.get("amount"))),
            Td(str(item.get("balanceAfter", 0))),
            Td(Code(str(item.get("taskId") or "-"))),
        )
        for item in transactions
    ]
    return _page(
        "积分流水",
        Div("积分流水读取生产 point_transactions，当前页只提供查询筛选。", cls="banner"),
        Div(error, cls="error") if error else "",
        Div(
            H1("积分流水"),
            Form(
                Div(
                    _field("OpenID", "openid", str(filters.get("openid") or "")),
                    _field("任务 ID", "task_id", str(filters.get("task_id") or "")),
                    _select_field("原因 reason", "reason", str(filters.get("reason") or ""), TX_REASON_OPTIONS),
                    _select_field("类型 type", "tx_type", str(filters.get("tx_type") or ""), TX_TYPE_OPTIONS),
                    _field("每页数量", "page_size", str(page_size)),
                    cls="grid",
                ),
                Div(Button("筛选", type="submit"), A("清空", href="/admin/transactions", cls="button secondary"), cls="actions"),
                method="get",
                action="/admin/transactions",
                cls="stack",
            ),
            cls="panel",
        ),
        Div(
            P(f"共匹配 {total} 条，当前第 {page} 页。", cls="muted"),
            Table(
                Thead(Tr(Th("时间"), Th("OpenID"), Th("类型"), Th("原因"), Th("变动"), Th("变动后余额"), Th("任务 ID"))),
                Tbody(*rows),
            ),
            Div(
                _page_link("/admin/transactions", filters, max(1, page - 1), "上一页", page <= 1),
                _page_link("/admin/transactions", filters, page + 1, "下一页", page * page_size >= total),
                cls="actions",
            ),
            cls="panel",
        ),
    )


def _tasks_page(
    tasks: list[dict[str, Any]],
    total: int,
    filters: dict[str, Any],
    error: str | None = None,
    preview: dict[str, Any] | None = None,
) -> HTMLResponse:
    page = int(filters.get("page") or 1)
    page_size = int(filters.get("page_size") or 20)
    rows = [
        Tr(
            Td(Code(str(task.get("_id", "")))),
            Td(Code(_mask_openid(task.get("openid")))),
            Td(str(task.get("type", ""))),
            Td(_task_status_text(task)),
            Td(_task_file_button(task.get("_id"), "fileID", "查看", filters)),
            Td(_task_file_button(task.get("_id"), "posterFileID", "查看", filters) if task.get("posterFileID") else "-"),
            Td(str(task.get("pointsCost", 0))),
            Td("是" if task.get("pointsConsumed") else "否"),
            Td("是" if task.get("pointsRefunded") else "否"),
            Td(_fmt_time(task.get("createdAt"))),
        )
        for task in tasks
    ]
    return _page(
        "生成任务",
        Div("生成任务读取生产 feature_jobs，当前页只提供查询筛选。", cls="banner"),
        Div(error, cls="error") if error else "",
        _tasks_preview_modal(preview, filters) if preview else "",
        Div(
            H1("生成任务"),
            Form(
                Div(
                    _field("OpenID", "openid", str(filters.get("openid") or "")),
                    _field("任务 ID", "task_id", str(filters.get("task_id") or "")),
                    _field("玩法 type", "feature_type", str(filters.get("feature_type") or "")),
                    _select_field("状态 status", "status", str(filters.get("status") or ""), TASK_STATUS_OPTIONS),
                    _select_field("已扣分", "points_consumed", str(filters.get("points_consumed") or ""), BOOL_FILTER_OPTIONS),
                    _select_field("已退款", "points_refunded", str(filters.get("points_refunded") or ""), BOOL_FILTER_OPTIONS),
                    _field("每页数量", "page_size", str(page_size)),
                    cls="grid",
                ),
                Div(Button("筛选", type="submit"), A("清空", href="/admin/tasks", cls="button secondary"), cls="actions"),
                method="get",
                action="/admin/tasks",
                cls="stack",
            ),
            cls="panel",
        ),
        Div(
            P(f"共匹配 {total} 条，当前第 {page} 页。", cls="muted"),
            Table(
                Thead(Tr(Th("任务 ID"), Th("OpenID"), Th("玩法"), Th("状态"), Th("原图"), Th("海报"), Th("积分成本"), Th("已扣分"), Th("已退款"), Th("创建时间"))),
                Tbody(*rows),
            ),
            Div(
                _page_link("/admin/tasks", filters, max(1, page - 1), "上一页", page <= 1),
                _page_link("/admin/tasks", filters, page + 1, "下一页", page * page_size >= total),
                cls="actions",
            ),
            cls="panel",
        ),
    )


def _tasks_preview_modal(preview: dict[str, Any], filters: dict[str, Any]) -> Any:
    close_params = {key: value for key, value in filters.items() if value not in ("", None)}
    close_href = f"/admin/tasks?{urlencode(close_params)}" if close_params else "/admin/tasks"
    return Div(
        Div(
            Div(
                H2("图片预览"),
                P("任务 ID：", Code(str(preview.get("task_id", "")))),
                P("字段：", Code(str(preview.get("field", "")))),
                P("Cloud Object ID：", Code(str(preview.get("file_id", "")))),
                Div(
                    A("点击下载", href=str(preview.get("url", "")), target="_blank", cls="button") if preview.get("url") else "",
                    A("关闭", href=close_href, cls="button secondary"),
                    cls="actions",
                ),
            ),
            Img(src=str(preview.get("url", ""))) if preview.get("url") else Div("未获取到图片链接", cls="error"),
            cls="preview-modal",
        ),
        cls="preview-mask",
    )


def _storage_page(
    cloud_object_id: str = "",
    object_id: str = "",
    download_info: list[dict[str, Any]] | None = None,
    upload_info: list[dict[str, Any]] | None = None,
    composed_preview: dict[str, Any] | None = None,
    error: str | None = None,
) -> HTMLResponse:
    download_rows = [
        Tr(
            Td(Code(str(item.get("cloudObjectId", "")))),
            Td(A("打开", href=str(item.get("downloadUrl") or item.get("downloadUrlEncoded") or ""), target="_blank") if (item.get("downloadUrl") or item.get("downloadUrlEncoded")) else "-"),
        )
        for item in (download_info or [])
    ]
    upload_rows = [
        Tr(
            Td(Code(str(item.get("objectId", "")))),
            Td(Code(str(item.get("cloudObjectId", "")))),
            Td(A("下载地址", href=str(item.get("downloadUrl") or ""), target="_blank") if item.get("downloadUrl") else "-"),
        )
        for item in (upload_info or [])
    ]
    return _page(
        "云存储",
        Div("云存储工具页支持获取授权信息，也支持生成玩法预览图并上传到云存储。", cls="banner"),
        Div(error, cls="error") if error else "",
        Div(
            H1("云存储"),
            Form(
                _field("Cloud Object ID（cloud://...）", "cloud_object_id", cloud_object_id),
                Div(Button("获取下载链接", type="submit"), cls="actions"),
                method="post",
                action="/admin/storage/download-info",
                cls="stack",
            ),
            cls="panel",
        ),
        Div(
            H2("下载信息"),
            Table(Thead(Tr(Th("Cloud Object ID"), Th("下载链接"))), Tbody(*download_rows)),
            cls="panel",
        ) if download_info is not None else "",
        Div(
            H2("上传授权"),
            Form(
                _field("对象路径（例如 user-avatars/demo.jpg）", "object_id", object_id),
                Div(Button("获取上传授权", type="submit"), cls="actions"),
                method="post",
                action="/admin/storage/upload-info",
                cls="stack",
            ),
            cls="panel",
        ),
        Div(
            H2("上传信息"),
            P("完整授权响应包含敏感临时 token，当前页面只展示对象 ID 和下载地址。", cls="muted"),
            Table(Thead(Tr(Th("Object ID"), Th("Cloud Object ID"), Th("下载地址"))), Tbody(*upload_rows)),
            cls="panel",
        ) if upload_info is not None else "",
        Div(
            H2("玩法预览图合成"),
            P("上传原图和生成后的图片，系统会把原图缩小后叠到生成图右上角，并上传为 JPG。", cls="muted"),
            Form(
                Label("原图", Input(type="file", name="original_image", accept="image/*", required=True)),
                Label("生成后的图片", Input(type="file", name="generated_image", accept="image/*", required=True)),
                _field("保存路径", "object_id", object_id or f"preview-image/feature-preview-{uuid4().hex[:8]}.jpg"),
                Div(Button("合成并上传", type="submit"), cls="actions"),
                method="post",
                action="/admin/storage/compose-preview",
                enctype="multipart/form-data",
                cls="stack",
            ),
            cls="panel",
        ),
        _composed_preview_result(composed_preview) if composed_preview else "",
    )


def _composed_preview_result(composed_preview: dict[str, Any]) -> Any:
    cloud_object_id = str(composed_preview.get("cloud_object_id", ""))
    download_url = str(composed_preview.get("download_url", ""))
    return Div(
        H2("合成结果"),
        P("Cloud Object ID：", Code(cloud_object_id)),
        P("文件大小：", str(composed_preview.get("size", 0)), " bytes"),
        Div(
            A("打开预览", href=download_url, target="_blank", cls="button") if download_url else "",
            cls="actions",
        ),
        Img(src=download_url, style="max-width:360px;border-radius:8px;border:1px solid #dfe4ea;") if download_url else "",
        cls="panel",
    )
