"""系统可配置环境变量定义清单。

每个 SettingDef 描述一项可通过管理员界面修改的环境变量：
- key: 环境变量名（与 Settings 类字段名一致）
- label: 中文显示名
- group: 分组
- value_type: 值类型 string/int/float/bool/json
- default: 默认值（与 app.core.config.Settings 中保持一致）
- description: 说明文字
- is_sensitive: 是否敏感（前端脱敏显示，仅提示是否已设置）
- is_readonly: 是否只读（不允许通过界面修改）
- requires_restart: 修改后是否需要重启服务才生效
- sort_order: 排序

写入 .env 文件时，根据 value_type 转换为字符串。
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SettingDef:
    key: str
    label: str
    group: str
    value_type: str            # string/int/float/bool/json
    default: Any
    description: str = ""
    is_sensitive: bool = False
    is_readonly: bool = False
    requires_restart: bool = True
    sort_order: int = 0


# 默认值与 app/core/config.py 中 Settings 保持一致
_SETTING_DEFS = [
    # 服务运行
    SettingDef(
        key="PORT",
        label="服务端口",
        group="服务运行",
        value_type="int",
        default=8000,
        description="后端服务监听端口（局域网用户通过 http://<服务端IP>:<端口> 访问）",
        requires_restart=True,
        sort_order=1,
    ),
    SettingDef(
        key="HOST",
        label="绑定地址",
        group="服务运行",
        value_type="string",
        default="0.0.0.0",
        description="后端服务绑定网卡地址。0.0.0.0 = 监听所有网卡(局域网可访问)；127.0.0.1 = 仅本机访问",
        requires_restart=True,
        sort_order=2,
    ),
    # 安全
    SettingDef(
        key="ACCESS_TOKEN_EXPIRE_MINUTES",
        label="登录Token有效期(分钟)",
        group="安全",
        value_type="int",
        default=60 * 24 * 7,
        description="登录会话保持时长，超时后需重新登录。默认 10080 分钟(7天)",
        requires_restart=True,
        sort_order=3,
    ),
    SettingDef(
        key="SECRET_KEY",
        label="JWT签名密钥",
        group="安全",
        value_type="string",
        default="change-me-in-production-please-use-a-long-random-string",
        description="用于签发登录Token的密钥。重新生成后所有现有登录会立即失效，需重新登录",
        is_sensitive=True,
        requires_restart=True,
        sort_order=4,
    ),
    SettingDef(
        key="BACKEND_CORS_ORIGINS",
        label="允许跨域来源",
        group="安全",
        value_type="json",
        default=["http://localhost:5173", "http://localhost:8080"],
        description="允许的前端来源列表(JSON数组)。开发模式下需配置 vite dev server 地址；生产模式下后端托管前端可留空",
        requires_restart=True,
        sort_order=5,
    ),
    # 数据
    SettingDef(
        key="SQLALCHEMY_DATABASE_URI",
        label="数据库连接",
        group="数据",
        value_type="string",
        default="sqlite:///./data/app.db",
        description="数据库连接字符串。修改需谨慎，错误的值会导致服务无法启动",
        is_readonly=True,
        requires_restart=True,
        sort_order=6,
    ),
]


# 去重保序
SETTING_DEFS: list[SettingDef] = []
_seen = set()
for _d in _SETTING_DEFS:
    if _d.key in _seen:
        continue
    _seen.add(_d.key)
    SETTING_DEFS.append(_d)

SETTING_BY_KEY: dict[str, SettingDef] = {d.key: d for d in SETTING_DEFS}


def all_setting_keys() -> list[str]:
    return [d.key for d in SETTING_DEFS]
