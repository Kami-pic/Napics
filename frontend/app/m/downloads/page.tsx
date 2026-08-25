import MobileShell from "@/components/mobile/MobileShell";
import MobileStateView from "@/components/mobile/MobileStateView";

export default function MobileDownloadsPage() {
  return (
    <MobileShell title="下载">
      <MobileStateView state="empty" emptyText="下载任务列表正在开发中" />
    </MobileShell>
  );
}
