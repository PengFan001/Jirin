# Java Exception (JE) 总览与传播链路

## 1. JE 在 Android 中的完整传播链路

### 1.1 异常抛出到进程终止

```
代码执行中抛出 Exception/Error
  → 沿调用栈向上传播
  → 若无 catch 块捕获，到达 Thread.UncaughtExceptionHandler
  → Android 注册的 KillingHandler 被调用
  → RuntimeInit.KillingHandler.uncaughtException()
  → 记录到 dropbox (/data/system/dropbox/)
  → 通过 Process.killProcess(Process.myPid()) 终止进程
  → ActivityManager 收到进程死亡通知
  → 清理进程资源
```

### 1.2 关键源码路径

#### Thread.java — UncaughtExceptionHandler 机制
```
libcore/ojluni/src/main/java/java/lang/Thread.java
```
- `dispatchUncaughtException(Throwable)`: 调用 UncaughtExceptionHandler
- `getUncaughtExceptionHandler()`: 获取处理器，优先自定义，否则为 ThreadGroup

#### RuntimeInit.java — Android 异常处理入口
```
frameworks/base/core/java/com/android/internal/os/RuntimeInit.java
```
- `KillingHandler`: 内部类，实现 `Thread.UncaughtExceptionHandler`
- `KillingHandler.uncaughtException(Thread t, Throwable e)`:
  1. 调用 `logUncaughtException(t, e)` 记录到 dropbox
  2. 调用 `Process.killProcess(Process.myPid())` 终止进程
  3. 调用 `System.exit(10)` 确保退出

#### ActivityThread.java — 应用主线程入口
```
frameworks/base/core/java/android/app/ActivityThread.java
```
- `main(String[] args)`: 应用入口，调用 `RuntimeInit.main()`
- `handleUncaughtException(Throwable)`: 处理未捕获异常（Android 12+）
- `H.handleMessage(Message)`: Handler 消息分发，异常会从此处冒出

#### ActivityManagerService.java — 进程死亡处理
```
frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
```
- `handleAppDiedLocked(IApplicationThread app, ...)`: 处理应用进程死亡
- `removeDyingProcessLocked(...)`: 清理死亡进程
- `AppDeathHandler`: 内部类，处理应用死亡回调

### 1.3 Handler 异常传播链路

大多数 Android 组件（Activity/Service/BroadcastReceiver）的生命周期回调通过 Handler 消息队列执行：

```
Looper.loop()
  → MessageQueue.next() 获取消息
  → msg.target.dispatchMessage(msg)
  → Handler.dispatchMessage()
  → Handler.handleMessage()
    → 调用 Activity/Service 生命周期方法
    → 若抛出异常
  → 异常传播到 Looper.loop()
  → Looper 捕获异常（Android 30+ 有 Looper.setMessageLogging）
  → 若无捕获，传播到 Thread.UncaughtExceptionHandler
```

关键源码：
```
frameworks/base/core/java/android/os/Looper.java
```
- `loop()`: 消息循环主方法
- Android 10+ 中 `Looper.loop()` 不再捕获异常，让其自然传播到 UncaughtExceptionHandler

### 1.4 Dropbox 记录机制

异常信息会被记录到 `/data/system/dropbox/` 目录：
```
frameworks/base/core/java/com/android/internal/os/DropBoxManager.java
frameworks/base/services/core/java/com/android/server/DropBoxManagerService.java
```
- 文件命名格式：`system_app_crash@timestamp.txt` 或 `data_app_crash@timestamp.txt`
- 包含：异常堆栈、进程信息、设备信息

### 1.5 典型日志特征

**logcat 中的标志**：
```
FATAL EXCEPTION: main          # 主线程崩溃
FATAL EXCEPTION: Thread-X      # 子线程崩溃
Process: com.xxx, PID: 1234    # 进程名和 PID
java.lang.XxxException: msg    # 异常类名和消息
    at xxx.xxx.method(File.java:line)  # 堆栈帧
```

**event log 中的标志**：
```
am_crash: [uid,pid,processName,flags,exceptionType,tag,msg,...]
am_anr: 如果崩溃伴随 ANR
```

### 1.6 常见根因分类

| 分类 | 异常类型 | 判断依据 |
|------|----------|----------|
| 空指针 | NullPointerException | 对 null 对象调用方法 |
| 类型转换 | ClassCastException | 强制类型转换失败 |
| 数组越界 | ArrayIndexOutOfBoundsException | 数组访问索引超出范围 |
| 内存溢出 | OutOfMemoryError | 内存分配失败 |
| 权限异常 | SecurityException | 缺少权限或权限被拒绝 |
| 状态异常 | IllegalStateException | 组件状态不允许当前操作 |
| 并发异常 | ConcurrentModificationException | 迭代时修改集合 |
| 资源未找到 | Resources$NotFoundException | 引用不存在的资源 ID |

### 1.7 误判陷阱

1. **Caused by 链的方向**：最顶层异常是"表象"，最底层 Caused by 才是"根因"。分析时应从 Caused by 链的末端开始。
2. **子线程崩溃 vs 主线程崩溃**：`FATAL EXCEPTION: main` 是主线程，其他线程名的崩溃可能不影响 UI，但同样会终止进程。
3. **二次崩溃**：有时崩溃处理代码本身也会崩溃，日志中会出现多个 FATAL EXCEPTION 块。应关注第一个。
4. **系统版本差异**：Android 12+ 对 UncaughtExceptionHandler 的行为有变化，`ActivityThread.handleUncaughtException()` 会先尝试处理。

### 1.8 Android 版本差异

| 版本 | 变化 |
|------|------|
| Android 12 (API 31) | 新增 `ActivityThread.handleUncaughtException()`，在 KillingHandler 之前尝试处理 |
| Android 11 (API 30) | Looper 不再捕获异常，直接传播到 UncaughtExceptionHandler |
| Android 10 (API 29) | 引入 `Looper.setMessageLogging()` 用于监控消息处理 |
| Android 9 (API 28) | 引入 `RuntimeInit.enableOpportunisticKilling()` |
