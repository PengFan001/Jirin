# 生命周期相关崩溃

## 1. Activity 生命周期崩溃

### 1.1 onCreate 崩溃
**触发时机**：Activity 创建过程中
**源码链路**：
```
ActivityThread.handleLaunchActivity()
  → performLaunchActivity()
    → Activity.onCreate(Bundle)
    → 若此处抛出异常 → FATAL EXCEPTION
```
**常见原因**：
- findViewById 返回 null（布局 ID 错误或 setContentView 未调用）
- Intent extras 为 null
- 权限初始化失败

### 1.2 onResume/onPause 崩溃
**源码链路**：
```
ActivityThread.handleResumeActivity()
  → performResumeActivity()
    → Activity.performResume()
      → Activity.onResume()
```
**常见原因**：
- 在 onResume 中访问已释放资源
- 传感器/相机注册失败

### 1.3 onDestroy 后回调
**典型异常**：
```
java.lang.IllegalStateException: Activity has been destroyed
java.lang.NullPointerException on destroyed Activity field
```
**源码链路**：
```
ActivityThread.handleDestroyActivity()
  → performDestroyActivity()
    → Activity.performDestroy()
    → mDestroyed = true
  → 异步回调到达 → 访问已置 null 的字段
```

## 2. Fragment 生命周期崩溃

### 2.1 Fragment 事务异常
**典型异常**：
```
IllegalStateException: Can not perform this action after onSaveInstanceState
```
**源码链路**：
```
FragmentManager.checkStateLoss()
  → if (mStateSaved) throw new IllegalStateException(...)
```
**常见原因**：
- 异步回调中执行 FragmentTransaction（回调到达时 Activity 已 onSaveInstanceState）
- 在 Activity.onStop() 之后提交事务

### 2.2 Fragment 重复添加
**典型异常**：
```
IllegalStateException: Fragment already added
IllegalStateException: Fragment already in use
```
**源码链路**：
```
FragmentManager.addFragment()
  → if (f.mAdded) throw new IllegalStateException("Fragment already added")
```

### 2.3 Fragment 依附问题
**典型异常**：
```
IllegalStateException: Fragment not attached to a context
```
**源码链路**：
```
Fragment.requireContext()
  → if (mHost == null) throw new IllegalStateException(...)
```
**常见原因**：
- Fragment detach 后异步回调到达
- 嵌套 Fragment 中 getChildFragmentManager() 时序问题

## 3. Service 生命周期崩溃

### 3.1 Service 启动崩溃
**源码链路**：
```
ActivityThread.handleCreateService()
  → service.onCreate()
  → 若抛出异常 → FATAL EXCEPTION
```
**常见原因**：
- 在 onCreate 中访问 null 参数
- 权限检查失败

### 3.2 IntentService 重复启动
**典型场景**：
```
IntentService 正在处理任务时再次 startService
→ 新 Intent 排队等待
→ 若 onHandleIntent 中抛出异常 → 线程终止 → 后续任务不执行
```

## 4. BroadcastReceiver 崩溃

### 4.1 onReceive 超时
**源码链路**：
```
ActivityThread.handleReceiver()
  → receiver.onReceive()
  → 若超过 10s（前台）/ 60s（后台）→ ANR
```
**注意**：BroadcastReceiver 中执行耗时操作会导致 ANR

### 4.2 隐式广播异常
**典型场景**：
```
java.lang.SecurityException: Permission Denial: receiving Intent
  { act=android.intent.action.BOOT_COMPLETED }
```
需要声明对应权限才能接收系统广播

## 5. 分析要点

### 5.1 判断生命周期崩溃的关键信息
1. **堆栈顶部**：确认是哪个生命周期方法（onCreate/onResume/onDestroy 等）
2. **异常类型**：
   - NPE → 通常是字段未初始化或已置 null
   - IllegalStateException → 通常是状态/时序问题
   - SecurityException → 通常是权限问题
3. **线程名**：`main` 线程的生命周期崩溃最常见，子线程的通常是 Service/IntentService

### 5.2 区分"直接原因"和"根本原因"
- 直接原因：哪个方法抛出了什么异常
- 根本原因：为什么在这个生命周期阶段会出现这个状态（时序？并发？配置变更？）

### 5.3 配置变更导致的崩溃
Android 配置变更（旋转屏幕、语言切换等）会导致 Activity 重建：
```
Activity.onDestroy() → Activity.onCreate()  // 重建
```
如果静态变量或单例持有旧 Activity 引用 → 内存泄漏或 NPE
