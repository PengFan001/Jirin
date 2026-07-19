# Binder 线程池耗尽导致 ANR

## 1. Binder 线程池机制

### 1.1 默认配置
每个进程默认有 16 个 Binder 线程（可通过 `Process.setThreadPriority()` 调整）。
system_server 有 31 个 Binder 线程。

### 1.2 源码路径
```
frameworks/native/libs/binder/ProcessState.cpp
  → setThreadPoolMaxThreadCount()
  → DEFAULT_MAX_BINDER_THREADS = 15 (+ 1 主线程 = 16)
```

## 2. Binder 线程池耗尽导致 ANR

### 2.1 触发条件
当所有 Binder 线程都在处理耗时请求时，新的 Binder 调用无法被处理。

### 2.2 链路
```
应用主线程发起 Binder 调用
  → IPCThreadState::transact()
  → 等待空闲的 Binder 线程处理响应
  → 所有 Binder 线程都在忙
  → 主线程阻塞等待
  → 超过 5s → Input ANR
```

### 2.3 traces 表现
```
"main" prio=5 tid=1 Native
  at android.os.BinderProxy.transact(Native Method)
  at android.os.BinderProxy.transact(Binder.java:xxx)
  → 等待 Binder 线程池响应

"Binder:1234_1" prio=5 tid=XX Native
  at android.os.Binder.nativeTransact(Native Method)
  → 正在处理某个耗时 Binder 调用

"Binder:1234_2" prio=5 tid=XX Native
  ... (所有 Binder 线程都在忙)
```

## 3. 常见场景

### 3.1 ContentProvider 并发查询
多个线程同时查询同一个 ContentProvider，导致 Provider 进程的 Binder 线程池耗尽。

### 3.2 系统服务过载
system_server 处理大量请求时，所有 Binder 线程被占用，其他进程调用系统服务时阻塞。

### 3.3 第三方 SDK 大量 Binder 调用
某些 SDK 在后台频繁通过 Binder 与系统服务通信，占满 Binder 线程。

## 4. 分析要点

### 4.1 识别 Binder 线程池耗尽
1. 主线程在 `BinderProxy.transact()` 上等待
2. 所有 Binder 线程（`Binder:PID_N`）都在 Native 方法中
3. 没有明显的锁竞争

### 4.2 责任归属
- 应用自身大量 Binder 调用 → 应用责任
- system_server 过载 → 系统/其他进程责任
- 第三方 SDK 导致 → SDK 责任

### 4.3 误判陷阱
1. **Binder 线程池耗尽 vs 普通 Binder 超时**：前者所有 Binder 线程都忙，后者可能只是某个特定调用慢
2. **需要看所有 Binder 线程**：不能只看 main 线程，要分析为什么所有 Binder 线程都在忙
