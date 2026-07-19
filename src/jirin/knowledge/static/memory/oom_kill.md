# OOM Kill 与 Low Memory Killer

## 1. OOM Kill 机制

### 1.1 触发流程
```
系统可用内存低于阈值
  → kernel 触发 Low Memory Killer (LMK)
  → 或 Android LMKD 守护进程触发
  → 选择 oom_score_adj 最高的进程
  → 发送 SIGKILL 杀死进程
  → 日志记录 oom_kill
```

### 1.2 关键源码路径
```
kernel/drivers/staging/android/lowmemorykiller.c  — kernel LMK（旧）
system/core/lmkd/lmkd.cpp                          — 用户空间 LMKD（新）
frameworks/base/services/core/java/.../OomAdjuster.java — OOM 分数调整
kernel/include/linux/oom.h                         — OOM 评分定义
```

## 2. OOM Score 机制

### 2.1 oom_score_adj 值
| 值 | 进程类型 | 被杀优先级 |
|----|----------|------------|
| -1000 | kernel/system | 永不杀 |
| -900 | system_server | 极低 |
| -800 | 前台服务 | 低 |
| 0 | 可见应用 | 中 |
| 500 | 缓存进程 | 高 |
| 700 | 空进程 | 最高 |
| 900 | adj > cached | 最先被杀 |

### 2.2 源码链路
```
OomAdjuster.updateOomAdjLocked()
  → 计算 oom_score_adj
  → 写入 /proc/PID/oom_score_adj
  → kernel/lmkd 读取该值决定杀哪个进程
```

## 3. OOM Kill 日志解读

### 3.1 kernel 日志
```
[12345.678] lowmemorykiller: Killing 'com.example.app' (12345), adj 500,
   score 120 to free 102400kB on behalf of 'lmkd' (678)
   because cache group has 200000kB below 204800kB low limit
```
字段解读：
- `Killing 'com.example.app' (12345)` — 被杀进程名和 PID
- `adj 500` — oom_score_adj 值
- `score 120` — 当前 oom_score
- `to free 102400kB` — 预计释放内存
- `cache group has 200000kB below 204800kB` — 触发原因

### 3.2 lmkd 日志
```
lmkd: lowmemorykiller: kill pid=12345 (com.example.app) adj=500 reason=memory pressure
```

### 3.3 ActivityManager 日志
```
ActivityManager: Low on memory:
  zram: 800MB/2048MB
  free: 50MB (limit: 200MB)
  ...
ActivityManager: Killing 12345:com.example.app (adj 500): empty for 60s
```

## 4. OOM Kill 的常见原因

### 4.1 系统级原因
| 原因 | 特征 | 解决方向 |
|------|------|----------|
| 内存碎片化 | 总空闲内存足够但连续内存不足 | 重启/清理缓存 |
| 大量后台进程 | cached 进程过多 | 限制后台进程数 |
| 内存泄漏（系统服务） | system_server RSS 异常 | 排查系统服务泄漏 |
| 应用内存泄漏 | 单个应用 RSS 持续增长 | 排查应用泄漏 |

### 4.2 应用级原因
| 原因 | 特征 | 解决方向 |
|------|------|----------|
| 应用内存泄漏 | PSS 持续增长 | hprof 分析 |
| 大图片/视频加载 | Graphics 内存突增 | 优化图片大小 |
| 大量 Bitmap 缓存 | Native Heap 增长 | 优化缓存策略 |
| 多进程应用 | 每个进程占用独立内存 | 减少进程数 |

## 5. OOM Kill 与稳定性问题的关系

### 5.1 OOM Kill → 应用重启
```
应用被 LMK 杀死
  → 用户重新打开应用
  → 应用从头启动
  → 用户体验：应用闪退/重启
```
日志特征：
```
lmkd: kill pid=12345 (com.example.app)
...（间隔一段时间）
ActivityManager: Start proc 12346:com.example.app for activity
```

### 5.2 OOM Kill → 服务丢失
```
后台 Service 被 LMK 杀死
  → 如果是 START_STICKY → 系统尝试重启
  → 如果重启也失败 → 服务永久丢失
```

### 5.3 频繁 OOM → 系统不稳定
```
LMK 频繁杀进程
  → 用户感知：应用频繁关闭/重启
  → 系统日志：大量 "lowmemorykiller" 记录
  → 可能影响系统服务 → 系统级卡顿/ANR
```

## 6. 分析要点

### 6.1 OOM Kill 分析流程
1. 查看 `dmesg` 或 `logcat` 中的 `lowmemorykiller` 日志
2. 确认被杀进程的 adj 值
3. 查看被杀进程的 RSS/PSS → 是否异常大
4. 查看系统总内存 → 是否整体紧张
5. 如果是单个应用异常 → 排查该应用内存泄漏
6. 如果整体紧张 → 排查系统服务或后台进程

### 6.2 关键命令
```bash
# 查看系统内存状态
cat /proc/meminfo
cat /proc/zoneinfo

# 查看进程 OOM 分数
cat /proc/PID/oom_score
cat /proc/PID/oom_score_adj

# 查看进程内存
cat /proc/PID/status | grep -E "VmRSS|VmSize"
dumpsys meminfo PID

# 查看 LMK 历史日志
dmesg | grep -i "lowmemory"
logcat | grep -i "lowmemory"
```

### 6.3 误判陷阱
1. **OOM Kill 不是 crash**：进程被 SIGKILL 杀死，没有 tombstone
2. **adj 值不等于原因**：adj=500 的进程被杀不代表它有 bug
3. **系统级 OOM 不是应用问题**：可能是系统服务泄漏导致
4. **LMK 杀缓存进程是正常的**：cached 进程被杀是预期行为
