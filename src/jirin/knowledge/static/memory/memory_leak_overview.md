# Android 内存泄漏总览

## 1. Android 内存模型

### 1.1 进程内存分类
```
进程总内存 (PSS)
├── Java Heap    — Java 对象（由 ART GC 管理）
├── Native Heap  — C/C++ 分配（malloc/new）
├── Stack        — 线程栈（固定大小，通常 8MB）
├── Graphics     — 图形缓冲区（Surface/GraphicBuffer）
├── Code         — 代码段（SO/JAR/DEX，可共享）
└── Other        — 内核 slab、文件映射等
```

### 1.2 关键源码路径
```
frameworks/base/core/java/android/os/Debug.java         — meminfo 接口
frameworks/base/services/core/java/.../ProcessStatsService.java — 进程统计
frameworks/native/libs/binder/MemoryDealer.cpp          — Binder 内存管理
art/runtime/gc/heap.cc                                  — ART 堆管理
bionic/libc/bionic/malloc.cpp                           — Native 内存分配
```

## 2. Java 内存泄漏

### 2.1 产生机制
```
Java 对象被 GC Root 引用
  → GC 无法回收
  → 对象持续占用 Java Heap
  → Java Heap 持续增长
  → GC 频繁触发
  → 最终 OOM: Java heap space
```

### 2.2 常见 GC Root
| GC Root 类型 | 泄漏场景 |
|--------------|----------|
| 静态变量 | 静态集合类持有 Activity/Context |
| 内部类引用 | 非静态内部类持有外部类引用 |
| Handler/Runnable | 消息队列中的 Message 持有 Handler |
| ThreadLocal | 线程池中的 ThreadLocal 未清理 |
| 监听器/回调 | 注册了回调但未注销 |
| WebView | WebView 持有 Activity 引用 |

### 2.3 典型日志
```
ActivityManager: Low on memory:
  zram: 500MB/1000MB
  Java: 256MB/256MB (100%) ← Java Heap 已满
  GC: 15次/分钟 ← GC 频繁
```
或：
```
java.lang.OutOfMemoryError: Failed to allocate a 1024 byte allocation with 0 free bytes;
  growing to 256MB to hold needed memory
```

### 2.4 检测方法
```bash
# 查看 Java Heap 使用
adb shell dumpsys meminfo <package_name>

# 使用 Android Studio Profiler
# 导出 hprof 文件
adb shell am dumpheap <pid> /data/local/tmp/heap.hprof
adb pull /data/local/tmp/heap.hprof
```

## 3. Native 内存泄漏

### 3.1 产生机制
```
malloc()/new 分配内存
  → 指针丢失（所有引用被覆盖或超出作用域）
  → 内存永远无法 free()
  → Native Heap 持续增长
  → 最终触发 LMK 或 SIGABRT
```

### 3.2 典型日志
```
ActivityManager: Killing 12345:com.example.app (adj 0): too much memory
  RSS: 512MB (limit: 384MB)
  Native Heap: 400MB ← Native 内存异常
```

### 3.3 检测方法
```bash
# 查看 Native Heap
adb shell dumpsys meminfo <pid>

# Malloc Debug
setprop libc.debug.malloc.options "backtrace"
# 重启后查看
adb shell dumpsys meminfo --allocations <pid>

# ASAN (需要重新编译)
ASAN_OPTIONS=detect_leaks=1 ./my_binary
```

## 4. 内存泄漏的连锁反应

### 4.1 泄漏 → OOM 链路
```
内存泄漏
  → 进程 RSS 持续增长
  → 系统可用内存减少
  → 触发 LMK (Low Memory Killer)
  → 进程被杀死
  → 日志中出现 "lowmemorykiller" 或 "oom_kill"
```

### 4.2 泄漏 → 性能问题
```
Java Heap 增长
  → GC 频率增加
  → STW (Stop The World) 暂停增多
  → 应用卡顿
  → 可能触发 ANR
```

## 5. 分析要点

### 5.1 判断内存泄漏的指标
| 指标 | 正常范围 | 异常信号 |
|------|----------|----------|
| Java Heap | < 128MB | 持续增长不回落 |
| Native Heap | < 100MB | 持续增长不回落 |
| PSS | < 200MB | 持续增长 |
| GC 频率 | < 5次/分钟 | > 10次/分钟 |

### 5.2 误判陷阱
1. **内存增长不等于泄漏**：可能是缓存策略（如 LRU Cache）
2. **Native Heap 包含 SO 库**：加载大量 SO 会增加 Native Heap
3. **Graphics 内存**：Bitmap 在 Android 8.0+ 放在 Native Heap
4. **进程间共享内存**：PSS 不等于 USS，需要看 USS（Unique Set Size）
