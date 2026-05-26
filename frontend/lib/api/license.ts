// License Key 授权 API
import { BASE_URL } from "./base";

export interface LicenseStatus {
  license_key: string;
  status: string;  // valid / expired / invalid / ""
  email: string;
  plan: string;    // lifetime / yearly
  validated_at: string;
  is_pro: boolean;
}

export interface LicenseValidateResult {
  success: boolean;
  status: string;
  email?: string;
  plan?: string;
  product_name?: string;
  message: string;
  error?: string;
}

export async function fetchLicenseStatus(): Promise<LicenseStatus> {
  const res = await fetch(`${BASE_URL}/config/license`);
  if (!res.ok) throw new Error("获取授权状态失败");
  return res.json();
}

export async function validateLicenseKey(licenseKey: string): Promise<LicenseValidateResult> {
  const res = await fetch(`${BASE_URL}/config/license/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ license_key: licenseKey }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw detail.detail || detail;
  }
  return res.json();
}

export async function clearLicense(): Promise<{ success: boolean; message: string }> {
  const res = await fetch(`${BASE_URL}/config/license/clear`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("清除授权失败");
  return res.json();
}
