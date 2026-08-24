import "@testing-library/jest-dom/vitest";
import { installMockEventSource } from "./__tests__/helpers/mockEventSource";

// jsdom 不提供 EventSource，BT 主搜索又靠它收流。全局装一个替身，
// 否则相关测试连 new EventSource() 都跑不起来。
installMockEventSource();
