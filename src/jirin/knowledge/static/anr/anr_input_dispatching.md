# Input ANR 详细链路

## 1. Input 事件处理流程

```
硬件触摸 → kernel → EventHub → InputReader → InputDispatcher → 应用窗口
```

### 1.1 关键源码路径
```
frameworks/native/services/inputflinger/reader/InputReader.cpp
frameworks/native/services/inputflinger/dispatcher/InputDispatcher.cpp
frameworks/base/core/java/android/view/ViewRootImpl.java  — Dispatching 入口
frameworks/base/core/java/android/view/View.java          — dispatchTouchEvent()
```

## 2. Input ANR 触发链路

```
InputDispatcher::dispatchOnceInnerLocked()
  → 找到目标窗口 Connection
  → 发送 InputEvent
  → 启动 ANR 计时器 (5s)
  → 等待应用调用 finishInputEvent()
  → 超时
  → InputDispatcher::handleTargetsTimedOutLocked()
  → InputDispatcher::onANR()
  → InputManagerService::notifyANR()
  → ActivityManagerService.inputDispatchingTimedOut()
  → ActivityManagerService.appNotResponding()
```

## 3. 主线程阻塞原因分析

### 3.1 主线程在做什么
查看 traces.txt 中 "main" 线程的状态：

**状态 BLOCKED**：
```
"main" prio=5 tid=1 Blocked
  - waiting to lock <0x12345678> held by thread 15
```
→ 锁竞争导致阻塞

**状态 WAITING**：
```
"main" prio=5 tid=1 Waiting
  at java.lang.Object.wait(Native Method)
  at java.lang.Object.wait(Object.java:xxx)
```
→ 等待其他线程通知

**状态 RUNNABLE（但在系统调用中）**：
```
"main" prio=5 tid=1 Runnable
  at android.os.BinderProxy.transact(Native Method)
```
→ Binder 调用阻塞（等待远端响应）

**状态 RUNNABLE（在 Java 代码中）**：
```
"main" prio=5 tid=1 Runnable
  at com.example.app.DataManager.processData(DataManager.java:120)
```
→ 主线程在做耗时计算

## 4. 分析要点

### 4.1 从 traces 定位根因
1. 找到 "main" 线程
2. 查看线程状态（Blocked/Waiting/Runnable）
3. 查看堆栈顶部（正在执行什么操作）
4. 如果是 Blocked → 找到持有锁的线程
5. 如果是 Binder 调用 → 需要查看远端进程

### 4.2 常见 Input ANR 模式
| 模式 | traces 特征 | 根因 |
|------|-------------|------|
| 锁竞争 | waiting to lock | synchronized 竞争 |
| Binder 阻塞 | transact(Native Method) | 等待 system_server 响应 |
| 主线程 I/O | FileInputStream.read() | 主线程读文件 |
| 主线程网络 | Socket.connect() | 主线程网络请求 |
| 主线程数据库 | SQLiteQuery.fillWindow() | 主线程查询数据库 |
| 计算密集 | 应用自己的方法 | 复杂算法/大循环 |

### 4.3 责任归属
- 主线程自身阻塞 → 应用责任
- Binder 调用等待 system_server → 可能是系统负载问题
- 系统 CPU 负载过高 → 系统/其他进程责任
