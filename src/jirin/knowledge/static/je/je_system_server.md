# system_server 特有异常

## 1. system_server 概述

system_server 是 Android 最核心的系统进程，承载 AMS、WMS、PMS 等关键服务。它的崩溃会导致整个系统重启。

### 1.1 关键源码路径
```
frameworks/base/services/java/com/android/server/SystemServer.java   — 启动入口
frameworks/base/services/core/java/com/android/server/am/            — AMS
frameworks/base/services/core/java/com/android/server/wm/            — WMS
frameworks/base/services/core/java/com/android/server/pm/            — PMS
```

## 2. system_server 崩溃特征

### 2.1 日志特征
```
pid: XXX, tid: XXX, name: system_server  >>> system_server <<<
FATAL EXCEPTION: main
Process: system_server, PID: XXX
```
或
```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: '...'
pid: XXX, tid: XXX, name: system_server  >>> system_server <<<
signal N (SIGxxx), code N (...), fault addr ...
```

### 2.2 常见崩溃原因

**原因 A：Watchdog 触发 system_server 重启**
```
Watchdog: *** WATCHDOG KILLING SYSTEM PROCESS: xxx ***
Watchdog: xxx blocked for more than xxx ms
```
源码链路：
```
Watchdog.java → evaluateCheckerCompletion()
  → killSystemServerProcess()
  → Process.killProcess(Process.myPid())
```

**原因 B：AMS 内部异常**
```
java.lang.NullPointerException in ActivityManagerService
java.lang.OutOfMemoryError in ActivityManagerService
```

**原因 C：Binder 线程池耗尽**
当 system_server 的 Binder 线程池（默认 31 个线程）全部被占用时，新的系统服务调用无法处理。

## 3. 分析要点

### 3.1 system_server 崩溃的影响范围
- system_server 崩溃 → 所有应用进程受影响
- 大量 DeadObjectException 级联出现
- 系统自动重启（zygote 重新 fork system_server）

### 3.2 区分 system_server 崩溃和应用崩溃
- system_server PID 固定（可从 init 进程查看）
- 进程名为 `system_server`
- 崩溃后系统会重启，所有应用重新连接

### 3.3 责任归属
- system_server 自身 bug → 系统厂商/ROM 问题
- 应用通过 Binder 传入非法数据导致 → 应用问题（但表现为 system_server 崩溃）
- 第三方系统服务（vendor service）导致 → 芯片厂商/ODM 问题

### 3.4 误判陷阱
1. **不要将 system_server 崩溃归因于应用**：即使堆栈中有应用的 Binder 调用，根因可能在 system_server 的参数校验不足
2. **Watchdog 不是崩溃**：Watchdog 是主动杀死 system_server，不是异常导致的崩溃。需要分析为什么 Watchdog 触发了
3. **重启后的日志**：system_server 重启后，之前的日志可能在 last_kmsg 或 pstore 中
