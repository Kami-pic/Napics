"""License Key 验证服务 — 对接外部授权平台。

验证流程：
1. 用户在设置页填入 License Key
2. 后端调用验证 API
3. 验证通过 → 保存状态到 config.json → 解锁扩展插件源
4. 下载插件后本地运行，不再验证（离线友好）
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict

import requests
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# LemonSqueezy License API 端点
LEMON_VALIDATE_URL = "https://api.lemonsqueezy.com/v1/licenses/validate"
LEMON_ACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/activate"
LEMON_DEACTIVATE_URL = "https://api.lemonsqueezy.com/v1/licenses/deactivate"


class LicenseInfo(BaseModel):
    """License 验证结果"""
    valid: bool = False
    status: str = ""          # valid / expired / invalid / disabled
    email: str = ""           # 购买者邮箱
    plan: str = ""            # lifetime / yearly（从 variant_name 推断）
    product_name: str = ""    # 产品名称
    expires_at: str = ""      # 过期时间
    error: str = ""           # 错误信息


def validate_license_key(license_key: str, instance_name: str = "napics") -> LicenseInfo:
    """验证 License Key 是否有效。

    参数：
        license_key: 用户填入的 License Key
        instance_name: 实例标识（用于激活，默认 "napics"）

    返回：
        LicenseInfo 包含验证结果
    """
    if not license_key or not license_key.strip():
        return LicenseInfo(valid=False, status="invalid", error="License Key 不能为空")

    key = license_key.strip()

    try:
        # 调用 LemonSqueezy validate API
        resp = requests.post(
            LEMON_VALIDATE_URL,
            data={"license_key": key, "instance_name": instance_name},
            headers={"Accept": "application/json"},
            timeout=15,
        )

        if resp.status_code == 404:
            return LicenseInfo(valid=False, status="invalid", error="License Key 无效")

        data = resp.json()

        # 解析响应
        valid = data.get("valid", False)
        error_msg = data.get("error", "")
        license_key_data = data.get("license_key", {})
        meta = data.get("meta", {})

        status = license_key_data.get("status", "")
        email = license_key_data.get("user_email", "")
        expires_at = license_key_data.get("expires_at", "")
        product_name = meta.get("product_name", "")
        variant_name = meta.get("variant_name", "")

        # 推断计划类型
        plan = ""
        if variant_name:
            vn_lower = variant_name.lower()
            if "lifetime" in vn_lower or "终身" in vn_lower:
                plan = "lifetime"
            elif "year" in vn_lower or "年" in vn_lower:
                plan = "yearly"
            else:
                plan = variant_name

        # 状态映射
        if valid:
            final_status = "valid"
        elif status == "expired":
            final_status = "expired"
        elif status == "disabled":
            final_status = "disabled"
        else:
            final_status = "invalid"

        return LicenseInfo(
            valid=valid,
            status=final_status,
            email=email,
            plan=plan,
            product_name=product_name,
            expires_at=expires_at,
            error=error_msg if not valid else "",
        )

    except requests.Timeout:
        logger.warning("[License] 验证超时")
        return LicenseInfo(valid=False, status="", error="验证超时，请检查网络连接")
    except requests.RequestException as e:
        logger.error(f"[License] 网络请求失败: {e}")
        return LicenseInfo(valid=False, status="", error=f"网络请求失败: {str(e)}")
    except Exception as e:
        logger.error(f"[License] 验证异常: {e}")
        return LicenseInfo(valid=False, status="", error=f"验证失败: {str(e)}")


def activate_license_key(license_key: str, instance_name: str = "napics") -> LicenseInfo:
    """激活 License Key（首次使用时调用）。

    激活会将此实例绑定到 License Key，消耗一个激活名额。
    """
    if not license_key or not license_key.strip():
        return LicenseInfo(valid=False, status="invalid", error="License Key 不能为空")

    key = license_key.strip()

    try:
        resp = requests.post(
            LEMON_ACTIVATE_URL,
            data={"license_key": key, "instance_name": instance_name},
            headers={"Accept": "application/json"},
            timeout=15,
        )

        data = resp.json()
        activated = data.get("activated", False)
        error_msg = data.get("error", "")

        if activated:
            # 激活成功，再验证一次获取完整信息
            return validate_license_key(key, instance_name)
        else:
            return LicenseInfo(valid=False, status="invalid", error=error_msg or "激活失败")

    except requests.Timeout:
        return LicenseInfo(valid=False, status="", error="激活超时，请检查网络连接")
    except requests.RequestException as e:
        return LicenseInfo(valid=False, status="", error=f"网络请求失败: {str(e)}")
    except Exception as e:
        return LicenseInfo(valid=False, status="", error=f"激活失败: {str(e)}")


def save_license_to_config(config_manager: Any, info: LicenseInfo, key: str) -> None:
    """将验证结果保存到配置文件"""
    conf = config_manager.config.model_copy()
    conf.license_key = key
    conf.license_status = info.status
    conf.license_email = info.email
    conf.license_plan = info.plan
    conf.license_validated_at = datetime.now(timezone.utc).isoformat()
    config_manager.save(conf)
    logger.info(f"[License] 保存授权状态: status={info.status} plan={info.plan} email={info.email}")


def clear_license_from_config(config_manager: Any) -> None:
    """清除授权信息"""
    conf = config_manager.config.model_copy()
    conf.license_key = ""
    conf.license_status = ""
    conf.license_email = ""
    conf.license_plan = ""
    conf.license_validated_at = ""
    config_manager.save(conf)
    logger.info("[License] 已清除授权信息")


def is_pro_licensed(config_manager: Any) -> bool:
    """检查当前是否有有效的 Pro 授权（本地检查，不联网）"""
    conf = config_manager.config
    return conf.license_status == "valid" and bool(conf.license_key)
