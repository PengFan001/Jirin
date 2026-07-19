# 常见 Java 异常类型与源码链路

## 1. NullPointerException (NPE)

### 1.1 产生原因
对 null 引用调用实例方法或访问实例字段。

### 1.2 Android 中的典型场景

**场景 A：View 未初始化**
```java
// 缺少 setContentView() 或 findViewById() 返回 null
TextView tv = findViewById(R.id.my_text);  // tv 为 null
tv.setText("hello");  // NPE
```
堆栈特征：`at com.xxx.Activity.onCreate()` 中直接调用未初始化对象

**场景 B：生命周期时序问题**
```java
// Activity 已 destroy 后异步回调到达
@Override
protected void onDestroy() {
    super.onDestroy();
    // 异步任务回调此时 activity 已为 null
}
```
堆栈特征：回调方法中出现 NPE，且涉及 Fragment/Activity 生命周期方法

**场景 C：Bundle 数据缺失**
```java
String value = getIntent().getStringExtra("key");  // 返回 null
value.length();  // NPE
```

### 1.3 源码链路
```
NullPointerException (java.lang)
  → Thread.dispatchUncaughtException()
  → Thread.getUncaughtExceptionHandler()
  → RuntimeInit$KillingHandler.uncaughtException()
  → RuntimeInit.logUncaughtException()
    → DropBox.addText()  // 记录到 dropbox
  → Process.killProcess(Process.myPid())
```

### 1.4 日志特征
```
java.lang.NullPointerException: Attempt to invoke virtual method
  'xxx.yyy()' on a null object reference
```
或
```
java.lang.NullPointerException: Attempt to read from field
  'xxx.yyy zzz' on a null object reference
```

---

## 2. IllegalStateException

### 2.1 产生原因
在对象不处于允许调用该方法的状态时调用方法。

### 2.2 Android 中的典型场景

**场景 A：Fragment 事务在 onSaveInstanceState 之后**
```
java.lang.IllegalStateException: Can not perform this action after onSaveInstanceState
```
源码：`FragmentManager.enqueueAction()` 检查 `mStateSaved` 标志

**场景 B：Activity 已销毁后操作**
```
java.lang.IllegalStateException: Activity has been destroyed
```
源码：`FragmentHostCallback.onHasFragments()` 检查 Activity 状态

**场景 C：数据库操作异常**
```
java.lang.IllegalStateException: Cannot perform this operation because the connection pool has been closed.
```

### 2.3 源码链路
```
frameworks/base/core/java/android/app/FragmentManager.java
  → enqueueAction() / checkStateLoss()
  → throw new IllegalStateException("Can not perform this action after onSaveInstanceState")

frameworks/base/core/java/android/app/Activity.java
  → onPostResume() / onResume() 状态管理
```

---

## 3. SecurityException

### 3.1 产生原因
尝试执行没有权限的操作。

### 3.2 Android 中的典型场景

**场景 A：缺少运行时权限**
```
java.lang.SecurityException: Permission Denial: starting Intent
  { act=android.intent.action.CALL } from ProcessRecord
  requires android.permission.CALL_PHONE
```

**场景 B：ContentProvider 权限不足**
```
java.lang.SecurityException: Permission Denial: reading
  com.xxx.Provider uri content://xxx from pid=xxx
  requires android.permission.READ_xxx
```

**场景 C：Binder 权限检查失败**
```
java.lang.SecurityException: uid xxx does not have permission to access resource
```
源码：`ActivityManagerService` 或 `ContextImpl` 中的权限检查

### 3.3 源码链路
```
frameworks/base/core/java/android/app/ContextImpl.java
  → enforceCallingPermission() / checkCallingPermission()

frameworks/base/services/core/java/com/android/server/am/ActivityManagerService.java
  → checkPermission() / startServiceAsUser()

frameworks/base/core/java/android/os/Binder.java
  → Binder.getCallingUid() / getCallingPid()
```

---

## 4. OutOfMemoryError (OOM)

### 4.1 产生原因
JVM 无法分配对象，因为内存不足。

### 4.2 Android 中的典型场景

**场景 A：Bitmap 过大**
```
java.lang.OutOfMemoryError: Failed to allocate a xxx byte allocation
  with xxx free bytes and xxxMB until OOM, target footprint xxx, growth xxx
```
常见于大图片加载

**场景 B：内存泄漏积累**
```
java.lang.OutOfMemoryError: pthread_create (xxxKB stack) failed:
  Try again
```
线程数过多导致

**场景 C：Native 内存耗尽**
```
java.lang.OutOfMemoryError: Could not allocate JNI Env
```
Native 内存不足

### 4.3 源码链路
```
ART Runtime 内存分配失败
  → gc::Heap::AllocateInternal()
  → GC 尝试回收内存
  → 仍然不足
  → ThrowOutOfMemoryError()

frameworks/base/core/jni/android_util_Binder.cpp
  → JNI 层内存分配失败传播到 Java 层
```

### 4.4 日志特征
```
java.lang.OutOfMemoryError: Failed to allocate a NNNN byte allocation
  with NNNN free bytes and NNNNMB until OOM
  target footprint NNNN, growth NNNN
```
关键信息：
- `byte allocation`: 请求分配的大小
- `free bytes`: 当前可用内存
- `until OOM`: 距离 OOM 限制的剩余空间
- `target footprint`: GC 目标堆大小

---

## 5. ClassNotFoundException / NoClassDefFoundError

### 5.1 产生原因
类加载器无法找到指定的类。

### 5.2 Android 中的典型场景

**场景 A：MultiDex 问题**
```
java.lang.ClassNotFoundException: Didn't find class "xxx" on path:
  DexPathList[[zip file "/data/app/xxx"],nativeLibraryDirectories=[...]]
```
在 Android 5.0 以下，主 dex 中找不到类

**场景 B：ProGuard/R8 混淆问题**
```
java.lang.NoClassDefFoundError: xxx
```
类被混淆工具移除或重命名

**场景 C：动态加载失败**
```
java.lang.ClassNotFoundException: xxx
  at dalvik.system.BaseDexClassLoader.findClass()
```
DexClassLoader 加载外部 dex 失败

### 5.3 源码链路
```
dalvik.system.BaseDexClassLoader.findClass(String name)
  → pathList.findClass(name, suppressedExceptions)
  → DexPathList.findClass()
  → 遍历 dexFile 列表
  → 找不到 → ClassNotFoundException

libcore/dalvik/src/main/java/dalvik/system/DexPathList.java
  → findClass(String name, List<Throwable> suppressed)
```

---

## 6. RemoteException / TransactionTooLargeException

### 6.1 产生原因
Binder IPC 调用失败。

### 6.2 Android 中的典型场景

**场景 A：TransactionTooLargeException**
```
java.lang.RuntimeException: TransactionTooLargeException
  data parcel size xxx bytes
```
通过 Binder 传递的数据超过 1MB 限制（常见于 onSaveInstanceState）

**场景 B：DeadObjectException**
```
android.os.DeadObjectException: Transaction failed on small parcel;
  remote process probably died
```
目标进程已死亡

**场景 C：Service 连接断开**
```
java.lang.IllegalStateException: Service has been disconnected
```

### 6.3 源码链路
```
frameworks/base/core/java/android/os/BinderProxy.java
  → transactNative()
  → IPCThreadState::transact()
  → 内核 binder 驱动处理
  → 失败时抛出 RemoteException

frameworks/base/core/java/android/app/ActivityThread.java
  → handleSaveActivityState()  // TransactionTooLarge 常发生在此
```

### 6.4 误判陷阱

1. **TransactionTooLarge 不一定是数据太大**：可能是 Binder 缓冲区被其他进程占满
2. **DeadObjectException 的根因在远端进程**：需要查看目标进程的崩溃日志
3. **RemoteException 是基类**：很多具体的 IPC 异常都继承自它，注意区分具体子类
