# ANR 总览与检测机制

## 1. ANR 定义

ANR (Application Not Responding) 是 Android 系统检测到应用主线程长时间无响应时触发的错误状态。

## 2. ANR 类型与超时阈值

| ANR 类型 | 超时时间 | 触发条件 |
|----------|----------|----------|
| Input Dispatching | 5s | 输入事件未被处理 |
| Service Timeout (前台) | 20s | Service 生命周期方法未返回 |
| Service Timeout (后台) | 200s | 后台 Service 超时 |
| Broadcast Timeout (前台) | 10s | onReceive() 未返回 |
| Broadcast Timeout (后台) | 60s | 后台 Receiver 超时 |
| Content Provider Timeout | 10s | ContentProvider 方法未返回 |

## 3. ANR 检测机制源码链路

### 3.1 Input Dispatching ANR
```
InputDispatcher (system_server/native)
  → 发送输入事件给应用
  → 启动超时计时器 (5s)
  → 应用未在时限内调用 finishInputEvent()
  → InputDispatcher::onANR()
  → ActivityManagerService.inputDispatchingTimedOut()
  → 记录 am_anr event log
  → 收集 traces (/data/anr/traces.txt)
  → 弹出 ANR 对话框（前台应用）
```
关键源码：
```
frameworks/native/services/inputflinger/dispatcher/InputDispatcher.cpp
  → dispatchOnceInnerLocked() → handleTargetsTimedOut()
frameworks/base/services/core/java/com/android/server/input/InputManagerService.java
  → nativeInputDispatchTimeout()
frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
  → inputDispatchingTimedOut() → ProcessList.handleAppDiedLocked()
```

### 3.2 Service ANR
```
ActivityManagerService
  → startService() / bindService()
  → ActiveServices.realStartServiceLocked()
  → 启动超时计时器 (前台 20s / 后台 200s)
  → Service.onCreate() / onStartCommand() 未返回
  → ServiceTimeout 触发
  → ActiveServices.serviceTimeout()
  → 记录 am_anr
```
关键源码：
```
frameworks/base/services/core/java/com/android/server/am/ActiveServices.java
  → serviceTimeout() → appNotResponding()
```

### 3.3 Broadcast ANR
```
ActivityManagerService
  → broadcastIntent()
  → BroadcastQueue.processNextBroadcast()
  → 启动超时计时器 (前台 10s / 后台 60s)
  → BroadcastReceiver.onReceive() 未返回
  → BroadcastTimeout 触发
  → BroadcastQueue.broadcastTimeout()
  → appNotResponding()
```
关键源码：
```
frameworks/base/services/core/java/com/android/server/am/BroadcastQueue.java
  → broadcastTimeout() → appNotResponding()
```

### 3.4 appNotResponding 统一处理
```
ActivityManagerService.appNotResponding()
  → 记录 event log: am_anr
  → 收集 CPU 使用信息
  → 收集 traces: ProcessCpuTracker + Debug.dumpTraces()
  → 如果是前台应用 → 弹出 ANR 对话框
  → 如果是后台应用 → 静默处理（Android 10+）
  → 可选：终止进程
```
关键源码：
```
frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
  → appNotResponding()
```

## 4. traces.txt 结构

ANR 发生时系统会 dump 所有线程的堆栈到 `/data/anr/traces.txt`：
```
----- pid 1234 at 2024-01-15 10:30:00 -----
Cmd line: com.example.app
...
"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0 flags=1
  at com.example.app.DataManager.processData(DataManager.java:120)
  - waiting to lock <0x12345678> (a java.lang.Object) held by thread 15
  at com.example.app.MainActivity.onButtonClick(MainActivity.java:55)
...
----- end 1234 -----
```

## 5. 典型日志特征

**event log**:
```
am_anr: [0,1234,com.example.app,0,Input dispatching timed out]
am_anr: [0,1234,com.example.app,1,ServiceTimeout]
```

**logcat**:
```
I InputDispatcher: ANR in com.example.app
I InputDispatcher: Reason: Input dispatching timed out
I InputDispatcher: LOAD: 12.5  (CPU load)
```

## 6. ANR 根因分类

| 分类 | 占比 | 特征 |
|------|------|------|
| 主线程 I/O 阻塞 | ~30% | 主线程读写文件/网络 |
| 锁竞争/死锁 | ~25% | waiting to lock / BLOCKED 状态 |
| Binder 调用超时 | ~15% | 主线程做 Binder 调用等待远端响应 |
| 系统负载过高 | ~15% | CPU 使用率 > 90%，LOAD 值高 |
| 数据库操作 | ~10% | SQLite 查询/写入在主线程 |
| SharedPreferences.apply() | ~5% | QueuedWork 等待磁盘写入完成 |

## 7. 误判陷阱

1. **ANR 不等于应用 bug**：系统负载过高（其他进程占用 CPU）也会导致 ANR
2. **traces.txt 的时间点**：traces 是 ANR 发生时的快照，主线程可能已经恢复，但 ANR 已经触发
3. **多进程 ANR**：一个进程 ANR 可能导致依赖它的其他进程也报 ANR（Binder 调用阻塞）
4. **Android 版本差异**：Android 12+ 引入了更严格的 ANR 检测，同样的应用在新系统上更容易触发 ANR
