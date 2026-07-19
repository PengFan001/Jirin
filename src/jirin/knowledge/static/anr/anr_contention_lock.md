# 锁竞争与主线程阻塞

## 1. 锁竞争导致 ANR 的机制

### 1.1 典型场景
主线程需要获取一个锁，但该锁被其他线程持有，且持有锁的线程长时间未释放。

### 1.2 traces 中的表现
```
"main" prio=5 tid=1 Blocked
  | group="main" sCount=1 dsCount=0
  at com.example.app.DataManager.getData(DataManager.java:80)
  - waiting to lock <0x0a1b2c3d> (a java.lang.Object) held by thread 15
  at com.example.app.MainActivity.updateUI(MainActivity.java:120)

"Thread-15" prio=5 tid=15 Runnable
  | group="main" sCount=0 dsCount=0
  at com.example.app.DataManager.processData(DataManager.java:95)
  - locked <0x0a1b2c3d> (a java.lang.Object)
  at com.example.app.BackgroundTask.run(BackgroundTask.java:45)
```

## 2. 死锁场景

### 2.1 经典死锁
```
Thread A: 持有 Lock1，等待 Lock2
Thread B: 持有 Lock2，等待 Lock1
→ 两者互相等待，永远不会释放
```

### 2.2 traces 中的死锁表现
```
"main" prio=5 tid=1 Blocked
  - waiting to lock <0xAAA> held by thread 15

"Worker-15" prio=5 tid=15 Blocked
  - waiting to lock <0xBBB> held by thread 1  (main)
```
→ 循环等待 = 死锁

## 3. 主线程阻塞的其他模式

### 3.1 SharedPreferences.apply()
```
frameworks/base/core/java/android/app/SharedPreferencesImpl.java
  → apply() → QueuedWork.add(work)
  → Activity.onPause() → QueuedWork.waitToFinish()
  → 等待所有 apply() 的磁盘写入完成
  → 如果磁盘慢 → 主线程阻塞 → ANR
```
traces 特征：
```
"main" prio=5 tid=1 Native
  at android.os.MessageQueue.nativePollOnce(Native Method)
  at QueuedWork.waitToFinish(QueuedWork.java:xxx)
```

### 3.2 主线程 Handler 消息堆积
```
"main" prio=5 tid=1 Blocked
  at android.os.MessageQueue.enqueueMessage(MessageQueue.java:xxx)
  at android.os.Handler.sendMessageDelayed(Handler.java:xxx)
```
→ Handler 消息队列中有大量待处理消息

### 3.3 GC 暂停
```
"main" prio=5 tid=1 WaitingForGcToComplete
  at java.lang.Runtime.gc(Native Method)
```
→ 等待 GC 完成，通常伴随内存压力

## 4. 分析要点

### 4.1 锁竞争分析步骤
1. 找到 main 线程的 "waiting to lock" 信息
2. 记录锁地址（如 `<0x12345678>`）
3. 在 traces 中搜索该锁地址
4. 找到持有锁的线程
5. 分析持有锁的线程在做什么

### 4.2 责任归属
- 应用自身锁设计问题 → 应用责任
- 系统服务持有锁导致 → 可能是系统问题
- 第三方 SDK 内部锁竞争 → SDK 责任

### 4.3 误判陷阱
1. **锁地址格式**：不同 Android 版本的锁地址格式可能不同
2. **synchronized vs ReentrantLock**：traces 中只显示 synchronized 的锁信息
3. **线程名可能变化**：不要只搜索 "main"，也要搜索 tid=1
