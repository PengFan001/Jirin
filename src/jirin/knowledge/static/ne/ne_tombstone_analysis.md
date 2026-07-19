# Tombstone 结构与解读

## 1. Tombstone 生成机制

### 1.1 触发流程
```
进程收到致命信号
  → kernel 发送信号
  → debuggerd (tombstoned) 捕获
  → 收集进程信息（寄存器、backtrace、maps）
  → 写入 /data/tombstones/tombstone_XX
  → 终止进程
```

### 1.2 关键源码路径
```
system/core/debuggerd/tombstoned/tombstoned.cpp    — tombstone 守护进程
system/core/debuggerd/debuggerd.cpp                 — 信号拦截入口
system/core/debuggerd/util.cpp                      — 信息收集工具
system/core/debuggerd/handler/handler.cpp           — 信号处理器
frameworks/native/libs/debuggerd/debuggerd_client.cpp — 客户端接口
```

## 2. Tombstone 文件结构

### 2.1 典型 tombstone 格式
```
*** *** *** *** *** *** *** *** *** *** *** *** *** *** *** ***
Build fingerprint: 'google/oriole/oriole:14/xxx:user/release-keys'
Revision: 'MP1.0'
ABI: 'arm64'
Timestamp: 2024-01-15 10:30:45.123456789+0800
Process uptime: 12s
Cmdline: com.example.app
pid: 12345, tid: 12367, name: Thread-5  >>> com.example.app <<<
uid: 10123
signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0
    x0  0000000000000000  x1  0000000000000001  x2  0000000000000002
    ...
    sp  0000007f12345678  pc  0000007f9876abcd  pstate  00000000
    backtrace:
      #00 pc 0x0000000000123456  /system/lib64/libexample.so (function_name+0x10)
      #01 pc 0x0000000000789abc  /system/lib64/libexample.so (caller_func+0x20)
      #02 pc 0x0000000000abcdef  /apex/com.android.art/lib64/libart.so (art_method+0x30)
    ...
    memory near crash:
      [stack]  7f12345000-7f12346000  rwxp  ...
    ...
```

### 2.2 各字段含义

| 字段 | 含义 | 分析价值 |
|------|------|----------|
| Build fingerprint | 系统版本 | 确认 Android 版本和编译信息 |
| ABI | 架构 (arm/arm64/x86) | 决定使用哪种 addr2line |
| Cmdline | 进程名 | 确认崩溃进程 |
| pid/tid/name | 线程信息 | 确认崩溃线程 |
| signal/code/fault addr | 信号详情 | 定位根因类型 |
| 寄存器 (x0-x30, sp, pc) | CPU 状态 | 分析崩溃时上下文 |
| backtrace | 调用栈 | 定位崩溃代码路径 |
| maps | 内存映射 | 确认 SO 库加载地址 |
| open files | 打开的文件 | 排查资源泄漏 |

## 3. Backtrace 解读

### 3.1 格式说明
```
#00 pc 0x0000000000123456  /path/to/lib.so (symbol+offset)
```
- `#00`：栈帧编号（0 = 崩溃点）
- `pc`：程序计数器值（代码地址）
- `/path/to/lib.so`：所属库文件
- `(symbol+offset)`：符号名 + 偏移（如果有符号表）

### 3.2 有符号 vs 无符号
**有符号**：
```
#00 pc 0x1234  /lib/libexample.so (MyClass::myMethod()+0x10)
```
→ 可以直接看到函数名

**无符号**：
```
#00 pc 0x1234  /lib/libexample.so
```
→ 需要 addr2line 解析

### 3.3 跨库调用链
```
#00 pc 0x1234  /system/lib64/libnative.so     — Native 代码崩溃
#01 pc 0x5678  /system/lib64/libnative.so     — Native 调用链
#02 pc 0xabcd  /apex/.../libart.so            — ART JNI 桥接
#03 pc 0xef01  /system/framework/framework.jar — Java 调用者
```
→ 从 Native 崩溃追溯到 Java 调用者

## 4. 寄存器分析

### 4.1 ARM64 关键寄存器
| 寄存器 | 用途 | 分析价值 |
|--------|------|----------|
| x0-x7 | 函数参数 | 查看传入崩溃函数的参数 |
| x8 | 间接返回值 | 结构体返回值 |
| x29 (FP) | 帧指针 | 栈回溯 |
| x30 (LR) | 链接寄存器 | 返回地址 |
| SP | 栈指针 | 栈位置 |
| PC | 程序计数器 | 崩溃指令地址 |

### 4.2 通过寄存器定位问题
```
x0 = 0x0000000000000000  → 第一个参数为 NULL（空指针）
x1 = 0x0000000000000010  → 偏移量 16（结构体成员偏移）
fault addr = 0x10        → 访问 NULL + 16 = 结构体成员偏移
```
→ 结论：某个对象的指针为 NULL，访问了其 offset=16 的成员

## 5. Maps 文件分析

### 5.1 格式
```
address           perms offset   dev   inode  pathname
7f12345000-7f12346000 r-xp 00001000 fc:01 12345  /system/lib64/libexample.so
```

### 5.2 分析用途
- 确认 SO 库的加载基地址
- 计算实际偏移 = pc - 基地址
- 检查是否有权限异常（如 RWX 页面）

## 6. 分析要点

### 6.1 标准分析流程
1. 读取 signal + code + fault addr → 确定崩溃类型
2. 读取 backtrace → 确定崩溃代码路径
3. 用 addr2line 解析无符号帧 → 获取源码位置
4. 查看寄存器 → 理解崩溃时上下文
5. 查看 maps → 确认 SO 版本是否正确
6. 查看 open files → 排查资源问题

### 6.2 常见 tombstone 模式
| 模式 | 特征 | 根因 |
|------|------|------|
| 空指针 | SIGSEGV, fault addr 0x0 | 未检查 NULL |
| JNI 错误 | SIGABRT + JNI DETECTED ERROR | JNI 使用不当 |
| 堆损坏 | SIGABRT + double free detected | 内存管理错误 |
| 栈溢出 | SIGSEGV + SP 在栈区域外 | 递归过深/大局部变量 |
| SO 版本不匹配 | backtrace 中有未知符号 | OTA 不完整/混用库 |

### 6.3 误判陷阱
1. **tombstone 中的 pc 是崩溃指令地址，不是调用者地址**
2. **fault addr 是数据地址，不是代码地址**
3. **多个 tombstone 文件可能属于同一问题的不同表现**
4. **Build fingerprint 不匹配 → SO 库版本可能不对**
