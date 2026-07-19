# NE 调试工具链

## 1. addr2line — 地址解析

### 1.1 用途
将 tombstone 中的 PC 地址转换为源码文件名和行号。

### 1.2 使用方法
```bash
# 基本用法
aarch64-linux-android-addr2line -e /path/to/libexample.so 0x123456

# 带函数名解析
aarch64-linux-android-addr2line -f -e /path/to/libexample.so 0x123456

# 批量解析
aarch64-linux-android-addr2line -f -C -e /path/to/libexample.so 0x123456 0x789abc
```

### 1.3 参数说明
| 参数 | 含义 |
|------|------|
| `-e` | 指定 ELF 文件（SO 或可执行文件） |
| `-f` | 显示函数名 |
| `-C` | 反修饰（demangle）C++ 函数名 |
| `-i` | 显示内联函数信息 |

### 1.4 注意事项
- 需要与 tombstone 中的 SO 版本完全一致（Build fingerprint 匹配）
- Release 版本通常没有符号，需要使用未 strip 的 SO
- 未 strip 的 SO 通常在编译产物目录：`out/target/product/xxx/symbols/system/lib64/`

## 2. ndk-stack — NDK 堆栈解析

### 2.1 用途
直接解析 tombstone 或 logcat 中的 backtrace，自动调用 addr2line。

### 2.2 使用方法
```bash
# 从文件解析
ndk-stack -sym /path/to/symbols/ < tombstone_00

# 从 logcat 实时解析
adb logcat | ndk-stack -sym /path/to/symbols/
```

### 2.3 符号目录结构
```
symbols/
├── system/lib64/
│   ├── libexample.so      — 未 strip 的 SO（含符号）
│   └── libart.so
└── data/app/
    └── lib/arm64/
        └── libnative.so
```

## 3. ASAN (Address Sanitizer)

### 3.1 编译时启用
```makefile
# Android.bp
cc_library {
    name: "libexample",
    sanitize: {
        address: true,
    },
}

# Android.mk
LOCAL_SANITIZE := address
```

### 3.2 运行时配置
```bash
# 启用 ASAN
setprop wrap.$PACKAGE "ASAN_OPTIONS=log_path=/data/local/tmp/asan:halt_on_error=1"

# 查看 ASAN 报告
cat /data/local/tmp/asan.*
```

### 3.3 ASAN 报告格式
```
==12345==ERROR: AddressSanitizer: heap-use-after-free on address 0x7f12345678
READ of size 4 at 0x7f12345678 thread T5
    #0 0x123456 in MyClass::processData() /path/to/file.cpp:100
    #1 0x789abc in callback() /path/to/file.cpp:200

freed by thread T3 here:
    #0 0xabcdef in operator delete(void*) /path/to/asan_interceptors.cpp
    #1 0x111222 in MyClass::~MyClass() /path/to/file.cpp:50

allocated by thread T0 here:
    #0 0x333444 in operator new(unsigned long) /path/to/asan_interceptors.cpp
    #1 0x555666 in createObject() /path/to/file.cpp:30
```

### 3.4 ASAN 检测能力
| 类型 | 检测能力 |
|------|----------|
| Heap buffer overflow | ✅ 精确检测 |
| Stack buffer overflow | ✅ 精确检测 |
| Use after free | ✅ 精确检测（含分配/释放/使用位置） |
| Use after return | ✅ 可选启用 |
| Memory leak | ✅ detect_leaks=1 |
| Double free | ✅ 精确检测 |

## 4. HWASan (Hardware ASAN)

### 4.1 特点
- 利用 ARM64 TBI (Top Byte Ignore) 特性
- 性能开销比 ASAN 低（~15% vs ~100%）
- 内存开销低（~15% vs ~200%）
- 可以检测与 ASAN 相同的错误类型

### 4.2 启用
```makefile
cc_library {
    name: "libexample",
    sanitize: {
        hwaddress: true,
    },
}
```

### 4.3 限制
- 仅支持 ARM64
- 无法检测栈上小缓冲区的越界（tag 粒度为 16 字节）
- 需要 kernel 支持 TBI

## 5. Malloc Debug

### 5.1 用途
Android 内置的堆调试工具，无需重新编译。

### 5.2 启用
```bash
# 设置属性
setprop libc.debug.malloc.options "backtrace guard"

# 重启 zygote（需要 root）
stop; start
```

### 5.3 选项
| 选项 | 功能 |
|------|------|
| `backtrace` | 记录每次分配的 backtrace |
| `guard` | 在分配前后放置 guard 页 |
| `fill` | 分配时填充 0xeb，释放时填充 0xef |
| `leaks` | 跟踪未释放的内存 |

### 5.4 查看结果
```bash
# 查看内存泄漏
dumpsys meminfo --allocations <pid>

# 查看 backtrace
debuggerd -b <pid>
```

## 6. Simpleperf — 性能分析

### 6.1 用途
分析 Native 代码性能，辅助定位性能相关的 NE 问题。

### 6.2 使用方法
```bash
# 录制
simpleperf record -p <pid> -g --duration 10

# 报告
simpleperf report
```

## 7. 分析要点

### 7.1 工具选择
| 场景 | 推荐工具 |
|------|----------|
| 解析 tombstone backtrace | addr2line / ndk-stack |
| 复现 UAF/Overflow | ASAN / HWASan |
| 检测内存泄漏 | Malloc Debug + dumpsys |
| 生产环境调试 | Malloc Debug（无需重编译） |
| 性能分析 | Simpleperf |

### 7.2 工具链限制
1. **addr2line 需要匹配版本的 SO**：不同编译版本的地址不同
2. **ASAN 有性能开销**：不适合生产环境
3. **HWASan 需要 ARM64 + kernel 支持**
4. **Malloc Debug 需要 root 权限**

### 7.3 误判陷阱
1. **addr2line 结果偏移几行**：编译器优化导致，需要结合源码确认
2. **ASAN 报告中的 "unknown module"**：可能是动态加载的 SO
3. **HWASan 无法检测小缓冲区越界**：tag 粒度是 16 字节
