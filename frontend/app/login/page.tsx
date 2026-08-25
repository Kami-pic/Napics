import { Suspense } from "react";

import LoginForm from "@/components/auth/LoginForm";

// 桌面与移动端共用同一个登录页：门在后端，两边都得过。
export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
