// 锁定登录页行为：未启用时不拦人、密码错误不跳转、next 参数不能变成跳转中转站。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import LoginForm from "@/components/auth/LoginForm";

const { mockRouter, searchParamsRef } = vi.hoisted(() => ({
  mockRouter: { replace: vi.fn(), push: vi.fn() },
  searchParamsRef: { value: new URLSearchParams() },
}));
vi.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  useSearchParams: () => searchParamsRef.value,
}));

const { mockApi } = vi.hoisted(() => ({
  mockApi: { getAuthStatus: vi.fn(), login: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ api: mockApi }));

beforeEach(() => {
  mockRouter.replace.mockReset();
  mockApi.getAuthStatus.mockReset();
  mockApi.login.mockReset();
  searchParamsRef.value = new URLSearchParams();
  mockApi.getAuthStatus.mockResolvedValue({ enabled: true, authenticated: false });
  mockApi.login.mockResolvedValue({ ok: true });
});

describe("登录页", () => {
  it("没启用访问密码时直接放人进去，不卡在登录页", async () => {
    mockApi.getAuthStatus.mockResolvedValue({ enabled: false, authenticated: true });
    render(<LoginForm />);
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/"));
  });

  it("已登录时也直接跳走", async () => {
    mockApi.getAuthStatus.mockResolvedValue({ enabled: true, authenticated: true });
    render(<LoginForm />);
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/"));
  });

  it("未登录时显示密码输入框", async () => {
    render(<LoginForm />);
    await waitFor(() => expect(screen.getByLabelText("访问密码")).toBeInTheDocument());
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  it("登录成功后跳回原地址", async () => {
    searchParamsRef.value = new URLSearchParams("next=/m/search%3Fq%3Dx");
    render(<LoginForm />);
    await waitFor(() => expect(screen.getByLabelText("访问密码")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("访问密码"), { target: { value: "letmein" } });
    fireEvent.click(screen.getByRole("button", { name: "进入" }));

    await waitFor(() => expect(mockApi.login).toHaveBeenCalledWith("letmein"));
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/m/search?q=x"));
  });

  it("密码错误时显示原因，留在原地不跳转", async () => {
    mockApi.login.mockResolvedValue({ ok: false, error: "密码错误" });
    render(<LoginForm />);
    await waitFor(() => expect(screen.getByLabelText("访问密码")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("访问密码"), { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: "进入" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("密码错误"));
    expect(mockRouter.replace).not.toHaveBeenCalled();
    // 失败后清空输入，避免用户以为还留着
    expect(screen.getByLabelText("访问密码")).toHaveValue("");
  });

  it("空密码时按钮不可点", async () => {
    render(<LoginForm />);
    await waitFor(() => expect(screen.getByRole("button", { name: "进入" })).toBeDisabled());
  });

  it.each([
    ["https://evil.example.com/steal", "外站绝对地址"],
    ["//evil.example.com/steal", "协议相对地址"],
    ["javascript:alert(1)", "javascript 伪协议"],
  ])("next 参数是 %s（%s）时退回首页，不做开放跳转", async (raw) => {
    searchParamsRef.value = new URLSearchParams();
    searchParamsRef.value.set("next", raw);
    mockApi.getAuthStatus.mockResolvedValue({ enabled: false, authenticated: true });

    render(<LoginForm />);
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/"));
  });

  it("状态查询失败时仍然显示表单，不白屏", async () => {
    mockApi.getAuthStatus.mockRejectedValue(new Error("后端没起来"));
    render(<LoginForm />);
    await waitFor(() => expect(screen.getByLabelText("访问密码")).toBeInTheDocument());
  });
});
