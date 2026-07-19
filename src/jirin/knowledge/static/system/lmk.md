# Low Memory Killer (LMK) 详解

## 1. LMK 机制

### 1.1 从 kernel LMK 到用户空间 LMKD
```
旧方案（kernel 4.x 之前）：
  kernel/drivers/staging/android/lowmemorykiller.c
  → 直接在 kernel 中实现
  → 根据 oom_score_adj 杀进程

新方案（kernel 4.x+，PSI 支持）：
  system/core/lmkd/lmkd.cpp
  → 用户空间守护进程
  → 监听 kernel PSI (Pressure Stall Information)
  → 内存压力超阈值时杀进程
```

### 1.2 关键源码路径
```
system/core/lmkd/lmkd.cpp                          — LMKD 守护进程
kernel/drivers/staging/android/lowmemorykiller.c    — 旧 kernel LMK
kernel/include/uapi/linux/psi.h                     — PSI 接口
frameworks/base/services/core/java/.../ProcessList.java — adj 阈值定义
```

## 2. LMKD 工作原理

### 2.1 PSI 监控模式
```
lmkd 启动
  → 打开 /proc/pressure/memory
  → 注册 PSI 事件监听
  → 当 memory pressure 超过阈值
  → 扫描进程列表
  → 选择 oom_score_adj 最高 + RSS 最大的进程
  → 发送 SIGKILL
```

### 2.2 进程选择算法
```
1. 过滤：只考虑 oom_score_adj > 0 的进程
2. 排序：按 oom_score_adj 从高到低
3. 同 adj 时：按 RSS 从大到小
4. 选择：第一个进程（最高 adj + 最大 RSS）
5. 杀死：发送 SIGKILL
6. 评估：释放的内存是否足够
7. 如果不够：继续选择下一个进程
```

## 3. LMK 日志解读

### 3.1 kernel LMK 日志
```
<6>[12345.678] lowmemorykiller: Killing 'com.example.app' (12345), adj 523,
   score 135 to free 85600kB on behalf of 'lmkd' (678)
   because cache group has 180000kB below 204800kB low limit
```

### 3.2 LMKD 日志
```
I/lmkd  : lowmemorykiller: kill pid=12345 (com.example.app) adj=523 reason=psi
I/lmkd  :   score=135 rss=87654321kB
```

### 3.3 字段解读
| 字段 | 含义 |
|------|------|
| adj | oom_score_adj 值，越高越容易被杀 |
| score | 综合 OOM 分数（包含 adj + 内存使用比例） |
| rss | 进程实际物理内存占用 |
| reason | 触发原因（psi/memory pressure） |
| to free | 预计释放的内存量 |

## 4. LMK 与稳定性的关系

### 4.1 LMK 杀前台应用
```
异常场景：前台应用被 LMK 杀死
原因：
  1. 系统内存极度紧张
  2. 前台应用的 adj 被错误设置为较高值
  3. 后台进程占用过多内存
日志特征：
  lmkd: kill pid=12345 (com.example.app) adj=0  ← adj=0 说明是前台应用
```

### 4.2 LMK 杀系统服务
```
异常场景：关键系统服务被杀
影响：可能导致系统功能异常
日志特征：
  lmkd: kill pid=XXX (com.android.systemui) adj=XXX
```

### 4.3 频繁 LMK → 用户体验问题
```
频繁 LMK 的表现：
  1. 应用频繁重启（用户感知为"闪退"）
  2. 后台任务频繁中断
  3. 系统卡顿（LMK 本身消耗资源）
  4. 通知丢失（推送服务被杀）
```

## 5. 分析要点

### 5.1 LMK 分析流程
1. 查看 lmkd 日志 → 确认哪些进程被杀
2. 查看被杀进程的 adj → 是否合理
3. 查看系统内存状态 → `/proc/meminfo`
4. 查看内存占用 Top 进程 → `dumpsys meminfo`
5. 判断是系统级问题还是单个应用问题

### 5.2 关键指标
| 指标 | 正常值 | 异常信号 |
|------|--------|----------|
| 系统可用内存 | > 200MB | < 100MB |
| 被杀进程 adj | > 500 (cached) | < 100 (前台/可见) |
| LMK 频率 | < 1次/分钟 | > 5次/分钟 |
| ZRAM 使用率 | < 70% | > 90% |

### 5.3 误判陷阱
1. **LMK 杀 cached 进程是正常行为**：不代表有 bug
2. **adj=0 的进程被杀才是异常**：说明系统内存极度紧张
3. **LMK 日志中 RSS 不等于 PSS**：RSS 包含共享内存
4. **ZRAM 压缩比影响实际可用内存**：高压缩比 = 更多可用内存
