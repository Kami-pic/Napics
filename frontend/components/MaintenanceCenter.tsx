"use client";

import React, { useState } from "react";
import { api } from "@/lib/api";

export default function MaintenanceCenter() {
  const [isOpen, setIsOpen] = useState(false);
  const [isRestarting, setIsRestarting] = useState(false);
  const [message, setMessage] = useState("");

  const handleRestart = async () => {
    if (!confirm("确定要重启前后端服务吗？页面会短暂不可用。")) return;
    
    setIsRestarting(true);
    setMessage("正在发送重启指令...");
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    try {
      await fetch(`${backendUrl}/api/system/restart`, { method: "POST" }).catch(() => {});
      
      // 后端会杀掉自己，等一会再开始轮询
      await new Promise(r => setTimeout(r, 3000));
      
      let attempts = 0;
      const checkBackend = setInterval(async () => {
        attempts++;
        setMessage(`等待服务恢复... (${attempts})`);
        try {
          const ping = await fetch(`${backendUrl}/`, { cache: 'no-store', signal: AbortSignal.timeout(2000) });
          if (ping.ok) {
            clearInterval(checkBackend);
            setMessage("服务已恢复，正在刷新...");
            setTimeout(() => window.location.reload(), 500);
          }
        } catch {
          // 还没起来，继续等
        }
        
        if (attempts > 40) {
          clearInterval(checkBackend);
          setMessage("重启耗时过长，请手动刷新页面。");
          setTimeout(() => setIsRestarting(false), 3000);
        }
      }, 1000);

    } catch (error) {
      console.error(error);
      setMessage("指令发送失败，请手动运行 restart.bat");
      setTimeout(() => setIsRestarting(false), 3000);
    }
  };


  return (
    <div className="fixed bottom-6 left-6 z-[9999] flex flex-col-reverse items-start gap-3">
      {/* 按钮主体 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="group flex h-12 w-12 items-center justify-center rounded-full bg-blue-600 shadow-lg transition-all hover:bg-blue-700 active:scale-95 focus:outline-none"
        title="系统维护中心"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
          className={`h-6 w-6 text-white transition-transform duration-300 ${isOpen ? "rotate-90" : ""}`}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"
          />
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {/* 展开菜单 */}
      {isOpen && (
        <div className="flex flex-col gap-2 overflow-hidden rounded-xl border border-white/10 bg-gray-900/80 p-2 shadow-2xl backdrop-blur-md transition-all animate-in fade-in slide-in-from-bottom-4">
          <button
            onClick={handleRestart}
            className="flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium text-red-400 hover:bg-white/5 transition-colors"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="h-4 w-4">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" />
            </svg>
            重启后端服务 (刷新数据)
          </button>
        </div>
      )}

      {/* 重启全屏遮罩 */}
      {isRestarting && (
        <div className="fixed inset-0 z-[10000] flex flex-col items-center justify-center bg-black/80 backdrop-blur-xl animate-in fade-in duration-500">
          <div className="relative">
            <div className="h-20 w-20 animate-spin rounded-full border-4 border-blue-500/20 border-t-blue-500 shadow-[0_0_20px_rgba(59,130,246,0.3)]"></div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="h-10 w-10 animate-pulse rounded-full bg-blue-500/10"></div>
            </div>
          </div>
          <h2 className="mt-8 text-2xl font-bold text-white">正在重启后端服务</h2>
          <p className="mt-2 text-gray-400 font-medium tracking-wide">{message}</p>
          <div className="mt-8 flex flex-col items-center gap-4">
            <div className="flex space-x-2">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-1.5 w-1.5 animate-bounce rounded-full bg-blue-500" style={{ animationDelay: `${i * 0.15}s` }}></div>
              ))}
            </div>
            <button 
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 rounded-full border border-white/20 text-xs font-medium text-gray-400 hover:bg-white/5 transition-colors"
            >
              等不及了？手动强制刷新
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
