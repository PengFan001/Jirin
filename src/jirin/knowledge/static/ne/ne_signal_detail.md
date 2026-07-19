# NE 信号类型详解

## 1. 信号机制概述

Native 进程异常终止时，kernel 会向该进程发送一个信号。如果进程没有捕获该信号，则执行默认动作（通常是 core dump + 终止）。

### 1.1 关键源码路径
```
kernel/signal.c                      — 信号发送与处理
bionic/libc/bionic/signals.cpp       — Android C 库信号处理
system/core/debuggerd/debuggerd.cpp  — debuggerd 拦截信号
bionic/libc/arch-arm/bionic/crtbegin.c — __libc_init_main_thread
```

## 2. SIGSEGV (Signal 11) — 段错误

### 2.1 触发条件
- 访问未映射的内存地址
- 访问无权限的内存（如写只读页）
- 空指针解引用（地址 0x0 附近）

### 2.2 子类型
| 子类型 | 含义 | 典型原因 |
|--------|------|----------|
| SEGV_MAPERR | 地址未映射 | 空指针、野指针、UAF |
| SEGV_ACCERR | 权限错误 | 写只读内存、执行非可执行页 |

### 2.3 tombstone 表现
```
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
```
→ 空指针解引用

```
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0xdeadbeef
```
→ 访问已释放/未映射的地址

```
signal 11 (SIGSEGV), code 2 (SEGV_ACCERR), fault addr 0x7f123456
```
→ 权限错误（可能是写常量区）

### 2.4 常见根因
1. **空指针**：Java 对象 JNI 层未检查 NULL
2. **UAF (Use After Free)**：对象已释放但指针仍被使用
3. **野指针**：未初始化的指针
4. **栈溢出**：递归过深导致 SP 进入未映射区域

## 3. SIGABRT (Signal 6) — 主动中止

### 3.1 触发条件
- 程序主动调用 `abort()`
- `__builtin_trap()` 触发
- FORTIFY_SOURCE 检测到缓冲区溢出
- 堆损坏被 malloc_debug 检测到
- 断言失败 (`assert()`)

### 3.2 tombstone 表现
```
signal 6 (SIGABRT), code -6 (SI_TKILL), fault addr --------
Abort message: '...'
```

### 3.3 常见根因
1. **堆损坏**：double-free、buffer overflow 被检测到
2. **断言失败**：开发阶段的 assert 未移除
3. **FORTIFY 失败**：`memcpy`/`strcpy` 等函数越界
4. **JNI 检查失败**：JNIEnv 检测到非法操作

### 3.4 Abort message 分析
Abort message 是定位根因的关键：
```
Abort message: 'art/runtime/java_vm_ext.cc:xxx: JNI DETECTED ERROR IN APPLICATION: use of deleted global reference'
```
→ JNI 使用了已删除的全局引用

```
Abort message: 'libc: Fatal signal 11 (SIGSEGV) ...'
```
→ 实际是 SIGSEGV 被包装为 abort

## 4. SIGBUS (Signal 7) — 总线错误

### 4.1 触发条件
- 内存对齐错误（访问非对齐地址）
- mmap 文件被截断后访问
- 物理地址访问失败（硬件相关）

### 4.2 tombstone 表现
```
signal 7 (SIGBUS), code 1 (BUS_ADRALN), fault addr 0x7f123457
```
→ 地址对齐错误

```
signal 7 (SIGBUS), code 4 (BUS_OBJERR), fault addr 0x7f123000
```
→ 硬件/对象错误（通常是 mmap 文件被截断）

### 4.3 常见根因
1. **对齐问题**：ARM64 对内存对齐要求严格
2. **mmap 文件被删除/截断**：文件被其他进程修改
3. **JNI 直接操作内存**：未正确处理对齐

## 5. SIGFPE (Signal 8) — 算术错误

### 5.1 触发条件
- 除以零
- 整数溢出（某些架构）

### 5.2 tombstone 表现
```
signal 8 (SIGFPE), code 1 (FPE_INTDIV), fault addr 0x1234
```

### 5.3 常见根因
- 除零错误（通常是计算逻辑 bug）
- 音频/图像处理中的数值溢出

## 6. SIGILL (Signal 4) — 非法指令

### 6.1 触发条件
- 执行非法 CPU 指令
- 代码段被损坏
- 跳转到非代码地址执行

### 6.2 tombstone 表现
```
signal 4 (SIGILL), code 1 (ILL_ILLOPC), fault addr 0x12345678
```

### 6.3 常见根因
1. **代码段损坏**：内存溢出覆盖了代码区域
2. **架构不匹配**：在 ARMv7 上执行 ARMv8 指令
3. **JIT 编译器 bug**：动态生成的代码有误
4. **栈溢出返回**：函数返回地址被覆盖

## 7. 其他信号

| 信号 | 编号 | 含义 | 常见场景 |
|------|------|------|----------|
| SIGTRAP | 5 | 断点/跟踪 | ptrace 附加、__builtin_trap() |
| SIGSTKFLT | 16 | 协处理器栈错误 | 罕见，通常是栈溢出 |
| SIGSYS | 31 | 非法系统调用 | seccomp 过滤、syscall 不存在 |

## 8. 分析要点

### 8.1 信号分析优先级
1. 先看 signal 编号和 code
2. 看 fault addr（是否为 0x0 = 空指针）
3. 看 backtrace（哪个函数出错）
4. 看 Abort message（如果是 SIGABRT）
5. 看寄存器状态

### 8.2 fault addr 分析
| fault addr | 含义 |
|------------|------|
| 0x0 ~ 0xFFF | 空指针解引用 |
| 小地址 (0x1~0xFF) | 结构体成员偏移（基指针为 NULL） |
| 栈地址范围 | 栈溢出 |
| 已释放的堆地址 | UAF |
| 完全无效地址 | 野指针 |

### 8.3 误判陷阱
1. **SIGABRT 不一定是主动 abort**：可能是堆损坏检测后的被动终止
2. **SIGSEGV code 1 vs code 2**：MAPERR 和 ACCERR 的根因完全不同
3. **fault addr 不是代码地址**：是数据访问地址，backtrace 中的 PC 才是代码地址
