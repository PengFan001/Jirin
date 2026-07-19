# Watchdog 机制与 system_server 卡死

## 1. Watchdog 机制概述

### 1.1 作用
Watchdog 是 Android 系统的"看门狗"，监控 system_server 中关键线程是否存活、关键锁是否超时。如果检测到异常，会触发 system_server 重启（等同于手机重启）。

### 1.2 关键源码路径
```
frameworks/base/services/core/java/com/android/server/Watchdog.java
  → Watchdog 主类，监控所有关键服务
  → HandlerChecker: 检查 Handler 线程是否响应
  → Monitor: 监控锁是否超时

frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
  → 注册 Watchdog 监控
```

## 2. Watchdog 触发机制

### 2.1 检查流程
```
Watchdog 线程（每 30s 执行一次）
  → 向所有被监控的 Handler 发送心跳消息
  → 等待 60s（DEFAULT_TIMEOUT）
  → 检查所有 HandlerChecker
  → 如果有 Handler 未响应
  → 等待额外 30s（二次确认）
  → 仍未响应
  → 触发 system_server 重启
```

### 2.2 被监控的关键线程
| 线程/Handler | 所属服务 | 检查内容 |
|--------------|----------|----------|
| main (ActivityManager) | AMS | 主线程是否响应 |
| android.fg (FileIo) | 文件 I/O | 文件操作是否阻塞 |
| android.ui | UI 线程 | UI 操作是否阻塞 |
| android.io | I/O 线程 | I/O 操作是否阻塞 |
| android.display | 显示线程 | 显示操作是否阻塞 |
| Monitor (Binder) | Binder | Binder 线程池是否正常 |

## 3. Watchdog 触发日志

### 3.1 典型日志
```
Watchdog: *** WATCHDOG KILLING SYSTEM PROCESS: main thread blocked
Watchdog: main thread stack:
"main" prio=5 tid=1 Blocked
  at com.android.server.am.ActivityManagerService.dumpStackTraces(ActivityManagerService.java:xxx)
  - waiting to lock <0x12345678> held by thread 15
  ...
Watchdog: *** GOODBYE!
```

### 3.2 日志解读
- `WATCHDOG KILLING SYSTEM PROCESS` — Watchdog 触发了
- `main thread blocked` — 主线程阻塞
- `waiting to lock` — 锁竞争导致阻塞
- `held by thread 15` — 锁被线程 15 持有

### 3.3 后续日志
```
Process: system_server (pid XXXX)
Signal: SIGKILL
...
I ServiceManager: service 'activity' died
I Zygote: System server process exited
I Zygote: Starting Zygote...
```
→ system_server 被杀 → Zygote 重启 → 手机重启

## 4. Watchdog 触发的常见原因

### 4.1 锁竞争
```
场景：system_server 中两个线程互相持有对方需要的锁
Thread A: 持有 Lock1，等待 Lock2
Thread B: 持有 Lock2，等待 Lock1
→ Watchdog 检测到 main 线程等待超时
```

### 4.2 Binder 调用阻塞
```
场景：system_server 的 main 线程调用其他进程的 Binder
→ 远端进程无响应
→ main 线程阻塞超过 60s
→ Watchdog 触发
```

### 4.3 磁盘 I/O 阻塞
```
场景：system_server 执行磁盘操作（如写入数据库）
→ 磁盘繁忙/损坏
→ I/O 操作阻塞超过 60s
→ Watchdog 触发
```

### 4.4 死循环/长时间计算
```
场景：system_server 中某段代码进入死循环
→ main 线程无法处理其他消息
→ Watchdog 心跳超时
```

## 5. Watchdog dump 分析

### 5.1 dumpStackTraces 输出
Watchdog 触发前会调用 `dumpStackTraces()` 保存所有线程堆栈到 `/data/anr/traces.txt` 或 `/data/system/dumpstate/` 目录。

### 5.2 分析步骤
1. 找到 `WATCHDOG KILLING` 日志
2. 查看 main 线程堆栈 → 确定阻塞原因
3. 查看锁持有者线程堆栈 → 确定锁竞争原因
4. 查看 Binder 调用目标 → 确定远端是否无响应
5. 查看 CPU 使用 → 确定是否系统负载过高

### 5.3 常见模式
| 模式 | traces 特征 | 根因 |
|------|-------------|------|
| 锁竞争 | waiting to lock | synchronized 竞争 |
| Binder 阻塞 | BinderProxy.transact | 等待远端响应 |
| 磁盘 I/O | SQLiteQuery/fopen | 磁盘操作阻塞 |
| 死锁 | 循环 waiting to lock | 线程互相等待 |

## 6. 分析要点

### 6.1 Watchdog vs ANR
| 维度 | Watchdog | ANR |
|------|----------|-----|
| 影响范围 | system_server（整个系统） | 单个应用 |
| 后果 | 手机重启 | 应用弹窗 |
| 超时时间 | 60s | 5s (Input) / 10s (Service) |
| 日志特征 | WATCHDOG KILLING | ANR in |

### 6.2 误判陷阱
1. **Watchdog 触发不等于系统有 bug**：可能是某个应用导致 system_server 阻塞
2. **锁竞争可能是第三方服务引入**：如厂商定制服务
3. **Binder 阻塞可能是目标进程正在 GC**：短暂阻塞不算问题
4. **重启后第一次 Watchdog 可能误触发**：系统初始化阶段负载高
