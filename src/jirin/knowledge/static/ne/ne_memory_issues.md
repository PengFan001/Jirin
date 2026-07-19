# NE 内存相关问题

## 1. 内存问题分类

### 1.1 常见内存错误
| 类型 | 信号 | 检测方式 | 难度 |
|------|------|----------|------|
| Use After Free (UAF) | SIGSEGV | 困难，地址可能已被重用 | 高 |
| Double Free | SIGABRT | malloc_debug/ASAN | 中 |
| Buffer Overflow (Heap) | SIGABRT/SIGSEGV | FORTIFY/ASAN | 中 |
| Stack Buffer Overflow | SIGSEGV/SIGABRT | Stack Protector | 中 |
| Memory Leak | 不崩溃，OOM 终止 | 需要长时间监控 | 高 |
| Uninitialized Memory | 不确定 | ASAN/MSAN | 高 |

## 2. Use After Free (UAF)

### 2.1 产生机制
```
1. 分配内存 A (malloc/new)
2. 释放内存 A (free/delete)
3. 内存 A 被重新分配给其他用途（或被回收）
4. 代码仍通过旧指针访问 A
5. 如果 A 已被回收 → SIGSEGV (MAPERR)
6. 如果 A 已被重用 → 读取到错误数据 → 后续崩溃
```

### 2.2 tombstone 特征
```
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x7f12345678
    backtrace:
      #00 pc 0x1234  /lib/libexample.so (processData+0x20)
      #01 pc 0x5678  /lib/libexample.so (callback+0x10)
```
→ fault addr 在堆范围内但已释放

### 2.3 典型场景
1. **回调中的 UAF**：对象已销毁但回调仍持有其指针
2. **容器迭代器失效**：容器被修改后仍使用旧迭代器
3. **多线程 UAF**：线程 A 释放对象，线程 B 仍在使用
4. **JNI UAF**：Java 对象被 GC 回收但 Native 层仍持有指针

### 2.4 分析方法
- 查看 fault addr 是否在已释放的堆范围内
- 查看 backtrace 中是否有回调/异步操作
- 使用 ASAN 复现（`-fsanitize=address`）

## 3. Double Free

### 3.1 产生机制
```
1. 分配内存 A
2. free(A)
3. free(A)  ← 第二次释放
4. 堆管理器检测到异常 → abort()
```

### 3.2 tombstone 特征
```
signal 6 (SIGABRT), code -6 (SI_TKILL), fault addr --------
Abort message: '*** Error in `/system/bin/my_service': double free or corruption (fasttop): 0x7f12345678 ***'
```

### 3.3 典型场景
1. **异常路径 double free**：正常路径已释放，异常路径再次释放
2. **多线程竞争**：两个线程同时释放同一对象
3. **智能指针循环引用**：shared_ptr 循环引用 + 手动 reset

### 3.4 与 UAF 的区别
- Double Free：立即 abort，Abort message 明确
- UAF：可能延迟崩溃，fault addr 可能已被重用

## 4. Buffer Overflow

### 4.1 Heap Buffer Overflow
```
1. 分配 N 字节
2. 写入超过 N 字节
3. 覆盖相邻堆块的元数据或数据
4. 后续 malloc/free 检测到损坏 → abort()
```

### 4.2 tombstone 特征
```
signal 6 (SIGABRT), code -6 (SI_TKILL), fault addr --------
Abort message: 'heap-buffer-overflow: write of size 8 at 0x7f12345690'
```
或（FORTIFY 检测）：
```
signal 6 (SIGABRT), code -6 (SI_TKILL), fault addr --------
Abort message: 'FORTIFY failed: memcpy: prevented 100-byte write into 50-byte buffer'
```

### 4.3 Stack Buffer Overflow
```
1. 函数局部变量分配在栈上
2. 写入超过缓冲区大小
3. 覆盖栈上的返回地址/保存的寄存器
4. 函数返回时跳转到错误地址 → SIGSEGV/SIGILL
```

### 4.4 Stack Canary 检测
```
signal 6 (SIGABRT), code -6 (SI_TKILL), fault addr --------
Abort message: 'stack corruption detected by canary'
```

## 5. Memory Leak

### 5.1 产生机制
```
1. 分配内存 (malloc/new)
2. 所有指向该内存的指针丢失
3. 内存永远无法被释放
4. 进程 RSS 持续增长
5. 最终触发 OOM Killer 或 LowMemoryKiller
```

### 5.2 不直接导致 tombstone
Memory leak 不会直接产生 crash，但会导致：
- 进程 RSS 持续增长
- 系统内存压力增大
- 最终被 LMK 杀死（产生 `oom_kill` 日志）
- 或者分配失败返回 NULL → 后续空指针崩溃

### 5.3 检测方法
- `/proc/PID/smaps` 查看内存分布
- `dumpsys meminfo <pid>` 查看 Java/Native/其他内存
- ASAN leak 检测（`detect_leaks=1`）
- Malloc Debug（`libc.debug.malloc.options`）

## 6. Android 内存保护机制

### 6.1 FORTIFY_SOURCE
```
system/core/libc/include/sys/cdefs.h
  → __BIONIC_FORTIFY 宏
  → 编译时替换 memcpy/strcpy 等为安全版本
  → 运行时检查缓冲区大小
  → 越界 → abort()
```

### 6.2 Stack Protector
```
frameworks/base/core/jni/Android.mk
  → -fstack-protector-strong
  → 在函数入口放置 canary 值
  → 函数返回前检查 canary 是否被覆盖
  → 被覆盖 → abort()
```

### 6.3 ASAN (Address Sanitizer)
```
编译时：-fsanitize=address
运行时：拦截所有内存访问
  → 维护 shadow memory
  → 每次访问检查 shadow
  → 检测到非法访问 → 立即报告
```

### 6.4 HWASan (Hardware ASAN, ARM64 TBI)
```
利用 ARM64 Top Byte Ignore 特性
  → 指针高位存储 tag
  → 内存分配时分配 tag
  → 访问时检查 tag 匹配
  → 不匹配 → 报告错误
```

## 7. 分析要点

### 7.1 内存问题定位流程
1. 看 signal 和 Abort message → 确定问题类型
2. 看 backtrace → 确定崩溃位置
3. 如果是 SIGABRT + 堆损坏 → 搜索 "Error in" 或 "detected"
4. 如果是 SIGSEGV + 堆地址 → 可能是 UAF
5. 如果不崩溃但 OOM → 检查内存泄漏

### 7.2 常见误判
1. **UAF 的 fault addr 看起来像有效地址**：因为它可能已被重新分配
2. **Double Free 的 backtrace 指向第二次 free，不是第一次**
3. **Buffer Overflow 的崩溃点可能不在溢出点，而在后续的 malloc/free**
4. **Memory Leak 不会直接崩溃，需要结合 meminfo 分析**
