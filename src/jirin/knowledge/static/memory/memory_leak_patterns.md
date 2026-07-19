# 内存泄漏常见模式

## 1. Java 层常见泄漏模式

### 1.1 Activity 泄漏
**模式**：Activity 销毁后仍被持有
```java
// 错误：静态变量持有 Activity 引用
private static Activity sActivity;
sActivity = this;  // Activity 无法被 GC

// 错误：单例持有 Activity Context
public class DataManager {
    private static DataManager instance;
    private Context context;  // 应该用 ApplicationContext
}
```
日志特征：`LeakCanary` 报告或 `hprof` 中 Activity 实例数 > 预期

### 1.2 Handler 泄漏
**模式**：非静态内部类的 Handler 持有外部 Activity 引用
```java
// 错误：非静态内部类 Handler
private Handler mHandler = new Handler() {
    @Override
    public void handleMessage(Message msg) {
        // 持有 MainActivity.this 引用
    }
};
mHandler.sendMessageDelayed(msg, 60000);  // Activity 销毁后消息仍在队列
```
源码链路：
```
android.os.Handler → Message.target = Handler
android.os.MessageQueue → 持有 Message 链表
→ Activity 销毁 → Handler 仍被 Message 引用
→ Activity 无法 GC
```

### 1.3 监听器/回调泄漏
**模式**：注册了监听器但未在 onDestroy 中注销
```java
// 错误：注册但未注销
ContentResolver.registerContentObserver(uri, false, observer);
// 忘记在 onDestroy 中 unregisterContentObserver
```

### 1.4 ThreadLocal 泄漏
**模式**：线程池中的 ThreadLocal 未 remove
```java
// 线程池复用线程，ThreadLocal 值不会自动清理
private static ThreadLocal<Object> sLocal = new ThreadLocal<>();
sLocal.set(new MyObject());  // 线程池中的线程复用 → 对象泄漏
```

## 2. Native 层常见泄漏模式

### 2.1 JNI 引用泄漏
**模式**：创建了 JNI 全局引用但未释放
```c
// 错误：创建全局引用但未释放
jclass cls = (*env)->FindClass(env, "com/example/MyClass");
jclass gCls = (*env)->NewGlobalRef(env, cls);
// 忘记在适当时机调用 DeleteGlobalRef(env, gCls)
```
源码链路：
```
art/runtime/jni/jni_env_ext.cc
  → NewGlobalRef() → 添加到全局引用表
  → 表持续增长 → JNI Global Reference Table 溢出
  → 日志: "JNI ERROR: global reference table overflow"
```

### 2.2 C/C++ malloc/new 泄漏
**模式**：分配内存后未释放
```c
char* buffer = malloc(1024);
// 使用 buffer...
// 某个 return 路径忘记 free(buffer)
return result;  // buffer 泄漏
```

### 2.3 文件描述符泄漏
**模式**：打开文件/socket 但未关闭
```java
// 错误：未使用 try-with-resources
FileInputStream fis = new FileInputStream(file);
// 如果后续代码抛异常，fis 不会被关闭
```
日志特征：
```
Too many open files
  at java.io.FileInputStream.open0(Native Method)
```
或：
```
Unable to create new file: java.io.IOException: Too many open files
```

## 3. 图形内存泄漏

### 3.1 Bitmap 泄漏
**模式**：Bitmap 未 recycle 或未 GC 回收
```java
// Android 8.0+ Bitmap 像素数据在 Native Heap
Bitmap bitmap = Bitmap.createBitmap(1920, 1080, Bitmap.Config.ARGB_8888);
// 忘记 bitmap.recycle() 或让 GC 回收
// Native Heap 持续增长
```

### 3.2 Surface/GraphicBuffer 泄漏
**模式**：Surface 未释放导致 GraphicBuffer 泄漏
```
GraphicBuffer 泄漏通常发生在：
- SurfaceView 未正确销毁
- TextureView 的 SurfaceTexture 未释放
- 自定义 View 中的 Canvas 未释放
```
日志特征：
```
dumpsys meminfo 中 Graphics 项异常增长
```

## 4. Binder 内存泄漏

### 4.1 Binder 缓冲区泄漏
**模式**：Binder 事务过大或 Binder 对象未释放
```
TransactionTooLargeException 的根因：
Binder 缓冲区大小限制为 1MB（每个进程）
  → 大量数据通过 Binder 传输
  → 缓冲区耗尽
  → TransactionTooLargeException
```
源码链路：
```
frameworks/native/libs/binder/ProcessState.cpp
  → IPCThreadState::transact()
  → binder_transaction_data → 数据超过 1MB
  → 返回 FAILED_TRANSACTION
```

## 5. 分析要点

### 5.1 泄漏定位流程
1. `dumpsys meminfo` 确认哪类内存增长
2. Java Heap → hprof 分析 → 找 GC Root 引用链
3. Native Heap → Malloc Debug / ASAN → 找未释放的分配点
4. Graphics → 检查 Bitmap/Surface 使用
5. FD → `ls -la /proc/PID/fd` 查看打开的文件

### 5.2 常见误判
1. **缓存不等于泄漏**：LRU Cache 有上限，不会无限增长
2. **Bitmap 在 Native Heap**：Android 8.0+ 不要只看 Java Heap
3. **WebView 内存**：WebView 有自己的内存管理，单独统计
4. **多进程应用**：每个进程独立计算，不要简单加总
