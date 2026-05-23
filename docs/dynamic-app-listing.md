# 动态 App 列表获取

## 概述

Open-AutoGLM 通过 **ADBKeyBoard + AppListReceiver** 机制，能够动态获取手机上实际安装的所有用户应用（最多 300 个），而不仅限于内置的静态 App 白名单。这使得 Agent 可以打开和操作手机上任意已安装的应用。

## 工作原理

### 整体架构

```
Agent 请求打开 "某某App"
         │
         ▼
  _resolve_package_name()
         │
         ├─ 1. 先查静态 APP_PACKAGES（内置白名单）
         │     └─ 命中 → 直接返回 package name
         │
         └─ 2. 未命中 → 查动态映射表
               │
               ▼
     _get_dynamic_app_mappings()
               │
               ▼
   adb shell am broadcast \
     -n com.android.adbkeyboard/.AppListReceiver \
     -a ADB_LIST_APPS \
     --ez include_system false \
     --ei limit 300
               │
               ▼
     手机端 AppListReceiver 扫描已安装应用
     返回 JSON: [{"label":"微信","package":"com.tencent.mm","activity":"..."}, ...]
               │
               ▼
     _parse_apps_json_from_broadcast() 解析 JSON
               │
               ▼
     缓存到 _dynamic_apps_cache（TTL 60 秒）
               │
               ▼
     _resolve_package_name() 模糊匹配 app name
     （支持 label / package / 中文名 / 拼音匹配）
```

### 核心组件

#### 1. AppListReceiver（手机端）

位于 `third_party/ADBKeyBoard/keyboardservice/src/main/java/com/android/adbkeyboard/AppListReceiver.java`。

- 接收 `ADB_LIST_APPS` 广播
- 调用 `PackageManager.getInstalledApplications()` 获取所有用户安装的应用
- 提取 `label`（应用名）、`package`（包名）、`activity`（启动 Activity）
- 以 JSON 数组格式通过广播结果返回

#### 2. 动态映射表（Agent 端）

位于 `phone_agent/adb/device.py:_get_dynamic_app_mappings()`。

```python
def _get_dynamic_app_mappings(device_id: str | None = None) -> list[dict[str, str]]:
    """
    通过 ADB 广播触发手机端 AppListReceiver，
    获取手机上所有用户安装的应用列表（最多 300 个）。
    结果缓存 60 秒。
    """
```

#### 3. 包名解析器

位于 `phone_agent/adb/device.py:_resolve_package_name()`。

匹配策略（按优先级）：
1. 精确匹配静态 `APP_PACKAGES` 白名单
2. 标准化后（去空格、小写）匹配静态白名单
3. 精确匹配动态列表中的 `label`
4. 子串匹配动态列表中的 `label`
5. 子串匹配动态列表中的 `package`

## 使用方法

### 部署 ADBKeyBoard 到手机

首次使用前需要将 ADBKeyBoard APK 安装到手机上：

```bash
cd third_party/ADBKeyBoard
./gradlew assembleDebug
adb install keyboardservice/build/outputs/apk/debug/keyboardservice-debug.apk
```

安装后需要在手机 **设置 → 语言和输入法** 中启用 ADBKeyBoard。

### 验证是否工作

```bash
# 发送广播测试
adb shell am broadcast \
  -n com.android.adbkeyboard/.AppListReceiver \
  -a ADB_LIST_APPS \
  --ez include_system false \
  --ei limit 10
```

若正常，会看到类似输出：
```
Broadcast completed: result=0, data="[{\"label\":\"微信\",\"package\":\"com.tencent.mm\",...}]"
```

### 在任务中使用

无需任何额外配置。当 Agent 遇到不在静态白名单中的应用时，会自动通过动态列表解析包名。例如：

```bash
python main.py -y --model qwen3.6:27b-24576 "打开抖省省，搜索肯德基双人套餐"
```

即使"抖省省"不在静态 `APP_PACKAGES` 中，Agent 也会通过动态列表找到对应的包名并打开。

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `include_system` | `false` | 是否包含系统应用 |
| `limit` | `300` | 最多返回的应用数量 |
| `_APP_CACHE_TTL_SECONDS` | `60` | 动态列表缓存时间（秒） |

## 优势

- **无需维护白名单**：用户安装的任何应用都可以被 Agent 识别和打开
- **低延迟**：结果缓存 60 秒，避免频繁 ADB 调用
- **模糊匹配**：支持中文名、拼音、包名等多种方式匹配应用
- **轻量级**：通过 Android 标准广播机制实现，无需额外权限

## 相关文件

| 文件 | 说明 |
|------|------|
| `phone_agent/adb/device.py:304-371` | 动态映射表核心逻辑 |
| `phone_agent/config/apps.py` | 静态 App 白名单 |
| `third_party/ADBKeyBoard/` | ADBKeyBoard 源码（含 AppListReceiver） |
