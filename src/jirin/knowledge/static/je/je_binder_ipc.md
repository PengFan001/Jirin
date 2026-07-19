# Binder/IPC 相关异常

## 1. Binder 机制概述

### 1.1 Binder 在 Android 中的角色
Android 的进程间通信（IPC）基于 Binder 机制。所有跨进程调用（ContentProvider、Service、SystemService）都通过 Binder 传输。

### 1.2 关键源码路径
```
frameworks/base/core/java/android/os/Binder.java        — Java 层 Binder 基类
frameworks/base/core/java/android/os/BinderProxy.java   — Binder 代理
frameworks/base/core/java/android/os/Parcel.java        — 序列化容器
frameworks/native/libs/binder/                          — Native 层 Binder 实现
drivers/staging/android/uapi/binder.h                   — 内核驱动接口
```

## 2. 常见 Binder 异常

### 2.1 DeadObjectException
```
android.os.DeadObjectException: Transaction failed on small parcel;
  remote process probably died
```
**含义**：目标进程已死亡，Binder 连接断开
**源码链路**：
```
BinderProxy.transact()
  → IPCThreadState::transact()
  → BpBinder::transact()
  → IPCThreadState::waitForResponse()
  → 收到 BR_DEAD_BINDER 回复
  → 抛出 DeadObjectException
```
**分析要点**：
- 根因在远端进程，需要查看目标进程的日志
- 常见于 system_server 进程崩溃后，所有依赖它的进程都报 DeadObjectException

### 2.2 TransactionTooLargeException
```
android.os.TransactionTooLargeException: data parcel size xxx bytes
```
**含义**：Binder 传输数据超过限制（通常 1MB）
**源码链路**：
```
BinderProxy.transact()
  → Parcel.writeToRemote()
  → 内核 binder 驱动检查数据大小
  → 超过 buffer 剩余空间
  → 返回 BR_FAILED_REPLY
  → 抛出 TransactionTooLargeException
```
**常见场景**：
- `Activity.onSaveInstanceState()` 保存过多数据
- `Intent` 传递大 Bundle
- `ContentProvider` 查询返回过多数据

### 2.3 SecurityException（Binder 权限检查）
```
java.lang.SecurityException: Permission Denial:
  opening provider com.xxx.Provider from ProcessRecord
  (pid=xxx, uid=xxx) requires android.permission.xxx
```
**源码链路**：
```
ActivityManagerService.checkPermission()
  → AppOpsManager.noteOp()
  → PackageManager.checkPermission()
  → 权限不匹配 → throw SecurityException
```

### 2.4 RemoteException 子类
| 异常类 | 含义 | 常见原因 |
|--------|------|----------|
| DeadObjectException | 远端进程死亡 | 目标进程崩溃或被杀 |
| TransactionTooLargeException | 数据过大 | Bundle/Intent 数据超限 |
| ServiceSpecificException | 服务特定错误 | 服务端自定义异常 |
| OnAlreadyHolderedException | 状态冲突 | 重复操作 |

## 3. ContentProvider 相关异常

### 3.1 Provider 查询失败
```
java.lang.IllegalArgumentException: Unknown URL content://xxx
java.lang.SecurityException: Permission Denial: reading provider
```
**源码链路**：
```
ContentResolver.query()
  → ContentProviderProxy.query()
  → Binder.transact()
  → ContentProviderNative.onTransact()
  → ContentProvider.query()
  → 若 URI 不匹配 → IllegalArgumentException
```

### 3.2 Provider 初始化失败
```
java.lang.RuntimeException: Unable to get provider xxx:
  java.lang.ClassNotFoundException
```
**源码链路**：
```
ActivityThread.installProvider()
  → context.getClassLoader().loadClass()
  → 类加载失败 → ClassNotFoundException
  → 包装为 RuntimeException
```

## 4. 分析要点

### 4.1 Binder 异常的识别
1. 堆栈中出现 `BinderProxy.transact()` 或 `Binder.transact()`
2. 异常消息包含 "remote process probably died" 或 "data parcel size"
3. 堆栈跨越多个进程（通过 PID 判断）

### 4.2 责任归属判断
- **DeadObjectException**：责任在远端进程，需要找到远端进程为什么死亡
- **TransactionTooLargeException**：
  - 如果是 onSaveInstanceState → 应用自身问题
  - 如果是 ContentProvider 查询 → 可能是 Provider 端返回数据过多
- **SecurityException**：
  - 缺少权限声明 → 应用自身问题
  - 系统权限变更 → 系统版本兼容问题

### 4.3 误判陷阱
1. **DeadObjectException 级联**：一个进程崩溃可能导致多个进程报 DeadObjectException，不要误判为多个问题
2. **TransactionTooLarge 的 1MB 限制**：是所有 Binder 事务共享的缓冲区，不是单个事务
3. **Binder 线程池耗尽**：默认 16 个线程，如果全部被占用，新的 Binder 调用会阻塞（不是异常，但会导致 ANR）
