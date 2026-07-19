# Service/Broadcast ANR

## 1. Service ANR

### 1.1 触发条件
Service 的 `onCreate()` 或 `onStartCommand()` 执行时间超过阈值。

### 1.2 源码链路
```
ActiveServices.realStartServiceLocked()
  → scheduleServiceTimeoutLocked()  // 设置超时消息
  → Service.onCreate() / onStartCommand()
  → 超时触发
  → ActiveServices.serviceTimeout()
  → ActivityManagerService.appNotResponding()
```
关键源码：
```
frameworks/base/services/core/java/com/android/server/am/ActiveServices.java
  → serviceTimeout(): 发送 SERVICE_TIMEOUT_MSG
  → serviceDoneExecutingLocked(): 取消超时消息
```

### 1.3 典型日志
```
am_anr: [0,1234,com.example.app,1,executing service com.example.app/.MyService]
ActivityManager: ANR in com.example.app
ActivityManager: Reason: executing service com.example.app/.MyService
```

### 1.4 常见原因
- Service.onCreate() 中做数据库初始化
- Service.onStartCommand() 中做网络请求
- IntentService.onHandleIntent() 中执行耗时任务

## 2. Broadcast ANR

### 2.1 触发条件
BroadcastReceiver.onReceive() 执行时间超过阈值（前台 10s，后台 60s）。

### 2.2 源码链路
```
BroadcastQueue.processNextBroadcast()
  → performReceiveLocked()
  → receiver.onReceive()
  → 启动超时计时器
  → 超时触发
  → BroadcastQueue.broadcastTimeout()
  → ActivityManagerService.appNotResponding()
```
关键源码：
```
frameworks/base/services/core/java/com/android/server/am/BroadcastQueue.java
  → broadcastTimeout(): 发送 BROADCAST_TIMEOUT_MSG
  → finishReceiver(): 取消超时消息
```

### 2.3 典型日志
```
am_anr: [0,1234,com.example.app,2,receiving broadcast ...]
ActivityManager: ANR in com.example.app
ActivityManager: Reason: BroadcastTimeout
```

### 2.4 常见原因
- onReceive() 中做数据库操作
- onReceive() 中做网络请求
- onReceive() 中启动大量子线程

## 3. 分析要点

### 3.1 Service ANR vs Broadcast ANR
- Service ANR：traces 中 Service 线程（通常是 main）在做什么
- Broadcast ANR：traces 中 Receiver 线程在做什么

### 3.2 与 Input ANR 的区别
- Input ANR：用户触摸事件未被处理
- Service/Broadcast ANR：组件生命周期方法未返回
- 两者的 traces 分析方式相同，都是看主线程在做什么

### 3.3 误判陷阱
1. **Service 超时不等于 Service 有 bug**：可能是系统负载导致 Service 启动慢
2. **Broadcast 超时**：Android 8.0+ 后台广播限制更严格，更容易超时
3. **goAsync() 忘记 finish()**：使用 `goAsync()` 后必须在超时前调用 `finish()`
