# system_server 崩溃分析

## 1. system_server 的重要性

### 1.1 角色
system_server 是 Android 系统的核心进程，承载了所有系统服务（AMS、WMS、PMS 等）。它的崩溃等同于手机重启。

### 1.2 关键服务
| 服务 | 功能 | 崩溃影响 |
|------|------|----------|
| ActivityManagerService | 应用生命周期管理 | 所有应用失控 |
| WindowManagerService | 窗口管理 | UI 系统崩溃 |
| PackageManagerService | 包管理 | 安装/卸载异常 |
| InputManagerService | 输入事件分发 | 触摸失效 |
| PowerManagerService | 电源管理 | 休眠/唤醒异常 |

### 1.3 关键源码路径
```
frameworks/base/services/core/java/com/android/server/SystemServer.java
  → 启动所有系统服务
  → main() → startBootstrapServices() → startCoreServices() → startOtherServices()

frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
frameworks/base/services/core/java/com/android/server/wm/WindowManagerService.java
```

## 2. system_server 崩溃类型

### 2.1 Watchdog 触发
```
原因：关键线程阻塞超过 60s
日志特征：Watchdog: *** WATCHDOG KILLING SYSTEM PROCESS ***
详见 watchdog.md
```

### 2.2 Native Crash
```
原因：system_server 中的 Native 代码崩溃
日志特征：
  signal 11 (SIGSEGV), code 1 (SEGV_MAPERR)
  pid: XXXX, tid: YYYY, name: main >>> system_server <<<
  backtrace:
    #00 pc ... /system/lib64/libandroid_runtime.so
```

### 2.3 Java Crash (FATAL)
```
原因：未捕获的 Java 异常
日志特征：
  FATAL EXCEPTION: main
  Process: system_server (pid: XXXX)
  java.lang.RuntimeException: ...
    at com.android.server.xxx
```

### 2.4 OOM Kill
```
原因：system_server 内存超限被 LMK 杀死
日志特征：
  lmkd: kill pid=XXXX (system_server) adj=-900
```

## 3. system_server 崩溃日志分析

### 3.1 崩溃前日志
```
# 查看崩溃前的系统状态
logcat -b all | grep -E "system_server|Watchdog|lmkd|FATAL" | tail -100
```

### 3.2 Tombstone 分析
```
# system_server 的 tombstone
/data/tombstones/tombstone_XX
Cmdline: system_server
pid: XXXX, tid: YYYY
signal 11 (SIGSEGV)
  backtrace:
    #00 pc ... /system/lib64/libandroid_runtime.so (JNI_function+0x10)
    #01 pc ... /system/lib64/libandroid_runtime.so
    #02 pc ... /apex/.../libart.so (art_method+0x20)
```

### 3.3 Java Crash 分析
```
FATAL EXCEPTION: main
Process: system_server (pid: 1234)
java.lang.NullPointerException: Attempt to invoke virtual method on null
  at com.android.server.am.ActivityManagerService.handleSomething(AMS.java:5678)
  at android.os.Handler.dispatchMessage(Handler.java:106)
```
→ 定位到具体的 AMS 代码行

## 4. system_server 重启后的影响

### 4.1 重启流程
```
system_server 崩溃
  → init 进程检测到
  → 重启 Zygote
  → 重启 system_server
  → 所有应用进程断开 Binder 连接
  → 应用收到 DeadObjectException
  → 应用重新绑定系统服务
```

### 4.2 应用侧日志
```
# 应用侧看到的日志
AndroidRuntime: FATAL EXCEPTION: main
  android.os.DeadObjectException
    at android.os.BinderProxy.transact(Native Method)
    at android.app.IActivityManager$Stub$Proxy.xxx

# 或者
ActivityManager: Process com.example.app (pid 12345) has died
```

### 4.3 数据影响
- 应用进程可能被杀
- 未保存的数据可能丢失
- 系统设置通常不受影响（持久化在文件中）

## 5. 常见 system_server 崩溃模式

### 5.1 厂商定制代码引入的 bug
```
场景：厂商在 system_server 中添加自定义服务
→ 自定义服务有 bug
→ 导致 system_server 崩溃
特征：backtrace 中出现厂商自定义的 SO 或 Java 类
```

### 5.2 SELinux 策略问题
```
场景：SELinux 策略阻止 system_server 访问某资源
→ SecurityException
→ 如果未捕获 → system_server 崩溃
日志特征：avc: denied { xxx } for pid=XXX comm="system_server"
```

### 5.3 数据库损坏
```
场景：system_server 的 SQLite 数据库损坏
→ SQLiteFullException / SQLiteDatabaseCorruptException
→ 如果未捕获 → system_server 崩溃
日志特征：sqlite database is corrupt
```

## 6. 分析要点

### 6.1 分析流程
1. 确认崩溃类型（Watchdog/Native/Java/OOM）
2. 查看 tombstack/Java stack → 定位崩溃代码
3. 查看崩溃前的日志 → 确定触发条件
4. 查看 backtrace 中的库 → 确认是 AOSP 还是厂商代码
5. 查看重启后的日志 → 确认是否恢复

### 6.2 关键命令
```bash
# 查看 system_server tombstone
adb shell ls -la /data/tombstones/
adb pull /data/tombstones/tombstone_XX

# 查看 system_server 内存
adb shell dumpsys meminfo system_server

# 查看系统服务状态
adb shell dumpsys activity services
```

### 6.3 误判陷阱
1. **system_server 重启不等于手机变砖**：init 会自动重启
2. **DeadObjectException 不一定意味着 system_server 崩溃**：可能是单个服务重启
3. **厂商代码崩溃和 AOSP 代码崩溃需要区分对待**
4. **system_server 内存泄漏是长期问题**：需要长时间监控 PSS 增长趋势
