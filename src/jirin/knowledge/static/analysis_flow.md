# Android 稳定性问题分析流程

## 1. 通用分析流程

### 1.1 问题接收

1. 获取问题日志（logcat / tombstone / traces.txt / bugreport）
2. 确认问题基本信息：
   - 设备型号和 Android 版本
   - 应用版本
   - 复现频率
   - 影响范围

### 1.2 问题分类

根据日志特征判断问题类型：

| 特征 | 问题类型 |
|------|----------|
| FATAL EXCEPTION / Java stack trace | JE |
| ANR in / am_anr / Input dispatching timed out | ANR |
| signal N (SIGxxx) / tombstone | NE |
| 多种特征混合 | MIXED |

### 1.3 分析原则

1. **先看现场**: 分析日志中记录的第一手信息
2. **追溯根因**: 不停留在表面现象，找到根本原因
3. **明确责任**: 判断是 app / SDK / system 的问题
4. **给出方案**: 提供可执行的修复建议
5. **闭环跟踪**: 确保问题被修复和验证

## 2. JE 分析流程

```
1. 定位 Exception 类型和消息
   |
2. 分析 Stack Trace
   |-- 找到 app 代码的第一个帧
   |-- 检查 Caused by 链
   |
3. 确定 crash 位置
   |-- 类名 + 方法名 + 行号
   |
4. 分析 crash 上下文
   |-- 为什么会发生（null? 越界? 状态错误?）
   |-- 触发条件是什么
   |
5. 判断责任方
   |-- app 代码 -> app
   |-- SDK 代码 -> SDK
   |-- framework 代码 -> 检查 app 使用是否正确
   |
6. 给出修复建议
```

## 3. ANR 分析流程

```
1. 确定 ANR 类型
   |-- Input Timeout (5s)
   |-- Service Timeout (20s)
   |-- Broadcast Timeout (10s/60s)
   |
2. 查看 traces.txt 中主线程状态
   |-- BLOCKED -> 等待锁 -> 找持锁线程
   |-- TIMED_WAITING -> 等待条件/超时
   |-- WAITING -> 无限等待
   |-- RUNNABLE -> 正在执行耗时操作
   |-- SLEEPING -> Thread.sleep()
   |
3. 分析阻塞原因
   |-- I/O 操作?
   |-- 锁竞争?
   |-- Binder 调用?
   |-- 系统资源不足?
   |
4. 检查系统状态
   |-- CPU LOAD
   |-- 内存状态
   |-- 其他进程影响
   |
5. 判断责任方
   |-- 主线程自身代码 -> app
   |-- 等待系统服务 -> system
   |-- SDK 阻塞 -> SDK
   |
6. 给出修复建议
```

## 4. NE 分析流程

```
1. 识别信号类型
   |-- SIGSEGV -> 内存访问问题
   |-- SIGABRT -> 主动 abort
   |-- SIGBUS -> 对齐/物理地址问题
   |
2. 分析 fault addr
   |-- 0x0 -> 空指针
   |-- 小地址 -> 结构体成员偏移
   |-- 正常地址范围 -> 野指针/已释放
   |
3. 分析 backtrace
   |-- 确定 crash 在哪个库
   |-- 找到 app 相关帧
   |-- 检查是否有 JNI 调用
   |
4. 分析寄存器和内存映射
   |-- 检查关键寄存器值
   |-- 确认内存映射状态
   |
5. 判断责任方
   |-- app .so -> app
   |-- JNI 调用 -> app
   |-- 系统库 -> system (需确认触发条件)
   |-- 驱动 -> driver/vendor
   |
6. 给出修复建议
```

## 5. 闭环路径

### 5.1 问题跟踪

1. 记录到缺陷管理系统
2. 标注责任方
3. 设定修复优先级

### 5.2 修复验证

1. 修复后复现步骤验证
2. 回归测试
3. 灰度发布观察

### 5.3 经验沉淀

1. 记录根因和解决方案
2. 归纳同类问题模式
3. 更新知识库
