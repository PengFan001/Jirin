# Native Exception (NE) 总览与信号机制

## 1. NE 产生原理

### 1.1 信号机制
Android Native Crash 基于 Linux 信号机制：
```
CPU 执行非法操作（如访问无效内存地址）
  → 内核检测到异常
  → 内核向进程发送对应信号
  → 进程中的信号处理器捕获信号
  → debuggerd 收集崩溃现场信息
  → 生成 tombstone
  → 进程终止
```

### 1.2 关键源码路径
```
system/core/debuggerd/                    — debuggerd 守护进程
  → debuggerd.cpp: 主入口
  → handler/handler.cpp: 信号处理
  → tombstone.cpp: tombstone 生成
bionic/libc/bionic/signalfd.cpp           — 信号处理
kernel/signal.c                           — 内核信号传递
```

## 2. 信号类型详解

| 信号 | 编号 | 含义 | 常见原因 |
|------|------|------|----------|
| SIGSEGV | 11 | 段错误 | 空指针解引用、访问已释放内存、越界访问 |
| SIGABRT | 6 | 主动终止 | abort()调用、double-free、heap corruption |
| SIGBUS | 7 | 总线错误 | 内存对齐错误、访问不存在的物理地址 |
| SIGFPE | 8 | 算术异常 | 除零、溢出 |
| SIGILL | 4 | 非法指令 | 代码段损坏、架构不匹配 |
| SIGTRAP | 5 | 断点/陷阱 | 调试断点、__builtin_trap() |
| SIGSTKFLT | 16 | 协处理器栈错误 | 极少见 |

### 2.1 SIGSEGV (Segmentation Fault)
**code 值含义**：
- `SEGV_MAPERR` (1): 地址未映射到任何内存区域
- `SEGV_ACCERR` (2): 地址已映射但权限不允许访问

**常见场景**：
- 空指针解引用：fault addr = 0x0 或接近 0x0
- 野指针/UAF：fault addr 是随机值
- 栈溢出：fault addr 接近栈边界

### 2.2 SIGABRT (Abort)
**触发方式**：
- 显式调用 `abort()`
- C 运行时检测到内存错误（如 glibc 的 heap corruption 检测）
- `__android_log_assert()` 断言失败
- `__builtin_trap()` 触发

**Abort message**：
```
Abort message: 'xxx'
```
这个 message 通常包含具体的错误原因。

## 3. Crash 处理链路（源码级）

### 3.1 信号捕获
```
Kernel 发送信号
  → do_signal() (kernel/signal.c)
  → 进程的信号处理器被调用
  → debuggerd 注册的 handler: signal_handler() (debuggerd/handler/handler.cpp)
```

### 3.2 debuggerd 处理
```
signal_handler()
  → debuggerd_dispatch_signal()
  → 收集寄存器状态
  → 收集 backtrace（通过 libunwindstack）
  → 通过 socket 发送给 tombstoned
```

### 3.3 Tombstone 生成
```
tombstoned (system/core/tombstoned/tombstoned.cpp)
  → 接收 debuggerd 的数据
  → 写入 /data/tombstones/tombstone_NN
  → 最多保留 10 个 tombstone（循环覆盖）
```

### 3.4 进程终止
```
默认信号处理行为：
  → SIGSEGV/SIGABRT/SIGBUS/SIGFPE/SIGILL → 终止进程并生成 core dump
  → 如果进程注册了自定义 handler → 自定义处理
```

## 4. Tombstone 结构

```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: '...'    — 系统版本
Revision: '...'             — 硬件版本
ABI: 'arm64'                — CPU 架构
Timestamp: ...              — 崩溃时间
Process uptime: NNNs        — 进程存活时间
Cmd line: com.xxx           — 进程名

pid: NNN, tid: NNN, name: xxx  >>> com.xxx <<<  — 崩溃线程
uid: NNNN
signal N (SIGxxx), code N (xxx), fault addr 0x...  — 信号信息
    x0  ... x1  ... x2  ...   — 寄存器状态
backtrace:
    #00 pc 0x...  /path/to/lib.so (symbol+offset)  — 调用栈帧
    #01 pc 0x...  /path/to/lib.so (symbol+offset)
    ...
```

## 5. 典型日志特征

**logcat**:
```
DEBUG: *** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
DEBUG: Build fingerprint: '...'
DEBUG: pid: 1234, tid: 1234, name: main  >>> com.example.app <<<
DEBUG: signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
```

**event log**:
```
am_crash: [uid,pid,processName,flags,subject,tag,Native crash,...]
```

## 6. 常见根因分类

| 信号 | 根因 | 判断依据 |
|------|------|----------|
| SIGSEGV | 空指针解引用 | fault addr = 0x0 |
| SIGSEGV | 野指针/UAF | fault addr 为随机值 |
| SIGSEGV | 栈溢出 | fault addr 接近栈边界 |
| SIGABRT | 显式 abort | 有 Abort message |
| SIGABRT | 堆损坏 | 无明确 Abort message |
| SIGBUS | 内存对齐 | SEGV_ACCERR + 非对齐地址 |
| SIGFPE | 除零 | 整数除法中除数为 0 |

## 7. 误判陷阱

1. **SIGSEGV fault addr 不总是 0**：偏移访问时 fault addr 可能是小值（如 0x8 表示偏移 8 字节的 null 对象字段）
2. **SIGABRT 的根因可能不是 abort 调用本身**：可能是底层 C 库检测到内存错误后自动 abort
3. **backtrace 可能不完整**：如果栈被破坏，unwind 可能失败，只显示部分栈帧
4. **Native 和 Java 栈帧混合**：JNI 调用时，backtrace 会同时包含 Native 和 Java 栈帧
